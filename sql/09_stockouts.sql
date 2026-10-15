-- Stockouts: items customers asked for that the store could not supply.
-- Lost revenue = value of the unfulfilled lines.
SELECT i.store_id, i.city_code, i.sku_id, p.product_name, p.category,
       count(*)                                                     AS times_requested,
       sum((NOT i.fulfilled)::INT)                                  AS times_unavailable,
       round(100 * avg((NOT i.fulfilled)::INT), 1)                  AS stockout_pct,
       round(coalesce(sum(i.line_value) FILTER (WHERE NOT i.fulfilled), 0), 0) AS lost_revenue_inr
FROM fact_order_items i
JOIN dim_product p USING (sku_id)
GROUP BY ALL
HAVING sum((NOT i.fulfilled)::INT) > 0
ORDER BY lost_revenue_inr DESC, i.store_id, i.sku_id;
