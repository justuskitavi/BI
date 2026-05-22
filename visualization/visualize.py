import os
import time
import psycopg2
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.io import to_html
from dotenv import load_dotenv
from datetime import datetime
import numpy as np
import warnings

# Suppress pandas warning about psycopg2 connection
warnings.filterwarnings("ignore", category=UserWarning, message=".*pandas only supports SQLAlchemy connectable.*")

load_dotenv()

print("🚀 SuperStore Dashboard Generator")
print("=" * 60)

# ---------------------------------------------------------------------------
# DB Connection
# ---------------------------------------------------------------------------
def get_connection():
    DATABASE_URL = os.getenv("DB_URL")
    for attempt in range(5):
        try:
            print(f"📡 Connecting to database... (attempt {attempt + 1}/5)")
            con = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            print("✅ Database connected successfully")
            return con
        except psycopg2.OperationalError as e:
            if attempt < 4:
                time.sleep(3)
            else:
                print(f"❌ Could not connect to database: {e}")
                exit(1)

def run_query(sql, conn):
    try:
        return pd.read_sql(sql, conn)
    except Exception as e:
        print(f"❌ Query failed: {e}")
        print(f"DEBUG SQL: {sql[:200]}...")
        exit(1)

def get_in_string(items, is_numeric=False):
    """Safely format items for a SQL IN clause."""
    if not items:
        return "NULL"
    if is_numeric:
        return ", ".join(map(str, items))
    cleaned_items = [str(i).replace("'", "''") for i in items]
    return ", ".join(f"'{i}'" for i in cleaned_items)

# ---------------------------------------------------------------------------
# Plotly base layout
# ---------------------------------------------------------------------------
BASE_LAYOUT = dict(
    paper_bgcolor="#111111",
    plot_bgcolor="#111111",
    font=dict(family="DM Mono, monospace", color="#aaaaaa", size=11),
    title=dict(font=dict(family="Syne, sans-serif", color="#e8e8e8", size=16), x=0.01, xanchor='left'),
    xaxis=dict(gridcolor="#1a1a1a", zerolinecolor="#222", tickfont=dict(color="#666")),
    yaxis=dict(gridcolor="#1a1a1a", zerolinecolor="#222", tickfont=dict(color="#666")),
    hovermode='closest',
)

COLORS = ["#3ecf8e", "#f59e0b", "#60a5fa", "#f87171", "#a78bfa", "#34d399", "#fb923c"]

def apply_base(fig, height=380, legend_h=True, margin=None):
    """Apply base layout to any figure, with optional horizontal legend."""
    m = margin or dict(t=50, b=40, l=60, r=40)
    leg = dict(
        orientation="h", 
        yanchor="bottom", 
        y=1.02, 
        xanchor="right", 
        x=1,
        bgcolor="rgba(0,0,0,0)", 
        font=dict(size=10, color="#888"),
        bordercolor="#333",
        borderwidth=1
    ) if legend_h else dict(
        font=dict(size=10, color="#888"),
        bgcolor="rgba(0,0,0,0)",
        bordercolor="#333",
        borderwidth=1
    )
    fig.update_layout(**BASE_LAYOUT, height=height, margin=m, legend=leg)
    return fig

