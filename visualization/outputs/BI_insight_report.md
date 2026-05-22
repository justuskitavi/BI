# SuperStore BI Mining Insight Report

This report is generated from the Python scripts in `scripts/`. It summarizes the main analytical evidence for each BI concept.

## A) Pattern Mining

Exact product mining finds very specific co-purchases. Because exact product names are sparse, the strongest lifts often have low support, which is realistic for retail baskets.

| item_a | item_b | orders_together | support | confidence_a_to_b | lift |
| --- | --- | --- | --- | --- | --- |
| Bevis Conference Table, Fully Assembled | Hon Conference Table, with Bottom Storage | 2 | 0.00016 | 0.4 | 2554.2 |
| Boston 16765 Mini Stand Up Battery Pencil Sharpener | Microsoft Natural Ergonomic Keyboard 4000 | 2 | 0.00016 | 0.6667 | 1702.8 |
| Eldon Expressions Punched Metal & Wood Desk Accessories, Black & Cherry | GBC DocuBind TL300 Electric Binding System | 2 | 0.00016 | 1.0 | 1596.375 |
| Anker Astro Mini 3000mAh Ultra-Compact Portable Charger | Bretford CR8500 Series Meeting Room Furniture | 2 | 0.00016 | 0.6667 | 1419.0 |
| Acco Side-Punched Conventional Columnar Pads | Avery Fluorescent Highlighter Four-Color Set | 2 | 0.00016 | 0.5 | 1277.1 |

At sub-category level the patterns are easier to explain to business users:

| item_a | item_b | orders_together | support | confidence_a_to_b | lift |
| --- | --- | --- | --- | --- | --- |
| Copiers | Labels | 243 | 0.01986 | 0.1531 | 1.047 |
| Appliances | Paper | 253 | 0.02068 | 0.1981 | 1.037 |
| Art | Storage | 833 | 0.06808 | 0.2698 | 1.022 |
| Bookcases | Copiers | 218 | 0.01782 | 0.1273 | 0.981 |
| Art | Machines | 267 | 0.02182 | 0.0865 | 0.98 |
| Labels | Machines | 154 | 0.01259 | 0.086 | 0.975 |
| Chairs | Supplies | 309 | 0.02526 | 0.1359 | 0.971 |
| Appliances | Binders | 391 | 0.03196 | 0.3062 | 0.97 |

## B) Predictive Analysis

The predictive script trains a ridge regression model to estimate order profit using sales, quantity, discounts, shipping, category mix, market, region, segment, and priority.

| metric | value |
| --- | --- |
| test_orders | 5007.0 |
| rmse_profit | 209.23 |
| mae_profit | 103.02 |
| r2 | 0.4039 |
| profitability_accuracy | 0.8736 |

## C) Cluster Formation

Customers are grouped using recency, frequency, monetary value, profit, discounts, market breadth, and category breadth.

| cluster | customers | avg_recency_days | avg_orders | total_sales | total_profit | business_label |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 253 | 21.767 | 34.522 | 5417996 | 769847.594 | Loyal active high-frequency customers |
| 1 | 211 | 27.863 | 27.227 | 2419521 | 362246.385 | Loyal active high-frequency customers |
| 2 | 264 | 19.614 | 35.027 | 3860274 | 402440.784 | Loyal active high-frequency customers |
| 3 | 67 | 30.06 | 30.254 | 945114 | -65499.942 | Loss-making / discount-sensitive customers |

## D) Rules Mining

Rules are mined as interpretable if-then business policies. High lift means the condition is much more associated with the decision than the baseline.

| if_condition | then_decision | support_rows | confidence | lift_vs_baseline | profit |
| --- | --- | --- | --- | --- | --- |
| sub_category = Furnishings AND discount_band = High discount | Review pricing/discounts | 356 | 1.0 | 4.089 | -17953.32 |
| sub_category = Phones AND discount_band = High discount | Review pricing/discounts | 305 | 1.0 | 4.089 | -61102.13 |
| sub_category = Chairs AND discount_band = High discount | Review pricing/discounts | 281 | 1.0 | 4.089 | -48509.53 |
| sub_category = Bookcases AND discount_band = High discount | Review pricing/discounts | 265 | 1.0 | 4.089 | -60362.7 |
| sub_category = Machines AND discount_band = High discount | Review pricing/discounts | 260 | 1.0 | 4.089 | -60065.36 |
| sub_category = Appliances AND discount_band = High discount | Review pricing/discounts | 220 | 1.0 | 4.089 | -50740.64 |
| sub_category = Binders AND discount_band = High discount | Review pricing/discounts | 1234 | 0.9984 | 4.083 | -49854.35 |
| category = Furniture AND discount_band = High discount | Review pricing/discounts | 1123 | 0.9982 | 4.082 | -221178.39 |
| sub_category = Tables AND discount_band = High discount | Review pricing/discounts | 221 | 0.991 | 4.052 | -94352.84 |
| sub_category = Art AND discount_band = High discount | Review pricing/discounts | 664 | 0.9895 | 4.046 | -18068.65 |

## E) Sequence Discovery

The sequence script treats each customer's order history as a journey and estimates what tends to follow next.

| from | to | times_seen | probability_next |
| --- | --- | --- | --- |
| Binders | Binders | 101 | 0.0642 |
| Art | Binders | 97 | 0.0723 |
| Binders | Art | 94 | 0.0598 |
| Storage | Storage | 84 | 0.0624 |
| Storage | Binders | 75 | 0.0557 |
| Art | Art | 71 | 0.0529 |
| Binders | Storage | 70 | 0.0445 |
| Binders | Paper | 69 | 0.0439 |
| Art | Storage | 68 | 0.0507 |
| Storage | Art | 68 | 0.0505 |

## F) Time Series Analysis

The time-series script creates monthly sales/profit trends, seasonality, moving averages, exponential smoothing, and a six-month sales forecast.

| forecast_month | forecast_sales | method |
| --- | --- | --- |
| 2015-01-01 | 349892.96 | linear trend x month seasonality blended with exponential smoothing |
| 2015-02-01 | 323616.73 | linear trend x month seasonality blended with exponential smoothing |
| 2015-03-01 | 374913.15 | linear trend x month seasonality blended with exponential smoothing |
| 2015-04-01 | 361318.41 | linear trend x month seasonality blended with exponential smoothing |
| 2015-05-01 | 409691.61 | linear trend x month seasonality blended with exponential smoothing |
| 2015-06-01 | 495870.78 | linear trend x month seasonality blended with exponential smoothing |

## How to Explain the Whole Project

Pattern mining and rules mining explain relationships in existing transactions. Predictive analysis estimates a future business outcome. Clustering creates customer segments for differentiated action. Sequence discovery adds order of behavior, showing customer journeys. Time series analysis adds time, trend, seasonality, and forecasting.
