"""
Generate a realistic synthetic dataset for a quick-commerce (10-minute delivery)
company operating 12 dark stores in Bengaluru, Jan-Jun 2026.

Real dark-store data is not public, so this script simulates it. The simulation
is driven by an explicit operational model rather than random numbers:

  delivery time = picking time + rider wait time + travel time

  * picking time grows with basket size and is slower in older/smaller stores
  * rider wait time grows sharply once rider utilisation passes ~75%
  * travel time grows with distance, peak-hour traffic and rain

Demand, basket contents, stockouts, cancellations, ratings and customer churn
all react to these operational conditions, so the analysis has real cause and
effect to uncover. A few data-quality problems (duplicates, inconsistent IDs,
clock-skew timestamps) are injected on purpose so the cleaning step has work
to do, just like a real export.

Run:  python src/generate_data.py
Output: data/raw/*.csv
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 17
START = pd.Timestamp("2026-01-01")
END = pd.Timestamp("2026-06-30")
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

rng = np.random.default_rng(SEED)

# --------------------------------------------------------------------------
# Master data
# --------------------------------------------------------------------------
# store_id, name, locality, lat, lon, area_sqft, opened, pick_penalty_min, staffing
STORES = [
    ("S01", "DS Koramangala", "Koramangala", 12.9352, 77.6245, 4200, "2024-03-01", 0.0, 1.4),
    ("S02", "DS Indiranagar", "Indiranagar", 12.9784, 77.6408, 4000, "2024-03-01", 0.0, 1.4),
    ("S03", "DS HSR Layout", "HSR Layout", 12.9116, 77.6474, 3800, "2024-06-15", 0.0, 1.4),
    ("S04", "DS Bellandur", "Bellandur", 12.9260, 77.6762, 3900, "2024-09-01", 0.0, 1.4),
    ("S05", "DS Jayanagar", "Jayanagar", 12.9299, 77.5826, 3600, "2024-06-15", 0.0, 1.4),
    ("S06", "DS BTM Layout", "BTM Layout", 12.9166, 77.6101, 3700, "2024-09-01", 0.0, 1.4),
    ("S07", "DS Whitefield", "Whitefield", 12.9698, 77.7500, 4100, "2025-01-10", 0.0, 0.85),
    ("S08", "DS Marathahalli", "Marathahalli", 12.9569, 77.7011, 3900, "2025-01-10", 0.0, 1.4),
    ("S09", "DS Malleshwaram", "Malleshwaram", 13.0031, 77.5643, 3500, "2025-04-01", 0.0, 1.4),
    ("S10", "DS Electronic City", "Electronic City", 12.8452, 77.6602, 2600, "2023-11-20", 1.9, 1.4),
    ("S11", "DS Hebbal", "Hebbal", 13.0358, 77.5970, 3800, "2025-04-01", 0.0, 1.4),
    ("S12", "DS Yelahanka", "Yelahanka", 13.1005, 77.5963, 3400, "2025-07-01", 0.0, 1.4),
]

# Planted incident: HSR Layout loses riders to a competitor from mid-May.
INCIDENT_STORE = "S03"
INCIDENT_START = pd.Timestamp("2026-05-18")
INCIDENT_STAFFING = 0.65

# Micro-areas customers live in: name, lat, lon, demand weight, monthly growth
AREAS = [
    ("Koramangala 5th Block", 12.9346, 77.6190, 1.0, 0.02),
    ("Koramangala 1st Block", 12.9285, 77.6330, 0.8, 0.02),
    ("Ejipura", 12.9440, 77.6260, 0.6, 0.02),
    ("Indiranagar 100ft Rd", 12.9719, 77.6412, 1.0, 0.02),
    ("Domlur", 12.9610, 77.6387, 0.7, 0.02),
    ("HAL 2nd Stage", 12.9850, 77.6480, 0.6, 0.02),
    ("HSR Sector 2", 12.9105, 77.6420, 1.0, 0.03),
    ("HSR Sector 7", 12.9080, 77.6540, 0.8, 0.03),
    ("Agara", 12.9240, 77.6510, 0.5, 0.03),
    ("Bellandur Lake Rd", 12.9300, 77.6780, 0.9, 0.03),
    ("Ecospace", 12.9265, 77.6920, 0.7, 0.03),
    ("Kasavanahalli", 12.9100, 77.6990, 0.6, 0.07),
    ("Carmelaram", 12.9050, 77.7080, 0.7, 0.10),
    ("Jayanagar 4th Block", 12.9250, 77.5838, 1.0, 0.01),
    ("Basavanagudi", 12.9420, 77.5750, 0.7, 0.01),
    ("JP Nagar", 12.9080, 77.5850, 0.8, 0.02),
    ("BTM 2nd Stage", 12.9160, 77.6100, 1.0, 0.02),
    ("Madiwala", 12.9220, 77.6180, 0.6, 0.02),
    ("Begur", 12.8800, 77.6250, 0.5, 0.06),
    ("Whitefield Main Rd", 12.9690, 77.7490, 0.9, 0.04),
    ("ITPL", 12.9850, 77.7350, 0.7, 0.04),
    ("Varthur", 12.9420, 77.7460, 0.6, 0.06),
    ("Marathahalli Bridge", 12.9560, 77.7010, 0.9, 0.03),
    ("Kundalahalli", 12.9650, 77.7150, 0.6, 0.03),
    ("Malleshwaram 8th Cross", 13.0030, 77.5700, 0.9, 0.01),
    ("Rajajinagar", 12.9910, 77.5550, 0.7, 0.01),
    ("Electronic City Ph 1", 12.8450, 77.6600, 1.0, 0.03),
    ("Electronic City Ph 2", 12.8350, 77.6800, 0.6, 0.03),
    ("Hebbal Kempapura", 13.0350, 77.5940, 0.8, 0.03),
    ("RT Nagar", 13.0220, 77.5950, 0.6, 0.02),
    ("Yelahanka New Town", 13.1000, 77.5900, 0.8, 0.03),
    ("Jakkur", 13.0700, 77.6050, 0.5, 0.05),
]

# sku_id, name, category, price (INR)
PRODUCTS = [
    ("P001", "Toned Milk 500ml", "Dairy & Bread", 28),
    ("P002", "Full Cream Milk 1L", "Dairy & Bread", 68),
    ("P003", "White Bread 400g", "Dairy & Bread", 45),
    ("P004", "Brown Bread 400g", "Dairy & Bread", 55),
    ("P005", "Eggs (6 pcs)", "Dairy & Bread", 54),
    ("P006", "Salted Butter 100g", "Dairy & Bread", 58),
    ("P007", "Curd 400g", "Dairy & Bread", 40),
    ("P008", "Paneer 200g", "Dairy & Bread", 90),
    ("P009", "Cheese Slices 200g", "Dairy & Bread", 140),
    ("P010", "Onion 1kg", "Fruits & Vegetables", 42),
    ("P011", "Tomato 1kg", "Fruits & Vegetables", 36),
    ("P012", "Potato 1kg", "Fruits & Vegetables", 38),
    ("P013", "Coriander Bunch", "Fruits & Vegetables", 15),
    ("P014", "Green Chilli 100g", "Fruits & Vegetables", 12),
    ("P015", "Banana (6 pcs)", "Fruits & Vegetables", 48),
    ("P016", "Apple Shimla (4 pcs)", "Fruits & Vegetables", 160),
    ("P017", "Lemon (4 pcs)", "Fruits & Vegetables", 20),
    ("P018", "Ginger 100g", "Fruits & Vegetables", 18),
    ("P019", "Potato Chips Classic 52g", "Snacks", 20),
    ("P020", "Masala Potato Chips 90g", "Snacks", 40),
    ("P021", "Bhujia Namkeen 200g", "Snacks", 55),
    ("P022", "Milk Chocolate Bar 50g", "Snacks", 50),
    ("P023", "Cream Biscuits 120g", "Snacks", 35),
    ("P024", "Salted Peanuts 200g", "Snacks", 60),
    ("P025", "Cola 750ml", "Beverages", 40),
    ("P026", "Lemon Soda 750ml", "Beverages", 40),
    ("P027", "Packaged Water 1L", "Beverages", 20),
    ("P028", "Mango Drink 600ml", "Beverages", 35),
    ("P029", "Instant Coffee 50g", "Beverages", 165),
    ("P030", "Tea Leaves 250g", "Beverages", 140),
    ("P031", "Energy Drink 250ml", "Beverages", 125),
    ("P032", "Instant Noodles Masala (4 pack)", "Instant Food", 56),
    ("P033", "Cup Noodles", "Instant Food", 50),
    ("P034", "Tomato Ketchup 500g", "Instant Food", 120),
    ("P035", "Ready-to-Eat Dal Makhani", "Instant Food", 99),
    ("P036", "Frozen Paratha (5 pcs)", "Instant Food", 85),
    ("P037", "Vanilla Ice Cream Tub 700ml", "Ice Cream & Frozen", 180),
    ("P038", "Chocolate Ice Cream Cone", "Ice Cream & Frozen", 45),
    ("P039", "Kulfi Stick", "Ice Cream & Frozen", 30),
    ("P040", "Frozen Peas 500g", "Ice Cream & Frozen", 95),
    ("P041", "Whole Wheat Atta 5kg", "Staples", 265),
    ("P042", "Sunflower Oil 1L", "Staples", 155),
    ("P043", "Basmati Rice 1kg", "Staples", 140),
    ("P044", "Toor Dal 1kg", "Staples", 170),
    ("P045", "Sugar 1kg", "Staples", 48),
    ("P046", "Iodised Salt 1kg", "Staples", 28),
    ("P047", "Liquid Detergent 1L", "Household", 210),
    ("P048", "Dishwash Bar (3 pcs)", "Household", 60),
    ("P049", "Garbage Bags (30 pcs)", "Household", 99),
    ("P050", "Toilet Cleaner 500ml", "Household", 105),
    ("P051", "Tissue Roll (4 pcs)", "Household", 140),
    ("P052", "Toothpaste 150g", "Personal Care", 110),
    ("P053", "Bath Soap (4 pcs)", "Personal Care", 160),
    ("P054", "Shampoo 180ml", "Personal Care", 185),
    ("P055", "Sanitary Pads (15 pcs)", "Personal Care", 199),
    ("P056", "Hand Wash Refill 750ml", "Personal Care", 115),
    ("P057", "Diapers Medium (20 pcs)", "Baby Care", 399),
    ("P058", "Baby Wipes (72 pcs)", "Baby Care", 165),
    ("P059", "Paracetamol Strip (OTC)", "Health & OTC", 32),
    ("P060", "Antacid Sachets", "Health & OTC", 45),
]

# Shopping "missions": core items bought together + time-of-day appeal.
# hours: weight by hour of day (24 values built from ranges)
MISSIONS = {
    "breakfast": {
        "core": ["P001", "P003", "P005", "P006"],
        "core_p": [0.85, 0.75, 0.55, 0.35],
        "extra": ["P007", "P015", "P029", "P004", "P002"],
        "hours": {range(6, 11): 5.0, range(11, 13): 1.0, range(20, 23): 0.8},
    },
    "evening_snacks": {
        "core": ["P019", "P025", "P021", "P022"],
        "core_p": [0.75, 0.7, 0.4, 0.35],
        "extra": ["P020", "P024", "P026", "P023", "P027"],
        "hours": {range(16, 19): 2.0, range(19, 24): 3.5, range(0, 2): 2.0},
    },
    "quick_meal": {
        "core": ["P032", "P033", "P034", "P036"],
        "core_p": [0.75, 0.35, 0.3, 0.3],
        "extra": ["P035", "P025", "P001", "P005"],
        "hours": {range(12, 15): 2.0, range(20, 24): 2.5, range(0, 3): 2.5},
    },
    "cooking": {
        "core": ["P010", "P011", "P013", "P014"],
        "core_p": [0.8, 0.75, 0.55, 0.45],
        "extra": ["P012", "P008", "P017", "P018", "P042", "P041", "P044"],
        "hours": {range(8, 13): 3.0, range(16, 20): 2.5},
    },
    "stock_up": {
        "core": ["P041", "P042", "P043", "P044", "P045"],
        "core_p": [0.5, 0.5, 0.4, 0.4, 0.4],
        "extra": ["P046", "P030", "P047", "P048"],
        "hours": {range(9, 13): 2.0, range(15, 21): 1.5},
    },
    "household": {
        "core": ["P047", "P048", "P049", "P050", "P051"],
        "core_p": [0.45, 0.45, 0.4, 0.3, 0.35],
        "extra": ["P056", "P053"],
        "hours": {range(9, 22): 1.0},
    },
    "personal_care": {
        "core": ["P052", "P053", "P054", "P055", "P056"],
        "core_p": [0.4, 0.4, 0.35, 0.3, 0.3],
        "extra": ["P059", "P051"],
        "hours": {range(8, 23): 1.0},
    },
    "ice_cream": {
        "core": ["P037", "P038", "P039"],
        "core_p": [0.6, 0.5, 0.35],
        "extra": ["P022", "P025"],
        "hours": {range(13, 17): 1.5, range(17, 24): 2.5},
    },
    "baby": {
        "core": ["P057", "P058"],
        "core_p": [0.8, 0.6],
        "extra": ["P001", "P055"],
        "hours": {range(0, 24): 1.0},
    },
    "fruits_healthy": {
        "core": ["P015", "P016", "P007", "P017"],
        "core_p": [0.6, 0.5, 0.4, 0.3],
        "extra": ["P027", "P001"],
        "hours": {range(7, 12): 2.0, range(16, 20): 1.5},
    },
    "unwell": {
        "core": ["P059", "P060", "P026"],
        "core_p": [0.7, 0.4, 0.4],
        "extra": ["P027", "P017"],
        "hours": {range(0, 24): 1.0},
    },
}
MISSION_BASE_SHARE = {
    "breakfast": 0.17, "evening_snacks": 0.17, "quick_meal": 0.12, "cooking": 0.15,
    "stock_up": 0.06, "household": 0.07, "personal_care": 0.07, "ice_cream": 0.06,
    "baby": 0.03, "fruits_healthy": 0.07, "unwell": 0.03,
}

HOUR_PROFILE = np.array([
    1.0, 0.6, 0.3, 0.15, 0.1, 0.2, 1.5, 3.5, 5.5, 6.0, 5.0, 4.2,
    4.0, 4.0, 3.2, 3.0, 3.6, 4.8, 6.8, 8.6, 9.6, 9.0, 6.2, 3.0,
])
PEAK_TRAFFIC_HOURS = set(range(8, 11)) | set(range(17, 22))
RAIN_PROB_BY_MONTH = {1: 0.02, 2: 0.03, 3: 0.08, 4: 0.18, 5: 0.33, 6: 0.42}
FESTIVAL_DAYS = {
    pd.Timestamp("2026-01-14"): 1.35,  # Makar Sankranti
    pd.Timestamp("2026-03-04"): 1.30,  # Holi
    pd.Timestamp("2026-03-19"): 1.30,  # Ugadi
}
ORDERS_PER_RIDER_HOUR = 2.2


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def hours_weight(spec: dict) -> np.ndarray:
    w = np.full(24, 0.15)
    for hrs, val in spec.items():
        for h in hrs:
            w[h] = max(w[h], val)
    return w


# --------------------------------------------------------------------------
# Calendar and weather
# --------------------------------------------------------------------------
def build_calendar():
    days = pd.date_range(START, END, freq="D")
    n = len(days)
    dow_mult = np.array([0.95, 0.95, 0.97, 1.0, 1.06, 1.2, 1.24])  # Mon..Sun
    month_idx = (days.month - 1).to_numpy()
    rain_day = rng.random(n) < np.array([RAIN_PROB_BY_MONTH[m] for m in days.month])
    day_weight = dow_mult[days.dayofweek] * (1 + 0.035 * month_idx) * np.where(rain_day, 1.08, 1.0)
    day_weight *= np.array([FESTIVAL_DAYS.get(d, 1.0) for d in days])

    # Hourly weather: rain arrives in the afternoon/evening on rain days
    weather = np.full((n, 24), "Clear", dtype=object)
    cloudy = rng.random((n, 24)) < 0.25
    weather[cloudy] = "Cloudy"
    hour_weights = np.tile(HOUR_PROFILE, (n, 1)).astype(float)
    for i in np.where(rain_day)[0]:
        start = int(rng.integers(14, 20))
        dur = int(rng.integers(2, 6))
        hrs = [h % 24 for h in range(start, start + dur)]
        heavy = rng.random() < 0.35
        for h in hrs:
            weather[i, h] = "Heavy Rain" if heavy else "Rain"
            hour_weights[i, h] *= 1.25 if heavy else 1.18  # people order in when it rains
    hour_weights /= hour_weights.sum(axis=1, keepdims=True)

    cal = pd.DataFrame({"date": days, "day_weight": day_weight, "rain_day": rain_day})
    weather_df = pd.DataFrame(
        [(days[i].date(), h, weather[i, h]) for i in range(n) for h in range(24)],
        columns=["date", "hour", "condition"],
    )
    return cal, weather, hour_weights, weather_df


# --------------------------------------------------------------------------
# Customers and candidate orders
# --------------------------------------------------------------------------
def build_customers(n_customers=25000):
    areas = pd.DataFrame(AREAS, columns=["area", "lat", "lon", "weight", "growth"])
    stores = pd.DataFrame(STORES, columns=["store_id", "store_name", "locality", "lat", "lon",
                                           "area_sqft", "opened_on", "pick_penalty", "staffing"])
    area_idx = rng.choice(len(areas), size=n_customers, p=areas.weight / areas.weight.sum())
    lat = areas.lat.to_numpy()[area_idx] + rng.normal(0, 0.0055, n_customers)
    lon = areas.lon.to_numpy()[area_idx] + rng.normal(0, 0.0055, n_customers)

    # Signup: 55% existing customers; growth areas skew towards later signups
    total_days = (END - START).days
    existing = rng.random(n_customers) < 0.55
    growth = areas.growth.to_numpy()[area_idx]
    late_skew = rng.beta(1 + growth * 25, 1.3, n_customers)
    signup_offset = np.where(existing, -rng.integers(30, 600, n_customers), (late_skew * total_days).astype(int))
    signup = START + pd.to_timedelta(signup_offset, unit="D")

    # Nearest store
    d = haversine_km(lat[:, None], lon[:, None], stores.lat.to_numpy()[None, :], stores.lon.to_numpy()[None, :])
    nearest = d.argmin(axis=1)
    road_km = d[np.arange(n_customers), nearest] * rng.uniform(1.22, 1.42, n_customers) + 0.15

    cust = pd.DataFrame({
        "customer_id": [f"C{100000 + i}" for i in range(n_customers)],
        "area": areas.area.to_numpy()[area_idx],
        "lat": lat.round(5),
        "lon": lon.round(5),
        "signup_date": signup.date,
        "home_store_id": stores.store_id.to_numpy()[nearest],
        "road_km": road_km.round(2),
        "order_rate": rng.gamma(1.15, 0.047 / 1.15, n_customers),  # orders/day propensity
        "segment": rng.choice(["Student", "Working Professional", "Family"], n_customers, p=[0.2, 0.5, 0.3]),
    })
    return cust, stores, areas


def candidate_orders(cust, cal, hour_weights):
    days = cal.date.to_numpy()
    w = cal.day_weight.to_numpy()
    w = w / w.mean()
    cumw = np.concatenate([[0], np.cumsum(w)])
    rows_c, rows_d = [], []
    start_idx = np.clip((pd.to_datetime(cust.signup_date) - START).dt.days.to_numpy(), 0, len(days) - 1)
    for ci, (s, rate) in enumerate(zip(start_idx, cust.order_rate.to_numpy())):
        expected = rate * (cumw[-1] - cumw[s])
        k = rng.poisson(expected)
        if k == 0:
            continue
        p = w[s:] / w[s:].sum()
        chosen = rng.choice(np.arange(s, len(days)), size=k, p=p)
        rows_c.extend([ci] * k)
        rows_d.extend(chosen.tolist())
    rows_c = np.array(rows_c)
    rows_d = np.array(rows_d)
    # Hour within day using that day's hour weights (includes rain uplift)
    u = rng.random(len(rows_d))
    cumh = np.cumsum(hour_weights, axis=1)
    hours = np.array([np.searchsorted(cumh[d], x) for d, x in zip(rows_d, u)])
    hours = np.clip(hours, 0, 23)
    minutes = rng.integers(0, 60, len(rows_d))
    seconds = rng.integers(0, 60, len(rows_d))
    ts = pd.to_datetime(days[rows_d]) + pd.to_timedelta(hours, "h") + pd.to_timedelta(minutes, "m") + pd.to_timedelta(seconds, "s")
    cand = pd.DataFrame({"cust_idx": rows_c, "day_idx": rows_d, "hour": hours, "order_ts": ts})
    cand = cand.sort_values("order_ts").reset_index(drop=True)
    return cand


# --------------------------------------------------------------------------
# Baskets and stockouts
# --------------------------------------------------------------------------
PRICE = {p[0]: p[3] for p in PRODUCTS}
ALL_SKUS = [p[0] for p in PRODUCTS]
MISSION_NAMES = list(MISSIONS)
MISSION_HOUR_W = np.array([hours_weight(MISSIONS[m]["hours"]) for m in MISSION_NAMES])  # (M,24)
MISSION_SHARE = np.array([MISSION_BASE_SHARE[m] for m in MISSION_NAMES])


def mission_probs(hour, month, weekend, segment):
    p = MISSION_SHARE * MISSION_HOUR_W[:, hour]
    if month in (4, 5):
        p[MISSION_NAMES.index("ice_cream")] *= 2.6
    elif month in (3, 6):
        p[MISSION_NAMES.index("ice_cream")] *= 1.5
    if weekend:
        p[MISSION_NAMES.index("evening_snacks")] *= 1.35
        p[MISSION_NAMES.index("stock_up")] *= 1.4
    if segment == "Family":
        p[MISSION_NAMES.index("baby")] *= 3.0
        p[MISSION_NAMES.index("cooking")] *= 1.4
        p[MISSION_NAMES.index("stock_up")] *= 1.5
    elif segment == "Student":
        p[MISSION_NAMES.index("quick_meal")] *= 1.8
        p[MISSION_NAMES.index("evening_snacks")] *= 1.4
        p[MISSION_NAMES.index("stock_up")] *= 0.3
        p[MISSION_NAMES.index("baby")] *= 0.05
    return p / p.sum()


def build_basket(mission):
    m = MISSIONS[mission]
    items = [s for s, pr in zip(m["core"], m["core_p"]) if rng.random() < pr]
    if not items:
        items = [m["core"][0]]
    for s in m["extra"]:
        if rng.random() < 0.18:
            items.append(s)
    n_random = rng.choice([0, 1, 2], p=[0.55, 0.32, 0.13])
    for s in rng.choice(ALL_SKUS, size=n_random, replace=False):
        items.append(s)
    seen, basket = set(), []
    for s in items:
        if s not in seen:
            seen.add(s)
            qty = 1 if rng.random() < 0.82 else int(rng.integers(2, 4))
            basket.append((s, qty))
    return basket


def stockout_prob(sku, store, month, hour):
    p = 0.018
    if sku in ("P013", "P014"):           # perishables: coriander, chilli
        p = 0.11
    if sku in ("P037", "P038", "P039") and store in ("S10", "S05") and month in (4, 5):
        p = 0.30                           # small freezers cannot keep up in summer
    elif sku in ("P037", "P038", "P039") and month in (4, 5):
        p = 0.06
    if sku in ("P001", "P002", "P003", "P004") and store in ("S07", "S08") and 6 <= hour <= 9:
        p = 0.17                           # morning dairy/bread restock arrives late
    if sku == "P005" and store == "S12":
        p = 0.09
    if sku == "P016" and month in (5, 6):
        p = 0.08                           # apples off-season
    return p


# --------------------------------------------------------------------------
# Operations simulation
# --------------------------------------------------------------------------
def rider_schedule(cand_store, cand, stores, survival=0.86):
    """Riders per store/day/hour planned from expected demand x staffing level."""
    tmp = pd.DataFrame({"store_id": cand_store, "date": cand.order_ts.dt.normalize(), "hour": cand.hour})
    tmp["dow"] = tmp.date.dt.dayofweek
    n_days = (END - START).days + 1
    # planners use average demand by store x hour-of-day x weekend flag
    tmp["weekend"] = tmp.dow >= 5
    counts = tmp.groupby(["store_id", "weekend", "hour"]).size().rename("n").reset_index()
    n_weekend_days = sum(1 for d in pd.date_range(START, END) if d.dayofweek >= 5)
    counts["per_day"] = counts.n / np.where(counts.weekend, n_weekend_days, n_days - n_weekend_days) * survival
    plan = {(r.store_id, r.weekend, r.hour): r.per_day for r in counts.itertuples()}

    staffing = dict(zip(stores.store_id, stores.staffing))
    rows = []
    for d in pd.date_range(START, END):
        wk = d.dayofweek >= 5
        for sid in stores.store_id:
            for h in range(24):
                exp_orders = plan.get((sid, wk, h), 0.0)
                st = staffing[sid]
                if sid == INCIDENT_STORE and d >= INCIDENT_START:
                    st = INCIDENT_STAFFING
                riders = exp_orders / ORDERS_PER_RIDER_HOUR * st
                riders = riders + rng.normal(0, 0.35)          # absenteeism / extra shifts
                min_r = 1
                riders = max(min_r, int(round(riders)))
                rows.append((d.date(), h, sid, riders))
    return pd.DataFrame(rows, columns=["date", "hour", "store_id", "riders_on_shift"])


def simulate(cand, cust, stores, weather, cal):
    n = len(cand)
    cust_store = cust.home_store_id.to_numpy()[cand.cust_idx]
    dist = cust.road_km.to_numpy()[cand.cust_idx] * rng.uniform(0.95, 1.08, n)
    segment = cust.segment.to_numpy()[cand.cust_idx]
    months = cand.order_ts.dt.month.to_numpy()
    weekend = (cand.order_ts.dt.dayofweek >= 5).to_numpy()
    hours = cand.hour.to_numpy()
    cond = weather[cand.day_idx.to_numpy(), hours]
    pick_pen = dict(zip(stores.store_id, stores.pick_penalty))

    # Baskets + stockouts (fixed across passes)
    baskets, missions = [], []
    for i in range(n):
        p = mission_probs(hours[i], months[i], weekend[i], segment[i])
        m = MISSION_NAMES[rng.choice(len(MISSION_NAMES), p=p)]
        missions.append(m)
        b = build_basket(m)
        b = [(s, q, rng.random() >= stockout_prob(s, cust_store[i], months[i], hours[i])) for s, q in b]
        baskets.append(b)
    n_items = np.array([sum(q for _, q, ok in b if ok) for b in baskets])
    n_missing = np.array([sum(1 for _, _, ok in b if not ok) for b in baskets])
    n_lines = np.array([len(b) for b in baskets])

    # Fixed noise so both passes are consistent
    e_pick = np.exp(rng.normal(0, 0.25, n))
    e_wait = np.exp(rng.normal(0, 0.40, n))
    e_trav = np.exp(rng.normal(0, 0.14, n))
    u_cancel = rng.random(n)
    u_churn = rng.random(n)

    peak = np.isin(hours, list(PEAK_TRAFFIC_HOURS))
    rain = np.isin(cond, ["Rain", "Heavy Rain"])
    heavy = cond == "Heavy Rain"
    speed = 2.4 * np.where(peak, 1.25, 1.0) * np.where(rain, 1.32, 1.0) * np.where(heavy, 1.12, 1.0) * np.where(weekend & ~peak, 0.95, 1.0)
    travel = (0.8 + dist * speed) * e_trav
    pick = (1.1 + 0.32 * np.maximum(n_items, 1) + np.array([pick_pen[s] for s in cust_store]) + 0.35 * peak) * e_pick
    promised = np.where(dist <= 1.5, 10, np.where(dist <= 2.5, 12, np.where(dist <= 3.5, 15, 18)))

    sched = rider_schedule(cust_store, cand, stores)
    sched_key = {(r.date, r.hour, r.store_id): r.riders_on_shift for r in sched.itertuples()}
    dates = cand.order_ts.dt.date.to_numpy()
    riders = np.array([sched_key[(dates[i], hours[i], cust_store[i])] for i in range(n)])

    def run_pass(alive):
        key = pd.Series(list(zip(dates, hours, cust_store)))
        load = key[alive].value_counts()
        orders_in_hour = key.map(load).fillna(1).to_numpy()
        util = orders_in_hour / (riders * ORDERS_PER_RIDER_HOUR)
        wait = (0.5 + 5.5 * np.maximum(0, util - 0.75) ** 1.4) * e_wait
        total = pick + wait + travel
        late_by = total - promised
        late = late_by > 0
        # Cancellation
        all_missing = n_missing == n_lines
        p_cancel = 0.018 + 0.55 * all_missing + 0.07 * (util > 1.35) + 0.03 * (n_missing > 0)
        cancelled = u_cancel < p_cancel
        # Churn: process chronologically per customer
        new_alive = np.ones(n, dtype=bool)
        churned = set()
        cidx = cand.cust_idx.to_numpy()
        for i in range(n):
            c = cidx[i]
            if c in churned:
                new_alive[i] = False
                continue
            if cancelled[i]:
                pc = 0.14
            elif late[i]:
                pc = 0.09 + 0.018 * min(late_by[i], 12)
            else:
                pc = 0.022
            if n_missing[i] > 0:
                pc += 0.05
            if u_churn[i] < pc:
                churned.add(c)
        return new_alive, orders_in_hour, util, wait, total, late, cancelled, all_missing

    alive = np.ones(n, dtype=bool)
    for _ in range(3):  # iterate so load reflects surviving orders
        alive, *_ = run_pass(alive)
    _, orders_in_hour, util, wait, total, late, cancelled, all_missing = run_pass(alive)

    keep = np.where(alive)[0]
    return dict(
        keep=keep, cust_store=cust_store, dist=dist, cond=cond, missions=missions, baskets=baskets,
        n_missing=n_missing, pick=pick, wait=wait, travel=travel, total=total, late=late,
        promised=promised, riders=riders, orders_in_hour=orders_in_hour, cancelled=cancelled,
        all_missing=all_missing, util=util, sched=sched,
    )


def assemble(cand, cust, sim):
    keep = sim["keep"]
    c = cand.iloc[keep].reset_index(drop=True)
    n = len(c)
    order_ids = [f"ORD{2600000 + i}" for i in range(n)]
    ts = c.order_ts
    pick = sim["pick"][keep]
    wait = sim["wait"][keep]
    travel = sim["travel"][keep]
    cancelled = sim["cancelled"][keep]
    late = sim["late"][keep]
    total = sim["total"][keep]
    promised = sim["promised"][keep]
    n_missing = sim["n_missing"][keep]
    all_missing = sim["all_missing"][keep]
    util = sim["util"][keep]

    packed = ts + pd.to_timedelta(pick, "m")
    dispatched = packed + pd.to_timedelta(wait, "m")
    delivered = dispatched + pd.to_timedelta(travel, "m")

    items_rows, item_totals = [], np.zeros(n)
    for j, i in enumerate(keep):
        tot = 0.0
        for line, (sku, q, ok) in enumerate(sim["baskets"][i], start=1):
            items_rows.append((order_ids[j], line, sku, q, PRICE[sku], int(ok)))
            if ok:
                tot += q * PRICE[sku]
        item_totals[j] = tot

    coupon = rng.random(n) < 0.28
    discount = np.where(coupon, np.minimum(np.round(item_totals * 0.10), 75), 0)
    delivery_fee = np.where(item_totals >= 199, 0, 25)
    small_cart_fee = np.where(item_totals < 99, 15, 0)

    reasons = np.where(
        all_missing, "Items unavailable",
        np.where(util > 1.35, "Delivery taking too long",
                 rng.choice(["Changed mind", "Payment failed", "Ordered by mistake"], n, p=[0.5, 0.3, 0.2])),
    )
    rated = rng.random(n) < 0.55
    late_by = total - promised
    rating = 4.75 - 1.25 * late - 0.07 * np.clip(late_by, 0, 20) - 0.85 * (n_missing > 0) + rng.normal(0, 0.45, n)
    rating = np.clip(np.round(rating), 1, 5)

    orders = pd.DataFrame({
        "order_id": order_ids,
        "customer_id": cust.customer_id.to_numpy()[c.cust_idx],
        "store_id": sim["cust_store"][keep],
        "order_ts": ts,
        "packed_ts": packed.where(~cancelled),
        "dispatched_ts": dispatched.where(~cancelled),
        "delivered_ts": delivered.where(~cancelled),
        "promised_eta_min": promised,
        "distance_km": sim["dist"][keep].round(2),
        "weather": sim["cond"][keep],
        "riders_on_shift": sim["riders"][keep],
        "store_orders_in_hour": sim["orders_in_hour"][keep].astype(int),
        "item_lines": [len(sim["baskets"][i]) for i in keep],
        "items_missing": n_missing,
        "item_total": np.where(cancelled, 0, item_totals).round(2),
        "discount": np.where(cancelled, 0, discount),
        "delivery_fee": np.where(cancelled, 0, delivery_fee),
        "small_cart_fee": np.where(cancelled, 0, small_cart_fee),
        "payment_method": rng.choice(["UPI", "Card", "Cash on Delivery", "Wallet"], n, p=[0.68, 0.14, 0.12, 0.06]),
        "status": np.where(cancelled, "Cancelled", "Delivered"),
        "cancel_reason": np.where(cancelled, reasons, None),
        "rating": np.where(rated & ~cancelled, rating, np.nan),
    })
    orders["order_value"] = (orders.item_total - orders.discount + orders.delivery_fee + orders.small_cart_fee).round(2)
    for col in ["order_ts", "packed_ts", "dispatched_ts", "delivered_ts"]:
        orders[col] = orders[col].dt.floor("s")

    items = pd.DataFrame(items_rows, columns=["order_id", "line_no", "sku_id", "quantity", "unit_price", "fulfilled"])
    return orders, items


def inject_quality_issues(orders: pd.DataFrame) -> pd.DataFrame:
    """Simulate a messy production export."""
    o = orders.copy()
    n = len(o)
    # 1) inconsistent store IDs (lower-case / padded)
    idx = rng.choice(n, int(n * 0.006), replace=False)
    o.loc[idx[: len(idx) // 2], "store_id"] = o.loc[idx[: len(idx) // 2], "store_id"].str.lower()
    o.loc[idx[len(idx) // 2:], "store_id"] = " " + o.loc[idx[len(idx) // 2:], "store_id"]
    # 2) payment method label drift
    idx = rng.choice(n, int(n * 0.01), replace=False)
    o.loc[idx, "payment_method"] = o.loc[idx, "payment_method"].replace({"Cash on Delivery": "COD", "UPI": "upi"})
    # 3) GPS / clock-skew: delivered before dispatched, or absurd 3-hour deliveries
    delivered = o.index[o.status == "Delivered"]
    bad = rng.choice(delivered, 70, replace=False)
    o.loc[bad[:40], "delivered_ts"] = o.loc[bad[:40], "dispatched_ts"] - pd.to_timedelta(rng.integers(1, 6, 40), "m")
    o.loc[bad[40:], "delivered_ts"] = o.loc[bad[40:], "dispatched_ts"] + pd.to_timedelta(rng.integers(150, 300, 30), "m")
    # 4) missing distance (geocoding failures)
    idx = rng.choice(n, int(n * 0.003), replace=False)
    o.loc[idx, "distance_km"] = np.nan
    # 5) duplicate rows from a retry bug in the export job
    dups = o.sample(frac=0.004, random_state=SEED)
    o = pd.concat([o, dups]).sort_values("order_ts", kind="stable").reset_index(drop=True)
    return o


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cal, weather, hour_weights, weather_df = build_calendar()
    cust, stores, areas = build_customers()
    cand = candidate_orders(cust, cal, hour_weights)
    print(f"candidate orders: {len(cand):,}")
    sim = simulate(cand, cust, stores, weather, cal)
    orders, items = assemble(cand, cust, sim)
    orders_raw = inject_quality_issues(orders)

    stores_out = stores[["store_id", "store_name", "locality", "lat", "lon", "area_sqft", "opened_on"]]
    products = pd.DataFrame(PRODUCTS, columns=["sku_id", "product_name", "category", "mrp"])
    customers_out = cust[["customer_id", "area", "lat", "lon", "signup_date", "segment"]]
    shifts = sim["sched"]

    stores_out.to_csv(RAW_DIR / "stores.csv", index=False)
    products.to_csv(RAW_DIR / "products.csv", index=False)
    customers_out.to_csv(RAW_DIR / "customers.csv", index=False)
    orders_raw.to_csv(RAW_DIR / "orders.csv", index=False)
    items.to_csv(RAW_DIR / "order_items.csv", index=False)
    shifts.to_csv(RAW_DIR / "rider_shifts.csv", index=False)
    weather_df.to_csv(RAW_DIR / "weather_hourly.csv", index=False)

    d = orders[orders.status == "Delivered"]
    dt = (d.delivered_ts - d.order_ts).dt.total_seconds() / 60
    print(f"orders: {len(orders):,} (raw with dups: {len(orders_raw):,}) | items: {len(items):,} | customers: {len(customers_out):,}")
    print(f"avg delivery {dt.mean():.1f} min | late rate {(dt > d.promised_eta_min).mean():.1%} | "
          f"cancel rate {(orders.status == 'Cancelled').mean():.1%}")


if __name__ == "__main__":
    main()
