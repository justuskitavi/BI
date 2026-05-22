import os
import sys
import time
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

print("Mission initialised, Snowflake schema ETL underway..!")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def print_progress(label, index, total, bar_length=30):
    """
    Displays a progress bar in the console to track the status of data loading.
    
    Args:
        label (str): The name of the process being tracked.
        index (int): Current progress count.
        total (int): Total count to reach.
        bar_length (int): The visual length of the progress bar.
    """
    if total <= 0:
        return
    filled = int(bar_length * index / total)
    bar = "=" * filled + " " * (bar_length - filled)
    percent = 100 * index / total
    sys.stdout.write(f"\r{label}: [{bar}] {index}/{total} ({percent:5.1f}%)")
    sys.stdout.flush()
    if index >= total:
        sys.stdout.write("\n")


def get_connection(retries=5, delay=5):
    
    DATABASE_URL = os.getenv("DB_URL")
    for attempt in range(1, retries + 1):
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            conn.autocommit = False
            return conn
        except psycopg2.OperationalError as e:
            print(f"\nConnection attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                print(f"Retrying in {delay}s...")
                time.sleep(delay)
    raise RuntimeError("Could not connect to database after multiple attempts.")


def execute_batch_safe(conn, cursor, sql, data, batch_size=500, progress_label=None, schema="snowflake"):
    
    total = len(data)
    for batch_start in range(0, total, batch_size):
        batch = data[batch_start: batch_start + batch_size]
        for attempt in range(5):
            try:
                psycopg2.extras.execute_batch(cursor, sql, batch, page_size=batch_size)
                conn.commit()
                break
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                print(f"\nDB error: {e}. Reconnecting (attempt {attempt+1})...")
                time.sleep(5)
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(f"SET search_path TO {schema};")
        else:
            raise RuntimeError(f"Failed to insert batch at {batch_start} after 5 attempts.")

        done = min(batch_start + batch_size, total)
        if progress_label:
            print_progress(progress_label, done, total)

    return conn, cursor


# ---------------------------------------------------------------------------
# Progress tracking
# Phases: start → dims_done → sales_done → shipping_done
# File format: phase|fact_sales_row|fact_shipping_row
# ---------------------------------------------------------------------------
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "snowflake_progress.txt")

