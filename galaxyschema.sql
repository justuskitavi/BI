SET search_path TO galaxy;

-- 1. What is the total sales, total profit, and overall profit margin of the company?
SELECT 
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit,
    (SUM(profit) / SUM(sales)) * 100 AS profit_margin_percentage
FROM fact_sales;

-- 2. Which product categories generate the highest total sales?
SELECT 
    p.category,
    SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN product_dim p ON f.product_id = p.product_id
GROUP BY p.category
ORDER BY total_sales DESC;

-- 3. Which product sub-categories are the most profitable?
SELECT 
    p.sub_category,
    SUM(f.profit) AS total_profit
FROM fact_sales f
JOIN product_dim p ON f.product_id = p.product_id
GROUP BY p.sub_category
ORDER BY total_profit DESC;

-- 4. Which regions generate the highest sales?
SELECT 
    l.region,
    SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN location_dim l ON f.location_id = l.location_id
GROUP BY l.region
ORDER BY total_sales DESC;

-- 5. Which customer segment generates the most revenue?
SELECT 
    c.segment,
    SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN customer_dim c ON f.customer_id = c.customer_id
GROUP BY c.segment
ORDER BY total_sales DESC;

-- 6. What are the top 10 products by sales?
SELECT 
    p.product_name,
    SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN product_dim p ON f.product_id = p.product_id
GROUP BY p.product_name
ORDER BY total_sales DESC
LIMIT 10;

-- 7. How does sales change over time (yearly trend)?
SELECT 
    EXTRACT(YEAR FROM t.date) AS year,
    SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN time_dim t ON f.date_id = t.date_id
GROUP BY EXTRACT(YEAR FROM t.date)
ORDER BY year;

-- 8. Which shipping mode is used most often?
SELECT 
    s.ship_mode,
    COUNT(*) AS total_orders
FROM fact_shipping f
JOIN shipping_dim s ON f.ship_mode_id = s.ship_mode_id
GROUP BY s.ship_mode
ORDER BY total_orders DESC;

-- 9. What is the average discount given by category?
SELECT 
    p.category,
    AVG(f.discount) AS avg_discount
FROM fact_sales f
JOIN product_dim p ON f.product_id = p.product_id
GROUP BY p.category;

-- 10. Which regions are the most profitable?
SELECT 
    l.region,
    SUM(f.profit) AS total_profit
FROM fact_sales f
JOIN location_dim l ON f.location_id = l.location_id
GROUP BY l.region
ORDER BY total_profit DESC;

-- 11. Which shipping mode results in the highest average shipping cost?
SELECT 
    s.ship_mode,
    AVG(f.shipping_cost) AS avg_shipping_cost
FROM fact_shipping f
JOIN shipping_dim s ON f.ship_mode_id = s.ship_mode_id
GROUP BY s.ship_mode
ORDER BY avg_shipping_cost DESC;

-- 12. Which states generate the most sales?
SELECT 
    l.state,
    SUM(f.sales) AS total_sales
FROM fact_sales f
JOIN location_dim l ON f.location_id = l.location_id
GROUP BY l.state
ORDER BY total_sales DESC
LIMIT 10;

-- 13. Do profitable products also incur high shipping costs?
SELECT 
    p.product_name,
    SUM(fs.profit) AS total_profit,
    SUM(fsh.shipping_cost) AS total_shipping_cost
FROM fact_sales fs
JOIN fact_shipping fsh ON fs.product_id = fsh.product_id
JOIN product_dim p ON fs.product_id = p.product_id
GROUP BY p.product_name
ORDER BY total_profit DESC;