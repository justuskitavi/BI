import os
import sys
import pandas as pd
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def print_progress(label, index, total, bar_length=30):
    if total <= 0:
        return
    filled = int(bar_length * index / total)
    bar = "=" * filled + " " * (bar_length - filled)
    percent = 100 * index / total
    sys.stdout.write(f"\r{label}: [{bar}] {index}/{total} ({percent:5.1f}%)")
    sys.stdout.flush()
    if index >= total:
        sys.stdout.write("\n")


# Progress tracking
progress_file = os.path.join(os.path.dirname(__file__), "galaxy_progress.txt")
if os.path.exists(progress_file):
    with open(progress_file) as f:
        start_index = int(f.read().strip())
    print(f"Resuming from row {start_index}")
else:
    start_index = 0
CSV_PATH = "data/SuperStoreOrders.csv"

df = pd.read_csv(CSV_PATH, skipinitialspace=True)

# Normalize column names to lowercase with underscores
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

df["order_date"] = pd.to_datetime(df["order_date"], dayfirst=True, errors="coerce")
df["ship_date"] = pd.to_datetime(df["ship_date"], dayfirst=True, errors="coerce")

# Clean numeric columns
for col in ["sales", "quantity", "discount", "profit", "shipping_cost"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")

# ---------------------------------------------------------------------------
# 2. Connect to database
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DB_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# ---------------------------------------------------------------------------
# 3. Setup Schema and Create tables
# ---------------------------------------------------------------------------
print("Setting up 'galaxy' schema and tables...")
cursor.execute("CREATE SCHEMA IF NOT EXISTS galaxy;")
cursor.execute("SET search_path TO galaxy;")

# Drop tables if they exist
cursor.execute("DROP TABLE IF EXISTS fact_shipping CASCADE;")
cursor.execute("DROP TABLE IF EXISTS fact_sales CASCADE;")
cursor.execute("DROP TABLE IF EXISTS time_dim CASCADE;")
cursor.execute("DROP TABLE IF EXISTS customer_dim CASCADE;")
cursor.execute("DROP TABLE IF EXISTS product_dim CASCADE;")
cursor.execute("DROP TABLE IF EXISTS location_dim CASCADE;")
cursor.execute("DROP TABLE IF EXISTS shipping_dim CASCADE;")

cursor.execute("CREATE TABLE time_dim (date_id SERIAL PRIMARY KEY, date DATE NOT NULL UNIQUE)")
cursor.execute("CREATE TABLE customer_dim (customer_id SERIAL PRIMARY KEY, customer_name VARCHAR(255), segment VARCHAR(100))")
cursor.execute("CREATE TABLE product_dim (product_id VARCHAR(100) PRIMARY KEY, product_name VARCHAR(500), category VARCHAR(100), sub_category VARCHAR(100))")
cursor.execute("CREATE TABLE location_dim (location_id SERIAL PRIMARY KEY, country VARCHAR(100), state VARCHAR(100), market VARCHAR(100), region VARCHAR(100))")
cursor.execute("CREATE TABLE shipping_dim (ship_mode_id SERIAL PRIMARY KEY, ship_mode VARCHAR(100), order_priority VARCHAR(100))")

cursor.execute("""
CREATE TABLE fact_sales (
    fact_sales_id SERIAL PRIMARY KEY,
    date_id INT REFERENCES time_dim(date_id),
    customer_id INT REFERENCES customer_dim(customer_id),
    product_id VARCHAR(100) REFERENCES product_dim(product_id),
    location_id INT REFERENCES location_dim(location_id),
    sales DECIMAL(15,2),
    quantity INT,
    discount DECIMAL(15,4),
    profit DECIMAL(15,5)
)
""")

cursor.execute("""
CREATE TABLE fact_shipping (
    fact_shipping_id SERIAL PRIMARY KEY,
    date_id INT REFERENCES time_dim(date_id),
    product_id VARCHAR(100) REFERENCES product_dim(product_id),
    location_id INT REFERENCES location_dim(location_id),
    ship_mode_id INT REFERENCES shipping_dim(ship_mode_id),
    shipping_cost DECIMAL(15,3)
)
""")

# ---------------------------------------------------------------------------
# 4. Load dimensions (using efficient mapping)
# ---------------------------------------------------------------------------
print("Loading time_dim...")
all_dates = pd.concat([df['order_date'], df['ship_date']]).dropna().unique()
for i, d in enumerate(sorted(all_dates), start=1):
    cursor.execute("INSERT INTO time_dim (date) VALUES (%s) ON CONFLICT (date) DO NOTHING", (pd.Timestamp(d).date(),))
    print_progress("time_dim", i, len(all_dates))
cursor.execute("SELECT date, date_id FROM time_dim")
date_map = dict(cursor.fetchall())

print("Loading customer_dim...")
customers = df[['customer_name', 'segment']].drop_duplicates()
for i, (_, row) in enumerate(customers.iterrows(), start=1):
    cursor.execute("INSERT INTO customer_dim (customer_name, segment) VALUES (%s, %s)", (row['customer_name'], row['segment']))
    print_progress("customer_dim", i, len(customers))
cursor.execute("SELECT customer_name, segment, customer_id FROM customer_dim")
cust_map = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

print("Loading product_dim...")
products = df[['product_id', 'product_name', 'category', 'sub_category']].drop_duplicates('product_id')
for i, (_, row) in enumerate(products.iterrows(), start=1):
    cursor.execute("INSERT INTO product_dim (product_id, product_name, category, sub_category) VALUES (%s, %s, %s, %s) ON CONFLICT (product_id) DO NOTHING", (row['product_id'], row['product_name'], row['category'], row['sub_category']))
    print_progress("product_dim", i, len(products))

print("Loading location_dim...")
locations = df[['country', 'state', 'market', 'region']].drop_duplicates()
for i, (_, row) in enumerate(locations.iterrows(), start=1):
    cursor.execute("INSERT INTO location_dim (country, state, market, region) VALUES (%s, %s, %s, %s)", (row['country'], row['state'], row['market'], row['region']))
    print_progress("location_dim", i, len(locations))
cursor.execute("SELECT country, state, market, region, location_id FROM location_dim")
loc_map = {(r[0], r[1], r[2], r[3]): r[4] for r in cursor.fetchall()}

print("Loading shipping_dim...")
shipping = df[['ship_mode', 'order_priority']].drop_duplicates()
for i, (_, row) in enumerate(shipping.iterrows(), start=1):
    cursor.execute("INSERT INTO shipping_dim (ship_mode, order_priority) VALUES (%s, %s)", (row['ship_mode'], row['order_priority']))
    print_progress("shipping_dim", i, len(shipping))
cursor.execute("SELECT ship_mode, order_priority, ship_mode_id FROM shipping_dim")
ship_map = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

# ---------------------------------------------------------------------------
# 5. Load fact tables
# ---------------------------------------------------------------------------
print("Loading fact_sales...")
for i, (_, row) in enumerate(df.iterrows(), start=1):
    if i <= start_index:
        continue
    
    if pd.isna(row['order_date']):
        print_progress("fact_sales", i, len(df))
        continue
    d_id = date_map.get(row['order_date'].date())
    c_id = cust_map.get((row['customer_name'], row['segment']))
    l_id = loc_map.get((row['country'], row['state'], row['market'], row['region']))
    if all([d_id, c_id, l_id]):
        cursor.execute("INSERT INTO fact_sales (date_id, customer_id, product_id, location_id, sales, quantity, discount, profit) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (d_id, c_id, row['product_id'], l_id, row['sales'], row['quantity'], row['discount'], row['profit']))
    print_progress("fact_sales", i, len(df))
    
    if i % 1000 == 0:
        conn.commit()
        with open(progress_file, 'w') as f:
            f.write(str(i))

print("Loading fact_shipping...")
for i, (_, row) in enumerate(df.iterrows(), start=1):
    s_date = row['ship_date'] if pd.notna(row['ship_date']) else row['order_date']
    if pd.isna(s_date):
        print_progress("fact_shipping", i, len(df))
        continue
    d_id = date_map.get(s_date.date())
    l_id = loc_map.get((row['country'], row['state'], row['market'], row['region']))
    sm_id = ship_map.get((row['ship_mode'], row['order_priority']))
    if all([d_id, l_id, sm_id]):
        cursor.execute("INSERT INTO fact_shipping (date_id, product_id, location_id, ship_mode_id, shipping_cost) VALUES (%s, %s, %s, %s, %s)", (d_id, row['product_id'], l_id, sm_id, row['shipping_cost']))
    print_progress("fact_shipping", i, len(df))
    
    if i % 1000 == 0:
        conn.commit()
        with open(progress_file, 'w') as f:
            f.write(str(i))

conn.commit()
cursor.close()
conn.close()

# Remove progress file on success
if os.path.exists(progress_file):
    os.remove(progress_file)

print("Mission Accomplished for Galaxy Schema!")

