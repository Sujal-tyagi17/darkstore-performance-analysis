import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lib

c = lib.colors()
W = lib.where()
label, start, end = lib.period()

k = lib.q(f"""
    SELECT count(*) orders,
           sum(order_value) FILTER (WHERE is_delivered) gmv,
           avg(delivery_min) FILTER (WHERE valid_timing) avg_min,
           100*avg(is_late::INT) FILTER (WHERE valid_timing) late,
           100*avg((status='Cancelled')::INT) cancel,
           avg(rating) rating,
           count(DISTINCT customer_id) customers
    FROM fact_orders WHERE {W}""").iloc[0]
monthly = lib.q(f"""
    SELECT month(order_date) m, count(*) orders, sum(order_value) FILTER (WHERE is_delivered) gmv,
           avg(delivery_min) FILTER (WHERE valid_timing) avg_min,
           100*avg(is_late::INT) FILTER (WHERE valid_timing) late,
           100*avg((status='Cancelled')::INT) cancel, avg(rating) rating
    FROM fact_orders WHERE {lib.where().replace(f"DATE '{start}'", "DATE '2026-01-01'")}
    GROUP BY 1 ORDER BY 1""").set_index("m")
weekly = lib.q(f"""
    SELECT date_trunc('week', order_date) w, count(*) orders, sum(order_value) FILTER (WHERE is_delivered) gmv,
           avg(delivery_min) FILTER (WHERE valid_timing) avg_min,
           100*avg(is_late::INT) FILTER (WHERE valid_timing) late,
           100*avg((status='Cancelled')::INT) cancel, avg(rating) rating
    FROM fact_orders WHERE {W} GROUP BY 1 HAVING count(DISTINCT order_date) = 7 ORDER BY 1""")

m_first, m_last = int(pd.Timestamp(start).month), int(pd.Timestamp(end).month)
if m_first == m_last:
    m_first = m_last - 1
mn = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun"}
FULL = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June"}
cmp = f"{mn[m_last]} vs {mn[m_first]}"


def delta(col, fmt, higher_is_good):
    a, b = monthly.loc[m_first, col], monthly.loc[m_last, col]
    if col in ("orders", "gmv"):
        d = 100 * (b / a - 1)
        return f"{d:+.0f}% {cmp}", (d > 0) == higher_is_good
    d = b - a
    return f"{d:+{fmt}} {cmp}", (d > 0) == higher_is_good if abs(d) > 1e-9 else None


city = lib.processed("city_scorecard")
city = city[city.city_code.isin(lib.selected_cities())]
league = lib.q(f"""
    SELECT o.city_code, d.city_name, count(DISTINCT store_id) stores, count(*) orders,
           avg(delivery_min) FILTER (WHERE valid_timing) avg_min,
           100*avg(is_late::INT) FILTER (WHERE valid_timing) late,
           avg(rating) rating, sum(order_value) FILTER (WHERE is_delivered) gmv
    FROM fact_orders o JOIN dim_city d USING (city_code) WHERE {lib.where('o')}
    GROUP BY 1, 2 ORDER BY late""")
trend = lib.q(f"""
    SELECT city_code, date_trunc('week', order_date) w, 100*avg(is_late::INT) FILTER (WHERE valid_timing) late
    FROM fact_orders WHERE {W} GROUP BY 1, 2 HAVING count(DISTINCT order_date) = 7 ORDER BY 1, 2""")
league["weekly_late"] = league.city_code.map(trend.groupby("city_code").late.apply(lambda s: [round(x, 1) for x in s]))

# ---- headline -------------------------------------------------------------------
late_per_100 = round(k.late)
if len(league) > 1:
    worst, best = league.iloc[-1], league.iloc[0]
    deck = (f"{worst.city_name} is the least reliable city ({worst.late:.0f}% late) and {best.city_name} the most "
            f"({best.late:.0f}%). From January to {FULL[int(monthly.index[-1])]}, orders grew "
            f"{100 * (monthly.orders.iloc[-1] / monthly.orders.iloc[0] - 1):.0f}% and the late rate went from "
            f"{monthly.late.iloc[0]:.0f}% to {monthly.late.iloc[-1]:.0f}%.")
else:
    deck = f"{league.iloc[0].city_name}, {label}: {k.orders:,.0f} orders from {league.iloc[0].stores} dark stores."
lib.headline(f"{late_per_100} of every 100 orders arrived after the promised time.", deck)

