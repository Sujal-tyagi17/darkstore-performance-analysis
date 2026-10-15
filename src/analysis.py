"""
Python analysis layer on top of the DuckDB warehouse (India-wide).

  1. Delivery-time driver model (OLS, store fixed effects, per-city cost of distance)
  2. Market basket analysis (FP-Growth association rules)
  3. Incident detection: weekly late-rate jumps per store, adjusted for city-wide events
  4. What-if simulations for every diagnosed problem
       a) add riders where orders wait for riders
       b) fix picking where in-store work is slow
       c) open a new dark store where far-away demand clusters (per city)
  5. Ranked national action plan
  6. Revenue impact of late deliveries

Outputs:
  data/processed/*.csv      tables for the dashboard
  reports/metrics.json      headline numbers quoted in the README
  reports/figures/*.png     charts used in the README and notebook

Run after build_warehouse.py:  python src/analysis.py
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.formula.api as smf  # noqa: E402
from mlxtend.frequent_patterns import association_rules, fpgrowth  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402

import charts  # noqa: E402
from build_warehouse import PROCESSED, REPORTS, connect  # noqa: E402

ORDERS_PER_RIDER_HOUR = 2.2
TARGET_UTILIZATION = 0.85
FAR_KM = 3.5
N_DAYS = 181


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
        SELECT o.*, c.lat AS cust_lat, c.lon AS cust_lon, c.area, d.is_weekend
        FROM fact_orders o
        JOIN dim_customer c USING (customer_id)
        JOIN dim_date d ON d.date = o.order_date
        ORDER BY o.order_id
    """).df()
    orders["order_date"] = pd.to_datetime(orders.order_date)
    stores = con.execute("SELECT * FROM dim_store ORDER BY store_id").df()
    cities = con.execute("SELECT * FROM dim_city ORDER BY city_code").df()
    items = con.execute("""
        SELECT i.order_id, p.product_name
        FROM fact_order_items i JOIN dim_product p USING (sku_id)
        WHERE i.status = 'Delivered'
        ORDER BY i.order_id, i.line_no
    """).df()
    return orders, stores, cities, items


