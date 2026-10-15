import plotly.graph_objects as go
import streamlit as st

import lib

c = lib.colors()
W = lib.where()

d = lib.q(f"""
    WITH b AS (
        SELECT is_late,
               distance_band,
               CASE WHEN rider_utilization < 0.6 THEN 'under 60%' WHEN rider_utilization < 0.9 THEN '60–90%'
                    WHEN rider_utilization < 1.2 THEN '90–120%' ELSE 'over 120%' END util,
               CASE WHEN order_hour BETWEEN 6 AND 10 THEN 'Morning' WHEN order_hour BETWEEN 11 AND 16 THEN 'Afternoon'
                    WHEN order_hour BETWEEN 17 AND 21 THEN 'Evening peak' ELSE 'Late night' END part,
               weather
        FROM fact_orders WHERE valid_timing AND {W})
    SELECT 'Distance' drv, distance_band lvl, count(*) n, 100*avg(is_late::INT) late FROM b GROUP BY 1, 2
    UNION ALL SELECT 'Rider load', util, count(*), 100*avg(is_late::INT) FROM b GROUP BY 1, 2
    UNION ALL SELECT 'Weather', weather, count(*), 100*avg(is_late::INT) FROM b GROUP BY 1, 2
    UNION ALL SELECT 'Time of day', part, count(*), 100*avg(is_late::INT) FROM b GROUP BY 1, 2""")
ORDER = {
    "Distance": ["0-1 km", "1-2 km", "2-3 km", "3-4 km", "4+ km"],
    "Rider load": ["under 60%", "60–90%", "90–120%", "over 120%"],
    "Weather": ["Clear", "Cloudy", "Fog", "Heatwave", "Rain", "Heavy Rain"],
    "Time of day": ["Morning", "Afternoon", "Evening peak", "Late night"],
}
dist = d[d.drv == "Distance"].set_index("lvl").late
load = d[d.drv == "Rider load"].set_index("lvl").late
lib.headline("Distance, rider load and rain decide whether an order is late.",
             f"In {lib.scope_label()}, {dist.get('4+ km', 0):.0f}% of orders going 4 km or more arrive late, against "
             f"{dist.get('0-1 km', 0):.0f}% under 1 km. When there are more orders than riders can handle (over 120% "
             f"load), {load.get('over 120%', 0):.0f}% are late.")

cols = st.columns(4, gap="medium")
for col, (drv, levels) in zip(cols, ORDER.items()):
    g = d[d.drv == drv].set_index("lvl").reindex([x for x in levels if x in set(d[d.drv == drv].lvl)]).reset_index()
    with col:
        lib.section(drv)
        fig = go.Figure(go.Bar(x=g.lvl, y=g.late, marker_color=c["blue"], customdata=g.n,
                               text=[f"{v:.0f}%" for v in g.late], textposition="outside", cliponaxis=False,
                               hovertemplate="%{x}: %{y:.1f}% late<br>%{customdata:,} orders<extra></extra>"))
        fig.update_yaxes(range=[0, 85], ticksuffix="%", showticklabels=drv == "Distance")
        fig.update_xaxes(tickangle=-30)
        lib.plot(fig, 280, key=f"drv_{drv}")

coef = lib.processed("delivery_time_drivers_model")
m = lib.metrics()
left, right = st.columns(2, gap="large")
with left:
    lib.section("What one extra kilometre costs, by city",
                f"Regression of delivery time on distance, weather, traffic, rider load, basket size and store "
                f"(R² = {m['model_r2']}). Slower roads shrink the area a store can serve on time.")
    km = coef[coef.group == "Minutes per extra km"].sort_values("minutes_added")
    sel = set(lib.city_names()[x] for x in lib.selected_cities())
    fig = go.Figure(go.Bar(y=km.driver, x=km.minutes_added, orientation="h",
                           marker_color=[c["blue"] if x in sel else c["grey"] for x in km.driver],
                           text=[f"{v:.2f} min" for v in km.minutes_added], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: +%{x:.2f} min per km<extra></extra>"))
    fig.update_xaxes(title="Extra minutes per km", range=[0, km.minutes_added.max() * 1.25])
    lib.plot(fig, 330)
with right:
    lib.section("Other conditions, all else equal", "Minutes added to an average delivery (95% confidence interval).")
    cond = coef[coef.group == "Condition"].sort_values("minutes_added")
    fig = go.Figure(go.Bar(y=cond.driver, x=cond.minutes_added, orientation="h", marker_color=c["blue"],
                           error_x=dict(type="data", array=cond.ci_high - cond.minutes_added, color=c["ink2"], thickness=1),
                           hovertemplate="%{y}: %{x:+.2f} min<extra></extra>"))
    fig.update_xaxes(title="Minutes added")
    lib.plot(fig, 330)

left, right = st.columns(2, gap="large")
ri = m["revenue_impact"]
with left:
    lib.section("Late orders get worse ratings",
                "Average rating by how late the order was. Missing items make it worse again.")
    r = lib.processed("rating_vs_lateness")
    r["lateness"] = r.lateness.str.replace(r"^\d\. ", "", regex=True)
    fig = go.Figure()
    for flag, colr, nm in [(False, c["blue"], "All items delivered"), (True, c["orange"], "Some items missing")]:
        g = r[r.has_missing_items == flag]
        fig.add_trace(go.Scatter(x=g.lateness, y=g.avg_rating, name=nm, mode="lines+markers",
                                 line=dict(color=colr, width=2.5), marker=dict(size=9),
                                 hovertemplate=f"{nm}<br>%{{x}}: %{{y:.2f}}<extra></extra>"))
    fig.update_yaxes(range=[1, 5], title="Average rating")
    lib.plot(fig, 300)
with right:
    lib.section("Late first orders lose repeat customers",
                f"New customers whose first order was late were {ri['repeat_gap_pp']} points less likely to order "
                f"again within 30 days.")
    rt = lib.processed("retention_first_order")
    codes = lib.selected_cities()
    rt = rt[rt.city_code == ("IN" if len(codes) != 1 else codes[0])]
    fig = go.Figure(go.Bar(x=rt.first_order_experience, y=rt.repeat_within_30d_pct,
                           marker_color=[c["blue"]] + [c["grey"]] * (len(rt) - 1), customdata=rt.customers,
                           text=[f"{v:.0f}%" for v in rt.repeat_within_30d_pct], textposition="outside",
                           hovertemplate="%{x}: %{y:.1f}% came back<br>%{customdata:,} customers<extra></extra>"))
    fig.update_yaxes(range=[0, 85], title="Ordered again within 30 days", ticksuffix="%")
    lib.plot(fig, 300)
