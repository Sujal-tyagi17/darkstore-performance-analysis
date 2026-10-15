import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lib

c = lib.colors()
names = lib.city_names()
label, start, end = lib.period()
S = lib.stores()
S = S[S.city_code.isin(lib.selected_cities())]
sc = lib.processed("store_scorecard").set_index("store_id")
opts = sorted(S.store_id, key=lambda s: -sc.loc[s, "late_pct"])
fmt = {r.store_id: f"{r.locality}, {r.city_name} ({r.store_id})" for r in S.itertuples()}
sid = st.selectbox("Store (worst first)", opts, format_func=lambda s: fmt[s], key="store_pick")
store = S.set_index("store_id").loc[sid]
W = f"order_date BETWEEN DATE '{start}' AND DATE '{end}'"

stages = lib.q(f"""
    SELECT 'This store' who, avg(pick_min) pick, avg(rider_wait_min) wait, avg(travel_min) travel,
           avg(delivery_min) total, 100*avg(is_late::INT) late, avg(distance_km) dist, count(*) n
    FROM fact_orders WHERE valid_timing AND {W} AND store_id = '{sid}'
    UNION ALL
    SELECT '{store.city_name} average', avg(pick_min), avg(rider_wait_min), avg(travel_min), avg(delivery_min),
           100*avg(is_late::INT), avg(distance_km), count(*)
    FROM fact_orders WHERE valid_timing AND {W} AND city_code = '{store.city_code}'
    UNION ALL
    SELECT 'India average', avg(pick_min), avg(rider_wait_min), avg(travel_min), avg(delivery_min),
           100*avg(is_late::INT), avg(distance_km), count(*)
    FROM fact_orders WHERE valid_timing AND {W}""")
me, city, india = stages.iloc[0], stages.iloc[1], stages.iloc[2]
issue = lib.processed("delivery_time_breakdown").set_index("store_id").loc[sid, "primary_bottleneck"]
plan = lib.processed("action_plan")
action = plan[plan.store_id.eq(sid)]
incident = [i for i in lib.metrics()["incidents"] if i["store_id"] == sid]

story = {
    "Rider shortage": f"Orders wait {me.wait:.1f} min for a free rider, against {india.wait:.1f} min across India.",
    "Slow picking": f"Packing an order takes {me.pick:.1f} min, against {india.pick:.1f} min across India.",
    "Long distances": f"Riders travel {me.dist:.1f} km on average, against {india.dist:.1f} km across India.",
    "On par": "Every stage of delivery is close to the India average.",
}[issue]
lib.headline(f"{store.locality}: {me.late:.0f}% of orders arrive late.",
             f"{story} {'Main issue: ' + issue.lower() + '.' if issue != 'On par' else ''}")

def gap(a, b, unit=""):
    d = round(a - b, 1)
    return "same as India" if d == 0 else f"{d:+.1f}{unit} vs India"


lib.kpi_band([
    {"label": "Orders", "value": lib.num(me.n), "note": label},
    {"label": "Average delivery", "value": f"{me.total:.1f} min", "delta": f"{me.total - city.total:+.1f} min vs city",
     "good": me.total < city.total},
    {"label": "Picking", "value": f"{me.pick:.1f} min", "delta": gap(me.pick, india.pick, " min"),
     "good": me.pick < india.pick + 0.05},
    {"label": "Waiting for a rider", "value": f"{me.wait:.1f} min", "delta": gap(me.wait, india.wait, " min"),
     "good": me.wait < india.wait + 0.05},
    {"label": "Travel", "value": f"{me.travel:.1f} min", "delta": gap(me.travel, india.travel, " min"),
     "good": me.travel < india.travel + 0.05},
    {"label": "Store size", "value": f"{store.area_sqft:,} sq ft", "note": f"opened {pd.Timestamp(store.opened_on):%b %Y}"},
])

if incident:
    i = incident[0]
    lib.callouts([{"tone": "alert", "title": f"Alert raised in the week of {pd.Timestamp(i['week_detected']):%d %b} "
                                              f"({i['status'].lower()})",
                   "body": f"Riders on shift fell from {i['riders_on_shift_before']} to {i['riders_on_shift_during']} "
                           f"per hour; rider wait rose from {i['rider_wait_min_before']} to {i['rider_wait_min_during']} "
                           f"min and the late rate from {i['late_pct_before']:.0f}% to {i['late_pct_during']:.0f}%."}])
