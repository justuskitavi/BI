from __future__ import annotations

from pathlib import Path

from bi_common import HTML_DIR, PAGE_STYLE


ANALYSES = [
    (
        "Pattern Mining",
        "Frequent co-purchases with support, confidence, and lift.",
        "pattern_mining_frequent_product_name_pairs.html",
    ),
    (
        "Pattern Mining: Sub-Categories",
        "Cleaner product-family associations for business storytelling.",
        "pattern_mining_frequent_sub_category_pairs.html",
    ),
    (
        "Predictive Analysis",
        "Profit prediction metrics, model coefficients, and prediction audit.",
        "predictive_analysis_metrics.html",
    ),
    (
        "Customer Clusters",
        "Customer groups based on recency, frequency, value, discounting, and profit.",
        "cluster_formation_customer_cluster_summary.html",
    ),
    (
        "Rules Mining",
        "If-then decision rules for discount, loss, and promotion choices.",
        "rules_mining_business_decision_rules.html",
    ),
    (
        "Sequence Discovery",
        "Next-purchase transitions across customer order histories.",
        "sequence_discovery_customer_next_purchase_transitions.html",
    ),
    (
        "Time Series Analysis",
        "Monthly sales/profit trend, seasonality, and forecast outputs.",
        "time_series_monthly_sales_profit.html",
    ),
    (
        "Forecast",
        "Six-month sales forecast from trend, seasonality, and smoothing.",
        "time_series_sales_forecast_next_6_months.html",
    ),
]


def build_dashboard() -> Path:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    
    # Custom block for PNG visualization
    png_path = Path("../customer_clusters_visualization.png")
    viz_card = f"""
    <article class="card" style="grid-column: 1 / -1;">
      <h2>Cluster Map Visualization</h2>
      <p class="note">PCA Projection of customer segments based on 6 behavioral dimensions.</p>
      <img src="{png_path}" style="width: 100%; border-radius: 8px; border: 1px solid var(--line); margin-top: 10px;">
    </article>
    """
    
    ts_png_path = Path("../time_series_forecast_visualization.png")
    ts_viz_card = f"""
    <article class="card" style="grid-column: 1 / -1;">
      <h2>Sales & Profit Forecast Visualization</h2>
      <p class="note">Historical monthly trends vs. 6-month projected growth.</p>
      <img src="{ts_png_path}" style="width: 100%; border-radius: 8px; border: 1px solid var(--line); margin-top: 10px;">
    </article>
    """

    cards = []
    cards.append(viz_card) 
    cards.append(ts_viz_card) # Add the time series visual card
    for title, description, filename in ANALYSES:
        status = "Open" if (HTML_DIR / filename).exists() else "Run analysis first"
        cards.append(
            f"""
            <article class="card">
              <h2>{title}</h2>
              <p class="note">{description}</p>
              <a class="button" href="{filename}">{status}</a>
            </article>
            """
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SuperStore BI Dashboard</title>
  <style>{PAGE_STYLE}</style>
</head>
<body>
  <header>
    <h1>SuperStore BI Dashboard</h1>
    <p>Browser-based GUI for the pattern mining, prediction, clustering, rules, sequence, and time-series analyses.</p>
  </header>
  <main>
    <div class="toolbar">
      <a class="button secondary" href="../BI_insight_report.html">Open Insight Report</a>
    </div>
    <section class="grid">
      {''.join(cards)}
    </section>
  </main>
  <footer>Run <strong>python scripts/run_all.py</strong> to refresh this dashboard.</footer>
</body>
</html>
"""
    path = HTML_DIR / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


if __name__ == "__main__":
    path = build_dashboard()
    print(f"Wrote {path}")
