import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import lib

c = lib.colors()
m = lib.metrics()
S = lib.stores().set_index("store_id")
mon = lib.processed("incident_monitor_weekly")
mon["week_start"] = pd.to_datetime(mon.week_start)
naive = lib.processed("naive_alerts")
incidents = [i for i in m["incidents"] if i["city_code"] in lib.selected_cities()]

lib.headline(f"{m['city_adjusted_alert_count']} real incidents, not {m['naive_alert_count']} alarms.",
             "Each week, every store's late rate is compared with its own 8-week baseline. A plain version of that "
             f"rule fires {m['naive_alert_count']} times, mostly when Mumbai's monsoon arrived and every store slowed "
             "at once. Subtracting the city's own swing leaves only the store-level problems.")

rows = []
for i in incidents:
    s = S.loc[i["store_id"]]
    rows.append({"tone": "alert" if i["status"] == "Ongoing" else "ok",
                 "title": f"{s.locality}, {s.city_name}: {i['status'].lower()}",
                 "body": f"Week of {pd.Timestamp(i['week_detected']):%d %b}. Riders per hour "
                         f"{i['riders_on_shift_before']} → {i['riders_on_shift_during']}, rider wait "
                         f"{i['rider_wait_min_before']} → {i['rider_wait_min_during']} min, late "
                         f"{i['late_pct_before']:.0f}% → {i['late_pct_during']:.0f}%. Picking and travel did not change, "
                         f"so the cause is rider capacity."})
if rows:
    lib.callouts(rows)
else:
    st.info("No store incidents in the selected cities. Select Bengaluru or Delhi NCR to see the two alerts.")

for i in incidents:
    s = S.loc[i["store_id"]]
    lib.section(f"{s.locality} ({i['store_id']}) against the rest of {s.city_name}")
    g = mon[mon.store_id == i["store_id"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=g.week_start, y=g.city_late_pct, name=f"{s.city_name} average",
                             line=dict(color=c["grey"], width=2), hovertemplate="City: %{y:.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=g.week_start, y=g.baseline_late_pct, name="Store's 8-week baseline",
                             line=dict(color=c["ink2"], width=1.5, dash="dot"),
                             hovertemplate="Baseline: %{y:.1f}%<extra></extra>"))
    fig.add_trace(go.Scatter(x=g.week_start, y=g.late_pct, name="This store", mode="lines+markers",
                             line=dict(color=c["blue"], width=3), hovertemplate="Store: %{y:.1f}%<extra></extra>"))
    fig.add_vline(x=pd.Timestamp(i["week_detected"]).timestamp() * 1000, line_dash="dot", line_color=c["orange"],
                  annotation_text="alert", annotation_position="top left")
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title="Late %", rangemode="tozero", ticksuffix="%")
    lib.plot(fig, 300, key=f"inc_{i['store_id']}")

lib.section("Why the city adjustment matters",
            "Alerts a plain rule would raise, and how much of each jump was the store itself once the city's swing is "
            "removed. Only jumps above 10 points (and still above 8 the next week) are real alerts.")
naive = naive.merge(S[["locality", "city_name"]], left_on="store_id", right_index=True)
naive["verdict"] = naive.jump_vs_city_pts.apply(lambda x: "Real incident" if x > 10 else "City-wide (weather)")
st.dataframe(naive[["store_id", "locality", "city_name", "week_start", "late_pct", "raw_jump_pts",
                    "jump_vs_city_pts", "verdict"]], hide_index=True, width="stretch",
             column_config={"store_id": "Store", "locality": "Locality", "city_name": "City", "week_start": "Week of",
                            "late_pct": st.column_config.NumberColumn("Late %", format="%.1f"),
                            "raw_jump_pts": st.column_config.NumberColumn("Jump vs own baseline", format="%+.1f pts"),
                            "jump_vs_city_pts": st.column_config.NumberColumn("Jump after removing city swing",
                                                                              format="%+.1f pts"),
                            "verdict": "Verdict"})