# ---------------------------------------------------------------------------
# Main Script
# ---------------------------------------------------------------------------
def main():
    conn = get_connection()
    
    # Get available filters
    print("\n📊 Loading filter options...")
    years_df = run_query("SELECT DISTINCT EXTRACT(YEAR FROM date)::int AS year FROM snowflake.time_dim ORDER BY year", conn)
    categories_df = run_query("SELECT category FROM snowflake.category_dim ORDER BY category", conn)
    regions_df = run_query("SELECT region FROM snowflake.region_dim ORDER BY region", conn)
    
    all_years = years_df["year"].tolist()
    all_categories = categories_df["category"].tolist()
    all_regions = regions_df["region"].tolist()
    
    if not all_years or not all_categories or not all_regions:
        print("\n⚠️  WARNING: Some filter lists are empty! Run ETL first.")
    
    selected_years = all_years
    selected_categories = all_categories
    selected_regions = all_regions
    
    years_sql = get_in_string(selected_years, is_numeric=True)
    cats_sql = get_in_string(selected_categories)
    regions_sql = get_in_string(selected_regions)
    
    # --- KPI Query ---
    print("\n📈 Calculating KPIs...")
    kpi_query = f"""
    SELECT
        SUM(f.sales)    AS total_sales,
        SUM(f.profit)   AS total_profit,
        SUM(f.quantity) AS total_quantity,
        AVG(f.discount) AS avg_discount,
        COUNT(*)        AS total_orders
    FROM snowflake.fact_sales f
    JOIN snowflake.time_dim t         ON f.order_date_id = t.date_id
    JOIN snowflake.product_dim p      ON f.product_id = p.product_id
    JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN snowflake.category_dim c     ON sc.category_id = c.category_id
    JOIN snowflake.state_dim st       ON f.state_id = st.state_id
    JOIN snowflake.market_dim m       ON st.market_id = m.market_id
    JOIN snowflake.region_dim r       ON m.region_id = r.region_id
    WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
      AND c.category IN ({cats_sql})
      AND r.region IN ({regions_sql})
    """
    df_kpi = run_query(kpi_query, conn)
    if df_kpi.empty or pd.isna(df_kpi.iloc[0]["total_sales"]):
        print("❌ No data found in 'fact_sales' for the selected filters.")
        exit(1)
        
    kpi = df_kpi.iloc[0]
    margin = (kpi["total_profit"] / kpi["total_sales"] * 100) if kpi["total_sales"] else 0
    
    # --- Chart 1: Gauge (Profit Margin) ---
    print("\n🎯 Generating Profit Margin Gauge...")
    gauge_fig = go.Figure()

    gauge_fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=round(margin, 2),
        number={"suffix": "%", "font": {"size": 44, "family": "Syne, sans-serif", "color": "#e8e8e8"}},
        delta={"reference": 15, "increasing": {"color": "#3ecf8e"}},
        gauge={
            "axis": {"range": [-10, 40], "tickcolor": "#444", "tickwidth": 2},
            "bar": {"color": "#3ecf8e", "thickness": 0.2},
            "bgcolor": "#161616",
            "steps": [
                {"range": [-10, 0],  "color": "#1a0a0a"},
                {"range": [0, 10],   "color": "#121212"},
                {"range": [10, 20],  "color": "#181818"},
                {"range": [20, 40],  "color": "#081a0e"}
            ],
            "threshold": {"line": {"color": "#fff", "width": 4}, "thickness": 0.8, "value": 15}
        },
        title={"text": "Profit Margin %<br><span style='font-size:0.8em;color:#555'>Target: 15%</span>", "font": {"size": 14}}
    ))

    # Add the indicator line (pointer) originating from the base
    # In Plotly Indicator, the gauge is centered. We add a line pointing up.
    gauge_fig.add_shape(
        type="line", x0=0.5, y0=0.25, x1=0.5, y1=0.45,
        line=dict(color="#3ecf8e", width=4),
        xref="paper", yref="paper"
    )

    gauge_fig.update_layout(paper_bgcolor="#111111", font={"family": "DM Mono"}, height=340, margin=dict(t=80, b=20, l=30, r=30))
    
    # --- Chart 2: Fever Chart (Monthly Sales Trends) ---
    print("🌡️  Generating Fever Chart...")
    fever_query = f"""
        SELECT DATE_TRUNC('month', t.date) AS month, c.category, SUM(f.sales) AS total_sales
        FROM snowflake.fact_sales f
        JOIN snowflake.time_dim t         ON f.order_date_id = t.date_id
        JOIN snowflake.product_dim p      ON f.product_id = p.product_id
        JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
        JOIN snowflake.category_dim c     ON sc.category_id = c.category_id
        JOIN snowflake.state_dim st       ON f.state_id = st.state_id
        JOIN snowflake.market_dim m       ON st.market_id = m.market_id
        JOIN snowflake.region_dim r       ON m.region_id = r.region_id
        WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
          AND c.category IN ({cats_sql})
          AND r.region IN ({regions_sql})
        GROUP BY 1, 2 ORDER BY 1
    """
    fever_df = run_query(fever_query, conn)
    overall_avg = fever_df.groupby("month")["total_sales"].sum().mean()
    fever_fig = px.line(fever_df, x="month", y="total_sales", color="category", color_discrete_sequence=COLORS,
                        title="Monthly Sales Trends")
    fever_fig.add_hline(y=overall_avg, line_dash="dot", line_color="#444", annotation_text=f"Avg ${overall_avg:,.0f}")
    apply_base(fever_fig, height=340)
    
    # --- Chart 3: Correlation Heatmap ---
    print("🔥 Generating Correlation Heatmap...")
    heatmap_query = f"""
        WITH sales_metrics AS (
            SELECT r.region,
                SUM(f.sales)          AS total_sales,
                SUM(f.profit)         AS total_profit,
                AVG(f.discount)       AS avg_discount,
                SUM(f.quantity)       AS total_quantity
            FROM snowflake.fact_sales f
            JOIN snowflake.time_dim t         ON f.order_date_id = t.date_id
            JOIN snowflake.product_dim p      ON f.product_id = p.product_id
            JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
            JOIN snowflake.category_dim c     ON sc.category_id = c.category_id
            JOIN snowflake.state_dim st       ON f.state_id = st.state_id
            JOIN snowflake.market_dim m       ON st.market_id = m.market_id
            JOIN snowflake.region_dim r       ON m.region_id = r.region_id
            WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
              AND c.category IN ({cats_sql})
              AND r.region IN ({regions_sql})
            GROUP BY r.region
        ),
        shipping_metrics AS (
            SELECT r.region,
                SUM(sh.shipping_cost) AS total_shipping
            FROM snowflake.fact_shipping sh
            JOIN snowflake.state_dim st       ON sh.state_id = st.state_id
            JOIN snowflake.market_dim m       ON st.market_id = m.market_id
            JOIN snowflake.region_dim r       ON m.region_id = r.region_id
            WHERE r.region IN ({regions_sql})
            GROUP BY r.region
        )
        SELECT s.*, sh.total_shipping
        FROM sales_metrics s
        JOIN shipping_metrics sh ON s.region = sh.region
    """
    heatmap_df = run_query(heatmap_query, conn)
    corr = heatmap_df.set_index("region").corr()
    heat_fig = px.imshow(corr, text_auto=".2f", 
                         color_continuous_scale=[[0, "#1a0a0a"], [0.5, "#161616"], [1, "#3ecf8e"]],
                         zmin=-1, zmax=1)
    heat_fig.update_layout(**BASE_LAYOUT)
    heat_fig.update_layout(height=550, margin=dict(t=80, b=80, l=150, r=150),
                           xaxis=dict(tickfont=dict(size=16, color="#eee")),
                           yaxis=dict(tickfont=dict(size=16, color="#eee")))
    heat_fig.update_traces(textfont=dict(size=18, color="#fff"))
    
    # --- Chart 4: Bubble Chart ---
    print("🫧 Generating Bubble Chart...")
    bubble_query = f"""
        SELECT r.region, s.segment,
            SUM(f.sales)    AS total_sales,
            SUM(f.profit)   AS total_profit,
            SUM(f.quantity) AS total_quantity
        FROM snowflake.fact_sales f
        JOIN snowflake.customer_dim cd    ON f.customer_id = cd.customer_id
        JOIN snowflake.segment_dim s      ON cd.segment_id = s.segment_id
        JOIN snowflake.state_dim st       ON f.state_id = st.state_id
        JOIN snowflake.market_dim m       ON st.market_id = m.market_id
        JOIN snowflake.region_dim r       ON m.region_id = r.region_id
        JOIN snowflake.time_dim t         ON f.order_date_id = t.date_id
        JOIN snowflake.product_dim p      ON f.product_id = p.product_id
        JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
        JOIN snowflake.category_dim c     ON sc.category_id = c.category_id
        WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
          AND c.category IN ({cats_sql})
          AND r.region IN ({regions_sql})
        GROUP BY r.region, s.segment
    """
    bubble_df = run_query(bubble_query, conn)
    bubble_fig = px.scatter(bubble_df, x="total_sales", y="total_profit", size="total_quantity", color="region", symbol="segment",
                            title="Profit vs Sales (Bubble size = Quantity)")
    apply_base(bubble_fig, height=420, legend_h=False)
    
    # --- Chart 5: Area Chart ---
    print("📈 Generating Stacked Area Chart...")
    area_query = f"""
        SELECT EXTRACT(YEAR FROM t.date)::int AS year, c.category, SUM(f.sales) AS total_sales
        FROM snowflake.fact_sales f
        JOIN snowflake.time_dim t         ON f.order_date_id = t.date_id
        JOIN snowflake.product_dim p      ON f.product_id = p.product_id
        JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
        JOIN snowflake.category_dim c     ON sc.category_id = c.category_id
        JOIN snowflake.state_dim st       ON f.state_id = st.state_id
        JOIN snowflake.market_dim m       ON st.market_id = m.market_id
        JOIN snowflake.region_dim r       ON m.region_id = r.region_id
        WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
          AND c.category IN ({cats_sql})
          AND r.region IN ({regions_sql})
        GROUP BY 1, 2 ORDER BY 1
    """
    area_df = run_query(area_query, conn)
    area_fig = px.area(area_df, x="year", y="total_sales", color="category", color_discrete_sequence=COLORS,
                       title="Yearly Sales Growth by Category")
    apply_base(area_fig, height=400)
    
    # --- Chart 6: Shipping Bar Chart ---
    print("🚚 Generating Shipping Chart...")
    ship_query = f"""
        SELECT sm.ship_mode, op.order_priority,
            SUM(sh.shipping_cost) AS total_shipping_cost
        FROM snowflake.fact_shipping sh
        JOIN snowflake.ship_mode_dim sm        ON sh.ship_mode_id = sm.ship_mode_id
        JOIN snowflake.order_priority_dim op   ON sh.order_priority_id = op.order_priority_id
        JOIN snowflake.state_dim st            ON sh.state_id = st.state_id
        JOIN snowflake.market_dim m            ON st.market_id = m.market_id
        JOIN snowflake.region_dim r            ON m.region_id = r.region_id
        WHERE r.region IN ({regions_sql})
        GROUP BY 1, 2 ORDER BY 3 DESC
    """
    ship_df = run_query(ship_query, conn)
    ship_fig = px.bar(ship_df, x="ship_mode", y="total_shipping_cost", color="order_priority", barmode="group",
                      title="Shipping Cost by Mode & Priority")
    apply_base(ship_fig, height=400)
    
    # --- Chart 7: Sunburst ---
    print("☀️  Generating Sunburst Chart...")
    sun_query = f"""
        SELECT c.category, sc.sub_category, p.product_name, SUM(f.sales) AS total_sales
        FROM snowflake.fact_sales f
        JOIN snowflake.time_dim t         ON f.order_date_id = t.date_id
        JOIN snowflake.product_dim p      ON f.product_id = p.product_id
        JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
        JOIN snowflake.category_dim c     ON sc.category_id = c.category_id
        JOIN snowflake.state_dim st       ON f.state_id = st.state_id
        JOIN snowflake.market_dim m       ON st.market_id = m.market_id
        JOIN snowflake.region_dim r       ON m.region_id = r.region_id
        WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
          AND c.category IN ({cats_sql})
          AND r.region IN ({regions_sql})
        GROUP BY 1, 2, 3
    """
    sun_df = run_query(sun_query, conn)
    sun_fig = px.sunburst(sun_df, path=["category", "sub_category", "product_name"], values="total_sales",
                          title="Product Sales Hierarchy")
    sun_fig.update_layout(paper_bgcolor="#111111", height=500, margin=dict(t=50, b=10, l=10, r=10))
    
    # --- Chart 8: Choropleth ---
    print("🌍 Generating World Map...")
    map_query = f"""
        SELECT ctry.country, SUM(f.sales) AS total_sales
        FROM snowflake.fact_sales f
        JOIN snowflake.time_dim t         ON f.order_date_id = t.date_id
        JOIN snowflake.product_dim p      ON f.product_id = p.product_id
        JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
        JOIN snowflake.category_dim c     ON sc.category_id = c.category_id
        JOIN snowflake.state_dim st       ON f.state_id = st.state_id
        JOIN snowflake.market_dim m       ON st.market_id = m.market_id
        JOIN snowflake.region_dim r       ON m.region_id = r.region_id
        JOIN snowflake.country_dim ctry   ON r.country_id = ctry.country_id
        WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
          AND c.category IN ({cats_sql})
          AND r.region IN ({regions_sql})
        GROUP BY 1 ORDER BY 2 DESC
    """
    map_df = run_query(map_query, conn)
    map_fig = px.choropleth(map_df, locations="country", locationmode="country names", color="total_sales", 
                            color_continuous_scale="Viridis", title="Global Sales Heatmap")
    map_fig.update_layout(paper_bgcolor="#111111", geo=dict(bgcolor="#111111"), height=500, margin=dict(t=50, b=10, l=0, r=0))
    
    conn.close()
    
    # --- HTML Building ---
    print("\n📝 Building HTML dashboard...")
    all_figs = [
        ("gauge",      "Profit Margin Performance",                gauge_fig),
        ("fever",      "Monthly Sales Trend",                      fever_fig),
        ("heatmap",    "Metric Correlation Matrix",                heat_fig),
        ("bubble",     "Profit vs Sales Analysis",                 bubble_fig),
        ("area",       "Category Growth Over Time",                area_fig),
        ("shipping",   "Logistics Cost Breakdown",                  ship_fig),
        ("sunburst",   "Product Hierarchy Sales",                  sun_fig),
        ("choropleth", "Global Revenue Distribution",               map_fig),
    ]
    
    chart_blocks = []
    for i, (key, title, fig) in enumerate(all_figs):
        include_js = "cdn" if i == 0 else False
        fig_html = to_html(fig, full_html=False, include_plotlyjs=include_js,
                           config={"displayModeBar": True,
                                   "modeBarButtonsToAdd": ["toggleFullscreen"],
                                   "modeBarButtonsToRemove": ["select2d", "lasso2d", "toggleSpikelines"],
                                   "displaylogo": False,
                                   "scrollZoom": True})
        chart_blocks.append(f"""
            <div class="chart-card" id="{key}">
                <div class="chart-title">{title}</div>
                <div class="chart-body">{fig_html}</div>
            </div>
        """)
    
    kpi_cards = f"""
    <div class="kpi-row">
        <div class="kpi-card"><div class="kpi-label">Total Sales</div><div class="kpi-value">${kpi['total_sales']:,.0f}</div></div>
        <div class="kpi-card"><div class="kpi-label">Total Profit</div><div class="kpi-value">${kpi['total_profit']:,.0f}</div></div>
        <div class="kpi-card"><div class="kpi-label">Units Sold</div><div class="kpi-value">{kpi['total_quantity']:,.0f}</div></div>
        <div class="kpi-card"><div class="kpi-label">Profit Margin</div><div class="kpi-value">{margin:.1f}%</div></div>
    </div>
    """
    
    rows = []
    for j in range(0, len(chart_blocks), 2):
        pair = chart_blocks[j:j+2]
        rows.append(f'<div class="chart-row">{"".join(pair)}</div>')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SuperStore BI Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono&display=swap" rel="stylesheet">
