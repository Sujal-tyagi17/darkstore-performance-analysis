-- Does a bad first order cost us the customer?
-- Cohort: customers who signed up in 2026 and placed their first order by 31 May,
-- so every customer has a full 30-day window to come back.
WITH first_orders AS (
    SELECT o.customer_id, o.city_code, o.order_ts, o.is_late, o.status, o.delivery_min, o.promised_eta_min
    FROM fact_orders o
    JOIN dim_customer c USING (customer_id)
    WHERE o.customer_order_seq = 1
      AND c.signup_date >= DATE '2026-01-01'
      AND o.order_ts < TIMESTAMP '2026-06-01'
),
next30 AS (
    SELECT f.customer_id, count(o.order_id) AS orders_next_30d
    FROM first_orders f
    LEFT JOIN fact_orders o
      ON o.customer_id = f.customer_id
     AND o.order_ts > f.order_ts
     AND o.order_ts <= f.order_ts + INTERVAL 30 DAY
    GROUP BY 1
),
labelled AS (
    SELECT f.city_code, n.orders_next_30d,
           CASE WHEN f.status = 'Cancelled' THEN 'Cancelled'
                WHEN f.is_late IS NULL THEN NULL
                WHEN f.is_late AND f.delivery_min - f.promised_eta_min > 5 THEN 'Late by 5+ min'
                WHEN f.is_late THEN 'Late by < 5 min'
                ELSE 'On time' END AS first_order_experience
    FROM first_orders f JOIN next30 n USING (customer_id)
)
SELECT coalesce(city_code, 'IN')                          AS city_code,
       first_order_experience,
       count(*)                                           AS customers,
       round(100 * avg((orders_next_30d > 0)::INT), 1)    AS repeat_within_30d_pct,
       round(avg(orders_next_30d), 2)                     AS avg_orders_next_30d
FROM labelled
WHERE first_order_experience IS NOT NULL
GROUP BY GROUPING SETS ((city_code, first_order_experience), (first_order_experience))
ORDER BY city_code,
         CASE first_order_experience WHEN 'On time' THEN 1 WHEN 'Late by < 5 min' THEN 2
                                     WHEN 'Late by 5+ min' THEN 3 ELSE 4 END;
