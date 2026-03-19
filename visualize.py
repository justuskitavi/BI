import pandas as pd
import mysql.connector
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt

# 1. Database Connection Setup
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Jaulsetxus2005.",
        database="snowflake"
    )

# 2. Visualizations implementation
def run_visualizations():
    conn = get_connection()
    
    # --- Visualization 1: Interactive Sunburst Chart (Plotly) ---
    print("Generating Sunburst Chart...")
    query1 = """
    SELECT 
        c.category, 
        sc.sub_category, 
        p.product_name, 
        SUM(f.sales) AS total_sales
    FROM fact_sales f
    JOIN product_dim p ON f.product_id = p.product_id
    JOIN sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN category_dim c ON sc.category_id = c.category_id
    GROUP BY c.category, sc.sub_category, p.product_name
    """
    df1 = pd.read_sql(query1, conn)
    fig1 = px.sunburst(df1, path=['category', 'sub_category', 'product_name'], values='total_sales',
                      title='Sales Hierarchy: Category > Sub-Category > Product',
                      color='total_sales', color_continuous_scale='RdBu')
    fig1.write_html("sunburst_sales_hierarchy.html")

    # --- Visualization 2: Profit vs. Sales Bubble Plot (Seaborn) ---
    print("Generating Profit vs Sales Bubble Plot...")
    query2 = """
    SELECT 
        r.region, 
        s.segment, 
        SUM(f.sales) AS total_sales, 
        SUM(f.profit) AS total_profit, 
        SUM(f.quantity) AS total_quantity
    FROM fact_sales f
    JOIN customer_dim cd ON f.customer_id = cd.customer_id
    JOIN segment_dim s ON cd.segment_id = s.segment_id
    JOIN state_dim st ON f.state_id = st.state_id
    JOIN market_dim m ON st.market_id = m.market_id
    JOIN region_dim r ON m.region_id = r.region_id
    GROUP BY r.region, s.segment
    """
    df2 = pd.read_sql(query2, conn)
    plt.figure(figsize=(12, 8))
    sns.set_style("whitegrid")
    bubble = sns.scatterplot(data=df2, x="total_sales", y="total_profit", 
                             size="total_quantity", hue="region", style="segment",
                             sizes=(100, 2000), alpha=0.7)
    plt.title("Profit vs Sales by Region and Segment (Bubble size = Quantity)")
    plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    plt.savefig("profit_vs_sales_bubble.png", bbox_inches='tight')
    plt.close()

    # --- Visualization 3: Geographical Heatmap (Plotly) ---
    print("Generating Geographical Heatmap...")
    query3 = """
    SELECT 
        ctry.country, 
        SUM(f.sales) AS total_sales
    FROM fact_sales f
    JOIN state_dim st ON f.state_id = st.state_id
    JOIN market_dim m ON st.market_id = m.market_id
    JOIN region_dim r ON m.region_id = r.region_id
    JOIN country_dim ctry ON r.country_id = ctry.country_id
    GROUP BY ctry.country
    """
    df3 = pd.read_sql(query3, conn)
    fig3 = px.choropleth(df3, locations="country", locationmode='country names',
                        color="total_sales", hover_name="country",
                        title='Global Sales Distribution by Country',
                        color_continuous_scale=px.colors.sequential.Plasma)
    fig3.write_html("geographical_sales_heatmap.html")

    # --- Visualization 4: Stacked Area Chart (Plotly) ---
    print("Generating Stacked Area Chart...")
    query4 = """
    SELECT 
        YEAR(t.date) AS year, 
        cat.category, 
        SUM(f.sales) AS total_sales
    FROM fact_sales f
    JOIN time_dim t ON f.order_date_id = t.date_id
    JOIN product_dim p ON f.product_id = p.product_id
    JOIN sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN category_dim cat ON sc.category_id = cat.category_id
    GROUP BY YEAR(t.date), cat.category
    ORDER BY year, cat.category
    """
    df4 = pd.read_sql(query4, conn)
    fig4 = px.area(df4, x="year", y="total_sales", color="category",
                  title='Sales Growth Over Time by Category',
                  labels={'total_sales': 'Total Sales', 'year': 'Year'})
    fig4.write_html("sales_growth_area_chart.html")

    conn.close()
    print("\nSuccess! The following files have been created:")
    print("- sunburst_sales_hierarchy.html (Interactive)")
    print("- profit_vs_sales_bubble.png (Static Image)")
    print("- geographical_sales_heatmap.html (Interactive Map)")
    print("- sales_growth_area_chart.html (Interactive)")

if __name__ == "__main__":
    try:
        run_visualizations()
    except Exception as e:
        print(f"Error: {e}")
