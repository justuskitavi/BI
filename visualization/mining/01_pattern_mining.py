from __future__ import annotations

from collections import Counter
from itertools import combinations

import pandas as pd

from bi_common import load_orders, order_baskets, write_table


def mine_frequent_itemsets(item_col: str = "product_name", min_support: float = 0.0001):
    df = load_orders()
    baskets = order_baskets(df, item_col=item_col)
    basket_count = len(baskets)
    min_count = max(2, int(basket_count * min_support))

    item_counts = Counter()
    pair_counts = Counter()
    triple_counts = Counter()

    for basket in baskets:
        item_counts.update(basket)
        pair_counts.update(combinations(basket, 2))
        if len(basket) >= 3:
            triple_counts.update(combinations(basket, 3))

    pairs = []
    for (a, b), count in pair_counts.items():
        if count < min_count:
            continue
        support = count / basket_count
        conf_a_b = count / item_counts[a]
        conf_b_a = count / item_counts[b]
        lift = support / ((item_counts[a] / basket_count) * (item_counts[b] / basket_count))
        pairs.append(
            {
                "item_a": a,
                "item_b": b,
                "orders_together": count,
                "support": round(support, 5),
                "confidence_a_to_b": round(conf_a_b, 4),
                "confidence_b_to_a": round(conf_b_a, 4),
                "lift": round(lift, 3),
            }
        )

    triples = [
        {
            "item_1": combo[0],
            "item_2": combo[1],
            "item_3": combo[2],
            "orders_together": count,
            "support": round(count / basket_count, 5),
        }
        for combo, count in triple_counts.items()
        if count >= min_count
    ]

    pair_df = pd.DataFrame(pairs)
    if not pair_df.empty:
        pair_df = pair_df.sort_values(["lift", "orders_together"], ascending=False)

    triple_df = pd.DataFrame(triples)
    if not triple_df.empty:
        triple_df = triple_df.sort_values(["orders_together", "support"], ascending=False)
    write_table(pair_df.head(100), f"pattern_mining_frequent_{item_col}_pairs.csv")
    write_table(triple_df.head(100), f"pattern_mining_frequent_{item_col}_triples.csv")
    return pair_df, triple_df, basket_count


if __name__ == "__main__":
    pairs, triples, baskets = mine_frequent_itemsets()
    print(f"Analyzed {baskets:,} multi-product orders.")
    print("\nTop product pairs by lift:")
    print(pairs.head(10).to_string(index=False))
    print("\nTop product triples by order count:")
    print(triples.head(10).to_string(index=False))

    sub_pairs, _, _ = mine_frequent_itemsets(item_col="sub_category", min_support=0.01)
    print("\nTop sub-category pairs by lift, useful for cleaner business storytelling:")
    print(sub_pairs.head(10).to_string(index=False))
