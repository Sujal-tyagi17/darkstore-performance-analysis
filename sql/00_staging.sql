-- =====================================================================
-- 00_staging.sql
-- Load raw exports, clean them, and build an analysis-ready star schema.
-- {raw} is replaced with the data/raw path by src/build_warehouse.py
-- =====================================================================

-- ---------- raw landing tables (as exported, untouched) --------------
CREATE OR REPLACE TABLE raw_orders      AS SELECT * FROM read_parquet('{raw}/orders.parquet');
CREATE OR REPLACE TABLE raw_order_items AS SELECT * FROM read_parquet('{raw}/order_items.parquet');

-- ---------- dimensions ----------------------------------------------
CREATE OR REPLACE TABLE dim_city AS
SELECT city_code, city_name, state, lat, lon, road_factor
FROM read_csv_auto('{raw}/cities.csv', header = true);

CREATE OR REPLACE TABLE dim_store AS
SELECT s.store_id, s.store_name, s.city_code, c.city_name, s.locality, s.lat, s.lon,
       s.area_sqft, CAST(s.opened_on AS DATE) AS opened_on
FROM read_csv_auto('{raw}/stores.csv', header = true) s
JOIN dim_city c USING (city_code);

CREATE OR REPLACE TABLE dim_product AS
SELECT sku_id, product_name, category, CAST(mrp AS DOUBLE) AS mrp
FROM read_csv_auto('{raw}/products.csv', header = true);

CREATE OR REPLACE TABLE dim_customer AS
SELECT customer_id, city_code, area, lat, lon, CAST(signup_date AS DATE) AS signup_date, segment
FROM read_parquet('{raw}/customers.parquet');

CREATE OR REPLACE TABLE dim_weather_hour AS
SELECT city_code, CAST(date AS DATE) AS date, hour, condition
FROM read_parquet('{raw}/weather_hourly.parquet');

CREATE OR REPLACE TABLE fact_rider_shifts AS
SELECT CAST(date AS DATE) AS date, hour, store_id, riders_on_shift
FROM read_parquet('{raw}/rider_shifts.parquet');

CREATE OR REPLACE TABLE dim_date AS
SELECT d::DATE                    AS date,
       year(d)                    AS year,
       month(d)                   AS month,
       strftime(d, '%b')          AS month_name,
       week(d)                    AS iso_week,
       dayofweek(d)               AS dow,          -- 0 = Sunday
       strftime(d, '%a')          AS day_name,
       dayofweek(d) IN (0, 6)     AS is_weekend
FROM range(DATE '2026-01-01', DATE '2026-07-01', INTERVAL 1 DAY) t(d);