if len(action):
    a = action.iloc[0]
    lib.callouts([{"tone": "info" if a.type != "New store" else "ok", "title": f"Recommended: {a.action[0].lower() + a.action[1:]}",
                   "body": f"{a.effort}. Simulated late rate {a.late_pct_now:.0f}% → {a.late_pct_after:.0f}%, "
                           f"about {a.late_avoided_per_day:.0f} fewer late orders a day (priority #{a.priority} in India)."}])

left, right = st.columns(2, gap="large")
with left:
    lib.section("Where the minutes go", "Average minutes per delivered order, by stage.")
    fig = go.Figure()
    for col, nm, colr in [("pick", "Picking", c["blue"]), ("wait", "Waiting for a rider", c["orange"]),
                          ("travel", "Travel", c["aqua"])]:
        fig.add_trace(go.Bar(y=stages.who, x=stages[col], name=nm, orientation="h", marker_color=colr,
                             marker_line=dict(width=2, color="rgba(0,0,0,0)"),
                             hovertemplate=f"{nm}: %{{x:.2f}} min<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.35, legend=dict(traceorder="normal"))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Minutes")
    lib.plot(fig, 260)
with right:
    lib.section("Weekly late rate", f"This store against the rest of {store.city_name}.")
    wk = lib.q(f"""
        SELECT date_trunc('week', order_date) w, store_id = '{sid}' me, 100*avg(is_late::INT) late
        FROM fact_orders WHERE valid_timing AND {W} AND city_code = '{store.city_code}'
        GROUP BY 1, 2 HAVING count(DISTINCT order_date) = 7 ORDER BY 1""")
    fig = go.Figure()
    for flag, colr, nm, wd in [(False, c["grey"], f"Rest of {store.city_name}", 2), (True, c["blue"], "This store", 3)]:
        g = wk[wk.me == flag]
        fig.add_trace(go.Scatter(x=g.w, y=g.late, name=nm, line=dict(color=colr, width=wd),
                                 hovertemplate=f"{nm}: %{{y:.1f}}%<extra></extra>"))
    for i in incident:
        fig.add_vline(x=pd.Timestamp(i["week_detected"]).timestamp() * 1000, line_dash="dot", line_color=c["ink2"])
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title="Late %", rangemode="tozero", ticksuffix="%")
    lib.plot(fig, 260)

left, right = st.columns(2, gap="large")
hr = lib.q(f"""
    SELECT order_hour h, count(*) / count(DISTINCT order_date) per_day, 100*avg(is_late::INT) late,
           avg(rider_utilization) util
    FROM fact_orders WHERE valid_timing AND {W} AND store_id = '{sid}' GROUP BY 1 HAVING count(*) >= 40 ORDER BY 1""")
with left:
    lib.section("Orders by hour of day", "Average orders per day in each hour.")
    fig = go.Figure(go.Bar(x=hr.h, y=hr.per_day, marker_color=c["blue"],
                           hovertemplate="%{x}:00 — %{y:.1f} orders/day<extra></extra>"))
    fig.update_xaxes(title="Hour of day", dtick=2)
    fig.update_yaxes(title="Orders per day")
    lib.plot(fig, 260)
with right:
    lib.section("Late rate by hour of day", "Peaks show when the store runs out of capacity.")
    fig = go.Figure(go.Scatter(x=hr.h, y=hr.late, mode="lines+markers", line=dict(color=c["orange"], width=2.5),
                               customdata=hr.util,
                               hovertemplate="%{x}:00 — %{y:.1f}% late<br>rider load %{customdata:.0%}<extra></extra>"))
    fig.update_xaxes(title="Hour of day", dtick=2)
    fig.update_yaxes(title="Late %", rangemode="tozero", ticksuffix="%")
    lib.plot(fig, 260)

lib.section("Most-missed products here", "Items customers ordered that the store could not supply (Jan–Jun).")
so = lib.processed("stockouts")
so = so[so.store_id == sid].head(8)
st.dataframe(so[["product_name", "category", "times_requested", "stockout_pct", "lost_revenue_inr"]], hide_index=True,
             width="stretch", column_config={
                 "product_name": "Product", "category": "Category",
                 "times_requested": st.column_config.NumberColumn("Requested", format="localized"),
                 "stockout_pct": st.column_config.ProgressColumn("Unavailable", format="%.1f%%", min_value=0, max_value=35),
                 "lost_revenue_inr": st.column_config.NumberColumn("Lost sales (₹)", format="localized")})
