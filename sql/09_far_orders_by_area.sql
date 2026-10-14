-- Which neighbourhoods are badly served? Orders by customer area and serving store.
SELECT c.area,
       o.store_id,
       count(*)                                         AS orders,
       round(avg(o.distance_km), 2)                     AS avg_distance_km,
       round(100 * avg((o.distance_km > 3)::INT), 1)    AS far_orders_pct,
       round(100 * avg(o.is_late::INT), 1)              AS late_pct,
       round(avg(o.delivery_min), 2)                    AS avg_delivery_min,
       round(sum(o.order_value) FILTER (WHERE o.is_delivered), 0) AS gmv_inr,
       round(100.0 * count(*) FILTER (WHERE month(o.order_date) = 6)
             / nullif(count(*) FILTER (WHERE month(o.order_date) = 1), 0) - 100, 1) AS jun_vs_jan_growth_pct
FROM fact_orders o
JOIN dim_customer c USING (customer_id)
GROUP BY 1, 2
ORDER BY avg_distance_km DESC;
