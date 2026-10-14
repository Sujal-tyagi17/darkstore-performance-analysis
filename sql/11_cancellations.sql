-- Cancellations by store and reason, with the GMV that never materialised
-- (estimated at each store's average delivered order value)
WITH aov AS (
    SELECT store_id, avg(order_value) AS aov FROM fact_orders WHERE is_delivered GROUP BY 1
)
SELECT o.store_id,
       o.cancel_reason,
       count(*)                          AS cancelled_orders,
       round(count(*) * a.aov, 0)        AS est_lost_gmv_inr
FROM fact_orders o
JOIN aov a USING (store_id)
WHERE o.status = 'Cancelled'
GROUP BY o.store_id, o.cancel_reason, a.aov
ORDER BY cancelled_orders DESC, o.store_id, o.cancel_reason;
