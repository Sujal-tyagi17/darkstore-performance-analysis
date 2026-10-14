-- Weekly trend per store: catches sudden changes (e.g. a store losing riders)
SELECT store_id,
       date_trunc('week', order_date)                   AS week_start,
       count(*)                                         AS orders,
       round(100 * avg(is_late::INT), 1)                AS late_pct,
       round(avg(delivery_min), 2)                      AS avg_delivery_min,
       round(avg(rider_wait_min), 2)                    AS avg_rider_wait_min,
       round(avg(riders_on_shift), 2)                   AS avg_riders_on_shift
FROM fact_orders
WHERE valid_timing
GROUP BY 1, 2
ORDER BY 1, 2;
