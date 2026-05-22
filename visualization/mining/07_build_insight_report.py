from __future__ import annotations

import pandas as pd

from bi_common import OUTPUT_DIR, PAGE_STYLE


def read_output(name: str) -> pd.DataFrame:
    json_path = OUTPUT_DIR / "data" / name.replace(".csv", ".json")
    return pd.read_json(json_path) if json_path.exists() else pd.DataFrame()


def html_table(df: pd.DataFrame, columns: list[str], rows: int = 5) -> str:
    if df.empty:
        return '<p class="note">No rows produced.</p>'
    view = df[columns].head(rows).fillna("")
    return f'<div class="table-wrap">{view.to_html(index=False, border=0, escape=True)}</div>'


def build_report():
    product_pairs = read_output("pattern_mining_frequent_product_name_pairs.csv")
    subcat_pairs = read_output("pattern_mining_frequent_sub_category_pairs.csv")
    metrics = read_output("predictive_analysis_metrics.csv")
    clusters = read_output("cluster_formation_customer_cluster_summary.csv")
    rules = read_output("rules_mining_business_decision_rules.csv")
    transitions = read_output("sequence_discovery_customer_next_purchase_transitions.csv")
    forecast = read_output("time_series_sales_forecast_next_6_months.csv")

    report = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SuperStore BI Mining Insight Report</title>
  <style>{PAGE_STYLE}</style>
</head>
<body>
<header>
  <h1>SuperStore BI Mining Insight Report</h1>
  <p>This browser report is generated from the Python GUI-style analysis outputs.</p>
</header>
<main>
<div class="toolbar">
  <a class="button" href="html/index.html">Dashboard Home</a>
</div>

<section class="card">
  <p class="note">This report is generated from the Python scripts in <strong>scripts/</strong>. It summarizes the main analytical evidence for each BI concept.</p>
</section>

<section class="card"><h2>A) Pattern Mining</h2>

Exact product mining finds very specific co-purchases. Because exact product names are sparse, the strongest lifts often have low support, which is realistic for retail baskets.

{html_table(product_pairs, ["item_a", "item_b", "orders_together", "support", "confidence_a_to_b", "lift"], 5)}

At sub-category level the patterns are easier to explain to business users:

{html_table(subcat_pairs, ["item_a", "item_b", "orders_together", "support", "confidence_a_to_b", "lift"], 8)}
</section>

<section class="card"><h2>B) Predictive Analysis</h2>

The predictive script trains a ridge regression model to estimate order profit using sales, quantity, discounts, shipping, category mix, market, region, segment, and priority.

{html_table(metrics, ["metric", "value"], 10)}
</section>

<section class="card"><h2>C) Cluster Formation</h2>

Customers are grouped using recency, frequency, monetary value, profit, discounts, market breadth, and category breadth.

{html_table(clusters, ["cluster", "customers", "avg_recency_days", "avg_orders", "total_sales", "total_profit", "business_label"], 10)}
</section>

<section class="card"><h2>D) Rules Mining</h2>

Rules are mined as interpretable if-then business policies. High lift means the condition is much more associated with the decision than the baseline.

{html_table(rules, ["if_condition", "then_decision", "support_rows", "confidence", "lift_vs_baseline", "profit"], 10)}
</section>

<section class="card"><h2>E) Sequence Discovery</h2>

The sequence script treats each customer's order history as a journey and estimates what tends to follow next.

{html_table(transitions, ["from", "to", "times_seen", "probability_next"], 10)}
</section>

<section class="card"><h2>F) Time Series Analysis</h2>

The time-series script creates monthly sales/profit trends, seasonality, moving averages, exponential smoothing, and a six-month sales forecast.

{html_table(forecast, ["forecast_month", "forecast_sales", "method"], 6)}
</section>

<section class="card"><h2>How to Explain the Whole Project</h2>

Pattern mining and rules mining explain relationships in existing transactions. Predictive analysis estimates a future business outcome. Clustering creates customer segments for differentiated action. Sequence discovery adds order of behavior, showing customer journeys. Time series analysis adds time, trend, seasonality, and forecasting.
</section>
</main>
<footer>Generated from SuperStore BI Python analysis.</footer>
</body>
</html>
"""

    path = OUTPUT_DIR / "BI_insight_report.html"
    path.write_text(report, encoding="utf-8")
    return path


if __name__ == "__main__":
    path = build_report()
    print(f"Wrote {path}")
