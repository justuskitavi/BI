import pandas as pd
import mysql.connector

# ---------------------------------------------------------------------------
# 1. Read and prepare CSV
# ---------------------------------------------------------------------------
CSV_PATH = r"C:\Users\Admin\Downloads\SuperStoreOrders - SuperStoreOrders.csv"

df = pd.read_csv(CSV_PATH)

# Normalize column names to lowercase with underscores (e.g., "Order Date" -> order_date)
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

df["order_date"] = pd.to_datetime(df["order_date"], dayfirst=True, errors="coerce")
if "ship_date" in df.columns:
    df["ship_date"] = pd.to_datetime(df["ship_date"], dayfirst=True, errors="coerce")

# Clean numeric columns (remove commas, coerce to numeric)
for col in ["sales", "quantity", "discount", "profit", "shipping_cost"]:
    if col in df.columns:
        df[col] = df[col].astype(str).str.replace(",", "", regex=False).str.strip()
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ---------------------------------------------------------------------------
# 2. Connect to database
# ---------------------------------------------------------------------------
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Jaulsetxus2005.",
    database="snowflake",
)
cursor = conn.cursor()

# ---------------------------------------------------------------------------
# 3. Drop existing tables (facts first, then dimensions)
# ---------------------------------------------------------------------------
print("Dropping existing tables...")
cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
cursor.execute("DROP TABLE IF EXISTS fact_shipping")
cursor.execute("DROP TABLE IF EXISTS fact_sales")

cursor.execute("DROP TABLE IF EXISTS state_dim")
cursor.execute("DROP TABLE IF EXISTS market_dim")
cursor.execute("DROP TABLE IF EXISTS region_dim")
cursor.execute("DROP TABLE IF EXISTS country_dim")

cursor.execute("DROP TABLE IF EXISTS product_dim")
cursor.execute("DROP TABLE IF EXISTS sub_category_dim")
cursor.execute("DROP TABLE IF EXISTS category_dim")

cursor.execute("DROP TABLE IF EXISTS customer_dim")
cursor.execute("DROP TABLE IF EXISTS segment_dim")

cursor.execute("DROP TABLE IF EXISTS ship_mode_dim")
cursor.execute("DROP TABLE IF EXISTS order_priority_dim")

cursor.execute("DROP TABLE IF EXISTS time_dim")
cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

# ---------------------------------------------------------------------------
# 4. Create dimension and fact tables (snowflake)
# ---------------------------------------------------------------------------
print("Creating tables...")

# Time
cursor.execute(
    """
CREATE TABLE time_dim (
    date_id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL UNIQUE
)
"""
)

# Segment / Customer
cursor.execute(
    """
CREATE TABLE segment_dim (
    segment_id INT AUTO_INCREMENT PRIMARY KEY,
    segment VARCHAR(50) NOT NULL UNIQUE
)
"""
)

cursor.execute(
    """
CREATE TABLE customer_dim (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    segment_id INT NOT NULL,
    UNIQUE (customer_name, segment_id),
    FOREIGN KEY (segment_id) REFERENCES segment_dim(segment_id)
)
"""
)

# Product hierarchy
cursor.execute(
    """
CREATE TABLE category_dim (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50) NOT NULL UNIQUE
)
"""
)

cursor.execute(
    """
CREATE TABLE sub_category_dim (
    sub_category_id INT AUTO_INCREMENT PRIMARY KEY,
    sub_category VARCHAR(50) NOT NULL,
    category_id INT NOT NULL,
    UNIQUE (sub_category, category_id),
    FOREIGN KEY (category_id) REFERENCES category_dim(category_id)
)
"""
)

cursor.execute(
    """
CREATE TABLE product_dim (
    product_id VARCHAR(100) PRIMARY KEY,
    product_name VARCHAR(500),
    sub_category_id INT NOT NULL,
    FOREIGN KEY (sub_category_id) REFERENCES sub_category_dim(sub_category_id)
)
"""
)

# Location hierarchy: Country -> Region -> Market -> State
cursor.execute(
    """
CREATE TABLE country_dim (
    country_id INT AUTO_INCREMENT PRIMARY KEY,
    country VARCHAR(50) NOT NULL UNIQUE
)
"""
)

