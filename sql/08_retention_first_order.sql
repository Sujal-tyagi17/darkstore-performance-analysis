-- Does a bad first order cost us the customer?
-- Cohort: customers who signed up during the period and placed their first order by 31 May,
-- so every customer has a full 30-day window to come back.
WITH first_orders AS (
    SELECT o.customer_id, o.order_ts, o.is_late, o.status, o.has_missing_items, o.delivery_min, o.promised_eta_min
    FROM fact_orders o
    JOIN dim_customer c USING (customer_id)
    WHERE o.customer_order_seq = 1
      AND c.signup_date >= DATE '2026-01-01'
      AND o.order_ts < TIMESTAMP '2026-06-01'
),
labelled AS (
    SELECT f.*,
           CASE WHEN f.status = 'Cancelled' THEN 'Cancelled'
                WHEN f.is_late IS NULL THEN NULL
                WHEN f.is_late AND f.delivery_min - f.promised_eta_min > 5 THEN 'Late by 5+ min'
                WHEN f.is_late THEN 'Late by < 5 min'
                ELSE 'On time' END AS first_order_experience,
           EXISTS (SELECT 1 FROM fact_orders o2
                   WHERE o2.customer_id = f.customer_id
                     AND o2.order_ts > f.order_ts
                     AND o2.order_ts <= f.order_ts + INTERVAL 30 DAY)          AS repeat_30d,
           (SELECT count(*) FROM fact_orders o3
            WHERE o3.customer_id = f.customer_id
              AND o3.order_ts > f.order_ts
              AND o3.order_ts <= f.order_ts + INTERVAL 30 DAY)                 AS orders_next_30d
    FROM first_orders f
)
SELECT first_order_experience,
       count(*)                                     AS customers,
       round(100 * avg(repeat_30d::INT), 1)         AS repeat_within_30d_pct,
       round(avg(orders_next_30d), 2)               AS avg_orders_next_30d
FROM labelled
WHERE first_order_experience IS NOT NULL
GROUP BY 1
ORDER BY CASE first_order_experience WHEN 'On time' THEN 1 WHEN 'Late by < 5 min' THEN 2
                                     WHEN 'Late by 5+ min' THEN 3 ELSE 4 END;
