# Building the Power BI report

The Streamlit app is the live dashboard. This guide rebuilds the same store scorecard in **Power BI Desktop** from the star schema exported by the pipeline, so the project also shows Power BI skills.

## 1. Export the data

```bash
python run_all.py          # builds the warehouse and writes data/powerbi/*.csv
```

## 2. Load and model

**Get Data → Text/CSV**, load all nine files from `data/powerbi/`. In **Model view**, create these relationships (single direction, many-to-one):

| From (many) | To (one) | Column |
|---|---|---|
| fact_orders | dim_store | store_id |
| fact_orders | dim_city | city_code |
| dim_store | dim_city | city_code (set fact_orders → dim_city as the active path, this one inactive) |
| fact_orders | dim_customer | customer_id |
| fact_orders | dim_date | order_date → date |
| fact_order_items | fact_orders | order_id |
| fact_order_items | dim_product | sku_id |
| fact_rider_shifts | dim_store | store_id |
| fact_rider_shifts | dim_date | date |
| dim_weather_hour | dim_city | city_code |

Mark `dim_date` as the date table (**Table tools → Mark as date table**). In Power Query, set `valid_timing`, `is_late`, `is_rain` and `fulfilled` to *True/False* type.

## 3. DAX measures

Create a `_Measures` table and add:

```DAX
Orders = COUNTROWS ( fact_orders )

Delivered Orders = CALCULATE ( [Orders], fact_orders[status] = "Delivered" )

GMV = CALCULATE ( SUM ( fact_orders[order_value] ), fact_orders[status] = "Delivered" )

AOV = DIVIDE ( [GMV], [Delivered Orders] )

Avg Delivery Min =
    CALCULATE ( AVERAGE ( fact_orders[delivery_min] ), fact_orders[valid_timing] = TRUE () )

P90 Delivery Min =
    CALCULATE (
        PERCENTILEX.INC ( fact_orders, fact_orders[delivery_min], 0.9 ),
        fact_orders[valid_timing] = TRUE ()
    )

Late % =
    DIVIDE (
        CALCULATE ( [Orders], fact_orders[is_late] = TRUE () ),
        CALCULATE ( [Orders], fact_orders[valid_timing] = TRUE () )
    )

Late % vs India =
    [Late %] - CALCULATE ( [Late %], REMOVEFILTERS ( dim_store ), REMOVEFILTERS ( dim_city ) )

Late % vs City =
    [Late %] - CALCULATE ( [Late %], REMOVEFILTERS ( dim_store ), VALUES ( dim_city[city_code] ) )

Cancel % = DIVIDE ( CALCULATE ( [Orders], fact_orders[status] = "Cancelled" ), [Orders] )

Avg Rating = AVERAGE ( fact_orders[rating] )

Avg Pick Min   = CALCULATE ( AVERAGE ( fact_orders[pick_min] ),       fact_orders[valid_timing] = TRUE () )
Avg Wait Min   = CALCULATE ( AVERAGE ( fact_orders[rider_wait_min] ), fact_orders[valid_timing] = TRUE () )
Avg Travel Min = CALCULATE ( AVERAGE ( fact_orders[travel_min] ),     fact_orders[valid_timing] = TRUE () )

Avg Rider Utilisation = AVERAGE ( fact_orders[rider_utilization] )

Stockout Lost Revenue =
    CALCULATE ( SUM ( fact_order_items[line_value] ), fact_order_items[fulfilled] = FALSE () )

Stockout % =
    DIVIDE (
        CALCULATE ( COUNTROWS ( fact_order_items ), fact_order_items[fulfilled] = FALSE () ),
        COUNTROWS ( fact_order_items )
    )

Late % MoM Change =
    VAR cur = [Late %]
    VAR prev = CALCULATE ( [Late %], DATEADD ( dim_date[date], -1, MONTH ) )
    RETURN cur - prev
```

## 4. Report pages

| Page | Visuals |
|---|---|
| **India** | KPI cards (Orders, GMV, Avg Delivery Min, Late %, Cancel %, Avg Rating), map of dim_city lat/lon (bubble = Orders, colour = Late %), table of cities, slicers for city and month |
| **City** | Store map (dim_store lat/lon), store table with Late % vs City, line chart of weekly Late % for the city against India |
| **Store scorecard** | Table: store × all measures with conditional formatting on Late %, stacked bar of Avg Pick / Wait / Travel Min by store |
| **Why late** | Columns: Late % by distance_band, weather and order_hour; scatter of Avg Rider Utilisation against Late % by store |
| **Stockouts** | Treemap of Stockout Lost Revenue by category, matrix of product × store with Stockout % |

Colour guidance: one highlight colour (`#2a78d6`) for the stores or bars you want the reader to look at, grey (`#c3c2b7`) for the rest, and an orange sequential scale for Late %.

## 5. Publish

**File → Publish → Publish to web** (needs a free Power BI service account) and paste the link at the top of the README. Save the `.pbix` as `dashboard/darkstore_performance.pbix`.
