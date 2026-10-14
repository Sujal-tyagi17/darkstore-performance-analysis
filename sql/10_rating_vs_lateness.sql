-- Customer rating by how late the order was
SELECT CASE WHEN delivery_min <= promised_eta_min THEN '1. On time'
            WHEN delivery_min - promised_eta_min <= 3 THEN '2. Late 0-3 min'
            WHEN delivery_min - promised_eta_min <= 6 THEN '3. Late 3-6 min'
            WHEN delivery_min - promised_eta_min <= 10 THEN '4. Late 6-10 min'
            ELSE '5. Late 10+ min' END                      AS lateness,
       has_missing_items,
       count(*)                                             AS rated_orders,
       round(avg(rating), 2)                                AS avg_rating,
       round(100 * avg((rating <= 2)::INT), 1)              AS bad_rating_pct
FROM fact_orders
WHERE valid_timing AND rating IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2;
