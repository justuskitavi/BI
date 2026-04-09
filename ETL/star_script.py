import os
import sys
import time
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

print("Mission initialised, Star schema ETL underway..!")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def get_connection(retries=5, delay=5):
    """Connect with retry logic for flaky networks."""
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


def execute_batch_safe(conn, cursor, sql, data, batch_size=500, progress_label=None,
                       progress_file=None, base_index=0):
    """
    Insert rows in batches. Commits every batch and saves progress.
    Reconnects automatically on connection failure.
    """
    total = len(data)
    for batch_start in range(0, total, batch_size):
        batch = data[batch_start: batch_start + batch_size]
        inserted = False
        for attempt in range(5):
            try:
                psycopg2.extras.execute_batch(cursor, sql, batch, page_size=batch_size)
                conn.commit()
                inserted = True
                break
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                print(f"\nDB error on batch {batch_start}: {e}. Reconnecting...")
                time.sleep(5)
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SET search_path TO star;")
        if not inserted:
            raise RuntimeError(f"Failed to insert batch starting at {batch_start} after 5 attempts.")

        done = min(batch_start + batch_size, total)
        if progress_label:
            print_progress(progress_label, done, total)
        if progress_file:
            with open(progress_file, "w") as f:
                f.write(str(base_index + done))

    return conn, cursor


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "star_progress.txt")

# Progress file stores: phase|row_index
# phases: dims_done, fact_done
def read_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            parts = f.read().strip().split("|")
            phase = parts[0] if len(parts) > 0 else "start"
            row = int(parts[1]) if len(parts) > 1 else 0
            return phase, row
    return "start", 0

def save_progress(phase, row=0):
    with open(PROGRESS_FILE, "w") as f:
        f.write(f"{phase}|{row}")

phase, fact_start_index = read_progress()
resuming = phase != "start"
if resuming:
    print(f"Resuming from phase='{phase}', row={fact_start_index}")

# ---------------------------------------------------------------------------
# Load CSV
# ---------------------------------------------------------------------------
CSV_PATH = "../data/SuperStoreOrders.csv"
df = pd.read_csv(CSV_PATH, skipinitialspace=True)
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
df["order_date"] = pd.to_datetime(df["order_date"], dayfirst=True, errors="coerce")
df["ship_date"] = pd.to_datetime(df["ship_date"], dayfirst=True, errors="coerce")
for col in ["sales", "quantity", "discount", "profit", "shipping_cost"]:
    if col in df.columns:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False).str.strip(),
            errors="coerce"
        )

# ---------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------
conn = get_connection()
cursor = conn.cursor()
cursor.execute("CREATE SCHEMA IF NOT EXISTS star;")
cursor.execute("SET search_path TO star;")
conn.commit()

# ---------------------------------------------------------------------------
# Schema setup (only if starting fresh)
# ---------------------------------------------------------------------------
if not resuming:
    print("Dropping and recreating tables...")
    for tbl in ["fact_table", "time_dim", "customer_dim", "product_dim", "location_dim", "shipping_dim"]:
        cursor.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")

    cursor.execute("CREATE TABLE time_dim (date_id SERIAL PRIMARY KEY, date DATE NOT NULL UNIQUE)")
    cursor.execute("CREATE TABLE customer_dim (customer_id SERIAL PRIMARY KEY, customer_name VARCHAR(255), segment VARCHAR(100))")
    cursor.execute("CREATE TABLE product_dim (product_id VARCHAR(100) PRIMARY KEY, product_name VARCHAR(500), category VARCHAR(100), sub_category VARCHAR(100))")
    cursor.execute("CREATE TABLE location_dim (location_id SERIAL PRIMARY KEY, country VARCHAR(100), state VARCHAR(100), market VARCHAR(100), region VARCHAR(100))")
    cursor.execute("CREATE TABLE shipping_dim (ship_mode_id SERIAL PRIMARY KEY, ship_mode VARCHAR(100), order_priority VARCHAR(100))")
    cursor.execute("""
        CREATE TABLE fact_table (
            fact_id SERIAL PRIMARY KEY,
            date_id INT REFERENCES time_dim(date_id),
            customer_id INT REFERENCES customer_dim(customer_id),
            product_id VARCHAR(100) REFERENCES product_dim(product_id),
            location_id INT REFERENCES location_dim(location_id),
            ship_mode_id INT REFERENCES shipping_dim(ship_mode_id),
            sales DECIMAL(15,2),
            quantity INT,
            discount DECIMAL(15,4),
            profit DECIMAL(15,5),
            shipping_cost DECIMAL(15,3)
        )
    """)
    conn.commit()

