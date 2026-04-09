import os
import time
import psycopg2
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SuperStore BI Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Mono', monospace;
    }

    .main {
        background-color: #0d0d0d;
    }

    section[data-testid="stSidebar"] {
        background-color: #111111;
        border-right: 1px solid #222;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3 {
        font-family: 'Syne', sans-serif !important;
        letter-spacing: -0.02em;
    }

    .dash-title {
        font-family: 'Syne', sans-serif;
        font-size: 2.4rem;
        font-weight: 800;
        color: #f0f0f0;
        letter-spacing: -0.04em;
        line-height: 1.1;
        margin-bottom: 0.2rem;
    }

    .dash-sub {
        font-family: 'DM Mono', monospace;
        font-size: 0.75rem;
        color: #555;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 2rem;
    }

    .kpi-card {
        background: #161616;
        border: 1px solid #222;
        border-radius: 8px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 0.5rem;
    }

    .kpi-label {
        font-family: 'DM Mono', monospace;
        font-size: 0.65rem;
        color: #555;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.3rem;
    }

    .kpi-value {
        font-family: 'Syne', sans-serif;
        font-size: 1.7rem;
        font-weight: 700;
        color: #e8e8e8;
        letter-spacing: -0.03em;
    }

    .kpi-delta {
        font-family: 'DM Mono', monospace;
        font-size: 0.7rem;
        color: #3ecf8e;
        margin-top: 0.2rem;
    }

    .section-label {
        font-family: 'DM Mono', monospace;
        font-size: 0.65rem;
        color: #444;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        border-top: 1px solid #1e1e1e;
        padding-top: 1.5rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }

    .stSelectbox label, .stMultiSelect label, .stSlider label {
        font-family: 'DM Mono', monospace !important;
        font-size: 0.7rem !important;
        color: #555 !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    div[data-testid="stMetric"] {
        background: #161616;
        border: 1px solid #1e1e1e;
        border-radius: 8px;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# DB Connection
# ---------------------------------------------------------------------------
@st.cache_resource
def get_connection():
    DATABASE_URL = os.getenv("DB_URL")
    for attempt in range(5):
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            return conn
        except psycopg2.OperationalError as e:
            if attempt < 4:
                time.sleep(3)
            else:
                st.error(f"Could not connect to database: {e}")
                st.stop()

@st.cache_data(ttl=300)
def run_query(sql):
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn)
    except Exception:
        conn = get_connection.clear()
        st.cache_resource.clear()
        st.rerun()

# ---------------------------------------------------------------------------
# Plotly dark theme base
# ---------------------------------------------------------------------------
PLOTLY_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor="#111111",
        plot_bgcolor="#111111",
        font=dict(family="DM Mono, monospace", color="#aaaaaa", size=11),
        title=dict(font=dict(family="Syne, sans-serif", color="#e8e8e8", size=16), x=0.01),
        # legend=dict(bgcolor="#161616", bordercolor="#222", borderwidth=1),
        # coloraxis_colorbar=dict(tickfont=dict(color="#888")),
        # xaxis=dict(gridcolor="#1a1a1a", zerolinecolor="#222", tickfont=dict(color="#666")),
        # yaxis=dict(gridcolor="#1a1a1a", zerolinecolor="#222", tickfont=dict(color="#666")),
    )
)

# ---------------------------------------------------------------------------
# Load filter data
# ---------------------------------------------------------------------------
years_df = run_query("SELECT DISTINCT EXTRACT(YEAR FROM date)::int AS year FROM snowflake.time_dim ORDER BY year")
categories_df = run_query("SELECT category FROM snowflake.category_dim ORDER BY category")
regions_df = run_query("SELECT region FROM snowflake.region_dim ORDER BY region")

