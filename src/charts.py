"""Static report charts (matplotlib). One consistent, colour-blind-safe style."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

# Palette (validated categorical order + recessive chrome)
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
MUTED_BAR = "#c3c2b7"
SURFACE = "#fcfcfb"
INK, INK_2, INK_MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

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


def chart_store_late(score: pd.DataFrame, path):
    s = score.sort_values("late_pct")
    network = s.late_pct.mean()
    flagged = set(score.head(3).store_id)
    colors = [BLUE if sid in flagged else MUTED_BAR for sid in s.store_id]
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    labels = [f"{n.replace('DS ', '')} ({sid})" for sid, n in zip(s.store_id, s.store_name)]
    ax.barh(labels, s.late_pct, color=colors, height=0.68, edgecolor=SURFACE, linewidth=2)
    for y, v in enumerate(s.late_pct):
        ax.text(v + 0.6, y, f"{v:.0f}%", va="center", fontsize=9, color=INK_2)
    ax.axvline(network, color=INK_MUTED, lw=1, ls=(0, (3, 3)))
    ax.text(network + 0.4, len(s) - 0.35, f"store average {network:.0f}%", fontsize=8.5, color=INK_MUTED)
    ax.set_xlabel("Orders delivered after the promised ETA (%)")
    ax.xaxis.grid(True); ax.set_axisbelow(True)
    ax.set_title("Electronic City and Whitefield are late on 4 in 10 orders")
    _subtitle(ax, "Late-delivery rate by dark store, Jan–Jun 2026 (highlighted: bottom three)")
    _save(fig, path)


def chart_breakdown(b: pd.DataFrame, path):
    b = b.sort_values("delivery_min")
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    left = np.zeros(len(b))
    for col, color, label in [("pick_min", BLUE, "Picking & packing"),
                              ("rider_wait_min", ORANGE, "Waiting for a rider"),
                              ("travel_min", AQUA, "Travel to customer")]:
        ax.barh(b.store_id, b[col], left=left, color=color, height=0.68, label=label,
                edgecolor=SURFACE, linewidth=2)
        left += b[col].to_numpy()
    for y, (tot, issue) in enumerate(zip(b.delivery_min, b.primary_bottleneck)):
        txt = f"{tot:.1f} min" + ("" if issue == "On par with network" else f"  ← {issue.split(' (')[0].lower()}")
        ax.text(tot + 0.2, y, txt, va="center", fontsize=8.5, color=INK_2)
    ax.set_xlim(0, b.delivery_min.max() * 1.55)
    ax.set_xlabel("Average minutes per delivered order")
    ax.legend(loc="lower right", ncol=1)
    ax.set_title("Each problem store fails for a different reason")
    _subtitle(ax, "Delivery time split into its three stages, by store")
    _save(fig, path)


def chart_drivers(dr: pd.DataFrame, path):
    order = ["Distance", "Rider utilisation", "Weather", "Time of day"]
    fig, axes = plt.subplots(1, 4, figsize=(13, 4.2), sharey=True)
    for ax, drv in zip(axes, order):
        d = dr[dr.driver == drv].copy()
        if drv == "Weather":
            d["level"] = pd.Categorical(d.level, ["Clear", "Cloudy", "Rain", "Heavy Rain"], ordered=True)
            d = d.sort_values("level")
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
    fig.suptitle("Lateness explodes past 4 km, above 120% rider utilisation and in rain",
                 x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    _save(fig, path)


def chart_heatmap(h: pd.DataFrame, path):
    piv = h.pivot(index="store_id", columns="order_hour", values="late_pct")
    piv = piv.reindex(columns=range(6, 24))
    cmap = LinearSegmentedColormap.from_list("seq", SEQ_BLUE)
    fig, ax = plt.subplots(figsize=(11, 5))
    im = ax.imshow(piv.to_numpy(), cmap=cmap, aspect="auto", vmin=0, vmax=70)
    ax.set_xticks(range(len(piv.columns)), [f"{c}:00" for c in piv.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(piv.index)), piv.index)
    for (i, j), v in np.ndenumerate(piv.to_numpy()):
        if not np.isnan(v):
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                    color="white" if v > 40 else INK)
    ax.spines[:].set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.set_label("Late %", color=INK_2); cb.outline.set_visible(False)
    ax.set_title("Late % by store and hour: S07 and S10 struggle at both daily peaks")
    _save(fig, path)


def chart_incident(wk: pd.DataFrame, incident, path):
    fig, ax = plt.subplots(figsize=(10, 4.6))
    sid = incident["store_id"] if incident else None
    for s, g in wk.groupby("store_id"):
        if s == sid:
            continue
        ax.plot(g.week_start, g.late_pct, color=MUTED_BAR, lw=1.2)
    if sid:
        g = wk[wk.store_id == sid]
        ax.plot(g.week_start, g.late_pct, color=BLUE, lw=2.4, marker="o", markersize=4, label=f"{sid} HSR Layout")
        when = pd.Timestamp(incident["week_detected"])
        ax.axvline(when, color=INK_MUTED, ls=(0, (3, 3)), lw=1)
        ax.text(when - pd.Timedelta(days=3), 66,
                f"Alert: week of {when:%d %b}\nriders on shift {incident['riders_on_shift_before']} → {incident['riders_on_shift_after']}\n"
                f"late {incident['late_pct_before']:.0f}% → {incident['late_pct_after']:.0f}%",
                va="top", ha="right", fontsize=8.5, color=INK_2)
    ax.plot([], [], color=MUTED_BAR, lw=1.2, label="Other 11 stores")
    ax.set_ylabel("Late deliveries (%)")
    ax.yaxis.grid(True); ax.set_axisbelow(True)
    ax.legend(loc="upper left")
    ax.set_title("Automated alert: HSR Layout's late rate jumped overnight in mid-May")
    _subtitle(ax, "Weekly late % per store; alert = >3 std devs above the store's 8-week baseline and >10 pts worse than the city-wide trend")
    _save(fig, path)


def chart_retention(r: pd.DataFrame, path):
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
    _subtitle(ax, "New customers (signed up in 2026), by how their first order went")
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
    ax.set_ylim(1, 5)
    ax.set_ylabel("Average customer rating (1–5)")
    ax.yaxis.grid(True); ax.set_axisbelow(True)
    ax.legend(loc="upper right")
    ax.set_title("Being even 0–3 minutes late costs more than a full rating star")
    ax.set_xlim(-0.45, 4.45)
    _save(fig, path)


def chart_stockouts(st: pd.DataFrame, path):
    top = st.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    labels = [f"{p}  ·  {s}" for p, s in zip(top.product_name, top.store_id)]
    colors = [BLUE if c == "Ice Cream & Frozen" else MUTED_BAR for c in top.category]
    ax.barh(labels, top.lost_revenue_inr / 1000, color=colors, height=0.68, edgecolor=SURFACE, linewidth=2)
    for y, (v, pct) in enumerate(zip(top.lost_revenue_inr, top.stockout_pct)):
        ax.text(v / 1000 + 0.5, y, f"₹{v/1000:.1f}k  ({pct:.0f}% of requests)", va="center", fontsize=8.5, color=INK_2)
    ax.set_xlim(0, top.lost_revenue_inr.max() / 1000 * 1.45)
    ax.set_xlabel("Revenue lost to stockouts, Jan–Jun 2026 (₹ thousand)")
    ax.set_title("Summer ice cream stockouts top the lost-sales list")
    _subtitle(ax, "Top 10 product × store stockouts by lost revenue (highlighted: ice cream & frozen)")
    _save(fig, path)


def chart_basket_rules(rules: pd.DataFrame, path):
    top = rules.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    labels = [f"{a}  →  {b}" for a, b in zip(top.if_customer_buys, top.they_also_buy)]
    ax.barh(labels, top.lift, color=BLUE, height=0.66, edgecolor=SURFACE, linewidth=2)
    for y, (l, c) in enumerate(zip(top.lift, top.confidence)):
        ax.text(l + 0.1, y, f"lift {l:.1f}  ·  {c*100:.0f}% also buy", va="center", fontsize=8.5, color=INK_2)
    ax.set_xlim(0, top.lift.max() * 1.45)
    ax.set_xlabel("Lift (how much more likely than chance)")
    ax.set_title("Bundle candidates from market basket analysis")
    _save(fig, path)


def chart_expansion_map(valid: pd.DataFrame, stores: pd.DataFrame, exp: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(8, 8))
    sample = valid.sample(min(len(valid), 25000), random_state=1)
    near = sample[sample.distance_km <= 3.5]
    far = sample[sample.distance_km > 3.5]
    ax.scatter(near.cust_lon, near.cust_lat, s=2, color=MUTED_BAR, alpha=0.5, linewidths=0, label="Order ≤ 3.5 km from store")
    ax.scatter(far.cust_lon, far.cust_lat, s=3, color=ORANGE, alpha=0.6, linewidths=0, label="Order > 3.5 km from store")
    ax.scatter(stores.lon, stores.lat, s=90, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3, label="Existing dark store")
    for _, s in stores.iterrows():
        ax.text(s.lon + 0.004, s.lat + 0.003, s.store_id, fontsize=8, color=INK_2, zorder=4)
    best = exp.iloc[0]
    ax.scatter([best.lon], [best.lat], s=320, marker="*", color=INK, edgecolor=SURFACE, linewidth=1.5, zorder=5,
               label="Proposed new store")
    ax.text(best.lon + 0.012, best.lat - 0.022, f"Proposed: near {best.candidate_site_near}\n"
            f"{best.orders_reassigned_per_day:.0f} orders/day move here,\nlate {best.late_pct_now:.0f}% → {best.late_pct_new:.0f}%",
            fontsize=8.5, color=INK, zorder=6,
            bbox=dict(boxstyle="round,pad=0.35", fc=SURFACE, ec=GRID, lw=0.8))
    ax.set_aspect(1 / np.cos(np.radians(12.95)))
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], ls="", marker="o", ms=5, color=MUTED_BAR, label="Order ≤ 3.5 km from store"),
        Line2D([], [], ls="", marker="o", ms=5, color=ORANGE, label="Order > 3.5 km from store"),
        Line2D([], [], ls="", marker="o", ms=9, color=BLUE, label="Existing dark store"),
        Line2D([], [], ls="", marker="*", ms=14, color=INK, label="Proposed new store"),
    ]
    ax.legend(handles=handles, loc="lower left")
    ax.set_title("Where to open the next dark store")
    _subtitle(ax, "Customer order locations, Bengaluru (25k-order sample)")
    _save(fig, path)
