import plotly.graph_objects as go
import streamlit as st

import lib

c = lib.colors()
names = lib.city_names()
codes = lib.selected_cities()
exp = lib.processed("expansion_candidates")
exp = exp[exp.city_code.isin(codes)].reset_index(drop=True)
S = lib.stores()
S = S[S.city_code.isin(codes)]

if exp.empty:
    lib.headline("No under-served neighbourhoods in this selection.")
    st.stop()
best = exp.iloc[0]
lib.headline(f"A new store near {best.candidate_site_near} would fix the most late orders.",
             f"{best.orders_reassigned_per_day:.0f} orders a day in {best.city_name} currently travel "
             f"{best.avg_distance_now_km:.1f} km on average and {best.late_pct_now:.0f}% arrive late. From a store "
             f"near {best.candidate_site_near} they would travel {best.avg_distance_new_km:.1f} km and the late rate "
             f"would drop to about {best.late_pct_new:.0f}%.")

lib.kpi_band([
    {"label": "Candidate sites", "value": str(len(exp)), "note": "best one or two per city"},
    {"label": "Orders a day they would serve", "value": f"{exp.orders_reassigned_per_day.sum():.0f}"},
    {"label": "Late orders avoided a day", "value": f"{exp.late_avoided_per_day.sum():.0f}"},
    {"label": "Gross order value moved", "value": lib.inr(exp.gmv_reassigned_6m_inr.sum()), "note": "Jan–Jun"},
])

lib.section("Candidate sites and today's stores",
            "Sites are the centre of neighbourhoods where at least 40% of orders travel more than 3.5 km.")
fig = go.Figure()
fig.add_trace(go.Scattermap(lat=S.lat, lon=S.lon, mode="markers", name="Existing store",
                            marker=dict(size=11, color=c["blue"]), text=S.store_name,
                            hovertemplate="%{text}<extra>Existing store</extra>"))
fig.add_trace(go.Scattermap(
    lat=exp.lat, lon=exp.lon, mode="markers+text", name="Candidate site", text=exp.candidate_site_near,
    textposition="top right", textfont=dict(size=12, color=c["ink"]),
    marker=dict(size=(exp.late_avoided_per_day / exp.late_avoided_per_day.max()) ** 0.5 * 26 + 8, color=c["orange"]),
    customdata=exp[["orders_reassigned_per_day", "late_pct_now", "late_pct_new"]],
    hovertemplate="<b>%{text}</b><br>%{customdata[0]:.0f} orders/day<br>late %{customdata[1]:.0f}% → "
                  "%{customdata[2]:.0f}%<extra>Candidate site</extra>"))
if len(codes) == 1:
    center, zoom = dict(lat=S.lat.mean(), lon=S.lon.mean()), 10
else:
    center, zoom = dict(lat=21.5, lon=79.5), 3.6
fig.update_layout(map=dict(style=c["map_style"], center=center, zoom=zoom), margin=dict(l=0, r=0, t=0, b=0),
                  height=480, legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.75)", font=dict(color="#18202F")))
st.plotly_chart(fig, width="stretch", theme=None, config={"displaylogo": False})

lib.section("All candidate sites, ranked by late orders avoided")
st.dataframe(
    exp[["rank", "candidate_site_near", "city_name", "currently_served_by", "orders_reassigned_per_day",
         "avg_distance_now_km", "avg_distance_new_km", "late_pct_now", "late_pct_new", "late_avoided_per_day"]],
    hide_index=True, width="stretch", column_config={
        "rank": st.column_config.NumberColumn("#", width="small"),
        "candidate_site_near": "Site near", "city_name": "City", "currently_served_by": "Now served by",
        "orders_reassigned_per_day": st.column_config.NumberColumn("Orders/day", format="%.0f"),
        "avg_distance_now_km": st.column_config.NumberColumn("Km now", format="%.1f"),
        "avg_distance_new_km": st.column_config.NumberColumn("Km after", format="%.1f"),
        "late_pct_now": st.column_config.NumberColumn("Late now", format="%.0f%%"),
        "late_pct_new": st.column_config.NumberColumn("Late after", format="%.0f%%"),
        "late_avoided_per_day": st.column_config.ProgressColumn("Late orders avoided/day", format="%.1f",
                                                                min_value=0, max_value=float(exp.late_avoided_per_day.max())),
    })
st.caption("Simulation: every order that would be closer to the new site is re-routed to it, travel time is "
           "scaled by the new distance and the app's ETA tiers are re-applied. Picking and rider wait stay at "
           "today's levels.")