all_years = years_df["year"].tolist()
all_categories = categories_df["category"].tolist()
all_regions = regions_df["region"].tolist()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="dash-title" style="font-size:1.4rem">SuperStore</div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-sub">BI Dashboard — Snowflake Schema</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">Filters</div>', unsafe_allow_html=True)

    selected_years = st.multiselect("Year", all_years, default=all_years)
    selected_categories = st.multiselect("Category", all_categories, default=all_categories)
    selected_regions = st.multiselect("Region", all_regions, default=all_regions)

    if not selected_years:
        selected_years = all_years
    if not selected_categories:
        selected_categories = all_categories
    if not selected_regions:
        selected_regions = all_regions

    years_sql = ", ".join(str(y) for y in selected_years)
    cats_sql = ", ".join(f"'{c}'" for c in selected_categories)
    regions_sql = ", ".join(f"'{r}'" for r in selected_regions)

    st.markdown('<div class="section-label">Schema</div>', unsafe_allow_html=True)
    st.markdown('<span style="font-size:0.7rem;color:#444">Using: snowflake.*</span>', unsafe_allow_html=True)
    st.markdown('<span style="font-size:0.7rem;color:#444">fact_sales + fact_shipping</span>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown('<div class="dash-title">SuperStore Analytics</div>', unsafe_allow_html=True)
st.markdown('<div class="dash-sub">Global Retail Intelligence · Snowflake Schema · Interactive BI Dashboard</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# KPI Row
# ---------------------------------------------------------------------------
kpi_query = f"""
SELECT
    SUM(f.sales)    AS total_sales,
    SUM(f.profit)   AS total_profit,
    SUM(f.quantity) AS total_quantity,
    AVG(f.discount) AS avg_discount,
    COUNT(*)        AS total_orders
FROM snowflake.fact_sales f
JOIN snowflake.time_dim t ON f.order_date_id = t.date_id
JOIN snowflake.product_dim p ON f.product_id = p.product_id
JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
JOIN snowflake.category_dim c ON sc.category_id = c.category_id
JOIN snowflake.state_dim st ON f.state_id = st.state_id
JOIN snowflake.market_dim m ON st.market_id = m.market_id
JOIN snowflake.region_dim r ON m.region_id = r.region_id
WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
  AND c.category IN ({cats_sql})
  AND r.region IN ({regions_sql})
"""
kpi = run_query(kpi_query).iloc[0]

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Total Sales", f"${kpi['total_sales']:,.0f}")
with col2:
    st.metric("Total Profit", f"${kpi['total_profit']:,.0f}")
with col3:
    st.metric("Total Orders", f"{kpi['total_orders']:,}")
with col4:
    st.metric("Units Sold", f"{kpi['total_quantity']:,.0f}")
with col5:
    margin = (kpi['total_profit'] / kpi['total_sales'] * 100) if kpi['total_sales'] else 0
    st.metric("Profit Margin", f"{margin:.1f}%")

st.markdown("---")

# ===========================================================================
# ROW 1: Dial Gauge + Fever Chart
# ===========================================================================
st.markdown('<div class="section-label">Performance Overview</div>', unsafe_allow_html=True)
col_gauge, col_fever = st.columns([1, 2])

# --- DIAL GAUGE ---
with col_gauge:
    st.markdown("#### 🎯 Profit Margin Gauge")
    gauge_fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(margin, 2),
        number={"suffix": "%", "font": {"size": 36, "family": "Syne, sans-serif", "color": "#e8e8e8"}},
        delta={"reference": 15, "increasing": {"color": "#3ecf8e"}, "decreasing": {"color": "#e55"}},
        gauge={
            "axis": {"range": [-10, 40], "tickcolor": "#444", "tickfont": {"color": "#555", "size": 10}},
            "bar": {"color": "#3ecf8e", "thickness": 0.25},
            "bgcolor": "#161616",
            "borderwidth": 0,
            "steps": [
                {"range": [-10, 0],  "color": "#1a0a0a"},
                {"range": [0,  10],  "color": "#141a14"},
                {"range": [10, 20],  "color": "#0d1a10"},
                {"range": [20, 40],  "color": "#081a0e"},
            ],
            "threshold": {
                "line": {"color": "#e8e8e8", "width": 2},
                "thickness": 0.75,
                "value": 15
            }
        },
        title={"text": "Profit Margin %<br><span style='font-size:0.7em;color:#555'>Target: 15%</span>",
               "font": {"family": "Syne, sans-serif", "color": "#888", "size": 13}}
    ))
    gauge_fig.update_layout(
        paper_bgcolor="#111111",
        font={"family": "DM Mono, monospace", "color": "#aaa"},
        height=300,
        margin=dict(t=60, b=20, l=30, r=30)
    )
    st.plotly_chart(gauge_fig, width='stretch')