cursor.execute(
    """
CREATE TABLE region_dim (
    region_id INT AUTO_INCREMENT PRIMARY KEY,
    region VARCHAR(50) NOT NULL,
    country_id INT NOT NULL,
    UNIQUE (region, country_id),
    FOREIGN KEY (country_id) REFERENCES country_dim(country_id)
)
"""
)

cursor.execute(
    """
CREATE TABLE market_dim (
    market_id INT AUTO_INCREMENT PRIMARY KEY,
    market VARCHAR(50) NOT NULL,
    region_id INT NOT NULL,
    UNIQUE (market, region_id),
    FOREIGN KEY (region_id) REFERENCES region_dim(region_id)
)
"""
)

cursor.execute(
    """
CREATE TABLE state_dim (
    state_id INT AUTO_INCREMENT PRIMARY KEY,
    state VARCHAR(50) NOT NULL,
    market_id INT NOT NULL,
    UNIQUE (state, market_id),
    FOREIGN KEY (market_id) REFERENCES market_dim(market_id)
)
"""
)

# Shipping-related dimensions
cursor.execute(
    """
CREATE TABLE ship_mode_dim (
    ship_mode_id INT AUTO_INCREMENT PRIMARY KEY,
    ship_mode VARCHAR(50) NOT NULL UNIQUE
)
"""
)

cursor.execute(
    """
CREATE TABLE order_priority_dim (
    order_priority_id INT AUTO_INCREMENT PRIMARY KEY,
    order_priority VARCHAR(50) NOT NULL UNIQUE
)
"""
)

# Fact tables
cursor.execute(
    """
CREATE TABLE fact_sales (
    fact_sales_id INT AUTO_INCREMENT PRIMARY KEY,
    order_date_id INT NOT NULL,
    customer_id INT NOT NULL,
    product_id VARCHAR(100) NOT NULL,
    state_id INT NOT NULL,
    sales DECIMAL(10,2),
    quantity INT,
    discount DECIMAL(10,4),
    profit DECIMAL(10,5),
    FOREIGN KEY (order_date_id) REFERENCES time_dim(date_id),
    FOREIGN KEY (customer_id) REFERENCES customer_dim(customer_id),
    FOREIGN KEY (product_id) REFERENCES product_dim(product_id),
    FOREIGN KEY (state_id) REFERENCES state_dim(state_id)
)
"""
)

cursor.execute(
    """
CREATE TABLE fact_shipping (
    fact_shipping_id INT AUTO_INCREMENT PRIMARY KEY,
    ship_date_id INT NOT NULL,
    product_id VARCHAR(100) NOT NULL,
    state_id INT NOT NULL,
    ship_mode_id INT NOT NULL,
    order_priority_id INT NOT NULL,
    shipping_cost DECIMAL(10,3),
    FOREIGN KEY (ship_date_id) REFERENCES time_dim(date_id),
    FOREIGN KEY (product_id) REFERENCES product_dim(product_id),
    FOREIGN KEY (state_id) REFERENCES state_dim(state_id),
    FOREIGN KEY (ship_mode_id) REFERENCES ship_mode_dim(ship_mode_id),
    FOREIGN KEY (order_priority_id) REFERENCES order_priority_dim(order_priority_id)
)
"""
)

# ---------------------------------------------------------------------------
# 5. Load dimensions
# ---------------------------------------------------------------------------

print("Loading time_dim...")
date_values = set()
for _, row in df.iterrows():
    if pd.notna(row.get("order_date")):
        try:
            date_values.add(row["order_date"].date())
        except Exception:
            pass
    if pd.notna(row.get("ship_date")):
        try:
            date_values.add(row["ship_date"].date())
        except Exception:
            pass

for d in sorted(date_values):
    cursor.execute("INSERT INTO time_dim (date) VALUES (%s)", (d,))

cursor.execute("SELECT date_id, date FROM time_dim")
date_lookup = {row[1]: row[0] for row in cursor.fetchall()}

# Segment and customer
print("Loading segment_dim...")
segments = sorted(set(df["segment"].dropna()))
for seg in segments:
    cursor.execute("INSERT INTO segment_dim (segment) VALUES (%s)", (seg,))

cursor.execute("SELECT segment_id, segment FROM segment_dim")
segment_lookup = {row[1]: row[0] for row in cursor.fetchall()}

