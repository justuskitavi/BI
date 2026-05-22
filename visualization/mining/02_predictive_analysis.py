from __future__ import annotations

import numpy as np
import pandas as pd

from bi_common import load_orders, order_level, write_table


def one_hot(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return pd.get_dummies(frame, columns=columns, drop_first=True, dtype=float)


def ridge_regression_fit(x: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    penalty = alpha * np.eye(x.shape[1])
    penalty[0, 0] = 0.0
    return np.linalg.solve(x.T @ x + penalty, x.T @ y)


def run_prediction():
    df = order_level(load_orders()).sort_values("order_date")

    features = [
        "sales",
        "quantity",
        "discount",
        "shipping_cost",
        "ship_days",
        "unique_products",
        "unique_sub_categories",
        "ship_mode",
        "segment",
        "market",
        "region",
        "order_priority",
        "Furniture",
        "Office Supplies",
        "Technology",
    ]
    model_df = df[["order_id", "order_date", "profit", "profitable"] + features].dropna()
    model_df = one_hot(model_df, ["ship_mode", "segment", "market", "region", "order_priority"])

    split = int(len(model_df) * 0.8)
    train = model_df.iloc[:split].copy()
    test = model_df.iloc[split:].copy()

    x_cols = [c for c in model_df.columns if c not in ["order_id", "order_date", "profit", "profitable"]]
    mean = train[x_cols].mean()
    std = train[x_cols].std(ddof=0).replace(0, 1)
    x_train = np.c_[np.ones(len(train)), ((train[x_cols] - mean) / std).to_numpy(float)]
    x_test = np.c_[np.ones(len(test)), ((test[x_cols] - mean) / std).to_numpy(float)]
    y_train = train["profit"].to_numpy(float)
    y_test = test["profit"].to_numpy(float)

    weights = ridge_regression_fit(x_train, y_train, alpha=10.0)
    pred = x_test @ weights
    residual = y_test - pred

    rmse = float(np.sqrt(np.mean(residual**2)))
    mae = float(np.mean(np.abs(residual)))
    r2 = float(1 - np.sum(residual**2) / np.sum((y_test - y_test.mean()) ** 2))
    predicted_profitable = pred > 0
    actual_profitable = test["profitable"].to_numpy(bool)
    accuracy = float((predicted_profitable == actual_profitable).mean())

    coef = pd.DataFrame(
        {
            "feature": ["intercept"] + x_cols,
            "coefficient": weights,
            "interpretation": [
                "baseline expected order profit"
            ]
            + ["positive raises predicted profit; negative lowers it"] * len(x_cols),
        }
    ).sort_values("coefficient", key=lambda s: s.abs(), ascending=False)

    predictions = test[["order_id", "order_date", "profit", "profitable"]].copy()
    predictions["predicted_profit"] = pred.round(2)
    predictions["predicted_profitable"] = predicted_profitable.astype(int)
    predictions["absolute_error"] = np.abs(residual).round(2)

    metrics = pd.DataFrame(
        [
            {"metric": "test_orders", "value": len(test)},
            {"metric": "rmse_profit", "value": round(rmse, 2)},
            {"metric": "mae_profit", "value": round(mae, 2)},
            {"metric": "r2", "value": round(r2, 4)},
            {"metric": "profitability_accuracy", "value": round(accuracy, 4)},
        ]
    )

    write_table(metrics, "predictive_analysis_metrics.csv")
    write_table(coef, "predictive_analysis_model_coefficients.csv")
    write_table(predictions.sort_values("absolute_error", ascending=False).head(200), "predictive_analysis_prediction_audit.csv")
    return metrics, coef


if __name__ == "__main__":
    metrics, coef = run_prediction()
    print("Predictive analysis: ridge regression predicts order profit from order characteristics.")
    print(metrics.to_string(index=False))
    print("\nLargest model signals:")
    print(coef.head(12).to_string(index=False))