# --- FEVER CHART ---
with col_fever:
    st.markdown("#### 🌡️ Fever Chart — Monthly Sales Trend")
    fever_query = f"""
    SELECT
        DATE_TRUNC('month', t.date) AS month,
        c.category,
        SUM(f.sales) AS total_sales
    FROM snowflake.fact_sales f
    JOIN snowflake.time_dim t ON f.order_date_id = t.date_id
    JOIN snowflake.product_dim p ON f.product_id = p.product_id
    JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN snowflake.category_dim c ON sc.category_id = c.category_id
    JOIN snowflake.state_dim st ON f.state_id = st.state_id
    JOIN snowflake.market_dim m ON st.market_id = m.market_id
    JOIN snowflake.region_dim r ON m.region_id = r.region_id
    WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
      AND c.category IN ({cats_sql})
      AND r.region IN ({regions_sql})
    GROUP BY DATE_TRUNC('month', t.date), c.category
    ORDER BY month
    """
    fever_df = run_query(fever_query)

    # Compute overall monthly average as baseline
    avg_df = fever_df.groupby("month")["total_sales"].sum().reset_index()
    overall_avg = avg_df["total_sales"].mean()

    fever_fig = px.line(
        fever_df, x="month", y="total_sales", color="category",
        title="Monthly Sales by Category with Baseline",
        labels={"total_sales": "Sales ($)", "month": "", "category": "Category"},
        color_discrete_sequence=["#3ecf8e", "#f59e0b", "#60a5fa", "#f87171", "#a78bfa"]
    )
    fever_fig.add_hline(
        y=overall_avg,
        line_dash="dot",
        line_color="#444",
        annotation_text=f"Avg ${overall_avg:,.0f}",
        annotation_font_color="#555",
        annotation_font_size=10
    )
    fever_fig.update_traces(line=dict(width=2))
    fever_fig.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        height=300,
        margin=dict(t=50, b=20, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10))
    )
    st.plotly_chart(fever_fig, width='stretch')

# ===========================================================================
# ROW 2: Heatmap + Bubble
# ===========================================================================
st.markdown('<div class="section-label">Correlation & Segment Analysis</div>', unsafe_allow_html=True)
col_heat, col_bubble = st.columns([1, 1])

# --- HEATMAP ---
with col_heat:
    st.markdown("#### 🔥 Metric Correlation Heatmap")
    heatmap_query = f"""
    SELECT
        r.region,
        SUM(f.sales)         AS total_sales,
        SUM(f.profit)        AS total_profit,
        AVG(f.discount)      AS avg_discount,
        SUM(f.quantity)      AS total_quantity,
        SUM(sh.shipping_cost) AS total_shipping
    FROM snowflake.fact_sales f
    JOIN snowflake.time_dim t ON f.order_date_id = t.date_id
    JOIN snowflake.product_dim p ON f.product_id = p.product_id
    JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN snowflake.category_dim c ON sc.category_id = c.category_id
    JOIN snowflake.state_dim st ON f.state_id = st.state_id
    JOIN snowflake.market_dim m ON st.market_id = m.market_id
    JOIN snowflake.region_dim r ON m.region_id = r.region_id
    JOIN snowflake.fact_shipping sh ON f.product_id = sh.product_id AND f.state_id = sh.state_id
    WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
      AND c.category IN ({cats_sql})
      AND r.region IN ({regions_sql})
    GROUP BY r.region
    """
    heatmap_df = run_query(heatmap_query)
    heatmap_df = heatmap_df.set_index("region")
    corr = heatmap_df.corr()

    heat_fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale=[[0, "#1a0a0a"], [0.5, "#161616"], [1, "#3ecf8e"]],
        title="Correlation: Sales · Profit · Discount · Quantity · Shipping",
        zmin=-1, zmax=1
    )
    heat_fig.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        height=360,
        margin=dict(t=50, b=10, l=10, r=10),
        coloraxis_showscale=True,
        xaxis=dict(tickfont=dict(size=10, color="#888"), side="bottom"),
        yaxis=dict(tickfont=dict(size=10, color="#888"))
    )
    heat_fig.update_traces(textfont=dict(size=11, color="#ccc"))
    st.plotly_chart(heat_fig, width='stretch')

