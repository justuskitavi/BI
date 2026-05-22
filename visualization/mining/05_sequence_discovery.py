from __future__ import annotations

from collections import Counter
from itertools import tee

import pandas as pd

from bi_common import load_orders, write_table


def pairwise(iterable):
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def run_sequences(level: str = "sub_category"):
    df = load_orders().sort_values(["customer_name", "order_date", "order_id"])
    order_sequences = (
        df.groupby(["customer_name", "order_id", "order_date"])[level]
        .apply(lambda s: tuple(sorted(set(s))))
        .reset_index()
        .sort_values(["customer_name", "order_date", "order_id"])
    )

    transition_counter = Counter()
    three_step_counter = Counter()

    for _, group in order_sequences.groupby("customer_name"):
        sequence = []
        for basket in group[level]:
            if len(basket) == 1:
                sequence.append(basket[0])
            else:
                sequence.append(" + ".join(basket[:3]))

        for a, b in pairwise(sequence):
            transition_counter[(a, b)] += 1
        for i in range(len(sequence) - 2):
            three_step_counter[(sequence[i], sequence[i + 1], sequence[i + 2])] += 1

    transitions = pd.DataFrame(
        [
            {"from": a, "to": b, "times_seen": count}
            for (a, b), count in transition_counter.items()
        ]
    )
    if not transitions.empty:
        totals = transitions.groupby("from")["times_seen"].transform("sum")
        transitions["probability_next"] = (transitions["times_seen"] / totals).round(4)
        transitions = transitions.sort_values(["times_seen", "probability_next"], ascending=False)

    three_steps = pd.DataFrame(
        [
            {"step_1": a, "step_2": b, "step_3": c, "times_seen": count}
            for (a, b, c), count in three_step_counter.items()
        ]
    ).sort_values("times_seen", ascending=False)

    write_table(transitions.head(200), "sequence_discovery_customer_next_purchase_transitions.csv")
    write_table(three_steps.head(100), "sequence_discovery_three_order_patterns.csv")
    return transitions, three_steps


if __name__ == "__main__":
    transitions, three_steps = run_sequences()
    print("Most common next-purchase transitions by customer order history:")
    print(transitions.head(15).to_string(index=False))
    print("\nMost common three-order sequences:")
    print(three_steps.head(10).to_string(index=False))
