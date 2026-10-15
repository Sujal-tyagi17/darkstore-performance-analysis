import streamlit as st

import lib

m = lib.metrics()
q = lib.processed

lib.headline("About the data and the method.",
             "Real dark-store data is not public, so this project simulates it with an explicit operational model. "
             "The analysis then has to find the problems from the order data alone.")

left, right = st.columns(2, gap="large")
with left:
    lib.section("What was simulated")
    st.markdown(f"""
- **{m['orders']:,} orders** from **{m['customers']:,} customers**, **{m['stores']} dark stores** in
  **{m['cities']} cities**, 1 January to 30 June 2026.
- **Delivery time = picking + waiting for a rider + travel.** Picking grows with basket size; waiting rises
  sharply when orders outnumber riders; travel depends on distance and each city's traffic.
- **City conditions:** Mumbai's June monsoon, Delhi's winter fog and summer heatwaves, Kolkata's April–May
  storms, summer heat in Ahmedabad, Hyderabad and Chennai, and regional festivals such as Pongal, Uttarayan,
  Holi, Ugadi, Eid and Poila Baisakh.
- **Customers react:** late orders and missing items lower ratings and make customers more likely to stop
  ordering.
- **A messy export:** duplicate rows, inconsistent store IDs, label drift, broken timestamps and missing
  distances, all fixed in the SQL staging layer.
""")
with right:
    lib.section("How it was analysed")
    st.markdown("""
- **SQL (DuckDB):** cleaning, a star schema and 13 analysis queries.
- **Bottleneck diagnosis:** each store's delivery stages compared with the India average.
- **Regression:** delivery time on distance (per city), weather, traffic, rider load, basket size and store.
- **Alerts:** weekly late rate against each store's baseline, minus the city's own swing.
- **Market basket analysis:** FP-Growth association rules.
- **What-if simulations** for every recommended fix, ranked into one action plan.
""")
    lib.section("Caveats")
    st.markdown("""
Treat the exact numbers as an illustration of the method. The retention comparison is observational, and the
simulations hold other factors constant (for example, a new store is assumed to pick and dispatch at today's
speed).
""")

lib.section("Data quality checks")
dq = lib.q("SELECT check_name, rows_affected FROM data_quality_log")
st.dataframe(dq, hide_index=True, width="stretch",
             column_config={"check_name": "Check", "rows_affected": st.column_config.NumberColumn("Rows", format="localized")})
st.markdown("Source code: [github.com/Sujal-tyagi17/darkstore-performance-analysis]"
            "(https://github.com/Sujal-tyagi17/darkstore-performance-analysis)")
