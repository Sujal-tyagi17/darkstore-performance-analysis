import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lib

c = lib.colors()
names = lib.city_names()
label, start, end = lib.period()
options = sorted(lib.selected_cities(), key=lambda x: names[x])

code = st.selectbox("City", options, format_func=lambda x: names[x], key="city_pick",
                    index=options.index("MUM") if "MUM" in options else 0)
name = names[code]
W = f"order_date BETWEEN DATE '{start}' AND DATE '{end}'"

k = lib.q(f"""
    SELECT count(*) orders, sum(order_value) FILTER (WHERE is_delivered) gmv,
           avg(delivery_min) FILTER (WHERE valid_timing) avg_min,
           100*avg(is_late::INT) FILTER (WHERE valid_timing) late,
           avg(rating) rating, avg(distance_km) dist, count(DISTINCT store_id) stores
    FROM fact_orders WHERE {W} AND city_code = '{code}'""").iloc[0]
india = lib.q(f"""
    SELECT avg(delivery_min) FILTER (WHERE valid_timing) avg_min, 100*avg(is_late::INT) FILTER (WHERE valid_timing) late,
           avg(rating) rating, avg(distance_km) dist, count(*) / count(DISTINCT store_id) per_store
    FROM fact_orders WHERE {W}""").iloc[0]
radius = lib.processed("promise_radius").set_index("city_code").loc[code]
coef = lib.processed("delivery_time_drivers_model")
per_km = coef[(coef.group == "Minutes per extra km") & (coef.driver == name)].minutes_added.iloc[0]

worse = k.late > india.late
lib.headline(f"{name}: {k.late:.0f} of every 100 orders arrive late.",
             f"That is {abs(k.late - india.late):.1f} points {'worse' if worse else 'better'} than India overall "
             f"({label}). Each extra kilometre adds {per_km:.2f} minutes here, so a true 10-minute promise only "
             f"reaches about {radius.radius_10min_km:.1f} km.")


def vs(a, b, unit, lower_good=True, fmt=".1f"):
    d = a - b
    return f"{d:+{fmt}}{unit} vs India", (d < 0) == lower_good if abs(d) > 1e-9 else None


lib.kpi_band([
    {"label": "Dark stores", "value": f"{k.stores:.0f}", "note": f"{k.orders / k.stores:,.0f} orders each"},
    {"label": "Orders", "value": lib.num(k.orders), "note": lib.inr(k.gmv)},
    {"label": "Average delivery", "value": f"{k.avg_min:.1f} min", "delta": vs(k.avg_min, india.avg_min, " min")[0],
     "good": vs(k.avg_min, india.avg_min, "")[1]},
    {"label": "Delivered late", "value": f"{k.late:.1f}%", "delta": vs(k.late, india.late, " pts")[0],
     "good": vs(k.late, india.late, "")[1]},
    {"label": "Average distance", "value": f"{k.dist:.2f} km", "delta": vs(k.dist, india.dist, " km", fmt=".2f")[0],
     "good": vs(k.dist, india.dist, "")[1]},
    {"label": "Customer rating", "value": f"{k.rating:.2f}", "delta": vs(k.rating, india.rating, "", False, ".2f")[0],
     "good": vs(k.rating, india.rating, "", False)[1]},
])

# ---- store map + table ---------------------------------------------------------------
st_tab = lib.q(f"""
    SELECT o.store_id, s.locality, s.lat, s.lon, count(*) orders,
           avg(delivery_min) FILTER (WHERE valid_timing) avg_min,
           100*avg(is_late::INT) FILTER (WHERE valid_timing) late,
           avg(pick_min) FILTER (WHERE valid_timing) pick, avg(rider_wait_min) FILTER (WHERE valid_timing) wait,
           avg(travel_min) FILTER (WHERE valid_timing) travel, avg(distance_km) dist, avg(rating) rating
    FROM fact_orders o JOIN dim_store s USING (store_id)
    WHERE {lib.where('o').split(' AND o.city_code')[0]} AND o.city_code = '{code}'
    GROUP BY ALL ORDER BY late DESC""")
wk = lib.q(f"""
    SELECT store_id, date_trunc('week', order_date) w, 100*avg(is_late::INT) FILTER (WHERE valid_timing) late
    FROM fact_orders WHERE {W} AND city_code = '{code}'
    GROUP BY 1, 2 HAVING count(DISTINCT order_date) = 7 ORDER BY 1, 2""")
st_tab["weekly"] = st_tab.store_id.map(wk.groupby("store_id").late.apply(lambda s: [round(x, 1) for x in s]))
diag = lib.processed("delivery_time_breakdown").set_index("store_id").primary_bottleneck
st_tab["issue"] = st_tab.store_id.map(diag).replace({"On par": "—"})

