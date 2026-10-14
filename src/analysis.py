"""
Python analysis layer on top of the DuckDB warehouse.

  1. Delivery-time driver model (OLS with store fixed effects)
  2. Market basket analysis (FP-Growth association rules)
  3. Incident detection: weekly late-rate jumps per store
  4. What-if simulations for each recommended fix
     a) add riders at understaffed stores
     b) fix slow picking at Electronic City
     c) open a new dark store where far-away demand clusters
  5. Revenue impact of late deliveries (retention + cancellations + stockouts)

Outputs:
  data/processed/*.csv      tables for the dashboard
  reports/metrics.json      headline numbers quoted in the README
  reports/figures/*.png     charts used in the README and findings report

Run after build_warehouse.py:  python src/analysis.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.formula.api as smf  # noqa: E402
from mlxtend.frequent_patterns import association_rules, fpgrowth  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402

from build_warehouse import DB_PATH, PROCESSED, REPORTS, connect  # noqa: E402
from charts import (  # noqa: E402
    chart_basket_rules,
    chart_breakdown,
    chart_drivers,
    chart_expansion_map,
    chart_heatmap,
    chart_incident,
    chart_rating,
    chart_retention,
    chart_stockouts,
    chart_store_late,
)

ORDERS_PER_RIDER_HOUR = 2.2
TARGET_UTILIZATION = 0.85
ROAD_FACTOR = 1.32


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def promise_for(distance_km):
    """Promised ETA tiers shown in the app (minutes)."""
    d = np.asarray(distance_km)
    return np.where(d <= 1.5, 10, np.where(d <= 2.5, 12, np.where(d <= 3.5, 15, 18)))


# ---------------------------------------------------------------------------
def load(con):
    orders = con.execute("""
        SELECT o.*, c.lat AS cust_lat, c.lon AS cust_lon, c.area, c.segment,
               d.is_weekend
        FROM fact_orders o
        JOIN dim_customer c USING (customer_id)
        JOIN dim_date d ON d.date = o.order_date
    """).df()
    stores = con.execute("SELECT * FROM dim_store ORDER BY store_id").df()
    items = con.execute("""
        SELECT i.order_id, p.product_name
        FROM fact_order_items i JOIN dim_product p USING (sku_id)
        WHERE i.status = 'Delivered'
    """).df()
    return orders, stores, items


# ---------------------------------------------------------------------------
# 1. Driver model
# ---------------------------------------------------------------------------
def driver_model(orders: pd.DataFrame):
    d = orders[orders.valid_timing].copy()
    d["heavy_rain"] = (d.weather == "Heavy Rain").astype(int)
    d["rain"] = (d.weather == "Rain").astype(int)
    d["peak_traffic"] = d.order_hour.isin([8, 9, 10, 17, 18, 19, 20, 21]).astype(int)
    d["util_over_75_pp"] = np.maximum(0, d.rider_utilization - 0.75) * 100
    d["weekend"] = d.is_weekend.astype(int)
    model = smf.ols(
        "delivery_min ~ distance_km + rain + heavy_rain + peak_traffic + util_over_75_pp"
        " + item_lines + weekend + C(store_id, Treatment('S01'))",
        data=d,
    ).fit(cov_type="HC1")

    labels = {
        "distance_km": "Each extra km of distance",
        "rain": "Rain (vs clear)",
        "heavy_rain": "Heavy rain (vs clear)",
        "peak_traffic": "Peak traffic hour",
        "util_over_75_pp": "Each +10 pts rider utilisation above 75%",
        "item_lines": "Each extra item in the basket",
        "weekend": "Weekend",
    }
    rows = []
    for var, label in labels.items():
        coef = model.params[var]
        lo, hi = model.conf_int().loc[var]
        scale = 10 if var == "util_over_75_pp" else 1
        rows.append({"driver": label, "minutes_added": round(coef * scale, 2),
                     "ci_low": round(lo * scale, 2), "ci_high": round(hi * scale, 2),
                     "p_value": float(f"{model.pvalues[var]:.2g}")})
    for name in model.params.index:
        if name.startswith("C(store_id"):
            sid = name.split("[T.")[1].rstrip("]")
            lo, hi = model.conf_int().loc[name]
            rows.append({"driver": f"Store effect {sid} (vs Koramangala, all else equal)",
                         "minutes_added": round(model.params[name], 2),
                         "ci_low": round(lo, 2), "ci_high": round(hi, 2),
                         "p_value": float(f"{model.pvalues[name]:.2g}")})
    coefs = pd.DataFrame(rows)
    coefs.to_csv(PROCESSED / "delivery_time_drivers_model.csv", index=False)
    return model, coefs


# ---------------------------------------------------------------------------
# 2. Market basket
# ---------------------------------------------------------------------------
def basket_analysis(items: pd.DataFrame):
    basket = pd.crosstab(items.order_id, items.product_name).astype(bool)
    freq = fpgrowth(basket, min_support=0.008, use_colnames=True)
    rules = association_rules(freq, metric="lift", min_threshold=1.5)
    rules = rules[(rules.confidence >= 0.25) & (rules.antecedents.apply(len) <= 2) & (rules.consequents.apply(len) == 1)]
    rules = rules.assign(
        if_customer_buys=rules.antecedents.apply(lambda s: " + ".join(sorted(s))),
        they_also_buy=rules.consequents.apply(lambda s: next(iter(s))),
    )
    # keep one direction per pair (the stronger confidence)
    rules["pair"] = rules.apply(lambda r: frozenset(r.antecedents | r.consequents), axis=1)
    rules = rules.sort_values("confidence", ascending=False).drop_duplicates("pair")
    out = (rules[["if_customer_buys", "they_also_buy", "support", "confidence", "lift"]]
           .sort_values("lift", ascending=False).head(25).round(3).reset_index(drop=True))
    out["orders_with_both"] = (out.support * len(basket)).round().astype(int)
    out.to_csv(PROCESSED / "basket_rules.csv", index=False)
    return out, len(basket)


# ---------------------------------------------------------------------------
# 3. Incident detection
# ---------------------------------------------------------------------------
def detect_incidents(con):
    wk = pd.read_csv(PROCESSED / "weekly_store_trend.csv", parse_dates=["week_start"])
    wk = wk[wk.orders >= 100].sort_values(["store_id", "week_start"])
    g = wk.groupby("store_id")
    wk["baseline_late_pct"] = g.late_pct.transform(lambda s: s.shift(1).rolling(8, min_periods=4).mean())
    wk["baseline_std"] = g.late_pct.transform(lambda s: s.shift(1).rolling(8, min_periods=4).std())
    wk["z_score"] = (wk.late_pct - wk.baseline_late_pct) / wk.baseline_std
    # Remove city-wide swings (e.g. monsoon weeks hit every store): compare each store's
    # jump with the network's jump in the same week.
    net = (wk.assign(late_n=wk.late_pct * wk.orders).groupby("week_start")
           .agg(late_n=("late_n", "sum"), orders=("orders", "sum")))
    net["network_late_pct"] = net.late_n / net.orders
    net["network_baseline"] = net.network_late_pct.shift(1).rolling(8, min_periods=4).mean()
    wk = wk.merge(net[["network_late_pct", "network_baseline"]], on="week_start", how="left")
    wk["jump_vs_network_pts"] = ((wk.late_pct - wk.baseline_late_pct)
                                 - (wk.network_late_pct - wk.network_baseline))
    alerts = wk[(wk.z_score > 3) & (wk.jump_vs_network_pts > 10)].copy()
    alerts = alerts.sort_values("week_start").groupby("store_id").head(1)
    alerts = alerts.sort_values("jump_vs_network_pts", ascending=False)
    alerts.round({c: 2 for c in alerts.select_dtypes("number").columns}).to_csv(PROCESSED / "incident_alerts.csv", index=False)

    incident = None
    if len(alerts):
        a = alerts.iloc[0]
        sid, start = a.store_id, a.week_start
        before = con.execute(f"""
            SELECT avg(riders_on_shift) r, avg(rider_wait_min) w, 100*avg(is_late::INT) l, avg(delivery_min) d
            FROM fact_orders WHERE valid_timing AND store_id = '{sid}'
              AND order_date >= DATE '{(start - pd.Timedelta(days=28)).date()}' AND order_date < DATE '{start.date()}'
        """).fetchone()
        after = con.execute(f"""
            SELECT avg(riders_on_shift) r, avg(rider_wait_min) w, 100*avg(is_late::INT) l, avg(delivery_min) d
            FROM fact_orders WHERE valid_timing AND store_id = '{sid}'
              AND order_date >= DATE '{start.date()}'
        """).fetchone()
        incident = {
            "store_id": sid, "week_detected": str(start.date()),
            "late_pct_before": round(before[2], 1), "late_pct_after": round(after[2], 1),
            "rider_wait_min_before": round(before[1], 2), "rider_wait_min_after": round(after[1], 2),
            "riders_on_shift_before": round(before[0], 2), "riders_on_shift_after": round(after[0], 2),
            "delivery_min_before": round(before[3], 2), "delivery_min_after": round(after[3], 2),
        }
    return wk, alerts, incident


# ---------------------------------------------------------------------------
# 4. What-if simulations
# ---------------------------------------------------------------------------
def staffing_gap(con, store_id, since=None):
    """Extra rider-hours needed so that no store-hour runs above TARGET_UTILIZATION."""
    where = f"AND s.date >= DATE '{since}'" if since else ""
    df = con.execute(f"""
        SELECT s.date, s.hour, s.riders_on_shift, count(o.order_id) AS orders
        FROM fact_rider_shifts s
        LEFT JOIN fact_orders o
          ON o.store_id = s.store_id AND o.order_date = s.date AND o.order_hour = s.hour
        WHERE s.store_id = '{store_id}' {where}
        GROUP BY 1, 2, 3
    """).df()
    needed = np.ceil(df.orders / (ORDERS_PER_RIDER_HOUR * TARGET_UTILIZATION)).clip(lower=1)
    gap = (needed - df.riders_on_shift).clip(lower=0)
    days = df.date.nunique()
    by_hour = (pd.DataFrame({"hour": df.hour, "gap": gap}).groupby("hour").gap.sum() / days)
    return {
        "extra_rider_hours_per_day": round(gap.sum() / days, 1),
        "current_rider_hours_per_day": round(df.riders_on_shift.sum() / days, 1),
        "biggest_gap_hours": sorted(int(h) for h in by_hour.nlargest(4).index),
    }


def simulate_late(d: pd.DataFrame, pick=None, wait=None, travel=None, promise=None):
    p = d.pick_min if pick is None else pick
    w = d.rider_wait_min if wait is None else wait
    t = d.travel_min if travel is None else travel
    pr = d.promised_eta_min if promise is None else promise
    return (p + w + t) > pr


def network_wait_curve(valid: pd.DataFrame):
    """Median rider wait at each utilisation level - used to re-price wait time after adding riders."""
    bins = np.arange(0, 3.01, 0.1)
    v = valid.assign(b=pd.cut(valid.rider_utilization, bins, include_lowest=True))
    curve = v.groupby("b", observed=True).rider_wait_min.median()
    mids = np.array([iv.mid for iv in curve.index])
    return mids, curve.to_numpy()


def whatif_staffing(valid, con, store_id, since=None):
    d = valid[valid.store_id == store_id]
    if since:
        d = d[d.order_date >= pd.Timestamp(since)]
    needed = np.ceil(d.store_orders_in_hour / (ORDERS_PER_RIDER_HOUR * TARGET_UTILIZATION)).clip(lower=1)
    riders_new = np.maximum(d.riders_on_shift, needed)
    util_new = d.store_orders_in_hour / (riders_new * ORDERS_PER_RIDER_HOUR)
    mids, med = network_wait_curve(valid)
    # scale each order's own wait by the ratio of typical wait at new vs old utilisation
    wait_old_typ = np.interp(d.rider_utilization, mids, med)
    wait_new_typ = np.interp(util_new, mids, med)
    wait_new = d.rider_wait_min * (wait_new_typ / np.maximum(wait_old_typ, 0.1))
    late_new = simulate_late(d, wait=wait_new)
    gap = staffing_gap(con, store_id, since)
    return {
        "store_id": store_id,
        "orders": int(len(d)),
        "late_pct_now": round(100 * d.is_late.mean(), 1),
        "late_pct_after_fix": round(100 * late_new.mean(), 1),
        "avg_delivery_now": round(d.delivery_min.mean(), 2),
        "avg_delivery_after_fix": round((d.pick_min + wait_new + d.travel_min).mean(), 2),
        **gap,
    }


def whatif_picking(valid, store_id="S10"):
    d = valid[valid.store_id == store_id]
    others = valid[valid.store_id != store_id]
    # pick time per item line, store vs rest of network
    excess = d.pick_min.mean() - others.pick_min.mean()
    new_pick = d.pick_min * (others.pick_min.mean() / d.pick_min.mean())
    late_new = simulate_late(d, pick=new_pick)
    return {
        "store_id": store_id,
        "pick_min_now": round(d.pick_min.mean(), 2),
        "pick_min_network": round(others.pick_min.mean(), 2),
        "excess_pick_min": round(excess, 2),
        "late_pct_now": round(100 * d.is_late.mean(), 1),
        "late_pct_after_fix": round(100 * late_new.mean(), 1),
    }


def whatif_new_store(valid, orders, stores, k=7):
    far = valid[valid.distance_km > 3.5]
    coords = np.c_[far.cust_lat, far.cust_lon * np.cos(np.radians(12.95))]
    km = KMeans(n_clusters=k, n_init=10, random_state=17).fit(coords)
    far = far.assign(cluster=km.labels_)
    clusters = (far.groupby("cluster")
                .agg(orders=("order_id", "size"), late_orders=("is_late", "sum"),
                     lat=("cust_lat", "mean"), lon=("cust_lon", "mean"),
                     main_area=("area", lambda s: s.value_counts().index[0]),
                     serving_store=("store_id", lambda s: s.value_counts().index[0]))
                .sort_values("late_orders", ascending=False).reset_index())

    results = []
    for _, c in clusters.iterrows():
        new_d = haversine_km(valid.cust_lat, valid.cust_lon, c.lat, c.lon) * ROAD_FACTOR + 0.15
        moved = new_d < valid.distance_km - 0.3
        d = valid[moved]
        nd = new_d[moved]
        travel_new = 0.8 + (d.travel_min - 0.8).clip(lower=0) * (nd / d.distance_km)
        late_new = simulate_late(d, travel=travel_new, promise=promise_for(nd))
        all_late_new = valid.is_late.copy()
        all_late_new[moved] = late_new
        delivered_moved = orders[orders.order_id.isin(d.order_id) & orders.is_delivered]
        results.append({
            "candidate_site_near": c.main_area,
            "lat": round(c.lat, 4), "lon": round(c.lon, 4),
            "currently_served_by": c.serving_store,
            "orders_reassigned_6m": int(moved.sum()),
            "orders_reassigned_per_day": round(moved.sum() / valid.order_date.nunique(), 1),
            "gmv_reassigned_6m_inr": round(delivered_moved.order_value.sum()),
            "avg_distance_now_km": round(d.distance_km.mean(), 2),
            "avg_distance_new_km": round(nd.mean(), 2),
            "late_pct_now": round(100 * d.is_late.mean(), 1),
            "late_pct_new": round(100 * late_new.mean(), 1),
            "avg_delivery_now": round(d.delivery_min.mean(), 2),
            "avg_delivery_new": round((d.pick_min + d.rider_wait_min + travel_new).mean(), 2),
            "network_late_pct_now": round(100 * valid.is_late.mean(), 2),
            "network_late_pct_new": round(100 * all_late_new.mean(), 2),
        })
    res = pd.DataFrame(results).sort_values("network_late_pct_new").reset_index(drop=True)
    res.to_csv(PROCESSED / "expansion_candidates.csv", index=False)
    return res, far


# ---------------------------------------------------------------------------
# 5. Revenue impact
# ---------------------------------------------------------------------------
def revenue_impact(orders, valid):
    ret = pd.read_csv(PROCESSED / "retention_first_order.csv")
    on_time = ret[ret.first_order_experience == "On time"].iloc[0]
    late_rows = ret[ret.first_order_experience.str.startswith("Late")]
    late_customers = late_rows.customers.sum()
    late_repeat = (late_rows.repeat_within_30d_pct * late_rows.customers).sum() / late_customers
    late_next = (late_rows.avg_orders_next_30d * late_rows.customers).sum() / late_customers
    aov = orders.loc[orders.is_delivered, "order_value"].mean()
    lost_orders_per_late_first = on_time.avg_orders_next_30d - late_next

    stock = pd.read_csv(PROCESSED / "stockouts.csv")
    canc = pd.read_csv(PROCESSED / "cancellations.csv")
    months = orders.order_date.dt.to_period("M").nunique()

    return {
        "aov_inr": round(aov, 1),
        "repeat_30d_on_time_pct": float(on_time.repeat_within_30d_pct),
        "repeat_30d_late_pct": round(late_repeat, 1),
        "repeat_gap_pp": round(on_time.repeat_within_30d_pct - late_repeat, 1),
        "orders_lost_per_late_first_order_30d": round(lost_orders_per_late_first, 2),
        "gmv_lost_per_1000_late_first_orders_inr": round(1000 * lost_orders_per_late_first * aov),
        "stockout_lost_revenue_6m_inr": round(stock.lost_revenue_inr.sum()),
        "stockout_lost_revenue_per_month_inr": round(stock.lost_revenue_inr.sum() / months),
        "icecream_s05_s10_lost_inr": round(stock[(stock.category == "Ice Cream & Frozen") & stock.store_id.isin(["S05", "S10"])].lost_revenue_inr.sum()),
        "slow_delivery_cancellations_6m": int(canc[canc.cancel_reason == "Delivery taking too long"].cancelled_orders.sum()),
        "slow_delivery_cancel_gmv_6m_inr": round(canc[canc.cancel_reason == "Delivery taking too long"].est_lost_gmv_inr.sum()),
    }


# ---------------------------------------------------------------------------
def main():
    (REPORTS / "figures").mkdir(parents=True, exist_ok=True)
    con = connect(read_only=True)
    orders, stores, items = load(con)
    for c in ["order_date"]:
        orders[c] = pd.to_datetime(orders[c])
    valid = orders[orders.valid_timing].copy()

    model, coefs = driver_model(orders)
    rules, n_baskets = basket_analysis(items)
    weekly, alerts, incident = detect_incidents(con)

    s07 = whatif_staffing(valid, con, "S07")
    s03 = whatif_staffing(valid, con, "S03", since=incident["week_detected"] if incident else None)
    s10 = whatif_picking(valid, "S10")
    expansion, far = whatif_new_store(valid, orders, stores)
    impact = revenue_impact(orders, valid)

    scorecard = pd.read_csv(PROCESSED / "store_scorecard.csv")
    kpis = pd.read_csv(PROCESSED / "network_kpis_monthly.csv")
    best = expansion.iloc[0].to_dict()

    metrics = {
        "period": "2026-01-01 to 2026-06-30",
        "stores": int(len(stores)),
        "orders": int(len(orders)),
        "delivered_orders": int(orders.is_delivered.sum()),
        "customers": int(orders.customer_id.nunique()),
        "gmv_inr": round(orders.loc[orders.is_delivered, "order_value"].sum()),
        "avg_delivery_min": round(valid.delivery_min.mean(), 2),
        "p90_delivery_min": round(valid.delivery_min.quantile(0.9), 2),
        "late_pct": round(100 * valid.is_late.mean(), 1),
        "late_pct_jan": float(kpis.late_pct.iloc[0]),
        "late_pct_jun": float(kpis.late_pct.iloc[-1]),
        "worst_stores": scorecard.head(3)[["store_id", "store_name", "late_pct"]].to_dict("records"),
        "best_store": scorecard.iloc[-1][["store_id", "store_name", "late_pct"]].to_dict(),
        "model_r2": round(model.rsquared, 3),
        "model_drivers": coefs.to_dict("records"),
        "basket_orders_analysed": int(n_baskets),
        "top_basket_rules": rules.head(8).to_dict("records"),
        "incident": incident,
        "whatif_staffing_S07": s07,
        "whatif_staffing_S03": s03,
        "whatif_picking_S10": s10,
        "whatif_new_store_best": best,
        "revenue_impact": impact,
    }
    (REPORTS / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    # ------------------------------- charts
    heat = pd.read_csv(PROCESSED / "store_hour_heatmap.csv")
    drivers = pd.read_csv(PROCESSED / "late_drivers.csv")
    breakdown = pd.read_csv(PROCESSED / "delivery_time_breakdown.csv")
    retention = pd.read_csv(PROCESSED / "retention_first_order.csv")
    rating = pd.read_csv(PROCESSED / "rating_vs_lateness.csv")
    stock = pd.read_csv(PROCESSED / "stockouts.csv")
    fig_dir = REPORTS / "figures"
    chart_store_late(scorecard, fig_dir / "01_store_late_rate.png")
    chart_breakdown(breakdown, fig_dir / "02_delivery_time_breakdown.png")
    chart_drivers(drivers, fig_dir / "03_late_rate_drivers.png")
    chart_heatmap(heat, fig_dir / "04_store_hour_heatmap.png")
    chart_incident(weekly, incident, fig_dir / "05_incident_detection.png")
    chart_retention(retention, fig_dir / "06_retention_after_first_order.png")
    chart_rating(rating, fig_dir / "07_rating_vs_lateness.png")
    chart_stockouts(stock, fig_dir / "08_stockout_lost_revenue.png")
    chart_basket_rules(rules, fig_dir / "09_basket_rules.png")
    chart_expansion_map(valid, stores, expansion, fig_dir / "10_expansion_map.png")
    con.close()

    print(f"model R^2 = {model.rsquared:.3f}")
    print(json.dumps({k: metrics[k] for k in ["late_pct", "incident", "whatif_staffing_S07",
                                              "whatif_staffing_S03", "whatif_picking_S10",
                                              "whatif_new_store_best", "revenue_impact"]}, indent=2, default=str))
    print(rules.head(10).to_string())


if __name__ == "__main__":
    main()