# ---------------------------------------------------------------------------
# Load dimensions (skip if already done)
# ---------------------------------------------------------------------------
if phase in ("start",):
    print("Loading time_dim...")
    all_dates = sorted(pd.concat([df["order_date"], df["ship_date"]]).dropna().unique())
    date_rows = [(pd.Timestamp(d).date(),) for d in all_dates]
    conn, cursor = execute_batch_safe(
        conn, cursor,
        "INSERT INTO time_dim (date) VALUES (%s) ON CONFLICT (date) DO NOTHING",
        date_rows, progress_label="time_dim"
    )

    print("Loading customer_dim...")
    customers = df[["customer_name", "segment"]].drop_duplicates().values.tolist()
    conn, cursor = execute_batch_safe(
        conn, cursor,
        "INSERT INTO customer_dim (customer_name, segment) VALUES (%s, %s)",
        customers, progress_label="customer_dim"
    )

    print("Loading product_dim...")
    products = df[["product_id", "product_name", "category", "sub_category"]].drop_duplicates("product_id").values.tolist()
    conn, cursor = execute_batch_safe(
        conn, cursor,
        "INSERT INTO product_dim (product_id, product_name, category, sub_category) VALUES (%s, %s, %s, %s) ON CONFLICT (product_id) DO NOTHING",
        products, progress_label="product_dim"
    )

    print("Loading location_dim...")
    locations = df[["country", "state", "market", "region"]].drop_duplicates().values.tolist()
    conn, cursor = execute_batch_safe(
        conn, cursor,
        "INSERT INTO location_dim (country, state, market, region) VALUES (%s, %s, %s, %s)",
        locations, progress_label="location_dim"
    )

    print("Loading shipping_dim...")
    shipping = df[["ship_mode", "order_priority"]].drop_duplicates().values.tolist()
    conn, cursor = execute_batch_safe(
        conn, cursor,
        "INSERT INTO shipping_dim (ship_mode, order_priority) VALUES (%s, %s)",
        shipping, progress_label="shipping_dim"
    )

    save_progress("dims_done", 0)
    phase = "dims_done"
    fact_start_index = 0

# ---------------------------------------------------------------------------
# Build lookup maps
# ---------------------------------------------------------------------------
print("Building lookup maps...")
cursor.execute("SELECT date, date_id FROM time_dim")
date_map = dict(cursor.fetchall())

cursor.execute("SELECT customer_name, segment, customer_id FROM customer_dim")
cust_map = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

cursor.execute("SELECT country, state, market, region, location_id FROM location_dim")
loc_map = {(r[0], r[1], r[2], r[3]): r[4] for r in cursor.fetchall()}

cursor.execute("SELECT ship_mode, order_priority, ship_mode_id FROM shipping_dim")
ship_map = {(r[0], r[1]): r[2] for r in cursor.fetchall()}

# ---------------------------------------------------------------------------
# Load fact_table in batches
# ---------------------------------------------------------------------------
if phase in ("dims_done",):
    print("Loading fact_table...")
    BATCH_SIZE = 500
    batch = []
    total = len(df)

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        if i <= fact_start_index:
            continue

        if pd.isna(row["order_date"]):
            print_progress("fact_table", i, total)
            continue

        date_id = date_map.get(row["order_date"].date())
        customer_id = cust_map.get((row["customer_name"], row["segment"]))
        location_id = loc_map.get((row["country"], row["state"], row["market"], row["region"]))
        ship_mode_id = ship_map.get((row["ship_mode"], row["order_priority"]))

        if not all([date_id, customer_id, location_id, ship_mode_id]):
            print_progress("fact_table", i, total)
            continue

        batch.append((
            date_id, customer_id, row["product_id"], location_id, ship_mode_id,
            row["sales"], row["quantity"], row["discount"], row["profit"], row["shipping_cost"]
        ))

        if len(batch) >= BATCH_SIZE:
            inserted = False
            for attempt in range(5):
                try:
                    psycopg2.extras.execute_batch(
                        cursor,
                        """INSERT INTO fact_table (date_id, customer_id, product_id, location_id, ship_mode_id,
                               sales, quantity, discount, profit, shipping_cost)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        batch
                    )
                    conn.commit()
                    inserted = True
                    break
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    print(f"\nReconnecting (attempt {attempt+1})...")
                    time.sleep(5)
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SET search_path TO star;")
            if not inserted:
                raise RuntimeError("Failed to insert fact batch after 5 attempts.")
            save_progress("dims_done", i)
            batch = []

        print_progress("fact_table", i, total)

    # Insert remaining rows
    if batch:
        psycopg2.extras.execute_batch(
            cursor,
            """INSERT INTO fact_table (date_id, customer_id, product_id, location_id, ship_mode_id,
                   sales, quantity, discount, profit, shipping_cost)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            batch
        )
        conn.commit()

    print_progress("fact_table", total, total)
    save_progress("fact_done", total)

conn.commit()
cursor.close()
conn.close()

if os.path.exists(PROGRESS_FILE):
    os.remove(PROGRESS_FILE)

print("\nMission Accomplished for Star Schema!")