# ---------------------------------------------------------------------------
# 1. Driver model
# ---------------------------------------------------------------------------
def driver_model(valid: pd.DataFrame, cities: pd.DataFrame):
    d = valid.copy()
    for w, col in [("Rain", "rain"), ("Heavy Rain", "heavy_rain"), ("Fog", "fog"), ("Heatwave", "heatwave")]:
        d[col] = (d.weather == w).astype(int)
    d["peak_traffic"] = d.order_hour.isin([8, 9, 10, 17, 18, 19, 20, 21]).astype(int)
    d["util_over_75_pp"] = np.maximum(0, d.rider_utilization - 0.75) * 100
    d["weekend"] = d.is_weekend.astype(int)
    model = smf.ols(
        "delivery_min ~ C(city_code):distance_km + rain + heavy_rain + fog + heatwave + peak_traffic"
        " + util_over_75_pp + item_lines + weekend + C(store_id, Treatment('BLR01'))",
        data=d,
    ).fit(cov_type="HC1")
    ci = model.conf_int()
    labels = {
        "rain": "Rain (vs clear)", "heavy_rain": "Heavy rain (vs clear)", "fog": "Fog (vs clear)",
        "heatwave": "Heatwave (vs clear)", "peak_traffic": "Peak traffic hour",
        "util_over_75_pp": "Each +10 pts rider utilisation above 75%",
        "item_lines": "Each extra item in the basket", "weekend": "Weekend",
    }
    rows = []
    for var, label in labels.items():
        scale = 10 if var == "util_over_75_pp" else 1
        rows.append({"group": "Condition", "driver": label, "minutes_added": round(model.params[var] * scale, 2),
                     "ci_low": round(ci.loc[var, 0] * scale, 2), "ci_high": round(ci.loc[var, 1] * scale, 2),
                     "p_value": float(f"{model.pvalues[var]:.2g}")})
    names = dict(zip(cities.city_code, cities.city_name))
    for name in model.params.index:
        if name.startswith("C(city_code)"):
            code = name.split("[")[1].split("]")[0]
            rows.append({"group": "Minutes per extra km", "driver": names[code],
                         "minutes_added": round(model.params[name], 2),
                         "ci_low": round(ci.loc[name, 0], 2), "ci_high": round(ci.loc[name, 1], 2),
                         "p_value": float(f"{model.pvalues[name]:.2g}")})
        elif name.startswith("C(store_id"):
            sid = name.split("[T.")[1].rstrip("]")
            rows.append({"group": "Store effect (vs BLR01, all else equal)", "driver": sid,
                         "minutes_added": round(model.params[name], 2),
                         "ci_low": round(ci.loc[name, 0], 2), "ci_high": round(ci.loc[name, 1], 2),
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
    rules = rules[(rules.confidence >= 0.25) & (rules.antecedents.apply(len) <= 2)
                  & (rules.consequents.apply(len) == 1)]
    rules = rules.assign(
        if_customer_buys=rules.antecedents.apply(lambda s: " + ".join(sorted(s))),
        they_also_buy=rules.consequents.apply(lambda s: next(iter(s))),
    )
    rules["pair"] = rules.apply(lambda r: frozenset(r.antecedents | r.consequents), axis=1)
    rules = rules.sort_values(["confidence", "if_customer_buys"], ascending=[False, True]).drop_duplicates("pair")
    out = (rules[["if_customer_buys", "they_also_buy", "support", "confidence", "lift"]]
           .sort_values(["lift", "if_customer_buys"], ascending=[False, True]).head(25).round(3).reset_index(drop=True))
    out["orders_with_both"] = (out.support * len(basket)).round().astype(int)
    out.to_csv(PROCESSED / "basket_rules.csv", index=False)
    return out, len(basket)


# ---------------------------------------------------------------------------
# 3. Incident detection (city-adjusted)
# ---------------------------------------------------------------------------
def detect_incidents(con):
    wk = pd.read_csv(PROCESSED / "weekly_store_trend.csv", parse_dates=["week_start"])
    wk = wk[wk.orders >= 60].sort_values(["store_id", "week_start"]).copy()
    g = wk.groupby("store_id")
    wk["baseline_late_pct"] = g.late_pct.transform(lambda s: s.shift(1).rolling(8, min_periods=4).mean())
    wk["baseline_std"] = g.late_pct.transform(lambda s: s.shift(1).rolling(8, min_periods=4).std())
    wk["z_score"] = (wk.late_pct - wk.baseline_late_pct) / wk.baseline_std

    # City-wide swings (Mumbai monsoon, Delhi fog) hit every store in a city: subtract them.
    city = (wk.assign(late_n=wk.late_pct * wk.orders).groupby(["city_code", "week_start"])
            .agg(late_n=("late_n", "sum"), n=("orders", "sum")).reset_index())
    city["city_late_pct"] = city.late_n / city.n
    city["city_baseline"] = city.groupby("city_code").city_late_pct.transform(
        lambda s: s.shift(1).rolling(8, min_periods=4).mean())
    wk = wk.merge(city[["city_code", "week_start", "city_late_pct", "city_baseline"]],
                  on=["city_code", "week_start"], how="left")
    wk["jump_vs_city_pts"] = (wk.late_pct - wk.baseline_late_pct) - (wk.city_late_pct - wk.city_baseline)
    wk["raw_jump_pts"] = wk.late_pct - wk.baseline_late_pct

    # Alert rule: a week >3 std devs above the store's own baseline, >10 pts worse than the
    # city's own swing, and still >8 pts worse the following week (sustained, not noise).
    wk["next_jump_vs_city_pts"] = wk.groupby("store_id").jump_vs_city_pts.shift(-1)
    wk["next_raw_jump_pts"] = wk.groupby("store_id").raw_jump_pts.shift(-1)
    alerts = wk[(wk.z_score > 3) & (wk.jump_vs_city_pts > 10) & (wk.next_jump_vs_city_pts > 8)].copy()
    alerts = alerts.sort_values("week_start").groupby("store_id").head(1)
    alerts = alerts.sort_values("jump_vs_city_pts", ascending=False)

    # the same rule WITHOUT the city adjustment, to show how many false alarms it avoids
    naive = wk[(wk.z_score > 3) & (wk.raw_jump_pts > 10) & (wk.next_raw_jump_pts > 8)].groupby("store_id").head(1)
    naive[["store_id", "city_code", "week_start", "late_pct", "raw_jump_pts", "jump_vs_city_pts"]].round(2).to_csv(
        PROCESSED / "naive_alerts.csv", index=False)

    incidents = []
    for a in alerts.itertuples():
        start = a.week_start
        q = lambda lo, hi: con.execute(f"""
            SELECT avg(riders_on_shift), avg(rider_wait_min), 100*avg(is_late::INT), avg(delivery_min),
                   avg(pick_min), avg(travel_min), count(*)
            FROM fact_orders WHERE valid_timing AND store_id = '{a.store_id}'
              AND order_date >= DATE '{lo}' AND order_date < DATE '{hi}'""").fetchone()
        before = q((start - pd.Timedelta(days=28)).date(), start.date())
        during = q(start.date(), (start + pd.Timedelta(days=14)).date())
        last4 = q(pd.Timestamp("2026-06-03").date(), pd.Timestamp("2026-07-01").date())
        ongoing = last4[2] - before[2] > 10
        incidents.append({
            "store_id": a.store_id, "city_code": a.city_code, "week_detected": str(start.date()),
            "status": "Ongoing" if ongoing else "Resolved",
            "late_pct_before": round(before[2], 1), "late_pct_during": round(during[2], 1),
            "late_pct_last_4_weeks": round(last4[2], 1),
            "riders_on_shift_before": round(before[0], 2), "riders_on_shift_during": round(during[0], 2),
            "rider_wait_min_before": round(before[1], 2), "rider_wait_min_during": round(during[1], 2),
            "pick_min_before": round(before[4], 2), "pick_min_during": round(during[4], 2),
            "travel_min_before": round(before[5], 2), "travel_min_during": round(during[5], 2),
            "root_cause": ("Fewer riders on shift" if during[0] < 0.75 * before[0]
                           else "Rider wait up, riders unchanged" if (during[1] - before[1]) > max(during[4] - before[4], during[5] - before[5])
                           else "Other"),
        })
    inc = pd.DataFrame(incidents)
    alerts = alerts.merge(inc[["store_id", "status", "root_cause"]], on="store_id", how="left")
    num = alerts.select_dtypes("number").columns
    alerts[num] = alerts[num].round(2)
    alerts.to_csv(PROCESSED / "incident_alerts.csv", index=False)
    mon = wk[["store_id", "city_code", "week_start", "late_pct", "baseline_late_pct", "z_score", "city_late_pct",
              "city_baseline", "jump_vs_city_pts"]].copy()
    num = mon.select_dtypes("number").columns
    mon[num] = mon[num].round(2)
    mon.to_csv(PROCESSED / "incident_monitor_weekly.csv", index=False)
    return wk, inc, len(naive)


# ---------------------------------------------------------------------------
# 4. What-if simulations
# ---------------------------------------------------------------------------
def network_wait_curve(valid: pd.DataFrame):
    bins = np.arange(0, 3.01, 0.1)
    v = valid.assign(b=pd.cut(valid.rider_utilization, bins, include_lowest=True))
    curve = v.groupby("b", observed=True).rider_wait_min.median()
    return np.array([iv.mid for iv in curve.index]), curve.to_numpy()


def staffing_gap(con, store_id, since=None):
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
    by_hour = pd.DataFrame({"hour": df.hour, "gap": gap}).groupby("hour").gap.sum() / days
    return round(gap.sum() / days, 1), sorted(int(h) for h in by_hour.nlargest(4).index)


def whatif_staffing(valid, con, curve, store_id, since=None):
    d = valid[valid.store_id == store_id]
    if since:
        d = d[d.order_date >= pd.Timestamp(since)]
    needed = np.ceil(d.store_orders_in_hour / (ORDERS_PER_RIDER_HOUR * TARGET_UTILIZATION)).clip(lower=1)
    riders_new = np.maximum(d.riders_on_shift, needed)
    util_new = d.store_orders_in_hour / (riders_new * ORDERS_PER_RIDER_HOUR)
    mids, med = curve
    ratio = np.interp(util_new, mids, med) / np.maximum(np.interp(d.rider_utilization, mids, med), 0.1)
    wait_new = d.rider_wait_min * ratio
    late_new = (d.pick_min + wait_new + d.travel_min) > d.promised_eta_min
    extra, hours = staffing_gap(con, store_id, since)
    days = d.order_date.nunique()
    return {
        "late_pct_now": round(100 * d.is_late.mean(), 1),
        "late_pct_after": round(100 * late_new.mean(), 1),
        "avg_delivery_now": round(d.delivery_min.mean(), 2),
        "avg_delivery_after": round((d.pick_min + wait_new + d.travel_min).mean(), 2),
        "orders_per_day": round(len(d) / days, 1),
        "late_avoided_per_day": round((d.is_late.sum() - late_new.sum()) / days, 1),
        "effort": f"+{extra:.0f} rider-hours a day, mostly {', '.join(f'{h}:00' for h in hours)}",
    }


def whatif_picking(valid, store_id):
    d = valid[valid.store_id == store_id]
    target = valid[valid.store_id != store_id].pick_min.mean()
    new_pick = d.pick_min * (target / d.pick_min.mean())
    late_new = (new_pick + d.rider_wait_min + d.travel_min) > d.promised_eta_min
    days = d.order_date.nunique()
    return {
        "late_pct_now": round(100 * d.is_late.mean(), 1),
        "late_pct_after": round(100 * late_new.mean(), 1),
        "avg_delivery_now": round(d.delivery_min.mean(), 2),
        "avg_delivery_after": round((new_pick + d.rider_wait_min + d.travel_min).mean(), 2),
        "orders_per_day": round(len(d) / days, 1),
        "late_avoided_per_day": round((d.is_late.sum() - late_new.sum()) / days, 1),
        "effort": f"Cut picking from {d.pick_min.mean():.1f} to {target:.1f} min an order",
    }


def whatif_new_stores(valid, orders, stores, cities):
    """Score every under-served neighbourhood as a possible new dark-store site.

    For each neighbourhood with many far-away orders, place a store at the centre of its
    customers, re-route every order in the city that would be closer to it, scale travel
    time by the new distance and re-apply the ETA tiers. Keep the best site per city,
    plus a second one if it is far enough from the first.
    """
    road = dict(zip(cities.city_code, cities.road_factor))
    names = dict(zip(cities.city_code, cities.city_name))
    area = (valid.groupby(["city_code", "area"])
            .agg(orders=("order_id", "size"), far_share=("distance_km", lambda x: (x > FAR_KM).mean()),
                 lat=("cust_lat", "mean"), lon=("cust_lon", "mean")).reset_index())
    cands = area[(area.far_share >= 0.4) & (area.orders >= 700)]
    results = []
    for c in cands.itertuples():
        v = valid[valid.city_code == c.city_code]
        new_d = haversine_km(v.cust_lat, v.cust_lon, c.lat, c.lon) * road[c.city_code] + 0.15
        moved = new_d < v.distance_km - 0.3
        d, nd = v[moved], new_d[moved]
        travel_new = 0.8 + (d.travel_min - 0.8).clip(lower=0) * (nd / d.distance_km)
        late_new = (d.pick_min + d.rider_wait_min + travel_new) > promise_for(nd)
        city_late_new = (v.is_late.sum() - d.is_late.sum() + late_new.sum()) / len(v)
        delivered = orders[orders.order_id.isin(d.order_id) & orders.is_delivered]
        results.append({
            "city_code": c.city_code, "city_name": names[c.city_code],
            "candidate_site_near": c.area, "lat": round(c.lat, 4), "lon": round(c.lon, 4),
            "currently_served_by": d.store_id.value_counts().index[0],
            "area_far_orders_pct": round(100 * c.far_share, 1),
            "orders_reassigned_per_day": round(moved.sum() / N_DAYS, 1),
            "gmv_reassigned_6m_inr": round(delivered.order_value.sum()),
            "avg_distance_now_km": round(d.distance_km.mean(), 2),
            "avg_distance_new_km": round(nd.mean(), 2),
            "late_pct_now": round(100 * d.is_late.mean(), 1),
            "late_pct_new": round(100 * late_new.mean(), 1),
            "avg_delivery_now": round(d.delivery_min.mean(), 2),
            "avg_delivery_new": round((d.pick_min + d.rider_wait_min + travel_new).mean(), 2),
            "late_avoided_per_day": round((d.is_late.sum() - late_new.sum()) / N_DAYS, 1),
            "city_late_pct_now": round(100 * v.is_late.mean(), 2),
            "city_late_pct_new": round(100 * city_late_new, 2),
        })
    res = pd.DataFrame(results).sort_values(["late_avoided_per_day", "city_code"], ascending=[False, True])
    keep = []
    for code, g in res.groupby("city_code", sort=False):
        chosen = []
        for r in g.itertuples():
            if all(haversine_km(r.lat, r.lon, k.lat, k.lon) > 3 for k in chosen):
                chosen.append(r)
            if len(chosen) == 2:
                break
        keep += [k.Index for k in chosen]
    res = res.loc[keep].sort_values(["late_avoided_per_day", "city_code"], ascending=[False, True]).reset_index(drop=True)
    res.insert(0, "rank", range(1, len(res) + 1))
    res.to_csv(PROCESSED / "expansion_candidates.csv", index=False)
    return res


def promise_radius(valid, cities):
    """How far can each city deliver while still hitting 10 minutes on 80% of orders?"""
    rows = []
    for code, name in zip(cities.city_code, cities.city_name):
        v = valid[valid.city_code == code].sort_values("distance_km")
        # share of orders within radius r that arrive in <= 10 min, for every r
        cum_ok = (v.delivery_min.to_numpy() <= 10).cumsum() / np.arange(1, len(v) + 1)
        dist = v.distance_km.to_numpy()
        idx = np.where((cum_ok >= 0.8) & (np.arange(len(v)) >= 50))[0]
        radius = round(float(dist[idx.max()]), 2) if len(idx) else 0.0
        rows.append({"city_code": code, "city_name": name, "radius_10min_km": radius,
                     "orders_within_radius_pct": round(100 * (v.distance_km <= radius).mean(), 1),
                     "travel_min_per_km": round(v.travel_min.sum() / v.distance_km.sum(), 2)})
    out = pd.DataFrame(rows).sort_values("radius_10min_km")
    out.to_csv(PROCESSED / "promise_radius.csv", index=False)
    return out


# ---------------------------------------------------------------------------
# 5. Action plan
# ---------------------------------------------------------------------------
def build_action_plan(valid, orders, con, stores, incidents, expansion):
    breakdown = pd.read_csv(PROCESSED / "delivery_time_breakdown.csv")
    names = dict(zip(stores.store_id, stores.store_name.str.replace("DS ", "", regex=False)))
    cities = dict(zip(stores.store_id, stores.city_name))
    curve = network_wait_curve(valid)
    actions = []
    ongoing = {r.store_id: r.week_detected for r in incidents.itertuples() if r.status == "Ongoing"} if len(incidents) else {}

    for r in breakdown.itertuples():
        if r.store_id in ongoing:
            sim = whatif_staffing(valid, con, curve, r.store_id, since=ongoing[r.store_id])
            since_txt = pd.Timestamp(ongoing[r.store_id]).strftime("%d %b").lstrip("0")
            actions.append({"type": "Riders", "problem": f"Riders on shift halved from the week of {since_txt} and have not recovered",
                            "action": "Restore rider capacity: re-hire and add incentive shifts", **sim,
                            "store_id": r.store_id})
        elif r.primary_bottleneck == "Rider shortage":
            sim = whatif_staffing(valid, con, curve, r.store_id)
            actions.append({"type": "Riders", "problem": f"Orders wait {r.rider_wait_min:.1f} min for a rider "
                                                         f"(India avg {r.rider_wait_min - r.wait_gap_vs_india:.1f})",
                            "action": "Add rider shifts at peak hours", **sim, "store_id": r.store_id})
        elif r.primary_bottleneck == "Slow picking":
            sim = whatif_picking(valid, r.store_id)
            actions.append({"type": "Picking", "problem": f"Picking takes {r.pick_min:.1f} min "
                                                          f"(India avg {r.pick_min - r.pick_gap_vs_india:.1f})",
                            "action": "Move fast-selling items next to packing and fix the store layout", **sim, "store_id": r.store_id})
    for a in actions:
        a["city_name"] = cities[a["store_id"]]
        a["where"] = f"{names[a['store_id']]} ({a['store_id']})"

    for e in expansion.itertuples():
        if e.late_avoided_per_day < 2.5:
            continue
        actions.append({
            "type": "New store", "store_id": e.currently_served_by, "city_name": e.city_name,
            "where": f"New site near {e.candidate_site_near}",
            "problem": f"{e.orders_reassigned_per_day:.0f} orders/day travel {e.avg_distance_now_km:.1f} km on average",
            "action": f"Open a dark store near {e.candidate_site_near}",
            "effort": "One new site, about 3 months to launch",
            "late_pct_now": e.late_pct_now, "late_pct_after": e.late_pct_new,
            "avg_delivery_now": e.avg_delivery_now, "avg_delivery_after": e.avg_delivery_new,
            "orders_per_day": e.orders_reassigned_per_day, "late_avoided_per_day": e.late_avoided_per_day,
        })
    plan = pd.DataFrame(actions)
    plan = plan.sort_values(["late_avoided_per_day", "where"], ascending=[False, True]).reset_index(drop=True)
    plan.insert(0, "priority", range(1, len(plan) + 1))
    plan = plan[["priority", "type", "city_name", "where", "store_id", "problem", "action", "effort",
                 "orders_per_day", "late_pct_now", "late_pct_after", "avg_delivery_now", "avg_delivery_after",
                 "late_avoided_per_day"]]
    plan.to_csv(PROCESSED / "action_plan.csv", index=False)
    return plan


# ---------------------------------------------------------------------------
# 6. Revenue impact
# ---------------------------------------------------------------------------
def revenue_impact(orders):
    ret = pd.read_csv(PROCESSED / "retention_first_order.csv")
    ret = ret[ret.city_code == "IN"]
    on_time = ret[ret.first_order_experience == "On time"].iloc[0]
    late = ret[ret.first_order_experience.str.startswith("Late")]
    late_repeat = (late.repeat_within_30d_pct * late.customers).sum() / late.customers.sum()
    late_next = (late.avg_orders_next_30d * late.customers).sum() / late.customers.sum()
    aov = orders.loc[orders.is_delivered, "order_value"].mean()
    stock = pd.read_csv(PROCESSED / "stockouts.csv")
    canc = pd.read_csv(PROCESSED / "cancellations.csv")
    slow = canc[canc.cancel_reason == "Delivery taking too long"]
    return {
        "aov_inr": round(aov, 1),
        "repeat_30d_on_time_pct": float(on_time.repeat_within_30d_pct),
        "repeat_30d_late_pct": round(late_repeat, 1),
        "repeat_gap_pp": round(on_time.repeat_within_30d_pct - late_repeat, 1),
        "orders_lost_per_late_first_order_30d": round(on_time.avg_orders_next_30d - late_next, 2),
        "gmv_lost_per_1000_late_first_orders_inr": round(1000 * (on_time.avg_orders_next_30d - late_next) * aov),
        "stockout_lost_revenue_6m_inr": round(stock.lost_revenue_inr.sum()),
        "stockout_lost_revenue_per_month_inr": round(stock.lost_revenue_inr.sum() / 6),
        "icecream_small_freezer_lost_inr": round(stock[(stock.category == "Ice Cream & Frozen")
                                                       & stock.store_id.isin(["BLR05", "BLR10", "MUM05", "AMD03"])]
                                                 .lost_revenue_inr.sum()),
        "slow_delivery_cancellations_6m": int(slow.cancelled_orders.sum()),
        "slow_delivery_cancel_gmv_6m_inr": round(slow.est_lost_gmv_inr.sum()),
    }


# ---------------------------------------------------------------------------
def main():
    (REPORTS / "figures").mkdir(parents=True, exist_ok=True)
    for old in (REPORTS / "figures").glob("*.png"):
        old.unlink()
    con = connect(read_only=True)
    orders, stores, cities, items = load(con)
    valid = orders[orders.valid_timing].copy()

    model, coefs = driver_model(valid, cities)
    rules, n_baskets = basket_analysis(items)
    weekly, incidents, naive_alerts = detect_incidents(con)
    expansion = whatif_new_stores(valid, orders, stores, cities)
    radius = promise_radius(valid, cities)
    plan = build_action_plan(valid, orders, con, stores, incidents, expansion)
    impact = revenue_impact(orders)

    city_sc = pd.read_csv(PROCESSED / "city_scorecard.csv")
    store_sc = pd.read_csv(PROCESSED / "store_scorecard.csv")
    kpis = pd.read_csv(PROCESSED / "monthly_kpis.csv")
    india = kpis[kpis.city_code == "IN"]
    city_weekly = pd.read_csv(PROCESSED / "weekly_city_trend.csv", parse_dates=["week_start"])

    def month_late(code, m):
        k = kpis[(kpis.city_code == code)]
        return float(k.late_pct.iloc[m - 1])

    metrics = {
        "period": "2026-01-01 to 2026-06-30",
        "cities": int(len(cities)),
        "stores": int(len(stores)),
        "orders": int(len(orders)),
        "delivered_orders": int(orders.is_delivered.sum()),
        "customers": int(orders.customer_id.nunique()),
        "gmv_inr": round(orders.loc[orders.is_delivered, "order_value"].sum()),
        "avg_delivery_min": round(valid.delivery_min.mean(), 2),
        "p90_delivery_min": round(valid.delivery_min.quantile(0.9), 2),
        "late_pct": round(100 * valid.is_late.mean(), 1),
        "late_pct_jan": float(india.late_pct.iloc[0]),
        "late_pct_jun": float(india.late_pct.iloc[-1]),
        "orders_jan": int(india.orders.iloc[0]),
        "orders_jun": int(india.orders.iloc[-1]),
        "best_city": city_sc.iloc[0][["city_name", "late_pct"]].to_dict(),
        "worst_city": city_sc.iloc[-1][["city_name", "late_pct"]].to_dict(),
        "city_scorecard": city_sc[["city_code", "city_name", "stores", "orders", "late_pct", "avg_delivery_min",
                                   "avg_rating"]].to_dict("records"),
        "worst_stores": store_sc.head(5)[["store_id", "store_name", "city_name", "late_pct"]].to_dict("records"),
        "city_events": {
            "mumbai_late_may": month_late("MUM", 5), "mumbai_late_jun": month_late("MUM", 6),
            "delhi_late_jan": month_late("DEL", 1), "delhi_late_mar": month_late("DEL", 3),
        },
        "model_r2": round(model.rsquared, 3),
        "model_drivers": coefs.to_dict("records"),
        "basket_orders_analysed": int(n_baskets),
        "top_basket_rules": rules.head(8).to_dict("records"),
        "incidents": incidents.to_dict("records"),
        "naive_alert_count": int(naive_alerts),
        "city_adjusted_alert_count": int(len(incidents)),
        "action_plan_top": plan.head(10).to_dict("records"),
        "action_plan_total_late_avoided_per_day": round(plan.late_avoided_per_day.sum(), 1),
        "late_orders_per_day_now": round(valid.is_late.sum() / N_DAYS, 1),
        "expansion_top": expansion.head(5).to_dict("records"),
        "promise_radius": radius.to_dict("records"),
        "revenue_impact": impact,
    }
    (REPORTS / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    # ------------------------------- charts
    fig = REPORTS / "figures"
    charts.chart_city_late(city_sc, metrics["late_pct"], fig / "01_city_late_rate.png")
    charts.chart_city_weekly(city_weekly, fig / "02_city_weekly_trend.png")
    charts.chart_weather_city(pd.read_csv(PROCESSED / "late_drivers.csv"), fig / "03_weather_by_city.png")
    charts.chart_store_breakdown(pd.read_csv(PROCESSED / "delivery_time_breakdown.csv"), stores,
                                 fig / "04_store_bottlenecks.png")
    charts.chart_drivers(pd.read_csv(PROCESSED / "late_drivers.csv"), fig / "05_late_rate_drivers.png")
    charts.chart_distance_cost(coefs, fig / "06_minutes_per_km_by_city.png")
    charts.chart_incidents(weekly, incidents, stores, fig / "07_incident_detection.png")
    charts.chart_retention(pd.read_csv(PROCESSED / "retention_first_order.csv"), fig / "08_retention_after_first_order.png")
    charts.chart_rating(pd.read_csv(PROCESSED / "rating_vs_lateness.csv"), fig / "09_rating_vs_lateness.png")
    charts.chart_stockouts(pd.read_csv(PROCESSED / "stockouts.csv"), fig / "10_stockout_lost_revenue.png")
    charts.chart_basket_rules(rules, fig / "11_basket_rules.png")
    charts.chart_action_plan(plan, fig / "12_action_plan.png")
    charts.chart_promise_radius(radius, fig / "13_ten_minute_radius.png")
    con.close()

    print(f"model R^2 = {model.rsquared:.3f} | incidents: {len(incidents)} (naive rule: {naive_alerts})")
    print(plan[["priority", "type", "city_name", "where", "late_pct_now", "late_pct_after", "late_avoided_per_day"]]
          .to_string(index=False))
    print(radius.to_string(index=False))
    print(expansion[["rank", "city_name", "candidate_site_near", "orders_reassigned_per_day", "avg_distance_now_km",
                     "avg_distance_new_km", "late_pct_now", "late_pct_new", "late_avoided_per_day"]].to_string(index=False))


if __name__ == "__main__":
    main()
