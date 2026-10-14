"""Data-integrity and analysis sanity tests. Run with:  pytest -q  (after python run_all.py)"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from build_warehouse import DB_PATH, PROCESSED, REPORTS, connect  # noqa: E402

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="run `python run_all.py` first")


@pytest.fixture(scope="module")
def con():
    c = connect(read_only=True)
    yield c
    c.close()


def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


def test_order_ids_unique_after_cleaning(con):
    assert scalar(con, "SELECT count(*) - count(DISTINCT order_id) FROM fact_orders") == 0


def test_store_ids_all_valid(con):
    bad = scalar(con, "SELECT count(*) FROM fact_orders WHERE store_id NOT IN (SELECT store_id FROM dim_store)")
    assert bad == 0


def test_payment_labels_standardised(con):
    labels = {r[0] for r in con.execute("SELECT DISTINCT payment_method FROM fact_orders").fetchall()}
    assert labels == {"UPI", "Card", "Cash on Delivery", "Wallet"}


def test_no_missing_distance(con):
    assert scalar(con, "SELECT count(*) FROM fact_orders WHERE distance_km IS NULL") == 0


def test_delivery_components_add_up(con):
    gap = scalar(con, """
        SELECT max(abs(pick_min + rider_wait_min + travel_min - delivery_min))
        FROM fact_orders WHERE valid_timing""")
    assert gap < 0.05


def test_valid_timings_are_positive_and_bounded(con):
    row = con.execute("SELECT min(delivery_min), max(delivery_min), min(travel_min) "
                      "FROM fact_orders WHERE valid_timing").fetchone()
    assert row[0] > 0 and row[1] <= 90 and row[2] > 0


def test_late_flag_matches_definition(con):
    wrong = scalar(con, """
        SELECT count(*) FROM fact_orders
        WHERE valid_timing AND is_late <> (delivery_min > promised_eta_min)""")
    assert wrong == 0


def test_cancelled_orders_have_no_revenue(con):
    assert scalar(con, "SELECT coalesce(sum(order_value), 0) FROM fact_orders WHERE status = 'Cancelled'") == 0


def test_items_link_to_orders(con):
    orphans = scalar(con, "SELECT count(*) FROM fact_order_items WHERE order_id NOT IN (SELECT order_id FROM fact_orders)")
    assert orphans == 0


def test_scorecard_covers_every_store():
    sc = pd.read_csv(PROCESSED / "store_scorecard.csv")
    assert len(sc) == 12 and sc.late_pct.between(0, 100).all()


def test_metrics_have_headline_numbers():
    m = json.loads((REPORTS / "metrics.json").read_text())
    for key in ["late_pct", "incident", "whatif_staffing_S07", "whatif_picking_S10",
                "whatif_new_store_best", "revenue_impact"]:
        assert key in m
    assert m["incident"]["store_id"] == "S03"
    assert m["whatif_new_store_best"]["late_pct_new"] < m["whatif_new_store_best"]["late_pct_now"]