# --- BUBBLE PLOT ---
with col_bubble:
    st.markdown("#### 🫧 Profit vs Sales — Region & Segment")
    bubble_query = f"""
    SELECT
        r.region,
        s.segment,
        SUM(f.sales)    AS total_sales,
        SUM(f.profit)   AS total_profit,
        SUM(f.quantity) AS total_quantity
    FROM snowflake.fact_sales f
    JOIN snowflake.customer_dim cd ON f.customer_id = cd.customer_id
    JOIN snowflake.segment_dim s ON cd.segment_id = s.segment_id
    JOIN snowflake.state_dim st ON f.state_id = st.state_id
    JOIN snowflake.market_dim m ON st.market_id = m.market_id
    JOIN snowflake.region_dim r ON m.region_id = r.region_id
    JOIN snowflake.time_dim t ON f.order_date_id = t.date_id
    JOIN snowflake.product_dim p ON f.product_id = p.product_id
    JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN snowflake.category_dim c ON sc.category_id = c.category_id
    WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
      AND c.category IN ({cats_sql})
      AND r.region IN ({regions_sql})
    GROUP BY r.region, s.segment
    """
    bubble_df = run_query(bubble_query)
    bubble_fig = px.scatter(
        bubble_df, x="total_sales", y="total_profit",
        size="total_quantity", color="region", symbol="segment",
        hover_name="region",
        hover_data={"segment": True, "total_quantity": True, "total_sales": ":.0f", "total_profit": ":.0f"},
        title="Profit vs Sales (bubble = quantity)",
        labels={"total_sales": "Sales ($)", "total_profit": "Profit ($)"},
        color_discrete_sequence=["#3ecf8e", "#f59e0b", "#60a5fa", "#f87171", "#a78bfa", "#34d399", "#fb923c"]
    )
    bubble_fig.add_hline(y=0, line_color="#333", line_dash="dot")
    bubble_fig.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        height=360,
        margin=dict(t=50, b=10, l=10, r=10),
        legend=dict(font=dict(size=10), orientation="v")
    )
    st.plotly_chart(bubble_fig, width='stretch')

# ===========================================================================
# ROW 3: Sunburst + Choropleth
# ===========================================================================
st.markdown('<div class="section-label">Product & Geographic Analysis</div>', unsafe_allow_html=True)
col_sun, col_map = st.columns([1, 1])

# --- SUNBURST ---
with col_sun:
    st.markdown("#### ☀️ Sales Hierarchy — Category → Sub-Category → Product")
    sunburst_query = f"""
    SELECT
        c.category,
        sc.sub_category,
        p.product_name,
        SUM(f.sales) AS total_sales
    FROM snowflake.fact_sales f
    JOIN snowflake.time_dim t ON f.order_date_id = t.date_id
    JOIN snowflake.product_dim p ON f.product_id = p.product_id
    JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN snowflake.category_dim c ON sc.category_id = c.category_id
    JOIN snowflake.state_dim st ON f.state_id = st.state_id
    JOIN snowflake.market_dim m ON st.market_id = m.market_id
    JOIN snowflake.region_dim r ON m.region_id = r.region_id
    WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
      AND c.category IN ({cats_sql})
      AND r.region IN ({regions_sql})
    GROUP BY c.category, sc.sub_category, p.product_name
    """
    sun_df = run_query(sunburst_query)
    sun_fig = px.sunburst(
        sun_df,
        path=["category", "sub_category", "product_name"],
        values="total_sales",
        title="Sales by Product Hierarchy",
        color="total_sales",
        color_continuous_scale=[[0, "#0d1a10"], [0.5, "#1a3a22"], [1, "#3ecf8e"]]
    )
    sun_fig.update_layout(
        paper_bgcolor="#111111",
        font=dict(family="DM Mono, monospace", color="#aaa"),
        title=dict(font=dict(family="Syne, sans-serif", color="#e8e8e8", size=14), x=0.01),
        height=420,
        margin=dict(t=50, b=10, l=10, r=10)
    )
    st.plotly_chart(sun_fig, width='stretch')

# --- CHOROPLETH ---
with col_map:
    st.markdown("#### 🌍 Global Sales Heatmap by Country")
    choropleth_query = f"""
    SELECT
        ctry.country,
        SUM(f.sales) AS total_sales
    FROM snowflake.fact_sales f
    JOIN snowflake.time_dim t ON f.order_date_id = t.date_id
    JOIN snowflake.product_dim p ON f.product_id = p.product_id
    JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN snowflake.category_dim c ON sc.category_id = c.category_id
    JOIN snowflake.state_dim st ON f.state_id = st.state_id
    JOIN snowflake.market_dim m ON st.market_id = m.market_id
    JOIN snowflake.region_dim r ON m.region_id = r.region_id
    JOIN snowflake.country_dim ctry ON r.country_id = ctry.country_id
    WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
      AND c.category IN ({cats_sql})
      AND r.region IN ({regions_sql})
    GROUP BY ctry.country
    ORDER BY total_sales DESC
    """
    map_df = run_query(choropleth_query)
    map_fig = px.choropleth(
        map_df,
        locations="country",
        locationmode="country names",
        color="total_sales",
        hover_name="country",
        title="Global Sales Distribution",
        color_continuous_scale=[[0, "#0a1a0d"], [0.5, "#1a4a25"], [1, "#3ecf8e"]]
    )
    map_fig.update_layout(
        paper_bgcolor="#111111",
        geo=dict(
            bgcolor="#111111",
            showframe=False,
            showcoastlines=True,
            coastlinecolor="#222",
            showland=True,
            landcolor="#161616",
            showocean=True,
            oceancolor="#0d0d0d",
            showlakes=False,
            showcountries=True,
            countrycolor="#222"
        ),
        font=dict(family="DM Mono, monospace", color="#aaa"),
        title=dict(font=dict(family="Syne, sans-serif", color="#e8e8e8", size=14), x=0.01),
        coloraxis_colorbar=dict(tickfont=dict(color="#666", size=9)),
        height=420,
        margin=dict(t=50, b=10, l=0, r=0)
    )
    st.plotly_chart(map_fig, width='stretch')

