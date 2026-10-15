-- Monthly KPIs for every city plus an all-India row (city_code = 'IN')
SELECT
    coalesce(city_code, 'IN')                                             AS city_code,
    date_trunc('month', order_date)                                       AS month,
    count(*)                                                              AS orders,
    count(DISTINCT customer_id)                                           AS active_customers,
    round(sum(order_value) FILTER (WHERE is_delivered), 0)                AS gmv_inr,
    round(avg(order_value) FILTER (WHERE is_delivered), 1)                AS aov_inr,
    round(avg(delivery_min) FILTER (WHERE valid_timing), 2)               AS avg_delivery_min,
    round(quantile_cont(delivery_min, 0.9) FILTER (WHERE valid_timing), 2) AS p90_delivery_min,
    round(100 * avg(is_late::INT) FILTER (WHERE valid_timing), 1)         AS late_pct,
    round(100 * avg((status = 'Cancelled')::INT), 2)                      AS cancel_pct,
    round(100 * avg(has_missing_items::INT) FILTER (WHERE is_delivered), 1) AS missing_items_pct,
    round(avg(rating), 2)                                                 AS avg_rating
FROM fact_orders
GROUP BY GROUPING SETS ((city_code, date_trunc('month', order_date)), (date_trunc('month', order_date)))
ORDER BY city_code, month;