-- ---------- cleaned orders -------------------------------------------
-- Issues handled:
--   1. duplicate rows from an export retry bug     -> keep one row per order_id
--   2. store_id casing / whitespace ('blr07', ' BLR07') -> trim + upper
--   3. payment labels drift ('upi', 'COD')          -> standard labels
--   4. impossible timings (delivered before dispatch, >90 min) -> flagged, excluded from time KPIs
--   5. missing distance (geocoding failures)         -> imputed from customer & store coordinates
CREATE OR REPLACE TABLE fact_orders AS
WITH dedup AS (
    SELECT *, row_number() OVER (PARTITION BY order_id ORDER BY order_ts) AS rn
    FROM raw_orders
),
std AS (
    SELECT
        order_id, customer_id,
        upper(trim(store_id))                     AS store_id,
        CAST(order_ts AS TIMESTAMP)               AS order_ts,
        CAST(packed_ts AS TIMESTAMP)              AS packed_ts,
        CAST(dispatched_ts AS TIMESTAMP)          AS dispatched_ts,
        CAST(delivered_ts AS TIMESTAMP)           AS delivered_ts,
        promised_eta_min, distance_km, weather, riders_on_shift, store_orders_in_hour,
        item_lines, items_missing, item_total, discount, delivery_fee, small_cart_fee, order_value,
        CASE lower(payment_method)
            WHEN 'upi' THEN 'UPI'
            WHEN 'cod' THEN 'Cash on Delivery'
            WHEN 'cash on delivery' THEN 'Cash on Delivery'
            WHEN 'card' THEN 'Card'
            WHEN 'wallet' THEN 'Wallet'
            ELSE payment_method
        END                                       AS payment_method,
        status, cancel_reason, rating
    FROM dedup
    WHERE rn = 1
),
imputed AS (
    SELECT o.*, s.city_code,
           coalesce(o.distance_km,
               round(ci.road_factor * 2 * 6371 * asin(sqrt(
                   pow(sin(radians(c.lat - s.lat) / 2), 2) +
                   cos(radians(s.lat)) * cos(radians(c.lat)) * pow(sin(radians(c.lon - s.lon) / 2), 2)
               )) + 0.15, 2))                     AS distance_km_clean,
           o.distance_km IS NULL                  AS distance_imputed
    FROM std o
    LEFT JOIN dim_customer c USING (customer_id)
    LEFT JOIN dim_store s ON s.store_id = o.store_id
    LEFT JOIN dim_city ci ON ci.city_code = s.city_code
)
SELECT
    order_id, customer_id, store_id, city_code,
    order_ts,
    CAST(order_ts AS DATE)                                             AS order_date,
    hour(order_ts)                                                     AS order_hour,
    packed_ts, dispatched_ts, delivered_ts,
    status,
    status = 'Delivered'                                               AS is_delivered,
    cancel_reason,
    promised_eta_min,
    distance_km_clean                                                  AS distance_km,
    distance_imputed,
    CASE WHEN distance_km_clean <= 1 THEN '0-1 km'
         WHEN distance_km_clean <= 2 THEN '1-2 km'
         WHEN distance_km_clean <= 3 THEN '2-3 km'
         WHEN distance_km_clean <= 4 THEN '3-4 km'
         ELSE '4+ km' END                                              AS distance_band,
    weather,
    weather IN ('Rain', 'Heavy Rain')                                  AS is_rain,
    riders_on_shift,
    store_orders_in_hour,
    round(store_orders_in_hour / (riders_on_shift * 2.2), 3)           AS rider_utilization,
    item_lines, items_missing,
    items_missing > 0                                                  AS has_missing_items,
    item_total, discount, delivery_fee, small_cart_fee, order_value,
    payment_method,
    rating,
    date_diff('second', order_ts, packed_ts) / 60.0                    AS pick_min,
    date_diff('second', packed_ts, dispatched_ts) / 60.0               AS rider_wait_min,
    date_diff('second', dispatched_ts, delivered_ts) / 60.0            AS travel_min,
    date_diff('second', order_ts, delivered_ts) / 60.0                 AS delivery_min,
    (status = 'Delivered'
        AND delivered_ts > dispatched_ts
        AND date_diff('second', order_ts, delivered_ts) / 60.0 <= 90)  AS valid_timing,
    CASE WHEN status = 'Delivered'
              AND delivered_ts > dispatched_ts
              AND date_diff('second', order_ts, delivered_ts) / 60.0 <= 90
         THEN date_diff('second', order_ts, delivered_ts) / 60.0 > promised_eta_min
    END                                                                AS is_late,
    row_number() OVER (PARTITION BY customer_id ORDER BY order_ts)     AS customer_order_seq
FROM imputed;

-- ---------- cleaned order items --------------------------------------
CREATE OR REPLACE TABLE fact_order_items AS
SELECT i.order_id, i.line_no, i.sku_id, i.quantity, i.unit_price,
       i.fulfilled = 1                         AS fulfilled,
       i.quantity * i.unit_price               AS line_value,
       o.store_id, o.city_code, o.order_date, o.order_hour, o.status
FROM (SELECT DISTINCT * FROM raw_order_items) i
JOIN fact_orders o USING (order_id);

-- ---------- data quality log ------------------------------------------
CREATE OR REPLACE TABLE data_quality_log AS
SELECT 'Duplicate order rows removed' AS check_name,
       (SELECT count(*) FROM raw_orders) - (SELECT count(DISTINCT order_id) FROM raw_orders) AS rows_affected
UNION ALL
SELECT 'Store IDs with bad casing/whitespace fixed',
       (SELECT count(*) FROM raw_orders WHERE store_id <> upper(trim(store_id)))
UNION ALL
SELECT 'Payment method labels standardised',
       (SELECT count(*) FROM raw_orders WHERE payment_method IN ('upi', 'COD'))
UNION ALL
SELECT 'Delivered orders with impossible timings (excluded from time KPIs)',
       (SELECT count(*) FROM fact_orders WHERE is_delivered AND NOT valid_timing)
UNION ALL
SELECT 'Missing distances imputed from coordinates',
       (SELECT count(*) FROM fact_orders WHERE distance_imputed)
UNION ALL
SELECT 'Orders not rated by customer (expected, left as NULL)',
       (SELECT count(*) FROM fact_orders WHERE is_delivered AND rating IS NULL);
