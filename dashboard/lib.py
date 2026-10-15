"""Shared data access, filters, styling and small UI components for DarkStore Pulse."""

from __future__ import annotations

import base64
import html
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from build_warehouse import DB_PATH, PROCESSED, REPORTS  # noqa: E402

# ---------------------------------------------------------------------------
# Palette (validated colour-blind-safe steps; light / dark)
# ---------------------------------------------------------------------------
LIGHT = dict(blue="#2A78D6", orange="#EB6834", aqua="#1BAF7A", grey="#B9BFCA", faint="#DDE2EA",
             ink="#18202F", ink2="#4A5468", map_style="carto-positron")
DARK = dict(blue="#3987E5", orange="#D95926", aqua="#199E70", grey="#4A5366", faint="#273042",
            ink="#E7EBF2", ink2="#B4BCCB", map_style="carto-darkmatter")
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
TYPE_LABEL = {"Riders": "Add riders", "Picking": "Fix picking", "New store": "Open new store"}

PERIODS = {
    "Jan–Jun": ("2026-01-01", "2026-06-30"),
    "Jan–Mar": ("2026-01-01", "2026-03-31"),
    "Apr–Jun": ("2026-04-01", "2026-06-30"),
    "June": ("2026-06-01", "2026-06-30"),
}


def colors() -> dict:
    try:
        dark = st.context.theme.type == "dark"
    except Exception:  # noqa: BLE001
        dark = False
    return DARK if dark else LIGHT


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Building the warehouse from the raw data (first run only)…")
def connection() -> duckdb.DuckDBPyConnection:
    def is_current() -> bool:
        if not DB_PATH.exists():
            return False
        try:
            with duckdb.connect(str(DB_PATH), read_only=True) as c:
                c.execute("SELECT city_code FROM fact_orders LIMIT 1")
            return True
        except duckdb.Error:          # missing, or built by an older version of the project
            return False

    if not is_current():
        import build_warehouse
        build_warehouse.build_database()
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data(show_spinner=False)
def q(sql: str) -> pd.DataFrame:
    return connection().cursor().execute(sql).df()


@st.cache_data(show_spinner=False)
def processed(name: str) -> pd.DataFrame:
    return pd.read_csv(PROCESSED / f"{name}.csv")


@st.cache_data(show_spinner=False)
def metrics() -> dict:
    return json.loads((REPORTS / "metrics.json").read_text())


@st.cache_data(show_spinner=False)
def cities() -> pd.DataFrame:
    return q("SELECT * FROM dim_city ORDER BY city_name")


@st.cache_data(show_spinner=False)
def stores() -> pd.DataFrame:
    return q("SELECT * FROM dim_store ORDER BY store_id")


def city_names() -> dict:
    c = cities()
    return dict(zip(c.city_code, c.city_name))


# ---------------------------------------------------------------------------
# Global filters (rendered once in app.py, read by every page)
# ---------------------------------------------------------------------------
def selected_cities() -> list[str]:
    sel = st.session_state.get("f_cities") or []
    return sel if sel else list(cities().city_code)


def period() -> tuple[str, str, str]:
    label = st.session_state.get("f_period") or "Jan–Jun"
    start, end = PERIODS[label]
    return label, start, end


def where(alias: str = "") -> str:
    p = f"{alias}." if alias else ""
    _, start, end = period()
    codes = ", ".join(f"'{c}'" for c in selected_cities())
    return f"{p}order_date BETWEEN DATE '{start}' AND DATE '{end}' AND {p}city_code IN ({codes})"


def scope_label() -> str:
    sel = st.session_state.get("f_cities") or []
    names = city_names()
    if not sel or len(sel) == len(names):
        return "all 8 cities"
    if len(sel) <= 3:
        return ", ".join(names[c] for c in sel)
    return f"{len(sel)} cities"


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def inr(v: float) -> str:
    if v >= 1e7:
        return f"₹{v/1e7:,.2f} Cr"
    if v >= 1e5:
        return f"₹{v/1e5:,.1f} L"
    return f"₹{v:,.0f}"


def num(v: float) -> str:
    return f"{v:,.0f}"


# ---------------------------------------------------------------------------
# Components (custom HTML inherits text colour, so it works in light and dark)
# ---------------------------------------------------------------------------
def headline(text: str, deck: str | None = None):
    deck_html = f'<p class="dsp-deck">{html.escape(deck)}</p>' if deck else ""
    st.html(f'<div class="dsp-head"><h1 class="dsp-headline">{html.escape(text)}</h1>{deck_html}</div>')


def _spark(values: list[float], color: str, w: int = 120, h: int = 28) -> str:
    vals = [v for v in values if v is not None and not pd.isna(v)]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i * w / (len(vals) - 1):.1f},{h - 3 - (v - lo) / rng * (h - 6):.1f}" for i, v in enumerate(vals))
    last_x, last_y = pts.split(" ")[-1].split(",")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-3 -1 {w + 6} {h + 2}" width="{w + 6}" height="{h + 2}">'
           f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>'
           f'<circle cx="{last_x}" cy="{last_y}" r="2.6" fill="{color}"/></svg>')
    uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return f'<img class="dsp-spark" src="{uri}" alt="">'