# ===========================================================================
# ROW 4: Stacked Area + Shipping Analysis
# ===========================================================================
st.markdown('<div class="section-label">Time Series & Shipping</div>', unsafe_allow_html=True)
col_area, col_ship = st.columns([1, 1])

# --- STACKED AREA ---
with col_area:
    st.markdown("#### 📈 Sales Growth Over Time by Category")
    area_query = f"""
    SELECT
        EXTRACT(YEAR FROM t.date)::int AS year,
        c.category,
        SUM(f.sales) AS total_sales
    FROM snowflake.fact_sales f
    JOIN snowflake.time_dim t ON f.order_date_id = t.date_id
    JOIN snowflake.product_dim p ON f.product_id = p.product_id
    JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN snowflake.category_dim c ON sc.category_id = c.category_id
    JOIN snowflake.state_dim st ON f.state_id = st.state_id
    JOIN snowflake.market_dim m ON st.market_id = m.market_id
    JOIN snowflake.region_dim r ON m.region_id = r.region_id
    WHERE EXTRACT(YEAR FROM t.date) IN ({years_sql})
      AND c.category IN ({cats_sql})
      AND r.region IN ({regions_sql})
    GROUP BY EXTRACT(YEAR FROM t.date), c.category
    ORDER BY year
    """
    area_df = run_query(area_query)
    area_fig = px.area(
        area_df, x="year", y="total_sales", color="category",
        title="Yearly Sales Growth by Category",
        labels={"total_sales": "Sales ($)", "year": "Year"},
        color_discrete_sequence=["#3ecf8e", "#f59e0b", "#60a5fa"]
    )
    area_fig.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        height=340,
        margin=dict(t=50, b=20, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10))
    )
    st.plotly_chart(area_fig, width='stretch')

# --- SHIPPING ANALYSIS ---
with col_ship:
    st.markdown("#### 🚚 Shipping Cost by Mode & Priority")
    ship_query = f"""
    SELECT
        sm.ship_mode,
        op.order_priority,
        SUM(sh.shipping_cost) AS total_shipping_cost,
        COUNT(*) AS shipment_count
    FROM snowflake.fact_shipping sh
    JOIN snowflake.ship_mode_dim sm ON sh.ship_mode_id = sm.ship_mode_id
    JOIN snowflake.order_priority_dim op ON sh.order_priority_id = op.order_priority_id
    JOIN snowflake.state_dim st ON sh.state_id = st.state_id
    JOIN snowflake.market_dim m ON st.market_id = m.market_id
    JOIN snowflake.region_dim r ON m.region_id = r.region_id
    WHERE r.region IN ({regions_sql})
    GROUP BY sm.ship_mode, op.order_priority
    ORDER BY total_shipping_cost DESC
    """
    ship_df = run_query(ship_query)
    ship_fig = px.bar(
        ship_df, x="ship_mode", y="total_shipping_cost",
        color="order_priority", barmode="group",
        title="Total Shipping Cost by Mode & Priority",
        labels={"total_shipping_cost": "Shipping Cost ($)", "ship_mode": "Ship Mode", "order_priority": "Priority"},
        color_discrete_sequence=["#f87171", "#f59e0b", "#60a5fa", "#3ecf8e"]
    )
    ship_fig.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        height=340,
        margin=dict(t=50, b=20, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10))
    )
    st.plotly_chart(ship_fig, width='stretch')

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    '<span style="font-family:\'DM Mono\',monospace;font-size:0.65rem;color:#333">'
    'SuperStore BI Dashboard · Snowflake Schema · Built with Streamlit + Plotly'
    '</span>',
    unsafe_allow_html=True
)