import plotly.graph_objects as go
import streamlit as st

import lib

c = lib.colors()
_, start, end = lib.period()
codes = ", ".join(f"'{x}'" for x in lib.selected_cities())
W = f"i.order_date BETWEEN DATE '{start}' AND DATE '{end}' AND i.city_code IN ({codes})"

cat = lib.q(f"""
    SELECT p.category, sum(i.line_value) FILTER (WHERE NOT i.fulfilled) lost,
           100*avg((NOT i.fulfilled)::INT) pct, count(*) lines
    FROM fact_order_items i JOIN dim_product p USING (sku_id) WHERE {W}
    GROUP BY 1 ORDER BY lost""")
monthly = lib.q(f"""
    SELECT month(i.order_date) m, p.category = 'Ice Cream & Frozen' frozen,
           100*avg((NOT i.fulfilled)::INT) pct
    FROM fact_order_items i JOIN dim_product p USING (sku_id) WHERE {W} GROUP BY 1, 2 ORDER BY 1""")
total = cat.lost.sum()
months = max(1, (int(end[5:7]) - int(start[5:7]) + 1))
top = cat.iloc[-1]
lib.headline(f"{lib.inr(total / months)} a month in sales lost to empty shelves.",
             f"{top.category} loses the most ({lib.inr(top.lost)} over the period). Small freezers run out of ice "
             "cream in summer, and morning milk and bread arrive too late at a few stores.")

left, right = st.columns([1, 1], gap="large")
with left:
    lib.section("Lost sales by category")
    fig = go.Figure(go.Bar(y=cat.category, x=cat.lost, orientation="h",
                           marker_color=[c["blue"] if x == top.category else c["grey"] for x in cat.category],
                           customdata=cat.pct, text=[lib.inr(v) for v in cat.lost], textposition="outside",
                           cliponaxis=False,
                           hovertemplate="%{y}: ₹%{x:,.0f} lost<br>%{customdata:.1f}% of requests unavailable<extra></extra>"))
    fig.update_xaxes(title="Lost sales (₹)", range=[0, cat.lost.max() * 1.3])
    lib.plot(fig, 380)
with right:
    lib.section("Ice cream stockouts spike in summer", "Share of requested items that were unavailable, by month.")
    mn = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun"}
    fig = go.Figure()
    for flag, colr, nm in [(False, c["grey"], "Everything else"), (True, c["blue"], "Ice cream & frozen")]:
        g = monthly[monthly.frozen == flag]
        fig.add_trace(go.Scatter(x=[mn[x] for x in g.m], y=g.pct, name=nm, mode="lines+markers",
                                 line=dict(color=colr, width=3 if flag else 2),
                                 hovertemplate=f"{nm}: %{{y:.1f}}%<extra></extra>"))
    fig.update_yaxes(title="Unavailable", rangemode="tozero", ticksuffix="%")
    lib.plot(fig, 380)

lib.section("Worst product and store combinations", "Jan–Jun totals.")
so = lib.processed("stockouts")
so = so[so.city_code.isin(lib.selected_cities())].head(15)
so = so.merge(lib.stores()[["store_id", "locality"]], on="store_id")
st.dataframe(so[["product_name", "locality", "store_id", "times_requested", "stockout_pct", "lost_revenue_inr"]],
             hide_index=True, width="stretch", column_config={
                 "product_name": "Product", "locality": "Store", "store_id": st.column_config.TextColumn("ID", width="small"),
                 "times_requested": st.column_config.NumberColumn("Requested", format="localized"),
                 "stockout_pct": st.column_config.ProgressColumn("Unavailable", format="%.1f%%", min_value=0, max_value=35),
                 "lost_revenue_inr": st.column_config.NumberColumn("Lost sales (₹)", format="localized")})

lib.section("Items bought together",
            f"Market basket analysis of {lib.metrics()['basket_orders_analysed']:,} delivered orders across India. "
            "Use the strongest pairs for 'frequently bought together' prompts and combo offers.")
rules = lib.processed("basket_rules").head(15)
st.dataframe(rules[["if_customer_buys", "they_also_buy", "confidence", "lift", "orders_with_both"]], hide_index=True,
             width="stretch", column_config={
                 "if_customer_buys": "If the basket has", "they_also_buy": "It often also has",
                 "confidence": st.column_config.ProgressColumn("How often", format="percent", min_value=0, max_value=1),
                 "lift": st.column_config.NumberColumn("Lift vs chance", format="%.1f×"),
                 "orders_with_both": st.column_config.NumberColumn("Orders with both", format="localized")})