left, right = st.columns([1, 1.1], gap="large")
with left:
    lib.section(f"Stores and the customers they serve",
                "Grey dots are a sample of orders; store colour = late %.")
    pts = lib.q(f"""
        SELECT c.lat, c.lon, o.distance_km FROM fact_orders o JOIN dim_customer c USING (customer_id)
        WHERE o.city_code = '{code}' AND o.{W} USING SAMPLE 4000 ROWS""")
    fig = go.Figure()
    fig.add_trace(go.Scattermap(lat=pts.lat, lon=pts.lon, mode="markers", hoverinfo="skip", name="Orders",
                                marker=dict(size=4, color=c["grey"], opacity=0.55)))
    fig.add_trace(go.Scattermap(
        lat=st_tab.lat, lon=st_tab.lon, mode="markers+text", text=st_tab.locality, textposition="top right",
        textfont=dict(size=12, color=c["ink"]), name="Dark store",
        marker=dict(size=17, color=st_tab.late, colorscale=lib.SEQ, cmin=10, cmax=50,
                    colorbar=dict(title="Late %", thickness=10, len=0.5, outlinewidth=0)),
        customdata=st_tab[["store_id", "late", "avg_min"]],
        hovertemplate="<b>%{text}</b> (%{customdata[0]})<br>%{customdata[1]:.1f}% late, "
                      "%{customdata[2]:.1f} min average<extra></extra>"))
    fig.update_layout(map=dict(style=c["map_style"], center=dict(lat=pts.lat.mean(), lon=pts.lon.mean()), zoom=10.3),
                      margin=dict(l=0, r=0, t=0, b=0), height=470, showlegend=False)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})
with right:
    lib.section("Store scorecard", "Issue = the delivery stage furthest above the India average.")
    st.dataframe(
        st_tab[["store_id", "locality", "orders", "avg_min", "late", "issue", "weekly"]],
        hide_index=True, width="stretch", height=lib.table_height(len(st_tab)),
        column_config={
            "store_id": st.column_config.TextColumn("Store", width="small"),
            "locality": st.column_config.TextColumn("Locality"),
            "orders": st.column_config.NumberColumn("Orders", format="localized"),
            "avg_min": st.column_config.NumberColumn("Avg min", format="%.1f", width="small"),
            "late": st.column_config.ProgressColumn("Late %", format="%.1f%%", min_value=0, max_value=70),
            "issue": st.column_config.TextColumn("Main issue"),
            "weekly": st.column_config.LineChartColumn("Weekly late %", y_min=0, y_max=80, color=c["orange"]),
        })

# ---- trend + weather -------------------------------------------------------------------
left, right = st.columns(2, gap="large")
with left:
    lib.section(f"Weekly late rate, {name} vs India")
    t = lib.processed("weekly_city_trend")
    t["week_start"] = pd.to_datetime(t.week_start)
    t = t[(t.week_start >= start) & (t.week_start <= end)]
    fig = go.Figure()
    for cc, col, nm, wd in [("IN", c["grey"], "India", 2), (code, c["blue"], name, 3)]:
        g = t[t.city_code == cc]
        fig.add_trace(go.Scatter(x=g.week_start, y=g.late_pct, name=nm, mode="lines", line=dict(color=col, width=wd),
                                 hovertemplate=f"{nm}: %{{y:.1f}}%<extra></extra>"))
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title="Late %", rangemode="tozero", ticksuffix="%")
    lib.plot(fig, 320)
with right:
    lib.section(f"Weather in {name}", "Late % by the weather at the time of the order.")
    w = lib.q(f"""
        SELECT weather, count(*) orders, 100*avg(is_late::INT) late FROM fact_orders
        WHERE valid_timing AND {W} AND city_code = '{code}' GROUP BY 1""")
    order = ["Clear", "Cloudy", "Fog", "Heatwave", "Rain", "Heavy Rain"]
    w["o"] = w.weather.map({x: i for i, x in enumerate(order)})
    w = w.sort_values("o")
    fig = go.Figure(go.Bar(x=w.weather, y=w.late, marker_color=[c["orange"] if x in ("Rain", "Heavy Rain", "Fog", "Heatwave")
                                                               else c["grey"] for x in w.weather],
                           customdata=w.orders, text=[f"{v:.0f}%" for v in w.late], textposition="outside",
                           hovertemplate="%{x}: %{y:.1f}% late<br>%{customdata:,} orders<extra></extra>"))
    fig.update_yaxes(title="Late %", range=[0, max(85, w.late.max() + 10)], ticksuffix="%")
    lib.plot(fig, 320)
