-- Store scorecard: every dark store, compared with its city and with India
WITH s AS (
    SELECT
        o.store_id, d.store_name, d.city_code, d.city_name, d.locality, d.area_sqft,
        count(*)                                                          AS orders,
        round(count(*) / count(DISTINCT o.order_date), 1)                 AS orders_per_day,
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
        round(avg(rider_utilization), 2)                                  AS avg_rider_utilization
    FROM fact_orders o
    JOIN dim_store d USING (store_id)
    GROUP BY ALL
),
city AS (
    SELECT city_code, round(100 * avg(is_late::INT) FILTER (WHERE valid_timing), 1) AS city_late_pct
    FROM fact_orders GROUP BY 1
)
SELECT s.*,
       c.city_late_pct,
       round(s.late_pct - c.city_late_pct, 1)                              AS late_pct_vs_city,
       rank() OVER (PARTITION BY s.city_code ORDER BY s.late_pct)          AS rank_in_city,
       rank() OVER (ORDER BY s.late_pct)                                   AS rank_in_india
FROM s JOIN city c USING (city_code)
ORDER BY s.late_pct DESC, s.store_id;
