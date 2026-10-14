"""
Export the cleaned star schema as CSVs that Power BI (or Tableau) can load directly.

Run after build_warehouse.py:  python src/export_powerbi.py
Output: data/powerbi/*.csv   (see docs/powerbi_guide.md for the model and DAX measures)
"""

from __future__ import annotations

from pathlib import Path

from build_warehouse import ROOT, connect

OUT = ROOT / "data" / "powerbi"

TABLES = {
    "dim_store": "SELECT * FROM dim_store",
    "dim_product": "SELECT * FROM dim_product",
    "dim_customer": "SELECT * FROM dim_customer",
    "dim_date": "SELECT * FROM dim_date",
    "fact_orders": """
        SELECT order_id, customer_id, store_id, order_date, order_hour, order_ts, status, cancel_reason,
               promised_eta_min, distance_km, distance_band, weather, is_rain, riders_on_shift,
               rider_utilization, item_lines, items_missing, item_total, discount, delivery_fee,
               small_cart_fee, order_value, payment_method, rating,
               round(pick_min, 2) AS pick_min, round(rider_wait_min, 2) AS rider_wait_min,
               round(travel_min, 2) AS travel_min, round(delivery_min, 2) AS delivery_min,
               valid_timing, is_late, customer_order_seq
        FROM fact_orders
    """,
    "fact_order_items": """
        SELECT order_id, line_no, sku_id, store_id, order_date, quantity, unit_price, line_value, fulfilled
        FROM fact_order_items
    """,
    "fact_rider_shifts": "SELECT * FROM fact_rider_shifts",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect(read_only=True)
    for name, sql in TABLES.items():
        path = OUT / f"{name}.csv"
        con.execute(f"COPY ({sql}) TO '{path.as_posix()}' (HEADER, DELIMITER ',')")
        n = con.execute(f"SELECT count(*) FROM ({sql})").fetchone()[0]
        print(f"  {name:<20} {n:>8,} rows -> {path.relative_to(ROOT)}")
    con.close()


if __name__ == "__main__":
    main()
