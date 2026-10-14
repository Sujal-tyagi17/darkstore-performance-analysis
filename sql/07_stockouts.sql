-- Stockouts: items customers asked for that the store could not supply.
-- Lost revenue = value of unfulfilled lines on delivered orders
--              + full basket value of orders cancelled because nothing was available.
WITH lines AS (
    SELECT i.*, p.product_name, p.category
    FROM fact_order_items i
    JOIN dim_product p USING (sku_id)
)
SELECT store_id,
       sku_id,
       product_name,
       category,
       count(*)                                                     AS times_requested,
       sum((NOT fulfilled)::INT)                                    AS times_unavailable,
       round(100 * avg((NOT fulfilled)::INT), 1)                    AS stockout_pct,
       round(sum(line_value) FILTER (WHERE NOT fulfilled), 0)       AS lost_revenue_inr
FROM lines
GROUP BY 1, 2, 3, 4
HAVING sum((NOT fulfilled)::INT) > 0
ORDER BY lost_revenue_inr DESC;
