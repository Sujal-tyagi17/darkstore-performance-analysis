-- Late-delivery rate across the main operational drivers
WITH base AS (
    SELECT *,
           CASE WHEN order_hour BETWEEN 6 AND 10 THEN '1. Morning (6-11)'
                WHEN order_hour BETWEEN 11 AND 16 THEN '2. Afternoon (11-17)'
                WHEN order_hour BETWEEN 17 AND 21 THEN '3. Evening peak (17-22)'
                ELSE '4. Late night (22-6)' END                          AS day_part,
           CASE WHEN rider_utilization < 0.6 THEN '1. <60%'
                WHEN rider_utilization < 0.9 THEN '2. 60-90%'
                WHEN rider_utilization < 1.2 THEN '3. 90-120%'
                ELSE '4. >120%' END                                      AS utilization_band
    FROM fact_orders
    WHERE valid_timing
)
SELECT 'Distance' AS driver, distance_band AS level, count(*) AS orders,
       round(100 * avg(is_late::INT), 1) AS late_pct, round(avg(delivery_min), 2) AS avg_delivery_min
FROM base GROUP BY 1, 2
UNION ALL
SELECT 'Weather', weather, count(*), round(100 * avg(is_late::INT), 1), round(avg(delivery_min), 2)
FROM base GROUP BY 1, 2
UNION ALL
SELECT 'Time of day', day_part, count(*), round(100 * avg(is_late::INT), 1), round(avg(delivery_min), 2)
FROM base GROUP BY 1, 2
UNION ALL
SELECT 'Rider utilisation', utilization_band, count(*), round(100 * avg(is_late::INT), 1), round(avg(delivery_min), 2)
FROM base GROUP BY 1, 2
ORDER BY driver, level;