print("Loading customer_dim...")
customers = set()
for _, row in df.iterrows():
    customers.add((row["customer_name"], row["segment"]))

customer_lookup = {}
for customer_name, segment in customers:
    seg_id = segment_lookup.get(segment)
    if seg_id is None:
        continue
    cursor.execute(
        """
        INSERT INTO customer_dim (customer_name, segment_id)
        VALUES (%s, %s)
        """,
        (customer_name, seg_id),
    )
    customer_id = cursor.lastrowid
    customer_lookup[(customer_name, segment)] = customer_id

# Product hierarchy
print("Loading product hierarchy...")
categories = sorted(set(df["category"].dropna()))
for cat in categories:
    cursor.execute("INSERT INTO category_dim (category) VALUES (%s)", (cat,))

cursor.execute("SELECT category_id, category FROM category_dim")
category_lookup = {row[1]: row[0] for row in cursor.fetchall()}

subcats = set()
for _, row in df.iterrows():
    subcats.add((row["sub_category"], row["category"]))

for sub_category, category in subcats:
    cat_id = category_lookup.get(category)
    if cat_id is None:
        continue
    cursor.execute(
        """
        INSERT INTO sub_category_dim (sub_category, category_id)
        VALUES (%s, %s)
        """,
        (sub_category, cat_id),
    )

cursor.execute(
    """
    SELECT sc.sub_category_id, sc.sub_category, c.category
    FROM sub_category_dim sc
    JOIN category_dim c ON sc.category_id = c.category_id
    """
)
subcat_lookup = {(row[1], row[2]): row[0] for row in cursor.fetchall()}

print("Loading product_dim...")
products = {}
for _, row in df.iterrows():
    prod_id = str(row["product_id"]) if pd.notna(row.get("product_id")) else ""
    if not prod_id or prod_id in products:
        continue
    prod_name = str(row.get("product_name", "") or "")
    category = row["category"]
    sub_category = row["sub_category"]
    sub_id = subcat_lookup.get((sub_category, category))
    if sub_id is None:
        continue
    products[prod_id] = (prod_name, sub_id)

for prod_id, (prod_name, sub_id) in products.items():
    cursor.execute(
        """
        INSERT INTO product_dim (product_id, product_name, sub_category_id)
        VALUES (%s, %s, %s)
        """,
        (prod_id, prod_name, sub_id),
    )

# Location hierarchy
print("Loading location hierarchy...")
countries = sorted(set(df["country"].dropna()))
for country in countries:
    cursor.execute("INSERT INTO country_dim (country) VALUES (%s)", (country,))

cursor.execute("SELECT country_id, country FROM country_dim")
country_lookup = {row[1]: row[0] for row in cursor.fetchall()}

regions = set()
for _, row in df.iterrows():
    regions.add((row["region"], row["country"]))

for region, country in regions:
    country_id = country_lookup.get(country)
    if country_id is None:
        continue
    cursor.execute(
        """
        INSERT INTO region_dim (region, country_id)
        VALUES (%s, %s)
        """,
        (region, country_id),
    )

cursor.execute(
    """
    SELECT r.region_id, r.region, c.country
    FROM region_dim r
    JOIN country_dim c ON r.country_id = c.country_id
    """
)
region_lookup = {(row[1], row[2]): row[0] for row in cursor.fetchall()}

markets = set()
for _, row in df.iterrows():
    markets.add((row["market"], row["region"], row["country"]))

for market, region, country in markets:
    region_id = region_lookup.get((region, country))
    if region_id is None:
        continue
    cursor.execute(
        """
        INSERT INTO market_dim (market, region_id)
        VALUES (%s, %s)
        """,
        (market, region_id),
    )

cursor.execute(
    """
    SELECT m.market_id, m.market, r.region, c.country
    FROM market_dim m
    JOIN region_dim r ON m.region_id = r.region_id
    JOIN country_dim c ON r.country_id = c.country_id
    """
)
market_lookup = {(row[1], row[2], row[3]): row[0] for row in cursor.fetchall()}

states = set()
for _, row in df.iterrows():
    states.add((row["state"], row["market"], row["region"], row["country"]))

