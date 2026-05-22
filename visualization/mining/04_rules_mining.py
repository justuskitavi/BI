from __future__ import annotations

import pandas as pd

from bi_common import load_orders, write_table


def run_rules():
    df = load_orders()
    df["outcome"] = df["is_loss"].map({True: "LOSS", False: "PROFIT"})
    overall_loss_rate = df["is_loss"].mean()
    dimensions = [
        ["category"],
        ["sub_category"],
        ["market"],
        ["region"],
        ["discount_band"],
        ["category", "discount_band"],
        ["sub_category", "discount_band"],
        ["market", "category"],
        ["ship_mode", "order_priority"],
    ]

    rules = []
    total = len(df)
    for dims in dimensions:
        grouped = df.groupby(dims, observed=False).agg(
            rows=("order_id", "size"),
            orders=("order_id", "nunique"),
            sales=("sales", "sum"),
            profit=("profit", "sum"),
            loss_rate=("is_loss", "mean"),
            avg_discount=("discount", "mean"),
            avg_margin=("profit_margin", "mean"),
        ).reset_index()

        for _, row in grouped.iterrows():
            if row["rows"] < 50:
                continue
            condition = " AND ".join(f"{dim} = {row[dim]}" for dim in dims)
            decision = "Review pricing/discounts" if row["loss_rate"] > overall_loss_rate * 1.35 else "Good candidate to promote"
            confidence = row["loss_rate"] if decision.startswith("Review") else 1 - row["loss_rate"]
            lift = row["loss_rate"] / overall_loss_rate if decision.startswith("Review") else (1 - row["loss_rate"]) / (1 - overall_loss_rate)
            rules.append(
                {
                    "if_condition": condition,
                    "then_decision": decision,
                    "support_rows": int(row["rows"]),
                    "support_pct": round(row["rows"] / total, 4),
                    "confidence": round(float(confidence), 4),
                    "lift_vs_baseline": round(float(lift), 3),
                    "sales": round(float(row["sales"]), 2),
                    "profit": round(float(row["profit"]), 2),
                    "avg_discount": round(float(row["avg_discount"]), 3),
                    "avg_margin": round(float(row["avg_margin"]), 3),
                }
            )

    rules_df = pd.DataFrame(rules).sort_values(["lift_vs_baseline", "support_rows"], ascending=False)
    write_table(rules_df.head(150), "rules_mining_business_decision_rules.csv")
    return rules_df, overall_loss_rate


if __name__ == "__main__":
    rules, baseline = run_rules()
    print(f"Baseline line-item loss rate: {baseline:.2%}")
    print("\nTop mined decision rules:")
    print(rules.head(15).to_string(index=False))