<style>
  body {{ background: #0d0d0d; color: #e0e0e0; font-family: 'DM Mono', monospace; margin: 0; }}
  header {{ padding: 2.5rem 3rem 1rem; border-bottom: 1px solid #1a1a1a; }}
  header h1 {{ font-family: 'Syne', sans-serif; font-size: 2.2rem; margin: 0; color: #f0f0f0; letter-spacing: -0.05em; }}
  
  .hint {{ font-size: 0.65rem; color: #333; text-align: right; padding: 0.5rem 3rem; }}
  
  .kpi-row {{ display: flex; gap: 1.5rem; padding: 1rem 3rem 2rem; flex-wrap: wrap; }}
  .kpi-card {{ flex: 1; min-width: 200px; background: #161616; border: 1px solid #222; border-radius: 12px; padding: 1.5rem; transition: border-color 0.2s; }}
  .kpi-card:hover {{ border-color: #2a2a2a; }}
  .kpi-label {{ font-size: 0.7rem; color: #555; text-transform: uppercase; margin-bottom: 0.5rem; letter-spacing: 0.1em; }}
  .kpi-value {{ font-family: 'Syne', sans-serif; font-size: 1.8rem; color: #3ecf8e; font-weight: 800; }}
  
  .chart-row {{ display: flex; gap: 1.5rem; padding: 0 3rem 2rem; flex-wrap: wrap; }}
  .chart-card {{ flex: 1; min-width: 450px; background: #111; border: 1px solid #1a1a1a; border-radius: 12px; overflow: hidden; transition: border-color 0.2s; }}
  .chart-card:hover {{ border-color: #2a2a2a; }}
  .chart-title {{ font-family: 'Syne', sans-serif; font-size: 1rem; color: #888; padding: 1.2rem; border-bottom: 1px solid #1a1a1a; }}
  .chart-body {{ padding: 1rem; }}

  /* Plotly modebar styling */
  .modebar {{ background-color: rgba(22, 22, 22, 0.9) !important; border-radius: 4px !important; padding: 2px !important; }}
  .modebar-btn {{ color: #666 !important; }}
  .modebar-btn:hover {{ color: #3ecf8e !important; background: rgba(62, 207, 142, 0.1) !important; }}

  @media (max-width: 1000px) {{ .chart-card {{ min-width: 100%; }} }}
</style>
</head>
<body>
<header><h1>SuperStore Intelligence</h1></header>
<div class="hint">💡 Use the [ ] button in the toolbar to maximize · Double-click charts to toggle fullscreen</div>
{kpi_cards}
{''.join(rows)}
<script>
  // Enable fullscreen on double-click
  document.addEventListener('dblclick', function(e) {{
    const chart = e.target.closest('.js-plotly-plot');
    if (chart) {{
      if (!document.fullscreenElement) {{
        chart.requestFullscreen().catch(() => {{}});
      }} else {{
        document.exitFullscreen();
      }}
    }}
  }});
</script>
</body>
</html>"""
    
    os.makedirs("output", exist_ok=True)
    with open("output/dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ Dashboard generated: {os.path.abspath('output/dashboard.html')}")

if __name__ == "__main__":
    main()