def kpi_band(items: list[dict]):
    """items: label, value, delta (str|None), good (bool|None), spark (list|None), note (str|None)"""
    c = colors()
    cells = []
    for it in items:
        delta = ""
        if it.get("delta"):
            g = it.get("good")
            tone = "dsp-flat" if g is None else ("dsp-good" if bool(g) else "dsp-bad")
            delta = f'<span class="dsp-delta {tone}">{html.escape(it["delta"])}</span>'
        note = f'<span class="dsp-note">{html.escape(it["note"])}</span>' if it.get("note") else ""
        spark = _spark(it["spark"], c["blue"] if it.get("spark_color") != "orange" else c["orange"]) if it.get("spark") else ""
        cells.append(
            f'<div class="dsp-kpi"><div class="dsp-kpi-label">{html.escape(it["label"])}</div>'
            f'<div class="dsp-kpi-value">{html.escape(it["value"])}</div>'
            f'<div class="dsp-kpi-meta">{delta}{note}</div>{spark}</div>')
    st.html(f'<div class="dsp-band">{"".join(cells)}</div>')


def callouts(rows: list[dict]):
    """rows: tone (alert | info | ok), title, body"""
    out = []
    for r in rows:
        out.append(f'<div class="dsp-callout dsp-{r["tone"]}"><div class="dsp-callout-title">{html.escape(r["title"])}</div>'
                   f'<div class="dsp-callout-body">{html.escape(r["body"])}</div></div>')
    st.html(f'<div class="dsp-callouts">{"".join(out)}</div>')


def table_height(n: int, max_rows: int = 20) -> int:
    return int(33.4 * min(n, max_rows)) + 40


def section(title: str, caption: str | None = None):
    cap = f'<p class="dsp-section-cap">{html.escape(caption)}</p>' if caption else ""
    st.html(f'<div class="dsp-section"><h2>{html.escape(title)}</h2>{cap}</div>')


def plot(fig: go.Figure, height: int = 360, key: str | None = None):
    fig.update_layout(
        height=height, margin=dict(l=4, r=4, t=8, b=4),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        hoverlabel=dict(font_size=13),
        font=dict(family="Archivo, sans-serif"),
    )
    fig.update_xaxes(showgrid=False, title_font=dict(size=12))
    fig.update_yaxes(title_font=dict(size=12))
    st.plotly_chart(fig, width="stretch", theme="streamlit", key=key,
                    config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


CSS = """
<style>
.block-container {max-width: 1320px;}
.dsp-head {margin: 0.4rem 0 1.1rem;}
.dsp-headline {font-family: Archivo, sans-serif; font-variation-settings: "wdth" 116; font-weight: 760;
  font-size: clamp(1.7rem, 3.1vw, 2.7rem); line-height: 1.08; letter-spacing: -0.012em; margin: 0;
  max-width: 30ch; padding: 0; font-variant-numeric: tabular-nums;}
.dsp-deck {margin: 0.55rem 0 0; max-width: 72ch; font-size: 1.02rem; line-height: 1.5; opacity: 0.78;}
.dsp-band {display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  border-top: 2px solid currentColor; border-bottom: 1px solid color-mix(in srgb, currentColor 18%, transparent);
  margin: 0.2rem 0 1.4rem;}
.dsp-kpi {padding: 0.75rem 1rem 0.7rem; border-right: 1px solid color-mix(in srgb, currentColor 14%, transparent);
  display: flex; flex-direction: column; gap: 0.15rem; min-width: 0;}
.dsp-kpi:last-child {border-right: none;}
.dsp-kpi:first-child {padding-left: 0;}
.dsp-kpi-label {font-size: 0.84rem; opacity: 0.72;}
.dsp-kpi-value {font-variation-settings: "wdth" 108; font-weight: 680; font-size: 1.75rem; line-height: 1.15;
  font-variant-numeric: tabular-nums; white-space: nowrap;}
.dsp-kpi-meta {font-size: 0.8rem; display: flex; gap: 0.45rem; flex-wrap: wrap; min-height: 1.1rem;}
.dsp-note {opacity: 0.62;}
.dsp-delta {font-weight: 600; font-variant-numeric: tabular-nums;}
.dsp-good {color: #1F8A5B;} .dsp-bad {color: #D2551E;} .dsp-flat {opacity: 0.7;}
@media (prefers-color-scheme: dark) {.dsp-good {color: #3FBF85;} .dsp-bad {color: #F08A5D;}}
.dsp-spark {width: 100%; height: 28px; margin-top: 0.4rem; display: block;}
.dsp-section {margin: 1.6rem 0 0.35rem;}
.dsp-section h2 {font-variation-settings: "wdth" 110; font-weight: 700; font-size: 1.28rem; margin: 0; padding: 0;}
.dsp-section-cap {margin: 0.25rem 0 0; opacity: 0.7; font-size: 0.92rem; max-width: 80ch;}
.dsp-callouts {display: grid; gap: 0.6rem; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); margin: 0.4rem 0 0.6rem;}
.dsp-callout {padding: 0.7rem 0.9rem 0.75rem; border-left: 4px solid; border-radius: 2px;
  background: color-mix(in srgb, currentColor 4%, transparent);}
.dsp-callout-title {font-weight: 650; margin-bottom: 0.2rem; line-height: 1.3;}
.dsp-callout-body {font-size: 0.9rem; line-height: 1.45; opacity: 0.82;}
.dsp-alert {border-color: #EB6834;} .dsp-info {border-color: #2A78D6;} .dsp-ok {border-color: #1BAF7A;}
div[data-testid="stPills"] button {font-variant-numeric: tabular-nums;}
@media (max-width: 640px) {
  .dsp-kpi {border-right: none; padding-left: 0; border-bottom: 1px solid color-mix(in srgb, currentColor 10%, transparent);}
}
</style>
"""
