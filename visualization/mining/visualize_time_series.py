import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[1]
HIST_PATH = ROOT / "outputs" / "time_series_monthly_sales_profit.csv"
FORECAST_PATH = ROOT / "outputs" / "time_series_sales_forecast_next_6_months.csv"
OUTPUT_PATH = ROOT / "outputs" / "time_series_forecast_visualization.png"

def generate_timeseries_plot():
    if not HIST_PATH.exists() or not FORECAST_PATH.exists():
        print("Error: Time series output files not found. Run analysis first.")
        return

    # Load data
    df_hist = pd.read_csv(HIST_PATH)
    df_forecast = pd.read_csv(FORECAST_PATH)

    # Convert to datetime
    df_hist['order_date'] = pd.to_datetime(df_hist['order_date'])
    df_forecast['forecast_month'] = pd.to_datetime(df_forecast['forecast_month'])

    # Prepare plot
    plt.figure(figsize=(14, 7))
    sns.set_style("whitegrid")

    # Plot Historical Sales
    plt.plot(df_hist['order_date'], df_hist['sales'], label='Historical Sales', color='#1d4ed8', linewidth=2.5, marker='o', markersize=4)
    
    # Plot Historical Profit (Secondary Axis)
    ax1 = plt.gca()
    ax2 = ax1.twinx()
    ax2.fill_between(df_hist['order_date'], df_hist['profit'], color='#10b981', alpha=0.15, label='Historical Profit')
    ax2.plot(df_hist['order_date'], df_hist['profit'], color='#10b981', linewidth=1.5, linestyle='--', alpha=0.6)

    # Plot Forecasted Sales
    # Connect historical to forecast for a smooth line
    last_hist_date = df_hist['order_date'].iloc[-1]
    last_hist_sales = df_hist['sales'].iloc[-1]
    
    forecast_dates = [last_hist_date] + df_forecast['forecast_month'].tolist()
    forecast_sales = [last_hist_sales] + df_forecast['forecast_sales'].tolist()
    
    ax1.plot(forecast_dates, forecast_sales, label='6-Month Sales Forecast', color='#f59e0b', linewidth=3, linestyle=':', marker='s', markersize=6)

    # Formatting
    ax1.set_title('Global SuperStore: Sales & Profit Forecast', fontsize=18, fontweight='bold', pad=25)
    ax1.set_xlabel('Timeline', fontsize=12)
    ax1.set_ylabel('Sales (USD)', fontsize=12, color='#1d4ed8')
    ax2.set_ylabel('Profit (USD)', fontsize=12, color='#10b981')
    
    # Grid and Legend
    ax1.grid(True, alpha=0.3)
    
    # Combine legends from both axes
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True, facecolor='white', framealpha=0.9)

    plt.tight_layout()

    # Save
    plt.savefig(OUTPUT_PATH, dpi=300)
    print(f"✅ Time series visualization saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_timeseries_plot()
