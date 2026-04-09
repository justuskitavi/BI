SET search_path TO star;

#1. What is the overal profit margin
SELECT
    (SUM(profit) / SUM(sales)) * 100 AS profit_margin_percentage
FROM fact_table;

#2. Product categories with the highest sales
SELECT 
    p.category,
    SUM(f.sales) AS total_sales
FROM fact_table f
JOIN product_dim p ON f.product_id = p.product_id
GROUP BY p.category
ORDER BY total_sales DESC;

#3.Which product categories are the most profitable
SELECT 
    p.sub_category,
    SUM(f.profit) AS total_profit
FROM fact_table f
JOIN product_dim p ON f.product_id = p.product_id
GROUP BY p.sub_category
ORDER BY total_profit DESC;

#4. Regions with the highest sales
SELECT 
    l.region,
    SUM(f.sales) AS total_sales
FROM fact_table f
JOIN location_dim l ON f.location_id = l.location_id
GROUP BY l.region
ORDER BY total_sales DESC;

#5. Which customer segment produces the most revenue
SELECT 
    c.segment,
    SUM(f.sales) AS total_sales
FROM fact_table f
JOIN customer_dim c ON f.customer_id = c.customer_id
GROUP BY c.segment
ORDER BY total_sales DESC;

#6. Top 10 products by sales
SELECT 
    p.product_name,
    SUM(f.sales) AS total_sales
FROM fact_table f
JOIN product_dim p ON f.product_id = p.product_id
GROUP BY p.product_name
ORDER BY total_sales DESC
LIMIT 10;

#7. Sales changes over time
SELECT 
    EXTRACT(YEAR FROM t.date) AS year,
    SUM(f.sales) AS total_sales
FROM fact_table f
JOIN time_dim t ON f.date_id = t.date_id
GROUP BY EXTRACT(YEAR FROM t.date)
ORDER BY year;