-- Where does each store lose time? Split delivery time into its three stages and
-- compare each stage with the all-India average to name the primary bottleneck.
-- Travel is judged on DISTANCE (catchment size), not on the city's traffic: a Mumbai
-- store is not "long distance" just because Mumbai roads are slow.
WITH stage AS (
    SELECT store_id, city_code,
           avg(pick_min) AS pick_min, avg(rider_wait_min) AS rider_wait_min,
           avg(travel_min) AS travel_min, avg(delivery_min) AS delivery_min,
           avg(distance_km) AS distance_km
    FROM fact_orders WHERE valid_timing
    GROUP BY 1, 2
),
city_speed AS (
    SELECT city_code, sum(travel_min) / sum(distance_km) AS travel_min_per_km
    FROM fact_orders WHERE valid_timing GROUP BY 1
),
net AS (
    SELECT avg(pick_min) AS n_pick, avg(rider_wait_min) AS n_wait, avg(distance_km) AS n_dist
    FROM fact_orders WHERE valid_timing
),
gaps AS (
    SELECT s.*, cs.travel_min_per_km,
           s.pick_min - n.n_pick                                  AS pick_gap,
           s.rider_wait_min - n.n_wait                            AS wait_gap,
           (s.distance_km - n.n_dist) * cs.travel_min_per_km      AS distance_gap
    FROM stage s
    JOIN city_speed cs USING (city_code)
    CROSS JOIN net n
)
SELECT
    store_id, city_code,
    round(pick_min, 2)          AS pick_min,
    round(rider_wait_min, 2)    AS rider_wait_min,
    round(travel_min, 2)        AS travel_min,
    round(delivery_min, 2)      AS delivery_min,
    round(distance_km, 2)       AS avg_distance_km,
    round(travel_min_per_km, 2) AS city_travel_min_per_km,
    round(pick_gap, 2)          AS pick_gap_vs_india,
    round(wait_gap, 2)          AS wait_gap_vs_india,
    round(distance_gap, 2)      AS distance_gap_vs_india,
    CASE
        WHEN greatest(pick_gap, wait_gap, distance_gap) < 0.75 THEN 'On par'
        WHEN pick_gap = greatest(pick_gap, wait_gap, distance_gap) THEN 'Slow picking'
        WHEN wait_gap = greatest(pick_gap, wait_gap, distance_gap) THEN 'Rider shortage'
        ELSE 'Long distances'
    END AS primary_bottleneck
FROM gaps
ORDER BY delivery_min DESC;
