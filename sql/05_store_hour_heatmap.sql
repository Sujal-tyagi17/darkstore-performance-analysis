-- Late % by store and hour of day (for the heatmap); hours with < 30 orders are suppressed
SELECT store_id,
       order_hour,
       count(*)                            AS orders,
       round(100 * avg(is_late::INT), 1)   AS late_pct,
       round(avg(rider_utilization), 2)    AS avg_rider_utilization
FROM fact_orders
WHERE valid_timing
GROUP BY 1, 2
HAVING count(*) >= 30
ORDER BY 1, 2;
