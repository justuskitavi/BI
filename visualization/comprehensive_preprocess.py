import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import LinearRegression
from sklearn.cluster import KMeans

# 1. LOAD DATA
# The dataset has thousands separators (commas) in the 'sales' column and extra spaces in headers/values
df = pd.read_csv("data/SuperStoreOrders.csv", thousands=',', skipinitialspace=True)
# Clean column names to remove whitespace
df.columns = df.columns.str.strip()

print("--- I. DATA CLEANING ---")

# --- 1a. Handling Missing Data ---
# Strategy: Impute missing Profit with Median
print(f"Missing values before: {df['profit'].isnull().sum()}")
df['profit'] = df['profit'].fillna(df['profit'].median())
print(f"Missing values after: {df['profit'].isnull().sum()}")

# --- 1b. Handling Noisy Data ---

# i. Binning (Smoothing by Bin Means)
# Sort sales and put into 10 bins
df = df.sort_values('sales')
df['sales_bin'] = pd.qcut(df['sales'], q=10, labels=False)
# Smooth: Replace each value with the mean of its bin
bin_means = df.groupby('sales_bin')['sales'].mean()
df['sales_smoothed_binning'] = df['sales_bin'].map(bin_means)

# ii. Regression (Smoothing by Linear Regression)
# Fit a line to Sales vs Profit to "smooth" the relationship
X = df[['sales']].values
y = df['profit'].values
model = LinearRegression().fit(X, y)
df['profit_smoothed_regression'] = model.predict(X)

# iii. Clustering (Outlier Detection)
# Use KMeans to find clusters. Data points far from centers are 'noise'
kmeans = KMeans(n_clusters=3, n_init=10).fit(df[['sales', 'profit']])
df['cluster_label'] = kmeans.labels_


print("\n--- II. TRANSFORMATION ---")

# Method 1: Normalization (Min-Max Scaling)
scaler = MinMaxScaler()
df['sales_normalized'] = scaler.fit_transform(df[['sales']])

# Method 2: Attribute Construction (Extract Month from Order Date)
df['order_date'] = pd.to_datetime(df['order_date'], dayfirst=True, errors='coerce')
df['order_month'] = df['order_date'].dt.month

# Method 3: Discretization (Concept Hierarchy Generation)
# Convert continuous quantity into 'Low', 'Medium', 'High'
df['quantity_group'] = pd.cut(df['quantity'], bins=[0, 5, 10, 100], labels=['Low', 'Medium', 'High'])


print("\n--- III. DATA REDUCTION ---")

# Method 1: Dimensionality Reduction (Removing irrelevant columns)
df_dim_reduced = df.drop(columns=['order_id', 'customer_name', 'product_name'])

# Method 2: Numerosity Reduction (Random Sampling 5%)
df_sampled = df.sample(frac=0.05, random_state=42)

# Method 3: Aggregation (Roll-up to Regional Totals)
df_agg = df.groupby('region')[['sales', 'profit']].sum().reset_index()

print(f"Original Row Count: {len(df)}")
print(f"Sampled Row Count: {len(df_sampled)}")
print(f"Reduced Columns: {df_dim_reduced.columns.tolist()[:5]}...")
print("\n--- SAMPLE OUTPUT (TRANSFORMED DATA) ---")
print(df[['sales', 'sales_smoothed_binning', 'sales_normalized', 'quantity_group']].head())
