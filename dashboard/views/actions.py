import streamlit as st

import lib

m = lib.metrics()
names = lib.city_names()
plan = lib.processed("action_plan")
plan = plan[plan.city_name.isin([names[x] for x in lib.selected_cities()])]

types = st.pills("Type of fix", options=list(lib.TYPE_LABEL), format_func=lambda t: lib.TYPE_LABEL[t],
                 selection_mode="multi", default=list(lib.TYPE_LABEL), key="plan_types")
plan = plan[plan.type.isin(types or list(lib.TYPE_LABEL))]

late_now = m["late_orders_per_day_now"]
avoided = plan.late_avoided_per_day.sum()
lib.headline(f"{len(plan)} fixes would prevent about {avoided:.0f} late orders a day.",
             f"India currently delivers about {late_now:.0f} orders a day late. Each fix below was simulated on the "
             f"order-level data and ranked by how many late deliveries it would prevent.")

lib.kpi_band([
    {"label": "Add riders", "value": str((plan.type == "Riders").sum()),
     "note": f"{plan[plan.type == 'Riders'].late_avoided_per_day.sum():.0f} late orders/day avoided"},
    {"label": "Fix picking", "value": str((plan.type == "Picking").sum()),
     "note": f"{plan[plan.type == 'Picking'].late_avoided_per_day.sum():.0f} late orders/day avoided"},
    {"label": "Open new stores", "value": str((plan.type == "New store").sum()),
     "note": f"{plan[plan.type == 'New store'].late_avoided_per_day.sum():.0f} late orders/day avoided"},
])

view = plan.assign(fix=plan.type.map(lib.TYPE_LABEL))
st.dataframe(
    view[["priority", "fix", "where", "city_name", "problem", "effort", "late_pct_now", "late_pct_after",
          "late_avoided_per_day"]],
    hide_index=True, width="stretch", height=lib.table_height(len(view)),
    column_config={
        "priority": st.column_config.NumberColumn("#", width="small"),
        "fix": "Fix", "where": "Where", "city_name": "City",
        "problem": st.column_config.TextColumn("What's wrong", width="large"),
        "effort": st.column_config.TextColumn("What it takes", width="large"),
        "late_pct_now": st.column_config.NumberColumn("Late now", format="%.0f%%"),
        "late_pct_after": st.column_config.NumberColumn("Late after", format="%.0f%%"),
        "late_avoided_per_day": st.column_config.ProgressColumn(
            "Late orders avoided/day", format="%.1f", min_value=0,
            max_value=float(max(plan.late_avoided_per_day.max(), 1)) if len(plan) else 1.0),
    })
st.download_button("Download the action plan (CSV)", view.to_csv(index=False).encode(), "darkstore_action_plan.csv",
                   mime="text/csv", icon=":material/download:")

lib.section("How each fix was simulated")
st.markdown("""
- **Add riders.** Schedule enough riders that no hour runs above 85% rider load, then re-price each order's
  waiting time using the network's own curve of rider load against wait time.
- **Fix picking.** Bring the store's picking time down to the India average for the same basket sizes.
- **Open a new store.** Re-route every order that would be closer to the new site, scale travel time by the new
  distance and re-apply the app's ETA tiers.
""")
