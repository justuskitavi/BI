from __future__ import annotations

import numpy as np
import pandas as pd

from bi_common import load_orders, write_table, zscore


def kmeans(x: np.ndarray, k: int = 4, max_iter: int = 100, seed: int = 42):
    rng = np.random.default_rng(seed)
    centers = x[rng.choice(len(x), size=k, replace=False)]
    labels = np.zeros(len(x), dtype=int)

    for _ in range(max_iter):
        distances = ((x[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_labels = distances.argmin(axis=1)
        if np.array_equal(labels, new_labels):
            break
        labels = new_labels
        for i in range(k):
            if np.any(labels == i):
                centers[i] = x[labels == i].mean(axis=0)
    return labels, centers


def run_clustering():
    df = load_orders()
    max_date = df["order_date"].max()
    customers = df.groupby("customer_name").agg(
        last_order=("order_date", "max"),
        first_order=("order_date", "min"),
        orders=("order_id", "nunique"),
        sales=("sales", "sum"),
        profit=("profit", "sum"),
        quantity=("quantity", "sum"),
        avg_discount=("discount", "mean"),
        markets=("market", "nunique"),
        categories=("category", "nunique"),
    )
    customers["recency_days"] = (max_date - customers["last_order"]).dt.days
    customers["profit_margin"] = np.where(customers["sales"] > 0, customers["profit"] / customers["sales"], 0.0)
    customers["avg_order_value"] = customers["sales"] / customers["orders"]

    cluster_features = [
        "recency_days",
        "orders",
        "sales",
        "profit",
        "quantity",
        "avg_discount",
        "markets",
        "categories",
        "profit_margin",
        "avg_order_value",
    ]
    model = customers[cluster_features].copy()
    for col in ["orders", "sales", "profit", "quantity", "avg_order_value"]:
        model[col] = np.sign(model[col]) * np.log1p(np.abs(model[col]))
    scaled = zscore(model).fillna(0)
    labels, _ = kmeans(scaled.to_numpy(float), k=4)
    customers["cluster"] = labels

    summary = customers.groupby("cluster").agg(
        customers=("orders", "size"),
        avg_recency_days=("recency_days", "mean"),
        avg_orders=("orders", "mean"),
        total_sales=("sales", "sum"),
        total_profit=("profit", "sum"),
        avg_profit_margin=("profit_margin", "mean"),
        avg_discount=("avg_discount", "mean"),
        avg_order_value=("avg_order_value", "mean"),
    ).reset_index()

    summary["business_label"] = summary.apply(label_cluster, axis=1)
    customers = customers.reset_index().merge(summary[["cluster", "business_label"]], on="cluster", how="left")

    customers_out = customers.copy()
    numeric_cols = customers_out.select_dtypes(include=np.number).columns
    customers_out[numeric_cols] = customers_out[numeric_cols].round(3)
    write_table(summary.round(3), "cluster_formation_customer_cluster_summary.csv")
    write_table(customers_out, "cluster_formation_customer_clusters.csv")
    return summary, customers


def label_cluster(row: pd.Series) -> str:
    if row["avg_profit_margin"] < 0:
        return "Loss-making / discount-sensitive customers"
    if row["avg_orders"] >= 8 and row["avg_recency_days"] <= 180:
        return "Loyal active high-frequency customers"
    if row["avg_order_value"] >= 800:
        return "High-value occasional customers"
    return "Standard customers with growth potential"


if __name__ == "__main__":
    summary, _ = run_clustering()
    print("Customer clusters from RFM, profitability, discount, and breadth features:")
    print(summary.to_string(index=False))
