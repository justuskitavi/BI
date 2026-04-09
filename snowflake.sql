SET search_path TO snowflake;

#DRILL DOWN
-- Year-level
SELECT
  EXTRACT(YEAR FROM t.date) AS year,
  SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN time_dim t ON f.order_date_id = t.date_id
GROUP BY EXTRACT(YEAR FROM t.date)
ORDER BY year;

-- Drill down to month
SELECT
  EXTRACT(YEAR FROM t.date)  AS year,
  EXTRACT(MONTH FROM t.date) AS month,
  SUM(f.sales)  AS total_sales
FROM fact_sales f
JOIN time_dim t ON f.order_date_id = t.date_id
GROUP BY EXTRACT(YEAR FROM t.date), EXTRACT(MONTH FROM t.date)
ORDER BY year, month;

-- Category level
SELECT
  c.category,
  SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN product_dim      p  ON f.product_id      = p.product_id
JOIN sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
JOIN category_dim     c  ON sc.category_id    = c.category_id
GROUP BY c.category
ORDER BY total_sales DESC;

-- Drill down: Category + Sub-category
SELECT
  c.category,
  sc.sub_category,
  SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN product_dim      p  ON f.product_id      = p.product_id
JOIN sub_category_dim sc ON p.sub_category_id = sc.sub_category_id
JOIN category_dim     c  ON sc.category_id    = c.category_id
GROUP BY c.category, sc.sub_category
ORDER BY c.category, total_sales DESC;

#SLICE
SELECT
  EXTRACT(YEAR FROM t.date) AS year,
  SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN time_dim     t  ON f.order_date_id = t.date_id
JOIN customer_dim cd ON f.customer_id   = cd.customer_id
JOIN segment_dim  s  ON cd.segment_id   = s.segment_id
WHERE s.segment = 'Consumer'
GROUP BY EXTRACT(YEAR FROM t.date)
ORDER BY year;

SELECT
  c.country,
  r.region,
  SUM(fs.shipping_cost) AS total_shipping_cost
FROM fact_shipping fs
JOIN state_dim       st ON fs.state_id      = st.state_id
JOIN market_dim      m  ON st.market_id     = m.market_id
JOIN region_dim      r  ON m.region_id      = r.region_id
JOIN country_dim     c  ON r.country_id     = c.country_id
JOIN ship_mode_dim   sm ON fs.ship_mode_id  = sm.ship_mode_id
WHERE sm.ship_mode = 'Same Day'
GROUP BY c.country, r.region
ORDER BY total_shipping_cost DESC;

#DICE
SELECT
  EXTRACT(YEAR FROM t.date) AS year,
  ctry.country,
  cat.category,
  s.segment,
  SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN time_dim       t     ON f.order_date_id = t.date_id
JOIN customer_dim   cd    ON f.customer_id   = cd.customer_id
JOIN segment_dim    s     ON cd.segment_id   = s.segment_id
JOIN product_dim    p     ON f.product_id    = p.product_id
JOIN sub_category_dim sc  ON p.sub_category_id = sc.sub_category_id
JOIN category_dim   cat   ON sc.category_id  = cat.category_id
JOIN state_dim      st    ON f.state_id      = st.state_id
JOIN market_dim     m     ON st.market_id    = m.market_id
JOIN region_dim     r     ON m.region_id     = r.region_id
JOIN country_dim    ctry  ON r.country_id    = ctry.country_id
WHERE s.segment     = 'Consumer'
  AND cat.category  = 'Technology'
  AND ctry.country  = 'United States'
  AND EXTRACT(YEAR FROM t.date) BETWEEN 2014 AND 2016
GROUP BY
  EXTRACT(YEAR FROM t.date),
  ctry.country,
  cat.category,
  s.segment
ORDER BY year;

#PIVOT
SELECT
  EXTRACT(YEAR FROM t.date) AS year,
  ctry.country,
  cat.category,
  s.segment,
  SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN time_dim       t     ON f.order_date_id = t.date_id
JOIN customer_dim   cd    ON f.customer_id   = cd.customer_id
JOIN segment_dim    s     ON cd.segment_id   = s.segment_id
JOIN product_dim    p     ON f.product_id    = p.product_id
JOIN sub_category_dim sc  ON p.sub_category_id = sc.sub_category_id
JOIN category_dim   cat   ON sc.category_id  = cat.category_id
JOIN state_dim      st    ON f.state_id      = st.state_id
JOIN market_dim     m     ON st.market_id    = m.market_id
JOIN region_dim     r     ON m.region_id     = r.region_id
JOIN country_dim    ctry  ON r.country_id    = ctry.country_id
WHERE s.segment     = 'Consumer'
  AND cat.category  = 'Technology'
  AND ctry.country  = 'United States'
  AND EXTRACT(YEAR FROM t.date) BETWEEN 2014 AND 2016
GROUP BY
  EXTRACT(YEAR FROM t.date),
  ctry.country,
  cat.category,
  s.segment
ORDER BY year;

SELECT
  r.region,
  SUM(CASE WHEN sm.ship_mode = 'First Class' THEN fs.shipping_cost ELSE 0 END) AS first_class_cost,
  SUM(CASE WHEN sm.ship_mode = 'Second Class' THEN fs.shipping_cost ELSE 0 END) AS second_class_cost,
  SUM(CASE WHEN sm.ship_mode = 'Standard Class' THEN fs.shipping_cost ELSE 0 END) AS standard_class_cost,
  SUM(CASE WHEN sm.ship_mode = 'Same Day' THEN fs.shipping_cost ELSE 0 END) AS same_day_cost
FROM fact_shipping fs
JOIN state_dim     st ON fs.state_id      = st.state_id
JOIN market_dim    m  ON st.market_id     = m.market_id
JOIN region_dim    r  ON m.region_id      = r.region_id
JOIN ship_mode_dim sm ON fs.ship_mode_id  = sm.ship_mode_id
GROUP BY r.region
ORDER BY r.region;