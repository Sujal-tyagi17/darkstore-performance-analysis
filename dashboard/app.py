"""
DarkStore Pulse: India-wide dashboard for the dark store performance analysis.

Run from the repository root:   streamlit run dashboard/app.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import lib

HERE = Path(__file__).parent
st.set_page_config(page_title="DarkStore Pulse", page_icon=":material/electric_moped:", layout="wide")
st.html(lib.CSS)

lib.connection()  # build the warehouse on first run

pages = [
    st.Page(HERE / "views/overview.py", title="India", icon=":material/public:", default=True),
    st.Page(HERE / "views/cities.py", url_path="cities", title="Cities", icon=":material/location_city:"),
    st.Page(HERE / "views/stores.py", url_path="stores", title="Stores", icon=":material/storefront:"),
    st.Page(HERE / "views/drivers.py", url_path="why-late", title="Why orders are late", icon=":material/timer:"),
    st.Page(HERE / "views/incidents.py", url_path="alerts", title="Alerts", icon=":material/notifications_active:"),
    st.Page(HERE / "views/stock.py", url_path="stock", title="Stock & baskets", icon=":material/inventory_2:"),
    st.Page(HERE / "views/expansion.py", url_path="new-stores", title="New stores", icon=":material/add_location_alt:"),
    st.Page(HERE / "views/actions.py", url_path="action-plan", title="Action plan", icon=":material/checklist:"),
    st.Page(HERE / "views/about.py", url_path="about", title="About the data", icon=":material/info:"),
]
page = st.navigation(pages, position="top")

# ---- global filter bar (shared by every page) -------------------------------
names = lib.city_names()
with st.container(horizontal=True, vertical_alignment="bottom", gap="medium"):
    st.pills("Cities", options=list(names), format_func=lambda c: names[c], selection_mode="multi",
             key="f_cities", help="Leave all unselected to see the whole of India.", wrap=True)
    st.segmented_control("Period", options=list(lib.PERIODS), key="f_period", default="Jan–Jun",
                         help="Data covers 1 January to 30 June 2026.")
page.run()

st.html('<p style="margin-top:3rem;opacity:.55;font-size:.8rem">Built by Sujal Tyagi. Simulated quick-commerce '
        'data for 8 Indian metros, January to June 2026.</p>')
