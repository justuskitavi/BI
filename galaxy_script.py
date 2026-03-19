import pandas as pd
import mysql.connector

# ---------------------------------------------------------------------------
# 1. Read and prepare CSV
# ---------------------------------------------------------------------------
CSV_PATH = r"C:\Users\Admin\Downloads\SuperStoreOrders - SuperStoreOrders.csv"

df = pd.read_csv(CSV_PATH)

# Normalize column names to lowercase with underscores
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

df["order_date"] = pd.to_datetime(df["order_date"], dayfirst=True, errors="coerce")
if "ship_date" in df.columns:
    df["ship_date"] = pd.to_datetime(df["ship_date"], dayfirst=True, errors="coerce")

# Clean numeric columns
for col in ["sales", "quantity", "discount", "profit", "shipping_cost"]:
    if col in df.columns:
        df[col] = (
            df[col].astype(str).str.replace(",", "", regex=False).str.strip()
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

# ---------------------------------------------------------------------------
# 2. Connect to database
# ---------------------------------------------------------------------------
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Jaulsetxus2005.",
    database="galaxyschema",
)
cursor = conn.cursor()


print("Mission initialised!")


# ---------------------------------------------------------------------------
# 3. Create dimension tables (same as star schema)
# ---------------------------------------------------------------------------
print("Creating dimension tables...")

cursor.execute("""
CREATE TABLE time_dim (
    date_id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL UNIQUE
)
""")

cursor.execute("""
CREATE TABLE customer_dim (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(100),
    segment VARCHAR(50)
)
""")

cursor.execute("""
CREATE TABLE product_dim (
    product_id VARCHAR(100) PRIMARY KEY,
    product_name VARCHAR(500),
    category VARCHAR(50),
    sub_category VARCHAR(50)
)
""")

cursor.execute("""
CREATE TABLE location_dim (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    country VARCHAR(50),
    state VARCHAR(50),
    market VARCHAR(50),
    region VARCHAR(50)
)
""")

cursor.execute("""
CREATE TABLE shipping_dim (
    ship_mode_id INT AUTO_INCREMENT PRIMARY KEY,
    ship_mode VARCHAR(50),
    order_priority VARCHAR(50)
)
""")

# 4. Create fact tables ( two facts sharing dims)
# fact_sales: time_dim, product_dim, customer_dim, location_dim
cursor.execute("""
CREATE TABLE fact_sales (
    fact_sales_id INT AUTO_INCREMENT PRIMARY KEY,
    date_id INT,
    customer_id INT,
    product_id VARCHAR(100),
    location_id INT,
    sales DECIMAL(10,2),
    quantity INT,
    discount DECIMAL(10,4),
    profit DECIMAL(10,5),
    FOREIGN KEY (date_id) REFERENCES time_dim(date_id),
    FOREIGN KEY (customer_id) REFERENCES customer_dim(customer_id),
    FOREIGN KEY (product_id) REFERENCES product_dim(product_id),
    FOREIGN KEY (location_id) REFERENCES location_dim(location_id)
)
""")

# fact_shipping: product_dim, shipping_dim, location_dim (+ optional ship_date for analysis)
cursor.execute("""
CREATE TABLE fact_shipping (
    fact_shipping_id INT AUTO_INCREMENT PRIMARY KEY,
    date_id INT,
    product_id VARCHAR(100),
    location_id INT,
    ship_mode_id INT,
    shipping_cost DECIMAL(10,3),
    FOREIGN KEY (date_id) REFERENCES time_dim(date_id),
    FOREIGN KEY (product_id) REFERENCES product_dim(product_id),
    FOREIGN KEY (location_id) REFERENCES location_dim(location_id),
    FOREIGN KEY (ship_mode_id) REFERENCES shipping_dim(ship_mode_id)
)
""")

# 5. Load time_dim
print("Loading time_dim...")
all_dates = set()
for _, row in df.iterrows():
    if pd.notna(row.get("order_date")):
        try:
            all_dates.add(row["order_date"].date())
        except Exception:
            pass
    if pd.notna(row.get("ship_date")):
        try:
            all_dates.add(row["ship_date"].date())
        except Exception:
            pass

for d in sorted(all_dates):
    cursor.execute("INSERT INTO time_dim (date) VALUES (%s)", (d,))

# 6. Load customer_dim
print("Loading customer_dim...")
customers = set()
for _, row in df.iterrows():
    customers.add((row["customer_name"], row["segment"]))

for customer_name, segment in customers:
    cursor.execute(
        "INSERT INTO customer_dim (customer_name, segment) VALUES (%s, %s)",
        (customer_name, segment),
    )

