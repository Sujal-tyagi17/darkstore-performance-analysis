-- Weekly trend per city plus India: shows city-wide events (monsoon, fog, heatwaves)
SELECT coalesce(city_code, 'IN')                        AS city_code,
       date_trunc('week', order_date)                   AS week_start,
       count(*)                                         AS orders,
       round(100 * avg(is_late::INT), 1)                AS late_pct,
       round(avg(delivery_min), 2)                      AS avg_delivery_min,
       round(100 * avg((weather IN ('Rain', 'Heavy Rain'))::INT), 1) AS rain_orders_pct,
       round(100 * avg((weather = 'Heatwave')::INT), 1) AS heatwave_orders_pct,
       round(100 * avg((weather = 'Fog')::INT), 1)      AS fog_orders_pct
FROM fact_orders
WHERE valid_timing
GROUP BY GROUPING SETS ((city_code, date_trunc('week', order_date)), (date_trunc('week', order_date)))
HAVING count(DISTINCT order_date) = 7
ORDER BY 1, 2;
