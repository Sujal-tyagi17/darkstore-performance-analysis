"""Static report charts (matplotlib). One consistent, colour-blind-safe style."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

# Validated categorical order + recessive chrome
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
MUTED_BAR = "#c3c2b7"
SURFACE = "#fcfcfb"
INK, INK_2, INK_MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
TYPE_COLORS = {"Riders": BLUE, "Picking": ORANGE, "New store": AQUA}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.edgecolor": BASELINE, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 24,
    "xtick.color": INK_MUTED, "ytick.color": INK_2, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": False, "grid.color": GRID, "grid.linewidth": 0.8,
    "legend.frameon": False, "legend.fontsize": 9,
})


def _subtitle(ax, text):
    ax.text(0, 1.01, text, transform=ax.transAxes, fontsize=9.5, color=INK_2, va="bottom")


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def chart_city_late(city: pd.DataFrame, india_late: float, path):
    c = city.sort_values("late_pct")
    colors = [BLUE if v > india_late else MUTED_BAR for v in c.late_pct]
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    ax.barh(c.city_name, c.late_pct, color=colors, height=0.66, edgecolor=SURFACE, linewidth=2)
    for y, (v, s, n) in enumerate(zip(c.late_pct, c.stores, c.orders)):
        ax.text(v + 0.5, y, f"{v:.0f}%   ·  {s} stores, {n/1000:.0f}k orders", va="center", fontsize=8.5, color=INK_2)
    ax.axvline(india_late, color=INK_MUTED, lw=1, ls=(0, (3, 3)))
    ax.text(india_late + 0.3, len(c) - 0.45, f"India {india_late:.0f}%", fontsize=8.5, color=INK_MUTED)
    ax.set_xlim(0, c.late_pct.max() * 1.55)
    ax.set_xlabel("Orders delivered after the promised ETA (%)")
    ax.xaxis.grid(True); ax.set_axisbelow(True)
    ax.set_title(f"{c.city_name.iloc[-1]} misses the promise twice as often as {c.city_name.iloc[0]}")
    _subtitle(ax, "Late-delivery rate by city, Jan–Jun 2026 (highlighted: above the India average)")
    _save(fig, path)


def chart_city_weekly(wk: pd.DataFrame, path):
    india = wk[wk.city_code == "IN"]
    order = ["MUM", "DEL", "KOL", "PUN", "BLR", "HYD", "AMD", "CHE"]
    names = {"MUM": "Mumbai", "DEL": "Delhi NCR", "KOL": "Kolkata", "PUN": "Pune", "BLR": "Bengaluru",
             "HYD": "Hyderabad", "AMD": "Ahmedabad", "CHE": "Chennai"}
    notes = {"MUM": "monsoon arrives 9 Jun", "DEL": "winter fog in Jan, heatwaves May–Jun",
             "KOL": "nor'wester storms Apr–Jun", "PUN": "monsoon in June", "BLR": "pre-monsoon rain Apr–Jun",
             "HYD": "summer heat, June rain", "AMD": "fast growth + heatwaves", "CHE": "best-run city all season"}
    fig, axes = plt.subplots(2, 4, figsize=(14, 6.2), sharex=True, sharey=True)
    for ax, code in zip(axes.ravel(), order):
        g = wk[wk.city_code == code]
        ax.plot(india.week_start, india.late_pct, color=MUTED_BAR, lw=1.4)
        ax.plot(g.week_start, g.late_pct, color=BLUE, lw=2.2)
        ax.set_title(names[code], fontsize=11, pad=6)
        ax.yaxis.grid(True); ax.set_axisbelow(True)
        ax.text(0.02, 0.97, notes[code], transform=ax.transAxes, va="top", fontsize=8.5, color=INK_2)
        ax.tick_params(axis="x", rotation=0)
        ax.xaxis.set_major_formatter(matplotlib_date_fmt())
    for ax in axes[:, 0]:
        ax.set_ylabel("Late %")
    axes[0, 0].plot([], [], color=BLUE, lw=2.2, label="City")
    axes[0, 0].plot([], [], color=MUTED_BAR, lw=1.4, label="All India")
    fig.legend(*axes[0, 0].get_legend_handles_labels(), loc="upper right", ncol=2, bbox_to_anchor=(1, 1.0))
    axes[0, 0].set_ylim(5, 58)
    fig.suptitle("Each city has its own seasons: Mumbai's monsoon, Delhi's fog, Kolkata's storms",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    _save(fig, path)


def matplotlib_date_fmt():
    import matplotlib.dates as mdates
    return mdates.DateFormatter("%b")


def chart_weather_city(dr: pd.DataFrame, path):
    w = dr[(dr.driver == "Weather")].copy()
    w["level"] = w.level.str.replace(r"^\d\. ", "", regex=True)
    piv = w.pivot(index="city_code", columns="level", values="late_pct")
    piv = piv[["Clear", "Cloudy", "Fog", "Heatwave", "Rain", "Heavy Rain"]]
    piv = piv.reindex(["IN", "MUM", "DEL", "KOL", "PUN", "BLR", "HYD", "AMD", "CHE"])
    labels = {"IN": "All India", "MUM": "Mumbai", "DEL": "Delhi NCR", "KOL": "Kolkata", "PUN": "Pune",
              "BLR": "Bengaluru", "HYD": "Hyderabad", "AMD": "Ahmedabad", "CHE": "Chennai"}
    cmap = LinearSegmentedColormap.from_list("seq", SEQ_BLUE)
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    im = ax.imshow(piv.to_numpy(dtype=float), cmap=cmap, aspect="auto", vmin=10, vmax=80)
    ax.set_xticks(range(piv.shape[1]), piv.columns)
    ax.set_yticks(range(piv.shape[0]), [labels[c] for c in piv.index])
    for (i, j), v in np.ndenumerate(piv.to_numpy(dtype=float)):
        ax.text(j, i, "–" if np.isnan(v) else f"{v:.0f}%", ha="center", va="center", fontsize=9,
                color=INK_MUTED if np.isnan(v) else ("white" if v > 45 else INK))
    ax.axhline(0.5, color=SURFACE, lw=3)
    ax.spines[:].set_visible(False)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("Late %", color=INK_2); cb.outline.set_visible(False)
    ax.set_title("Rain is the biggest disruptor everywhere; fog and heat matter in the north")
    _subtitle(ax, "Late % by city and weather at time of order (– = condition did not occur)")
    _save(fig, path)


def chart_store_breakdown(b: pd.DataFrame, stores: pd.DataFrame, path):
    names = dict(zip(stores.store_id, stores.locality))
    top = b.sort_values("delivery_min", ascending=False).head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.5, 6.4))
    left = np.zeros(len(top))
    labels = [f"{names[s]} ({s})" for s in top.store_id]
    for col, color, label in [("pick_min", BLUE, "Picking & packing"),
                              ("rider_wait_min", ORANGE, "Waiting for a rider"),
                              ("travel_min", AQUA, "Travel to customer")]:
        ax.barh(labels, top[col], left=left, color=color, height=0.68, label=label, edgecolor=SURFACE, linewidth=2)
        left += top[col].to_numpy()
    for y, (tot, issue) in enumerate(zip(top.delivery_min, top.primary_bottleneck)):
        txt = f"{tot:.1f} min" + ("" if issue == "On par" else f"  ← {issue.lower()}")
        ax.text(tot + 0.2, y, txt, va="center", fontsize=8.5, color=INK_2)
    ax.set_xlim(0, top.delivery_min.max() * 1.5)
    ax.set_xlabel("Average minutes per delivered order")
    ax.legend(loc="lower right")
    ax.set_title("The 15 slowest stores fail for three different reasons")
    _subtitle(ax, "Delivery time split into its three stages; bottleneck = stage furthest above the India average")
    _save(fig, path)


def chart_drivers(dr: pd.DataFrame, path):
    dr = dr[dr.city_code == "IN"]
    order = ["Distance", "Rider utilisation", "Weather", "Time of day"]
    fig, axes = plt.subplots(1, 4, figsize=(14, 4.4), sharey=True)
    for ax, drv in zip(axes, order):
        d = dr[dr.driver == drv].sort_values("level")
        lv = [str(x).split(". ")[-1] for x in d.level]
        ax.bar(lv, d.late_pct, color=BLUE, width=0.66, edgecolor=SURFACE, linewidth=2)
        for x, v in enumerate(d.late_pct):
            ax.text(x, v + 1.2, f"{v:.0f}%", ha="center", fontsize=8.5, color=INK_2)
        ax.set_title(drv, fontsize=11)
        ax.tick_params(axis="x", rotation=30)
        for t in ax.get_xticklabels():
            t.set_ha("right")
        ax.yaxis.grid(True); ax.set_axisbelow(True)
    axes[0].set_ylabel("Late deliveries (%)")
    fig.suptitle("Across India, lateness explodes past 4 km, above 120% rider load and in heavy rain",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    _save(fig, path)


def chart_distance_cost(coefs: pd.DataFrame, path):
    c = coefs[coefs.group == "Minutes per extra km"].sort_values("minutes_added")
    fig, ax = plt.subplots(figsize=(8, 4.2))
    colors = [BLUE if i == len(c) - 1 else MUTED_BAR for i in range(len(c))]
    ax.barh(c.driver, c.minutes_added, color=colors, height=0.62, edgecolor=SURFACE, linewidth=2)
    for y, v in enumerate(c.minutes_added):
        ax.text(v + 0.04, y, f"{v:.2f} min", va="center", fontsize=9, color=INK_2)
    ax.set_xlim(0, c.minutes_added.max() * 1.25)
    ax.set_xlabel("Extra delivery minutes for each additional km (regression estimate)")
    ax.set_title(f"An extra km costs {c.minutes_added.iloc[-1] / c.minutes_added.iloc[0]:.1f}× more time in "
                 f"{c.driver.iloc[-1]} than in {c.driver.iloc[0]}")
    _subtitle(ax, "So the safe delivery radius is smaller in slow-traffic cities")
    _save(fig, path)


def chart_incidents(wk: pd.DataFrame, incidents: pd.DataFrame, stores: pd.DataFrame, path):
    names = dict(zip(stores.store_id, stores.store_name.str.replace("DS ", "", regex=False)))
    n = max(len(incidents), 1)
    fig, axes = plt.subplots(1, n, figsize=(6.2 * n, 4.4), squeeze=False)
    for ax, inc in zip(axes[0], incidents.itertuples()):
        city = wk[wk.city_code == inc.city_code]
        for s, g in city.groupby("store_id"):
            if s != inc.store_id:
                ax.plot(g.week_start, g.late_pct, color=MUTED_BAR, lw=1.1)
        g = city[city.store_id == inc.store_id]
        ax.plot(g.week_start, g.late_pct, color=BLUE, lw=2.4, marker="o", markersize=3.5)
        when = pd.Timestamp(inc.week_detected)
        ax.axvline(when, color=INK_MUTED, ls=(0, (3, 3)), lw=1)
        ax.text(0.02, 0.97, f"{names[inc.store_id]} ({inc.store_id}) · {inc.status.lower()}\n"
                f"alert week of {when:%d %b}: riders {inc.riders_on_shift_before} → {inc.riders_on_shift_during}/hr,\n"
                f"late {inc.late_pct_before:.0f}% → {inc.late_pct_during:.0f}%",
                transform=ax.transAxes, va="top", fontsize=8.5, color=INK_2)
        ax.set_ylim(0, max(75, g.late_pct.max() + 5))
        ax.yaxis.grid(True); ax.set_axisbelow(True)
        ax.xaxis.set_major_formatter(matplotlib_date_fmt())
        ax.set_ylabel("Late %")
    fig.suptitle("City-adjusted alerts catch store incidents, and ignore city-wide weather swings",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    _save(fig, path)


def chart_retention(r: pd.DataFrame, path):
    r = r[r.city_code == "IN"]
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    colors = [BLUE] + [MUTED_BAR] * (len(r) - 1)
    ax.bar(r.first_order_experience, r.repeat_within_30d_pct, color=colors, width=0.62, edgecolor=SURFACE, linewidth=2)
    for x, (v, n) in enumerate(zip(r.repeat_within_30d_pct, r.customers)):
        ax.text(x, v + 1.2, f"{v:.0f}%", ha="center", fontsize=10, color=INK, fontweight="bold")
        ax.text(x, 3, f"n={n:,}", ha="center", fontsize=8, color=SURFACE)
    ax.set_ylim(0, 85)
    ax.set_ylabel("Ordered again within 30 days (%)")
    ax.yaxis.grid(True); ax.set_axisbelow(True)
    ax.set_title("A late first order costs repeat business")
    _subtitle(ax, "New customers across India (signed up in 2026), by how their first order went")
    _save(fig, path)


def chart_rating(r: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(8, 4.3))
    for flag, color, label in [(False, BLUE, "All items delivered"), (True, ORANGE, "Some items missing")]:
        g = r[r.has_missing_items == flag]
        x = [s.split(". ")[1] for s in g.lateness]
        ax.plot(x, g.avg_rating, color=color, lw=2, marker="o", markersize=7, label=label,
                markeredgecolor=SURFACE, markeredgewidth=2)
        ax.text(len(x) - 1 + 0.1, g.avg_rating.iloc[-1], f"{g.avg_rating.iloc[-1]:.1f}", va="center", fontsize=9, color=INK_2)
        ax.text(-0.12, g.avg_rating.iloc[0], f"{g.avg_rating.iloc[0]:.1f}", va="center", ha="right", fontsize=9, color=INK_2)
    ax.set_ylim(1, 5); ax.set_xlim(-0.45, 4.45)
    ax.set_ylabel("Average customer rating (1–5)")
    ax.yaxis.grid(True); ax.set_axisbelow(True)
    ax.legend(loc="upper right")
    ax.set_title("Being even 0–3 minutes late costs more than a full rating star")
    _save(fig, path)


def chart_stockouts(st: pd.DataFrame, path):
    top = st.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    labels = [f"{p}  ·  {s}" for p, s in zip(top.product_name, top.store_id)]
    colors = [BLUE if c == "Ice Cream & Frozen" else MUTED_BAR for c in top.category]
    ax.barh(labels, top.lost_revenue_inr / 1000, color=colors, height=0.68, edgecolor=SURFACE, linewidth=2)
    for y, (v, pct) in enumerate(zip(top.lost_revenue_inr, top.stockout_pct)):
        ax.text(v / 1000 + 0.5, y, f"₹{v/1000:.1f}k  ({pct:.0f}% of requests)", va="center", fontsize=8.5, color=INK_2)
    ax.set_xlim(0, top.lost_revenue_inr.max() / 1000 * 1.45)
    ax.set_xlabel("Revenue lost to stockouts, Jan–Jun 2026 (₹ thousand)")
    ax.set_title("Small freezers can't keep up with summer ice cream demand")
    _subtitle(ax, "Top 10 product × store stockouts by lost revenue (highlighted: ice cream & frozen)")
    _save(fig, path)


def chart_basket_rules(rules: pd.DataFrame, path):
    top = rules.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    labels = [f"{a}  →  {b}" for a, b in zip(top.if_customer_buys, top.they_also_buy)]
    ax.barh(labels, top.lift, color=BLUE, height=0.66, edgecolor=SURFACE, linewidth=2)
    for y, (l, c) in enumerate(zip(top.lift, top.confidence)):
        ax.text(l + 0.1, y, f"lift {l:.1f}  ·  {c*100:.0f}% also buy", va="center", fontsize=8.5, color=INK_2)
    ax.set_xlim(0, top.lift.max() * 1.45)
    ax.set_xlabel("Lift (how much more likely than chance)")
    ax.set_title("Bundle candidates from market basket analysis")
    _save(fig, path)


def chart_action_plan(plan: pd.DataFrame, path):
    top = plan.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    labels = [f"{w} · {c}" for w, c in zip(top["where"], top.city_name)]
    ax.barh(labels, top.late_avoided_per_day, color=[TYPE_COLORS[t] for t in top.type], height=0.66,
            edgecolor=SURFACE, linewidth=2)
    for y, (v, a, b) in enumerate(zip(top.late_avoided_per_day, top.late_pct_now, top.late_pct_after)):
        ax.text(v + 0.4, y, f"{v:.0f}/day  ·  late {a:.0f}% → {b:.0f}%", va="center", fontsize=8.5, color=INK_2)
    from matplotlib.patches import Patch
    handles = [Patch(color=c, label={"Riders": "Add riders", "Picking": "Fix picking",
                                     "New store": "Open new store"}[t]) for t, c in TYPE_COLORS.items()]
    ax.set_xlim(0, top.late_avoided_per_day.max() * 1.5)
    ax.legend(handles=handles, loc="lower right")
    ax.set_xlabel("Late deliveries avoided per day (simulated)")
    ax.set_title("The ten highest-impact fixes across India")
    _subtitle(ax, "Each action simulated on the order-level data, ranked by late deliveries it would prevent")
    _save(fig, path)


def chart_promise_radius(r: pd.DataFrame, path):
    r = r.sort_values("radius_10min_km")
    fig, ax = plt.subplots(figsize=(8, 4.2))
    colors = [BLUE if i == 0 else MUTED_BAR for i in range(len(r))]
    ax.barh(r.city_name, r.radius_10min_km, color=colors, height=0.62, edgecolor=SURFACE, linewidth=2)
    for y, (v, p) in enumerate(zip(r.radius_10min_km, r.orders_within_radius_pct)):
        ax.text(v + 0.04, y, f"{v:.1f} km  ·  {p:.0f}% of orders today are inside it", va="center", fontsize=8.5,
                color=INK_2)
    ax.set_xlim(0, r.radius_10min_km.max() * 1.9)
    ax.set_xlabel("Largest radius where 80% of the orders inside it arrive within 10 minutes (km)")
    ax.set_title(f"A true 10-minute promise reaches only {r.radius_10min_km.iloc[0]:.1f} km in {r.city_name.iloc[0]}")
    _subtitle(ax, "One national delivery radius doesn't fit every city's traffic")
    _save(fig, path)
