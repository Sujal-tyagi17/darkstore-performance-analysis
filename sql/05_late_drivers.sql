-- Late-delivery rate across the main operational drivers, for India ('IN') and each city
WITH base AS (
    SELECT *,
           CASE WHEN order_hour BETWEEN 6 AND 10 THEN '1. Morning (6-11)'
                WHEN order_hour BETWEEN 11 AND 16 THEN '2. Afternoon (11-17)'
                WHEN order_hour BETWEEN 17 AND 21 THEN '3. Evening peak (17-22)'
                ELSE '4. Late night (22-6)' END                          AS day_part,
           CASE WHEN rider_utilization < 0.6 THEN '1. <60%'
                WHEN rider_utilization < 0.9 THEN '2. 60-90%'
                WHEN rider_utilization < 1.2 THEN '3. 90-120%'
                ELSE '4. >120%' END                                      AS utilization_band,
           CASE weather WHEN 'Clear' THEN '1. Clear' WHEN 'Cloudy' THEN '2. Cloudy'
                        WHEN 'Fog' THEN '3. Fog' WHEN 'Heatwave' THEN '4. Heatwave'
                        WHEN 'Rain' THEN '5. Rain' ELSE '6. Heavy Rain' END AS weather_level
    FROM fact_orders
    WHERE valid_timing
),
long AS (
    SELECT city_code, 'Distance' AS driver, distance_band AS level, is_late, delivery_min FROM base
    UNION ALL SELECT city_code, 'Weather', weather_level, is_late, delivery_min FROM base
    UNION ALL SELECT city_code, 'Time of day', day_part, is_late, delivery_min FROM base
    UNION ALL SELECT city_code, 'Rider utilisation', utilization_band, is_late, delivery_min FROM base
)
SELECT coalesce(city_code, 'IN')            AS city_code,
       driver, level,
       count(*)                             AS orders,
       round(100 * avg(is_late::INT), 1)    AS late_pct,
       round(avg(delivery_min), 2)          AS avg_delivery_min
FROM long
GROUP BY GROUPING SETS ((city_code, driver, level), (driver, level))
ORDER BY city_code, driver, level;
