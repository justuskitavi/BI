import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv
import warnings

# Suppress pandas warning about psycopg2 connection (standard practice when using direct DB connections)
warnings.filterwarnings("ignore", category=UserWarning, message=".*pandas only supports SQLAlchemy connectable.*")

# Load database URL from environment variables
load_dotenv()

def get_connection():
    """Establishes a connection to the PostgreSQL database."""
    DATABASE_URL = os.getenv("DB_URL")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f" Connection failed: {e}")
        exit(1)

def run_and_print(title, sql, conn):
    """
    Executes a SQL query and prints the resulting DataFrame in a formatted way.
    
    Args:
        title (str): The name of the OLAP operation being performed.
        sql (str): The SQL query to execute.
        conn: The database connection.
    """
    print(f"\n{'='*80}")
    print(f" OLAP OPERATION: {title}")
    print(f"{'='*80}")
    try:
        # Load query result into a pandas DataFrame
        df = pd.read_sql(sql, conn)
        if df.empty:
            print("  No data found for this operation.")
            print("   Check if the filters (Year, Segment, Country) match your data.")
        else:
            # Print the data without indices for a cleaner look
            print(df.to_string(index=False))
    except Exception as e:
        print(f" Error executing query: {e}")

def main():
    """Main execution block for running various OLAP operations on the Snowflake schema."""
    conn = get_connection()
    
    # ---------------------------------------------------------------------------
    # Quick Diagnostics
    # ---------------------------------------------------------------------------
    print("\n Database Diagnostics:")
    # Check available years and countries to ensure filters in queries will work
    years = pd.read_sql("SELECT DISTINCT EXTRACT(YEAR FROM date)::int as y FROM snowflake.time_dim ORDER BY y", conn)
    countries = pd.read_sql("SELECT DISTINCT country FROM snowflake.country_dim LIMIT 5", conn)
    print(f"   Available Years: {years['y'].tolist()}")
    print(f"   Sample Countries: {countries['country'].tolist()}")
    
    # ---------------------------------------------------------------------------
    # 1. SLICING: Creating a sub-cube by selecting a single value for one dimension.
    # Here: Selecting only the 'Consumer' segment and year 2014.
    # ---------------------------------------------------------------------------
    slicing_sql = """
    SELECT EXTRACT(YEAR FROM t.date)::int as year, TRIM(s.segment) as segment, SUM(f.sales)::decimal(15,2) as total_sales
    FROM snowflake.fact_sales f
    JOIN snowflake.time_dim t ON f.order_date_id = t.date_id
    JOIN snowflake.customer_dim cd ON f.customer_id = cd.customer_id
    JOIN snowflake.segment_dim s ON cd.segment_id = s.segment_id
    WHERE TRIM(s.segment) = 'Consumer' AND EXTRACT(YEAR FROM t.date) = 2014
    GROUP BY year, s.segment;
    """
    run_and_print("SLICING (Consumer Segment in 2014)", slicing_sql, conn)

    # ---------------------------------------------------------------------------
    # 2. DICING: Creating a sub-cube by selecting multiple values for multiple dimensions.
    # Here: Selecting 'Technology' category AND 'United States' country.
    # ---------------------------------------------------------------------------
    dicing_sql = """
    SELECT TRIM(cat.category) as category, TRIM(ctry.country) as country, SUM(f.sales)::decimal(15,2) as total_sales
    FROM snowflake.fact_sales f
    JOIN snowflake.product_dim p ON f.product_id = p.product_id
    JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN snowflake.category_dim cat ON sc.category_id = cat.category_id
    JOIN snowflake.state_dim st ON f.state_id = st.state_id
    JOIN snowflake.market_dim m ON st.market_id = m.market_id
    JOIN snowflake.region_dim r ON m.region_id = r.region_id
    JOIN snowflake.country_dim ctry ON r.country_id = ctry.country_id
    WHERE TRIM(cat.category) = 'Technology' AND TRIM(ctry.country) = 'United States'
    GROUP BY cat.category, ctry.country;
    """
    run_and_print("DICING (Technology in US)", dicing_sql, conn)

    # ---------------------------------------------------------------------------
    # 3. PIVOTING: Rotating the data axes to view it from a different perspective.
    # Here: Showing Region as rows and Shipping Modes as columns.
    # ---------------------------------------------------------------------------
    pivoting_sql = """
    SELECT r.region,
        SUM(CASE WHEN sm.ship_mode = 'First Class' THEN fs.shipping_cost ELSE 0 END)::decimal(15,2) AS first_class,
        SUM(CASE WHEN sm.ship_mode = 'Standard Class' THEN fs.shipping_cost ELSE 0 END)::decimal(15,2) AS standard_class,
        SUM(CASE WHEN sm.ship_mode = 'Second Class' THEN fs.shipping_cost ELSE 0 END)::decimal(15,2) AS second_class
    FROM snowflake.fact_shipping fs
    JOIN snowflake.state_dim st ON fs.state_id = st.state_id
    JOIN snowflake.market_dim m ON st.market_id = m.market_id
    JOIN snowflake.region_dim r ON m.region_id = r.region_id
    JOIN snowflake.ship_mode_dim sm ON fs.ship_mode_id = sm.ship_mode_id
    GROUP BY r.region
    ORDER BY r.region;
    """
    run_and_print("PIVOTING (Shipping Cost by Mode)", pivoting_sql, conn)

    # ---------------------------------------------------------------------------
    # 4. DRILL-DOWN: Moving from high-level summary to more granular detail.
    # Here: Expanding from 'Category' to 'Sub-Category'.
    # ---------------------------------------------------------------------------
    drill_down_sql = """
    SELECT c.category, sc.sub_category, SUM(f.sales)::decimal(15,2) AS total_sales
    FROM snowflake.fact_sales f
    JOIN snowflake.product_dim p ON f.product_id = p.product_id
    JOIN snowflake.sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
    JOIN snowflake.category_dim c ON sc.category_id = c.category_id
    GROUP BY c.category, sc.sub_category
    ORDER BY c.category, total_sales DESC
    LIMIT 10;
    """
    run_and_print("DRILL-DOWN (Category -> Sub-Category)", drill_down_sql, conn)

    # ---------------------------------------------------------------------------
    # 5. DRILL-UP (ROLL-UP): Moving from granular detail to high-level summary.
    # Here: Summarizing all state/region sales up to the 'Country' level.
    # ---------------------------------------------------------------------------
    drill_up_sql = """
    SELECT ctry.country, SUM(f.sales)::decimal(15,2) AS total_sales
    FROM snowflake.fact_sales f
    JOIN snowflake.state_dim st ON f.state_id = st.state_id
    JOIN snowflake.market_dim m ON st.market_id = m.market_id
    JOIN snowflake.region_dim r ON m.region_id = r.region_id
    JOIN snowflake.country_dim ctry ON r.country_id = ctry.country_id
    GROUP BY ctry.country
    ORDER BY total_sales DESC
    LIMIT 10;
    """
    run_and_print("DRILL-UP (Roll-up to Country)", drill_up_sql, conn)

    # ---------------------------------------------------------------------------
    # 6. DRILL ACROSS: Querying across multiple fact tables using common dimensions.
    # Here: Joining 'fact_sales' and 'fact_shipping' by State and Product.
    # ---------------------------------------------------------------------------
    drill_across_sql = """
    SELECT st.state, SUM(fs.sales)::decimal(15,2) as total_sales, SUM(fsh.shipping_cost)::decimal(15,2) as total_shipping
    FROM snowflake.fact_sales fs
    JOIN snowflake.fact_shipping fsh ON fs.state_id = fsh.state_id AND fs.product_id = fsh.product_id
    JOIN snowflake.state_dim st ON fs.state_id = st.state_id
    GROUP BY st.state
    ORDER BY total_sales DESC
    LIMIT 10;
    """
    run_and_print("DRILL ACROSS (Sales vs Shipping by State)", drill_across_sql, conn)

    # ---------------------------------------------------------------------------
    # 7. DRILL THROUGH: Moving from a summary cell to the underlying raw transactions.
    # Here: Showing individual high-value sales transactions.
    # ---------------------------------------------------------------------------
    drill_through_sql = """
    SELECT f.fact_sales_id, cd.customer_name, s.segment, f.sales, f.profit
    FROM snowflake.fact_sales f
    JOIN snowflake.customer_dim cd ON f.customer_id = cd.customer_id
    JOIN snowflake.segment_dim s ON cd.segment_id = s.segment_id
    WHERE f.sales > 3000
    ORDER BY f.sales DESC
    LIMIT 10;
    """
    run_and_print("DRILL THROUGH (Detailed Transaction Data)", drill_through_sql, conn)

    # Close connection
    conn.close()
    print("\n All OLAP operations completed.")

if __name__ == "__main__":
    main()
