-- One row per city: scale, speed, reliability and customer experience
WITH c AS (
    SELECT
        o.city_code,
        d.city_name,
        count(DISTINCT o.store_id)                                        AS stores,
        count(*)                                                          AS orders,
        round(count(*) / count(DISTINCT o.order_date), 0)                 AS orders_per_day,
        count(DISTINCT o.customer_id)                                     AS customers,
        round(sum(order_value) FILTER (WHERE is_delivered), 0)            AS gmv_inr,
        round(avg(order_value) FILTER (WHERE is_delivered), 1)            AS aov_inr,
        round(avg(delivery_min) FILTER (WHERE valid_timing), 2)           AS avg_delivery_min,
        round(quantile_cont(delivery_min, 0.9) FILTER (WHERE valid_timing), 2) AS p90_delivery_min,
        round(100 * avg(is_late::INT) FILTER (WHERE valid_timing), 1)     AS late_pct,
        round(100 * avg((status = 'Cancelled')::INT), 2)                  AS cancel_pct,
        round(100 * avg(has_missing_items::INT) FILTER (WHERE is_delivered), 1) AS missing_items_pct,
        round(avg(rating), 2)                                             AS avg_rating,
        round(avg(distance_km), 2)                                        AS avg_distance_km,
        round(100 * avg((distance_km > 3.5)::INT), 1)                     AS far_orders_pct,
        round(avg(travel_min) FILTER (WHERE valid_timing), 2)             AS avg_travel_min,
        round(avg(rider_wait_min) FILTER (WHERE valid_timing), 2)         AS avg_rider_wait_min,
        round(avg(pick_min) FILTER (WHERE valid_timing), 2)               AS avg_pick_min
    FROM fact_orders o
    JOIN dim_city d USING (city_code)
    GROUP BY 1, 2
)
SELECT *, rank() OVER (ORDER BY late_pct) AS reliability_rank
FROM c
ORDER BY late_pct;