d_orders = delta("orders", ".0f", True)
d_gmv = delta("gmv", ".0f", True)
d_min = delta("avg_min", ".1f", False)
d_late = delta("late", ".1f", False)
d_cancel = delta("cancel", ".1f", False)
d_rating = delta("rating", ".2f", True)
lib.kpi_band([
    {"label": "Orders", "value": lib.num(k.orders), "delta": d_orders[0], "good": d_orders[1],
     "spark": weekly.orders.tolist()},
    {"label": "Gross order value", "value": lib.inr(k.gmv), "delta": d_gmv[0], "good": d_gmv[1],
     "spark": weekly.gmv.tolist()},
    {"label": "Average delivery", "value": f"{k.avg_min:.1f} min", "delta": d_min[0].replace(" ", " min ", 1),
     "good": d_min[1], "spark": weekly.avg_min.tolist()},
    {"label": "Delivered late", "value": f"{k.late:.1f}%", "delta": d_late[0].replace(" ", " pts ", 1),
     "good": d_late[1], "spark": weekly.late.tolist(), "spark_color": "orange"},
    {"label": "Cancelled", "value": f"{k.cancel:.1f}%", "delta": d_cancel[0].replace(" ", " pts ", 1),
     "good": d_cancel[1], "spark": weekly.cancel.tolist()},
    {"label": "Customer rating", "value": f"{k.rating:.2f} / 5", "delta": d_rating[0], "good": d_rating[1],
     "spark": weekly.rating.tolist()},
])

# ---- city league + map -------------------------------------------------------------
left, right = st.columns([1.15, 1], gap="large")
with left:
    lib.section("Cities, most reliable first", "Late % = delivered after the ETA promised in the app.")
    st.dataframe(
        league[["city_name", "stores", "orders", "avg_min", "late", "rating", "weekly_late"]],
        hide_index=True, width="stretch", height=lib.table_height(len(league)),
        column_config={
            "city_name": st.column_config.TextColumn("City"),
            "stores": st.column_config.NumberColumn("Stores", width="small"),
            "orders": st.column_config.NumberColumn("Orders", format="localized", width="small"),
            "avg_min": st.column_config.NumberColumn("Avg min", format="%.1f", width="small"),
            "late": st.column_config.ProgressColumn("Late %", format="%.1f%%", min_value=0, max_value=50),
            "rating": st.column_config.NumberColumn("Rating", format="%.2f", width="small"),
            "weekly_late": st.column_config.LineChartColumn("Weekly late %", y_min=0, y_max=60, color=c["orange"],
                                                            width="medium"),
        },
    )
with right:
    lib.section("Where the orders are", "Bubble size = orders; colour = late %.")
    cc = lib.cities().merge(league, on=["city_code", "city_name"])
    fig = go.Figure(go.Scattermap(
        lat=cc.lat, lon=cc.lon, mode="markers+text", text=cc.city_name, textposition="top right",
        textfont=dict(size=13, color=c["ink"]),
        marker=dict(size=(cc.orders / cc.orders.max()) ** 0.5 * 46 + 10, color=cc.late, colorscale=lib.SEQ,
                    cmin=15, cmax=40, opacity=0.9,
                    colorbar=dict(title="Late %", thickness=10, len=0.6, x=1.0, outlinewidth=0)),
        customdata=cc[["orders", "late", "avg_min"]],
        hovertemplate="<b>%{text}</b><br>%{customdata[0]:,} orders<br>%{customdata[1]:.1f}% late"
                      "<br>%{customdata[2]:.1f} min average<extra></extra>",
    ))
    fig.update_layout(map=dict(style=c["map_style"], center=dict(lat=21.8, lon=78.8), zoom=3.75),
                      margin=dict(l=0, r=0, t=0, b=0), height=lib.table_height(len(league)) + 10)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": False}, theme=None)

# ---- where to look first -------------------------------------------------------------
lib.section("Where to look first", "The biggest problems in your selection, from the alert monitor and the "
                                    "simulated action plan.")
rows = []
m = lib.metrics()
sel = set(lib.selected_cities())
for inc in m["incidents"]:
    if inc["city_code"] in sel and inc["status"] == "Ongoing":
        store = lib.stores().set_index("store_id").loc[inc["store_id"]]
        rows.append({"tone": "alert", "title": f"{store.locality} ({inc['store_id']}) lost half its riders",
                     "body": f"Since the week of {pd.Timestamp(inc['week_detected']):%d %b}, riders per hour fell "
                             f"from {inc['riders_on_shift_before']} to {inc['riders_on_shift_during']} and the late "
                             f"rate jumped from {inc['late_pct_before']:.0f}% to {inc['late_pct_during']:.0f}%. "
                             f"It has not recovered."})
plan = lib.processed("action_plan")
names = lib.city_names()
plan = plan[plan.city_name.isin([names[x] for x in sel])]
for r in plan.head(4 - len(rows)).itertuples():
    if any(r.store_id in x["title"] for x in rows):
        continue
    rows.append({"tone": "info" if r.type != "New store" else "ok",
                 "title": f"{lib.TYPE_LABEL[r.type]}: {r.where}, {r.city_name}",
                 "body": f"{r.problem}. Simulated effect: late rate {r.late_pct_now:.0f}% → {r.late_pct_after:.0f}%, "
                         f"about {r.late_avoided_per_day:.0f} fewer late orders a day."})
lib.callouts(rows[:4])
st.page_link("views/actions.py", label="See the full action plan", icon=":material/checklist:")