def read_progress():
    """Reads the progress file to determine where to resume if a previous run was interrupted."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            parts = f.read().strip().split("|")
        phase = parts[0] if len(parts) > 0 else "start"
        sales_row = int(parts[1]) if len(parts) > 1 else 0
        ship_row = int(parts[2]) if len(parts) > 2 else 0
        return phase, sales_row, ship_row
    return "start", 0, 0

def save_progress(phase, sales_row=0, ship_row=0):
    """Saves the current phase and row indices for sales and shipping fact tables."""
    with open(PROGRESS_FILE, "w") as f:
        f.write(f"{phase}|{sales_row}|{ship_row}")

# Check for existing progress
phase, sales_start, ship_start = read_progress()
resuming = phase != "start"
if resuming:
    print(f"Resuming from phase='{phase}', fact_sales row={sales_start}, fact_shipping row={ship_start}")

# ---------------------------------------------------------------------------
# Load and Clean CSV
# ---------------------------------------------------------------------------
CSV_PATH = "../data/SuperStoreOrders.csv"
df = pd.read_csv(CSV_PATH, skipinitialspace=True)

# Normalize column names: lowercase, trimmed, spaces replaced with underscores
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

# Strip whitespaces from all string (object) columns
df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

# Convert date columns to datetime objects
df["order_date"] = pd.to_datetime(df["order_date"], dayfirst=True, errors="coerce")
df["ship_date"] = pd.to_datetime(df["ship_date"], dayfirst=True, errors="coerce")

# Convert currency/numeric columns to proper numeric types, handling commas
for col in ["sales", "quantity", "discount", "profit", "shipping_cost"]:
    if col in df.columns:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False).str.strip(),
            errors="coerce"
        )

# ---------------------------------------------------------------------------
# Database Connection and Schema Initialization
# ---------------------------------------------------------------------------
conn = get_connection()
cursor = conn.cursor()
cursor.execute("CREATE SCHEMA IF NOT EXISTS snowflake;")
cursor.execute("SET search_path TO snowflake;")
conn.commit()

# ---------------------------------------------------------------------------
# Schema setup (only if starting fresh)
# In Snowflake schema, dimensions are normalized (split into sub-tables)
# ---------------------------------------------------------------------------
if not resuming:
    print("Dropping and recreating tables...")
    drops = [
        "fact_shipping", "fact_sales", "state_dim", "market_dim", "region_dim",
        "country_dim", "product_dim", "sub_category_dim", "category_dim",
        "customer_dim", "segment_dim", "ship_mode_dim", "order_priority_dim", "time_dim"
    ]
    for tbl in drops:
        cursor.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")

    # 1. Base Dimensions
    cursor.execute("CREATE TABLE time_dim (date_id SERIAL PRIMARY KEY, date DATE NOT NULL UNIQUE)")
    cursor.execute("CREATE TABLE segment_dim (segment_id SERIAL PRIMARY KEY, segment VARCHAR(100) NOT NULL UNIQUE)")
    
    # 2. Normalized Customer Dimension (references Segment)
    cursor.execute("""
        CREATE TABLE customer_dim (
            customer_id SERIAL PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            segment_id INT NOT NULL REFERENCES segment_dim(segment_id),
            UNIQUE (customer_name, segment_id)
        )
    """)
    
    # 3. Normalized Product Dimension (Category -> Sub-Category -> Product)
    cursor.execute("CREATE TABLE category_dim (category_id SERIAL PRIMARY KEY, category VARCHAR(100) NOT NULL UNIQUE)")
    cursor.execute("""
        CREATE TABLE sub_category_dim (
            sub_category_id SERIAL PRIMARY KEY,
            sub_category VARCHAR(100) NOT NULL,
            category_id INT NOT NULL REFERENCES category_dim(category_id),
            UNIQUE (sub_category, category_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE product_dim (
            product_id VARCHAR(100) PRIMARY KEY,
            product_name VARCHAR(500),
            sub_category_id INT NOT NULL REFERENCES sub_category_dim(sub_category_id)
        )
    """)
    
    # 4. Normalized Location Dimension (Country -> Region -> Market -> State)
    cursor.execute("CREATE TABLE country_dim (country_id SERIAL PRIMARY KEY, country VARCHAR(100) NOT NULL UNIQUE)")
    cursor.execute("""
        CREATE TABLE region_dim (
            region_id SERIAL PRIMARY KEY,
            region VARCHAR(100) NOT NULL,
            country_id INT NOT NULL REFERENCES country_dim(country_id),
            UNIQUE (region, country_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE market_dim (
            market_id SERIAL PRIMARY KEY,
            market VARCHAR(100) NOT NULL,
            region_id INT NOT NULL REFERENCES region_dim(region_id),
            UNIQUE (market, region_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE state_dim (
            state_id SERIAL PRIMARY KEY,
            state VARCHAR(100) NOT NULL,
            market_id INT NOT NULL REFERENCES market_dim(market_id),
            UNIQUE (state, market_id)
        )
    """)
    
    # 5. Shipping Dimensions
    cursor.execute("CREATE TABLE ship_mode_dim (ship_mode_id SERIAL PRIMARY KEY, ship_mode VARCHAR(100) NOT NULL UNIQUE)")
    cursor.execute("CREATE TABLE order_priority_dim (order_priority_id SERIAL PRIMARY KEY, order_priority VARCHAR(100) NOT NULL UNIQUE)")
    
    # 6. Fact Tables (Two fact tables: Sales and Shipping)
    cursor.execute("""
        CREATE TABLE fact_sales (
            fact_sales_id SERIAL PRIMARY KEY,
            order_date_id INT NOT NULL REFERENCES time_dim(date_id),
            customer_id INT NOT NULL REFERENCES customer_dim(customer_id),
            product_id VARCHAR(100) NOT NULL REFERENCES product_dim(product_id),
            state_id INT NOT NULL REFERENCES state_dim(state_id),
            sales DECIMAL(15,2),
            quantity INT,
            discount DECIMAL(15,4),
            profit DECIMAL(15,5)
        )
    """)
    cursor.execute("""
        CREATE TABLE fact_shipping (
            fact_shipping_id SERIAL PRIMARY KEY,
            ship_date_id INT NOT NULL REFERENCES time_dim(date_id),
            product_id VARCHAR(100) NOT NULL REFERENCES product_dim(product_id),
            state_id INT NOT NULL REFERENCES state_dim(state_id),
            ship_mode_id INT NOT NULL REFERENCES ship_mode_dim(ship_mode_id),
            order_priority_id INT NOT NULL REFERENCES order_priority_dim(order_priority_id),
            shipping_cost DECIMAL(15,3)
        )
    """)
    conn.commit()

# ---------------------------------------------------------------------------
# Load normalized dimensions (skip if already done)
# ---------------------------------------------------------------------------
if phase == "start":
    # Time
    print("Loading time_dim...")
    all_dates = sorted(pd.concat([df["order_date"], df["ship_date"]]).dropna().unique())
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO time_dim (date) VALUES (%s) ON CONFLICT (date) DO NOTHING",
        [(pd.Timestamp(d).date(),) for d in all_dates], progress_label="time_dim")

    # Segment
    print("Loading segment_dim...")
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO segment_dim (segment) VALUES (%s) ON CONFLICT (segment) DO NOTHING",
        [(s,) for s in df["segment"].dropna().unique()], progress_label="segment_dim")

    # Map segment to ID for Customer loading
    cursor.execute("SELECT segment, segment_id FROM segment_dim")
    seg_map = dict(cursor.fetchall())

    # Customer
    print("Loading customer_dim...")
    customers = df[["customer_name", "segment"]].drop_duplicates()
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO customer_dim (customer_name, segment_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        [(r["customer_name"], seg_map[r["segment"]]) for _, r in customers.iterrows()],
        progress_label="customer_dim")

    # Category
    print("Loading category_dim...")
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO category_dim (category) VALUES (%s) ON CONFLICT (category) DO NOTHING",
        [(c,) for c in df["category"].dropna().unique()], progress_label="category_dim")

    # Map category to ID for Sub-Category loading
    cursor.execute("SELECT category, category_id FROM category_dim")
    cat_map = dict(cursor.fetchall())

    # Sub-Category
    print("Loading sub_category_dim...")
    subcats = df[["sub_category", "category"]].drop_duplicates()
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO sub_category_dim (sub_category, category_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        [(r["sub_category"], cat_map[r["category"]]) for _, r in subcats.iterrows()],
        progress_label="sub_category_dim")

    # Map sub-category and category to ID for Product loading
    cursor.execute("SELECT sc.sub_category, c.category, sc.sub_category_id FROM sub_category_dim sc JOIN category_dim c ON sc.category_id = c.category_id")
    subcat_map = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

    # Product
    print("Loading product_dim...")
    products = df[["product_id", "product_name", "sub_category", "category"]].drop_duplicates("product_id")
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO product_dim (product_id, product_name, sub_category_id) VALUES (%s, %s, %s) ON CONFLICT (product_id) DO NOTHING",
        [(r["product_id"], r["product_name"], subcat_map[(r["sub_category"], r["category"])]) for _, r in products.iterrows()],
        progress_label="product_dim")

    # Country
    print("Loading country_dim...")
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO country_dim (country) VALUES (%s) ON CONFLICT (country) DO NOTHING",
        [(c,) for c in df["country"].dropna().unique()], progress_label="country_dim")

    # Map country to ID for Region loading
    cursor.execute("SELECT country, country_id FROM country_dim")
    ctry_map = dict(cursor.fetchall())

    # Region
    print("Loading region_dim...")
    regions = df[["region", "country"]].drop_duplicates()
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO region_dim (region, country_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        [(r["region"], ctry_map[r["country"]]) for _, r in regions.iterrows()],
        progress_label="region_dim")

    # Map region and country to ID for Market loading
    cursor.execute("SELECT r.region, c.country, r.region_id FROM region_dim r JOIN country_dim c ON r.country_id = c.country_id")
    region_map = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

    # Market
    print("Loading market_dim...")
    markets = df[["market", "region", "country"]].drop_duplicates()
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO market_dim (market, region_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        [(r["market"], region_map[(r["region"], r["country"])]) for _, r in markets.iterrows()],
        progress_label="market_dim")

    # Map market, region and country to ID for State loading
    cursor.execute("SELECT m.market, r.region, c.country, m.market_id FROM market_dim m JOIN region_dim r ON m.region_id = r.region_id JOIN country_dim c ON r.country_id = c.country_id")
    market_map = {(r[0], r[1], r[2]): r[3] for r in cursor.fetchall()}

    # State
    print("Loading state_dim...")
    states = df[["state", "market", "region", "country"]].drop_duplicates()
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO state_dim (state, market_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        [(r["state"], market_map[(r["market"], r["region"], r["country"])]) for _, r in states.iterrows()],
        progress_label="state_dim")

    # Shipping Mode
    print("Loading ship_mode_dim...")
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO ship_mode_dim (ship_mode) VALUES (%s) ON CONFLICT (ship_mode) DO NOTHING",
        [(s,) for s in df["ship_mode"].dropna().unique()], progress_label="ship_mode_dim")

    # Order Priority
    print("Loading order_priority_dim...")
    conn, cursor = execute_batch_safe(conn, cursor,
        "INSERT INTO order_priority_dim (order_priority) VALUES (%s) ON CONFLICT (order_priority) DO NOTHING",
        [(s,) for s in df["order_priority"].dropna().unique()], progress_label="order_priority_dim")

    save_progress("dims_done", 0, 0)
    phase, sales_start, ship_start = "dims_done", 0, 0

# ---------------------------------------------------------------------------
# Build lookup maps for fast ID retrieval during fact loading
# ---------------------------------------------------------------------------
print("Building lookup maps...")
cursor.execute("SELECT date, date_id FROM time_dim")
date_map = dict(cursor.fetchall())

cursor.execute("SELECT c.customer_name, s.segment, c.customer_id FROM customer_dim c JOIN segment_dim s ON c.segment_id = s.segment_id")
cust_map = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

cursor.execute("SELECT st.state, m.market, r.region, c.country, st.state_id FROM state_dim st JOIN market_dim m ON st.market_id = m.market_id JOIN region_dim r ON m.region_id = r.region_id JOIN country_dim c ON r.country_id = c.country_id")
state_map = {(r[3], r[2], r[1], r[0]): r[4] for r in cursor.fetchall()}

cursor.execute("SELECT ship_mode, ship_mode_id FROM ship_mode_dim")
sm_map = dict(cursor.fetchall())

cursor.execute("SELECT order_priority, order_priority_id FROM order_priority_dim")
op_map = dict(cursor.fetchall())

# ---------------------------------------------------------------------------
# Load fact_sales table
# ---------------------------------------------------------------------------
if phase in ("dims_done",):
    print("Loading fact_sales...")
    BATCH_SIZE = 500
    batch = []
    total = len(df)

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        if i <= sales_start:
            continue
        if pd.isna(row["order_date"]):
            print_progress("fact_sales", i, total)
            continue

        # Get foreign keys using maps
        order_date_id = date_map.get(row["order_date"].date())
        customer_id = cust_map.get((row["customer_name"], row["segment"]))
        state_id = state_map.get((row["country"], row["region"], row["market"], row["state"]))

        if not all([order_date_id, customer_id, state_id]):
            print_progress("fact_sales", i, total)
            continue

        batch.append((order_date_id, customer_id, row["product_id"], state_id,
                      row["sales"], row["quantity"], row["discount"], row["profit"]))

        if len(batch) >= BATCH_SIZE:
            for attempt in range(5):
                try:
                    psycopg2.extras.execute_batch(cursor,
                        "INSERT INTO fact_sales (order_date_id, customer_id, product_id, state_id, sales, quantity, discount, profit) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        batch)
                    conn.commit()
                    break
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    print(f"\nReconnecting (attempt {attempt+1})...")
                    time.sleep(5)
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SET search_path TO snowflake;")
            else:
                raise RuntimeError("Failed to insert fact_sales batch after 5 attempts.")
            save_progress("dims_done", i, 0)
            batch = []

        print_progress("fact_sales", i, total)

    if batch:
        psycopg2.extras.execute_batch(cursor,
            "INSERT INTO fact_sales (order_date_id, customer_id, product_id, state_id, sales, quantity, discount, profit) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            batch)
        conn.commit()

    print_progress("fact_sales", total, total)
    save_progress("sales_done", total, 0)
    phase, ship_start = "sales_done", 0

# ---------------------------------------------------------------------------
# Load fact_shipping table
# ---------------------------------------------------------------------------
if phase in ("sales_done",):
    print("Loading fact_shipping...")
    BATCH_SIZE = 500
    batch = []
    total = len(df)

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        if i <= ship_start:
            continue

        ship_date_val = row["ship_date"] if pd.notna(row["ship_date"]) else row["order_date"]
        if pd.isna(ship_date_val):
            print_progress("fact_shipping", i, total)
            continue

        # Get foreign keys
        ship_date_id = date_map.get(ship_date_val.date())
        state_id = state_map.get((row["country"], row["region"], row["market"], row["state"]))
        sm_id = sm_map.get(row["ship_mode"])
        op_id = op_map.get(row["order_priority"])

        if not all([ship_date_id, state_id, sm_id, op_id]):
            print_progress("fact_shipping", i, total)
            continue

        batch.append((ship_date_id, row["product_id"], state_id, sm_id, op_id, row["shipping_cost"]))

        if len(batch) >= BATCH_SIZE:
            for attempt in range(5):
                try:
                    psycopg2.extras.execute_batch(cursor,
                        "INSERT INTO fact_shipping (ship_date_id, product_id, state_id, ship_mode_id, order_priority_id, shipping_cost) VALUES (%s, %s, %s, %s, %s, %s)",
                        batch)
                    conn.commit()
                    break
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    print(f"\nReconnecting (attempt {attempt+1})...")
                    time.sleep(5)
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SET search_path TO snowflake;")
            else:
                raise RuntimeError("Failed to insert fact_shipping batch after 5 attempts.")
            save_progress("sales_done", total, i)
            batch = []

        print_progress("fact_shipping", i, total)

    if batch:
        psycopg2.extras.execute_batch(cursor,
            "INSERT INTO fact_shipping (ship_date_id, product_id, state_id, ship_mode_id, order_priority_id, shipping_cost) VALUES (%s, %s, %s, %s, %s, %s)",
            batch)
        conn.commit()

    print_progress("fact_shipping", total, total)

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
conn.commit()
cursor.close()
conn.close()

if os.path.exists(PROGRESS_FILE):
    os.remove(PROGRESS_FILE)

print("\nMission Accomplished for Snowflake Schema!")