state_lookup = {}
for state, market, region, country in states:
    market_id = market_lookup.get((market, region, country))
    if market_id is None:
        continue
    cursor.execute(
        """
        INSERT INTO state_dim (state, market_id)
        VALUES (%s, %s)
        """,
        (state, market_id),
    )
    state_id = cursor.lastrowid
    state_lookup[(country, region, market, state)] = state_id

# Shipping-related dims
print("Loading ship_mode_dim and order_priority_dim...")
ship_modes = sorted(set(df["ship_mode"].dropna()))
for mode in ship_modes:
    cursor.execute("INSERT INTO ship_mode_dim (ship_mode) VALUES (%s)", (mode,))

cursor.execute("SELECT ship_mode_id, ship_mode FROM ship_mode_dim")
ship_mode_lookup = {row[1]: row[0] for row in cursor.fetchall()}

order_priorities = sorted(set(df["order_priority"].dropna()))
for op in order_priorities:
    cursor.execute(
        "INSERT INTO order_priority_dim (order_priority) VALUES (%s)", (op,)
    )

cursor.execute("SELECT order_priority_id, order_priority FROM order_priority_dim")
order_priority_lookup = {row[1]: row[0] for row in cursor.fetchall()}

# ---------------------------------------------------------------------------
# 6. Load fact tables
# ---------------------------------------------------------------------------

print("Loading fact_sales...")
for _, row in df.iterrows():
    # order_date
    if pd.isna(row.get("order_date")):
        continue
    try:
        order_date = row["order_date"].date()
    except Exception:
        continue
    order_date_id = date_lookup.get(order_date)
    if order_date_id is None:
        continue

    # customer
    cust_key = (row["customer_name"], row["segment"])
    customer_id = customer_lookup.get(cust_key)
    if customer_id is None:
        continue

    # product
    product_id = str(row["product_id"]) if pd.notna(row.get("product_id")) else ""
    if not product_id or product_id not in products:
        continue

    # state (location)
    loc_key = (row["country"], row["region"], row["market"], row["state"])
    state_id = state_lookup.get(loc_key)
    if state_id is None:
        continue

    sales = row.get("sales") if pd.notna(row.get("sales")) else None
    quantity = int(row["quantity"]) if pd.notna(row.get("quantity")) else None
    discount = row.get("discount") if pd.notna(row.get("discount")) else None
    profit = row.get("profit") if pd.notna(row.get("profit")) else None

    cursor.execute(
        """
        INSERT INTO fact_sales (
            order_date_id, customer_id, product_id, state_id,
            sales, quantity, discount, profit
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            order_date_id,
            customer_id,
            product_id,
            state_id,
            sales,
            quantity,
            discount,
            profit,
        ),
    )

print("Loading fact_shipping...")
for _, row in df.iterrows():
    # ship_date (fallback to order_date)
    ship_date_val = (
        row.get("ship_date") if pd.notna(row.get("ship_date")) else row.get("order_date")
    )
    if pd.isna(ship_date_val):
        continue
    try:
        ship_date = ship_date_val.date()
    except Exception:
        continue
    ship_date_id = date_lookup.get(ship_date)
    if ship_date_id is None:
        continue

    # product
    product_id = str(row["product_id"]) if pd.notna(row.get("product_id")) else ""
    if not product_id or product_id not in products:
        continue

    # state (location)
    loc_key = (row["country"], row["region"], row["market"], row["state"])
    state_id = state_lookup.get(loc_key)
    if state_id is None:
        continue

    # ship_mode
    ship_mode_id = ship_mode_lookup.get(row["ship_mode"])
    if ship_mode_id is None:
        continue

    # order_priority
    order_priority_id = order_priority_lookup.get(row["order_priority"])
    if order_priority_id is None:
        continue

    shipping_cost = (
        row.get("shipping_cost") if pd.notna(row.get("shipping_cost")) else None
    )

    cursor.execute(
        """
        INSERT INTO fact_shipping (
            ship_date_id, product_id, state_id,
            ship_mode_id, order_priority_id, shipping_cost
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            ship_date_id,
            product_id,
            state_id,
            ship_mode_id,
            order_priority_id,
            shipping_cost,
        ),
    )

# ---------------------------------------------------------------------------
# 7. Commit and close
# ---------------------------------------------------------------------------
conn.commit()
cursor.close()
conn.close()

print("Mission Accomplished!")