# 7. Load product_dim
print("Loading product_dim...")
products = {}
for _, row in df.iterrows():
    product_id = str(row["product_id"]) if pd.notna(row.get("product_id")) else ""
    if not product_id or product_id in products:
        continue
    product_name = str(row.get("product_name", "") or "")
    category = str(row.get("category", "") or "")
    sub_category = str(row.get("sub_category", row.get("sub-category", "")) or "")
    products[product_id] = (product_name, category, sub_category)

for product_id, (product_name, category, sub_category) in products.items():
    cursor.execute(
        """INSERT INTO product_dim (product_id, product_name, category, sub_category)
           VALUES (%s, %s, %s, %s)""",
        (product_id, product_name, category, sub_category),
    )

# 8. Load location_dim
print("Loading location_dim...")
locations = set()
for _, row in df.iterrows():
    locations.add((row["country"], row["state"], row["market"], row["region"]))

for country, state, market, region in locations:
    cursor.execute(
        """INSERT INTO location_dim (country, state, market, region)
           VALUES (%s, %s, %s, %s)""",
        (country, state, market, region),
    )

# 9. Load shipping_dim
print("Loading shipping_dim...")
shipping = set()
for _, row in df.iterrows():
    shipping.add((row["ship_mode"], row["order_priority"]))

for ship_mode, order_priority in shipping:
    cursor.execute(
        "INSERT INTO shipping_dim (ship_mode, order_priority) VALUES (%s, %s)",
        (ship_mode, order_priority),
    )

# 10. Load fact_sales (time_dim, product_dim, customer_dim, location_dim)
print("Loading fact_sales...")
for _, row in df.iterrows():
    if pd.isna(row.get("order_date")):
        continue
    try:
        order_date = row["order_date"].date()
    except Exception:
        continue

    cursor.execute("SELECT date_id FROM time_dim WHERE date = %s", (order_date,))
    date_row = cursor.fetchone()
    if not date_row:
        continue
    date_id = date_row[0]

    cursor.execute(
        """SELECT customer_id FROM customer_dim
           WHERE customer_name = %s AND segment = %s""",
        (row["customer_name"], row["segment"]),
    )
    cust_row = cursor.fetchone()
    if not cust_row:
        continue
    customer_id = cust_row[0]

    product_id = row["product_id"]

    cursor.execute(
        """SELECT location_id FROM location_dim
           WHERE country = %s AND state = %s AND market = %s AND region = %s""",
        (row["country"], row["state"], row["market"], row["region"]),
    )
    loc_row = cursor.fetchone()
    if not loc_row:
        continue
    location_id = loc_row[0]

    sales = row.get("sales") if pd.notna(row.get("sales")) else None
    quantity = int(row["quantity"]) if pd.notna(row.get("quantity")) else None
    discount = row.get("discount") if pd.notna(row.get("discount")) else None
    profit = row.get("profit") if pd.notna(row.get("profit")) else None

    cursor.execute(
        """INSERT INTO fact_sales (date_id, customer_id, product_id, location_id,
               sales, quantity, discount, profit)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (date_id, customer_id, product_id, location_id, sales, quantity, discount, profit),
    )

# 11. Load fact_shipping (time_dim/ship_date, product_dim, location_dim, shipping_dim)
print("Loading fact_shipping...")
for _, row in df.iterrows():
    # Use ship_date for fact_shipping; fall back to order_date if missing
    ship_date_val = row.get("ship_date") if pd.notna(row.get("ship_date")) else row.get("order_date")
    if pd.isna(ship_date_val):
        continue
    try:
        ship_date = ship_date_val.date()
    except Exception:
        continue

    cursor.execute("SELECT date_id FROM time_dim WHERE date = %s", (ship_date,))
    date_row = cursor.fetchone()
    if not date_row:
        continue
    date_id = date_row[0]

    product_id = row["product_id"]

    cursor.execute(
        """SELECT location_id FROM location_dim
           WHERE country = %s AND state = %s AND market = %s AND region = %s""",
        (row["country"], row["state"], row["market"], row["region"]),
    )
    loc_row = cursor.fetchone()
    if not loc_row:
        continue
    location_id = loc_row[0]

    cursor.execute(
        """SELECT ship_mode_id FROM shipping_dim
           WHERE ship_mode = %s AND order_priority = %s""",
        (row["ship_mode"], row["order_priority"]),
    )
    ship_row = cursor.fetchone()
    if not ship_row:
        continue
    ship_mode_id = ship_row[0]

    shipping_cost = row.get("shipping_cost") if pd.notna(row.get("shipping_cost")) else None

    cursor.execute(
        """INSERT INTO fact_shipping (date_id, product_id, location_id, ship_mode_id, shipping_cost)
           VALUES (%s, %s, %s, %s, %s)""",
        (date_id, product_id, location_id, ship_mode_id, shipping_cost),
    )


conn.commit()
cursor.close()
conn.close()

print("Mission Accomplished!")
