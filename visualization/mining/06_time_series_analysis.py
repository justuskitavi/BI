from __future__ import annotations

import numpy as np
import pandas as pd

from bi_common import load_orders, write_table


def simple_exp_smoothing(values: np.ndarray, alpha: float = 0.35) -> np.ndarray:
    fitted = np.zeros_like(values, dtype=float)
    fitted[0] = values[0]
    for i in range(1, len(values)):
        fitted[i] = alpha * values[i - 1] + (1 - alpha) * fitted[i - 1]
    return fitted


def run_time_series():
    df = load_orders()
    monthly = df.set_index("order_date").resample("MS").agg(
        sales=("sales", "sum"),
        profit=("profit", "sum"),
        orders=("order_id", "nunique"),
        quantity=("quantity", "sum"),
        avg_discount=("discount", "mean"),
    ).reset_index()
    monthly["profit_margin"] = np.where(monthly["sales"] > 0, monthly["profit"] / monthly["sales"], 0.0)
    monthly["sales_mom_growth"] = monthly["sales"].pct_change().replace([np.inf, -np.inf], np.nan)
    monthly["profit_mom_growth"] = monthly["profit"].pct_change().replace([np.inf, -np.inf], np.nan)
    monthly["sales_3m_moving_avg"] = monthly["sales"].rolling(3).mean()
    monthly["profit_3m_moving_avg"] = monthly["profit"].rolling(3).mean()

    sales_values = monthly["sales"].to_numpy(float)
    fitted = simple_exp_smoothing(sales_values)
    monthly["sales_exp_smooth_fit"] = fitted

    month_seasonality = monthly.assign(month=monthly["order_date"].dt.month).groupby("month").agg(
        avg_sales=("sales", "mean"),
        avg_profit=("profit", "mean"),
        avg_orders=("orders", "mean"),
    ).reset_index()
    month_seasonality["seasonality_index"] = month_seasonality["avg_sales"] / month_seasonality["avg_sales"].mean()

    trend_x = np.arange(len(monthly))
    trend_coef = np.polyfit(trend_x, sales_values, deg=1)
    next_months = pd.date_range(monthly["order_date"].max() + pd.offsets.MonthBegin(1), periods=6, freq="MS")
    last_smoothed = monthly["sales_exp_smooth_fit"].iloc[-1]
    forecasts = []
    for i, month in enumerate(next_months, start=1):
        trend_forecast = np.polyval(trend_coef, len(monthly) + i - 1)
        seasonal_index = month_seasonality.loc[month_seasonality["month"] == month.month, "seasonality_index"].iloc[0]
        forecast = 0.55 * trend_forecast * seasonal_index + 0.45 * last_smoothed
        forecasts.append(
            {
                "forecast_month": month.date().isoformat(),
                "forecast_sales": round(float(forecast), 2),
                "method": "linear trend x month seasonality blended with exponential smoothing",
            }
        )

    forecast_df = pd.DataFrame(forecasts)
    monthly_out = monthly.copy()
    numeric_cols = monthly_out.select_dtypes(include=np.number).columns
    monthly_out[numeric_cols] = monthly_out[numeric_cols].round(4)
    write_table(monthly_out, "time_series_monthly_sales_profit.csv")
    write_table(month_seasonality.round(4), "time_series_monthly_seasonality.csv")
    write_table(forecast_df, "time_series_sales_forecast_next_6_months.csv")
    return monthly, month_seasonality, forecast_df


if __name__ == "__main__":
    monthly, seasonality, forecast = run_time_series()
    print("Monthly sales/profit trend sample:")
    print(monthly.tail(12).to_string(index=False))
    print("\nSeasonality by calendar month:")
    print(seasonality.to_string(index=False))
    print("\nNext 6-month sales forecast:")
    print(forecast.to_string(index=False))
