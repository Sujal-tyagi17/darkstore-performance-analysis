-- Where does each store lose time? Break delivery time into its three stages
-- and compare each stage to the network average to name the primary bottleneck.
WITH stage AS (
    SELECT store_id,
           avg(pick_min)       AS pick_min,
           avg(rider_wait_min) AS rider_wait_min,
           avg(travel_min)     AS travel_min,
           avg(delivery_min)   AS delivery_min
    FROM fact_orders
    WHERE valid_timing
    GROUP BY store_id
),
net AS (
    SELECT avg(pick_min) AS n_pick, avg(rider_wait_min) AS n_wait, avg(travel_min) AS n_travel
    FROM fact_orders WHERE valid_timing
),
gaps AS (
    SELECT s.*,
           s.pick_min - n.n_pick         AS pick_gap,
           s.rider_wait_min - n.n_wait   AS wait_gap,
           s.travel_min - n.n_travel     AS travel_gap
    FROM stage s CROSS JOIN net n
)
SELECT
    store_id,
    round(pick_min, 2)       AS pick_min,
    round(rider_wait_min, 2) AS rider_wait_min,
    round(travel_min, 2)     AS travel_min,
    round(delivery_min, 2)   AS delivery_min,
    round(pick_gap, 2)       AS pick_gap_vs_network,
    round(wait_gap, 2)       AS wait_gap_vs_network,
    round(travel_gap, 2)     AS travel_gap_vs_network,
    CASE
        WHEN greatest(pick_gap, wait_gap, travel_gap) < 0.5 THEN 'On par with network'
        WHEN pick_gap   = greatest(pick_gap, wait_gap, travel_gap) THEN 'Slow picking (in-store)'
        WHEN wait_gap   = greatest(pick_gap, wait_gap, travel_gap) THEN 'Rider shortage (orders wait for riders)'
        ELSE 'Long distances (catchment too wide)'
    END AS primary_bottleneck
FROM gaps
ORDER BY delivery_min DESC;
