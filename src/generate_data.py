"""
Generate a realistic synthetic dataset for a quick-commerce (10-minute delivery)
company running 52 dark stores across 8 Indian metros, Jan-Jun 2026.

Real dark-store data is not public, so this script simulates it. The simulation
is driven by an explicit operational model rather than random numbers:

  delivery time = picking time + rider wait time + travel time

  * picking time grows with basket size and is slower in older/smaller stores
  * rider wait time grows sharply once orders per rider pass capacity
  * travel time grows with distance and the city's traffic, and is hit by
    rain, fog and heatwaves

Every city has its own calendar: Mumbai's June monsoon, Delhi's winter fog and
summer heatwaves, Kolkata's April-May nor'westers, regional festivals (Pongal,
Uttarayan, Holi, Ugadi/Gudi Padwa, Eid, Poila Baisakh) and fast-growing suburbs
that sit far from the nearest store.

Demand, basket contents, stockouts, cancellations, ratings and customer churn
all react to these operational conditions, so the analysis has real cause and
effect to uncover. A few data-quality problems (duplicates, inconsistent IDs,
clock-skew timestamps) are injected on purpose so the cleaning step has work
to do, just like a real export.

Run:  python src/generate_data.py
Output: data/raw/*.parquet + small reference CSVs
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 17
START = pd.Timestamp("2026-01-01")
END = pd.Timestamp("2026-06-30")
DAYS = pd.date_range(START, END, freq="D")
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

rng = np.random.default_rng(SEED)

# --------------------------------------------------------------------------
# Cities
# --------------------------------------------------------------------------
# speed = minutes per road-km in normal traffic; road = road distance / straight line
CITIES = pd.DataFrame([
    # code, name,        state,          lat,     lon,    speed, road, customers, existing, basket
    ("BLR", "Bengaluru", "Karnataka",     12.9716, 77.5946, 2.40, 1.32, 25000, 0.55, 1.05),
    ("MUM", "Mumbai",    "Maharashtra",   19.0760, 72.8777, 2.65, 1.42, 14000, 0.55, 1.08),
    ("DEL", "Delhi NCR", "Delhi / Haryana / UP", 28.6139, 77.2090, 2.30, 1.30, 16000, 0.55, 1.05),
    ("HYD", "Hyderabad", "Telangana",     17.3850, 78.4867, 2.15, 1.30,  9000, 0.50, 1.00),
    ("PUN", "Pune",      "Maharashtra",   18.5204, 73.8567, 2.25, 1.32,  7000, 0.45, 1.00),
    ("CHE", "Chennai",   "Tamil Nadu",    13.0827, 80.2707, 2.05, 1.28,  7500, 0.55, 0.97),
    ("KOL", "Kolkata",   "West Bengal",   22.5726, 88.3639, 2.35, 1.30,  5000, 0.40, 0.95),
    ("AMD", "Ahmedabad", "Gujarat",       23.0225, 72.5714, 1.95, 1.28,  3500, 0.35, 0.95),
], columns=["city_code", "city_name", "state", "lat", "lon", "speed_min_per_km", "road_factor",
            "n_customers", "existing_share", "basket_mult"])

# --------------------------------------------------------------------------
# Dark stores: id, city, locality, lat, lon, area_sqft, opened, pick_penalty_min, staffing
#   staffing 1.4 = planners schedule 40% headroom over average demand (healthy)
# --------------------------------------------------------------------------
STORES = [
    # Bengaluru
    ("BLR01", "BLR", "Koramangala", 12.9352, 77.6245, 4200, "2024-03-01", 0.0, 1.4),
    ("BLR02", "BLR", "Indiranagar", 12.9784, 77.6408, 4000, "2024-03-01", 0.0, 1.4),
    ("BLR03", "BLR", "HSR Layout", 12.9116, 77.6474, 3800, "2024-06-15", 0.0, 1.4),
    ("BLR04", "BLR", "Bellandur", 12.9260, 77.6762, 3900, "2024-09-01", 0.0, 1.4),
    ("BLR05", "BLR", "Jayanagar", 12.9299, 77.5826, 3600, "2024-06-15", 0.0, 1.4),
    ("BLR06", "BLR", "BTM Layout", 12.9166, 77.6101, 3700, "2024-09-01", 0.0, 1.4),
    ("BLR07", "BLR", "Whitefield", 12.9698, 77.7500, 4100, "2025-01-10", 0.0, 0.85),
    ("BLR08", "BLR", "Marathahalli", 12.9569, 77.7011, 3900, "2025-01-10", 0.0, 1.4),
    ("BLR09", "BLR", "Malleshwaram", 13.0031, 77.5643, 3500, "2025-04-01", 0.0, 1.4),
    ("BLR10", "BLR", "Electronic City", 12.8452, 77.6602, 2600, "2023-11-20", 1.9, 1.4),
    ("BLR11", "BLR", "Hebbal", 13.0358, 77.5970, 3800, "2025-04-01", 0.0, 1.4),
    ("BLR12", "BLR", "Yelahanka", 13.1005, 77.5963, 3400, "2025-07-01", 0.0, 1.4),
    # Mumbai
    ("MUM01", "MUM", "Andheri West", 19.1364, 72.8296, 3800, "2024-02-01", 0.0, 1.4),
    ("MUM02", "MUM", "Powai", 19.1176, 72.9060, 4000, "2024-02-01", 0.0, 1.4),
    ("MUM03", "MUM", "Bandra West", 19.0596, 72.8295, 3400, "2024-05-01", 0.0, 1.4),
    ("MUM04", "MUM", "Lower Parel", 18.9980, 72.8300, 3600, "2024-05-01", 0.0, 1.4),
    ("MUM05", "MUM", "Dadar", 19.0178, 72.8478, 2400, "2023-10-15", 1.6, 1.4),
    ("MUM06", "MUM", "Goregaon", 19.1663, 72.8526, 3700, "2024-09-01", 0.0, 1.4),
    ("MUM07", "MUM", "Chembur", 19.0522, 72.9005, 3600, "2025-02-01", 0.0, 1.4),
    ("MUM08", "MUM", "Thane West", 19.1972, 72.9722, 3900, "2025-02-01", 0.0, 1.4),
    # Delhi NCR
    ("DEL01", "DEL", "Saket", 28.5245, 77.2066, 3800, "2024-01-15", 0.0, 1.4),
    ("DEL02", "DEL", "Lajpat Nagar", 28.5677, 77.2433, 3500, "2024-01-15", 0.0, 1.4),
    ("DEL03", "DEL", "Rajouri Garden", 28.6415, 77.1209, 3600, "2024-04-01", 0.0, 1.4),
    ("DEL04", "DEL", "Dwarka", 28.5921, 77.0460, 3900, "2024-08-01", 0.0, 1.4),
    ("DEL05", "DEL", "Gurugram Cyber City", 28.4950, 77.0890, 4000, "2024-03-01", 0.0, 1.4),
    ("DEL06", "DEL", "Gurugram Sector 56", 28.4243, 77.0997, 3800, "2024-10-01", 0.0, 1.4),
    ("DEL07", "DEL", "Noida Sector 18", 28.5708, 77.3261, 3700, "2024-06-01", 0.0, 1.4),
    ("DEL08", "DEL", "Rohini", 28.7383, 77.0822, 3600, "2025-03-01", 0.0, 1.4),
    ("DEL09", "DEL", "Noida Sector 62", 28.6270, 77.3730, 3800, "2025-03-01", 0.0, 1.4),
    # Hyderabad
    ("HYD01", "HYD", "Gachibowli", 17.4401, 78.3489, 4000, "2024-07-01", 0.0, 1.4),
    ("HYD02", "HYD", "Madhapur", 17.4483, 78.3915, 3800, "2024-07-01", 0.0, 0.92),
    ("HYD03", "HYD", "Banjara Hills", 17.4156, 78.4347, 3500, "2024-10-01", 0.0, 1.4),
    ("HYD04", "HYD", "Kukatpally", 17.4948, 78.3996, 3700, "2025-01-15", 0.0, 1.4),
    ("HYD05", "HYD", "Begumpet", 17.4447, 78.4664, 3600, "2025-01-15", 0.0, 1.4),
    ("HYD06", "HYD", "Kondapur", 17.4622, 78.3568, 3700, "2025-05-01", 0.0, 1.4),
    # Pune
    ("PUN01", "PUN", "Koregaon Park", 18.5362, 73.8940, 3600, "2024-11-01", 0.0, 1.4),
    ("PUN02", "PUN", "Baner", 18.5590, 73.7868, 3800, "2024-11-01", 0.0, 1.4),
    ("PUN03", "PUN", "Hinjewadi", 18.5913, 73.7389, 3900, "2025-03-01", 0.0, 1.4),
    ("PUN04", "PUN", "Kothrud", 18.5074, 73.8077, 3500, "2025-03-01", 0.0, 1.4),
    ("PUN05", "PUN", "Kharadi", 18.5515, 73.9348, 3800, "2025-06-01", 0.0, 1.4),
    # Chennai
    ("CHE01", "CHE", "T Nagar", 13.0418, 80.2341, 3700, "2024-08-01", 0.0, 1.4),
    ("CHE02", "CHE", "Adyar", 13.0012, 80.2565, 3600, "2024-08-01", 0.0, 1.4),
    ("CHE03", "CHE", "Anna Nagar", 13.0850, 80.2101, 3800, "2024-12-01", 0.0, 1.4),
    ("CHE04", "CHE", "Velachery", 12.9815, 80.2180, 3700, "2025-02-01", 0.0, 1.4),
    ("CHE05", "CHE", "OMR Thoraipakkam", 12.9416, 80.2362, 3900, "2025-05-01", 0.0, 1.4),
    # Kolkata
    ("KOL01", "KOL", "Salt Lake Sector V", 22.5697, 88.4337, 3800, "2025-01-15", 0.0, 1.4),
    ("KOL02", "KOL", "Park Street", 22.5535, 88.3520, 3400, "2025-01-15", 0.0, 1.4),
    ("KOL03", "KOL", "Ballygunge", 22.5276, 88.3657, 3500, "2025-04-01", 0.0, 1.4),
    ("KOL04", "KOL", "Behala", 22.4985, 88.3108, 3600, "2025-07-01", 0.0, 1.4),
    # Ahmedabad
    ("AMD01", "AMD", "Navrangpura", 23.0365, 72.5611, 3600, "2025-04-01", 0.0, 1.4),
    ("AMD02", "AMD", "Satellite", 23.0300, 72.5170, 3800, "2025-04-01", 0.0, 1.4),
    ("AMD03", "AMD", "Maninagar", 22.9962, 72.6030, 2700, "2025-08-01", 0.0, 1.4),
]

# Planted rider-capacity incidents: (store, start, end, staffing during incident)
INCIDENTS = [
    ("BLR03", pd.Timestamp("2026-05-18"), END, 0.65),                      # riders leave for a competitor
    ("DEL06", pd.Timestamp("2026-04-06"), pd.Timestamp("2026-04-19"), 0.5),  # two-week rider strike
]

# Customer micro-areas: city, name, lat, lon, demand weight, growth (higher = more recent signups)
AREAS = [
    # Bengaluru
    ("BLR", "Koramangala 5th Block", 12.9346, 77.6190, 1.0, 0.02),
    ("BLR", "Koramangala 1st Block", 12.9285, 77.6330, 0.8, 0.02),
    ("BLR", "Ejipura", 12.9440, 77.6260, 0.6, 0.02),
    ("BLR", "Indiranagar 100ft Rd", 12.9719, 77.6412, 1.0, 0.02),
    ("BLR", "Domlur", 12.9610, 77.6387, 0.7, 0.02),
    ("BLR", "HAL 2nd Stage", 12.9850, 77.6480, 0.6, 0.02),
    ("BLR", "HSR Sector 2", 12.9105, 77.6420, 1.0, 0.03),
    ("BLR", "HSR Sector 7", 12.9080, 77.6540, 0.8, 0.03),
    ("BLR", "Agara", 12.9240, 77.6510, 0.5, 0.03),
    ("BLR", "Bellandur Lake Rd", 12.9300, 77.6780, 0.9, 0.03),
    ("BLR", "Ecospace", 12.9265, 77.6920, 0.7, 0.03),
    ("BLR", "Kasavanahalli", 12.9100, 77.6990, 0.6, 0.07),
    ("BLR", "Carmelaram", 12.9050, 77.7080, 0.7, 0.10),
    ("BLR", "Jayanagar 4th Block", 12.9250, 77.5838, 1.0, 0.01),
    ("BLR", "Basavanagudi", 12.9420, 77.5750, 0.7, 0.01),
    ("BLR", "JP Nagar", 12.9080, 77.5850, 0.8, 0.02),
    ("BLR", "BTM 2nd Stage", 12.9160, 77.6100, 1.0, 0.02),
    ("BLR", "Madiwala", 12.9220, 77.6180, 0.6, 0.02),
    ("BLR", "Begur", 12.8800, 77.6250, 0.5, 0.06),
    ("BLR", "Whitefield Main Rd", 12.9690, 77.7490, 0.9, 0.04),
    ("BLR", "ITPL", 12.9850, 77.7350, 0.7, 0.04),
    ("BLR", "Varthur", 12.9420, 77.7460, 0.6, 0.06),
    ("BLR", "Marathahalli Bridge", 12.9560, 77.7010, 0.9, 0.03),
    ("BLR", "Kundalahalli", 12.9650, 77.7150, 0.6, 0.03),
    ("BLR", "Malleshwaram 8th Cross", 13.0030, 77.5700, 0.9, 0.01),
    ("BLR", "Rajajinagar", 12.9910, 77.5550, 0.7, 0.01),
    ("BLR", "Electronic City Ph 1", 12.8450, 77.6600, 1.0, 0.03),
    ("BLR", "Electronic City Ph 2", 12.8350, 77.6800, 0.6, 0.03),
    ("BLR", "Hebbal Kempapura", 13.0350, 77.5940, 0.8, 0.03),
    ("BLR", "RT Nagar", 13.0220, 77.5950, 0.6, 0.02),
    ("BLR", "Yelahanka New Town", 13.1000, 77.5900, 0.8, 0.03),
    ("BLR", "Jakkur", 13.0700, 77.6050, 0.5, 0.05),
    # Mumbai
    ("MUM", "Andheri Lokhandwala", 19.1420, 72.8270, 1.0, 0.02),
    ("MUM", "Versova", 19.1310, 72.8150, 0.7, 0.02),
    ("MUM", "Powai Hiranandani", 19.1180, 72.9100, 1.0, 0.03),
    ("MUM", "Vikhroli", 19.1100, 72.9280, 0.5, 0.03),
    ("MUM", "Bandra West", 19.0600, 72.8340, 1.0, 0.01),
    ("MUM", "Khar", 19.0700, 72.8370, 0.7, 0.01),
    ("MUM", "Lower Parel", 18.9960, 72.8270, 0.8, 0.02),
    ("MUM", "Worli", 19.0100, 72.8170, 0.8, 0.01),
    ("MUM", "Dadar West", 19.0190, 72.8420, 1.0, 0.01),
    ("MUM", "Matunga", 19.0270, 72.8560, 0.6, 0.01),
    ("MUM", "Goregaon East", 19.1650, 72.8600, 0.9, 0.02),
    ("MUM", "Malad West", 19.1870, 72.8420, 0.8, 0.03),
    ("MUM", "Chembur", 19.0520, 72.8990, 0.9, 0.02),
    ("MUM", "Ghatkopar East", 19.0790, 72.9100, 0.7, 0.02),
    ("MUM", "Thane Majiwada", 19.2080, 72.9780, 0.9, 0.04),
    ("MUM", "Ghodbunder Road", 19.2350, 72.9700, 0.8, 0.10),
    ("MUM", "Bhandup West", 19.1440, 72.9370, 0.6, 0.04),
    ("MUM", "Mulund West", 19.1720, 72.9560, 0.6, 0.03),
    # Delhi NCR
    ("DEL", "Saket", 28.5245, 77.2100, 1.0, 0.02),
    ("DEL", "Malviya Nagar", 28.5355, 77.2100, 0.8, 0.02),
    ("DEL", "Vasant Kunj", 28.5200, 77.1590, 0.6, 0.02),
    ("DEL", "Lajpat Nagar", 28.5677, 77.2400, 1.0, 0.01),
    ("DEL", "Greater Kailash", 28.5480, 77.2380, 0.8, 0.01),
    ("DEL", "Rajouri Garden", 28.6415, 77.1250, 1.0, 0.01),
    ("DEL", "Janakpuri", 28.6219, 77.0878, 0.7, 0.02),
    ("DEL", "Dwarka Sector 10", 28.5820, 77.0500, 0.9, 0.03),
    ("DEL", "Gurugram DLF Phase 3", 28.4930, 77.0950, 0.9, 0.03),
    ("DEL", "Gurugram Golf Course Rd", 28.4500, 77.0990, 0.8, 0.03),
    ("DEL", "Gurugram Sector 56", 28.4243, 77.1030, 0.9, 0.03),
    ("DEL", "Sohna Road", 28.4120, 77.0560, 0.6, 0.06),
    ("DEL", "Golf Course Ext Sector 67", 28.3900, 77.0680, 0.6, 0.10),
    ("DEL", "Noida Sector 18", 28.5708, 77.3240, 0.9, 0.02),
    ("DEL", "Noida Sector 50", 28.5710, 77.3600, 0.7, 0.03),
    ("DEL", "Noida Sector 62", 28.6260, 77.3700, 0.7, 0.03),
    ("DEL", "Noida Extension", 28.6100, 77.4200, 0.8, 0.10),
    ("DEL", "Rohini Sector 9", 28.7380, 77.0850, 0.9, 0.02),
    ("DEL", "Pitampura", 28.7033, 77.1325, 0.6, 0.02),
    # Hyderabad
    ("HYD", "Gachibowli", 17.4400, 78.3450, 1.0, 0.03),
    ("HYD", "Financial District", 17.4140, 78.3420, 0.7, 0.05),
    ("HYD", "Kokapet", 17.4000, 78.3400, 0.6, 0.10),
    ("HYD", "Madhapur", 17.4483, 78.3915, 1.0, 0.03),
    ("HYD", "Jubilee Hills", 17.4300, 78.4070, 0.8, 0.01),
    ("HYD", "Banjara Hills", 17.4156, 78.4380, 0.9, 0.01),
    ("HYD", "Kukatpally KPHB", 17.4930, 78.3920, 0.9, 0.02),
    ("HYD", "Miyapur", 17.4968, 78.3614, 0.6, 0.04),
    ("HYD", "Begumpet", 17.4447, 78.4630, 0.7, 0.01),
    ("HYD", "Secunderabad", 17.4399, 78.4983, 0.7, 0.01),
    ("HYD", "Kondapur", 17.4622, 78.3600, 0.8, 0.04),
    # Pune
    ("PUN", "Koregaon Park", 18.5362, 73.8940, 1.0, 0.02),
    ("PUN", "Kalyani Nagar", 18.5480, 73.9020, 0.7, 0.02),
    ("PUN", "Viman Nagar", 18.5679, 73.9143, 0.8, 0.03),
    ("PUN", "Baner", 18.5590, 73.7868, 1.0, 0.03),
    ("PUN", "Aundh", 18.5580, 73.8075, 0.7, 0.02),
    ("PUN", "Hinjewadi Phase 1", 18.5913, 73.7389, 0.9, 0.04),
    ("PUN", "Wakad", 18.5975, 73.7650, 0.8, 0.04),
    ("PUN", "Kothrud", 18.5074, 73.8077, 0.9, 0.01),
    ("PUN", "Kharadi", 18.5515, 73.9348, 0.9, 0.04),
    ("PUN", "Wagholi", 18.5808, 73.9787, 0.7, 0.10),
    ("PUN", "Hadapsar", 18.5089, 73.9260, 0.6, 0.03),
    # Chennai
    ("CHE", "T Nagar", 13.0418, 80.2341, 1.0, 0.01),
    ("CHE", "Nungambakkam", 13.0600, 80.2420, 0.7, 0.01),
    ("CHE", "Adyar", 13.0012, 80.2565, 1.0, 0.01),
    ("CHE", "Besant Nagar", 12.9990, 80.2690, 0.6, 0.01),
    ("CHE", "Anna Nagar", 13.0850, 80.2101, 1.0, 0.02),
    ("CHE", "Velachery", 12.9815, 80.2180, 0.9, 0.02),
    ("CHE", "OMR Thoraipakkam", 12.9416, 80.2362, 0.9, 0.04),
    ("CHE", "Sholinganallur", 12.9010, 80.2279, 0.6, 0.05),
    ("CHE", "Mylapore", 13.0368, 80.2676, 0.7, 0.01),
    # Kolkata
    ("KOL", "Salt Lake", 22.5800, 88.4150, 1.0, 0.02),
    ("KOL", "New Town", 22.5850, 88.4700, 0.8, 0.10),
    ("KOL", "Park Street", 22.5535, 88.3520, 0.9, 0.01),
    ("KOL", "Ballygunge", 22.5276, 88.3657, 0.9, 0.01),
    ("KOL", "Gariahat", 22.5180, 88.3700, 0.6, 0.01),
    ("KOL", "Behala", 22.4985, 88.3108, 0.8, 0.02),
    ("KOL", "Tollygunge", 22.4980, 88.3450, 0.6, 0.02),
    # Ahmedabad
    ("AMD", "Navrangpura", 23.0365, 72.5611, 1.0, 0.02),
    ("AMD", "Satellite", 23.0300, 72.5170, 1.0, 0.03),
    ("AMD", "Bodakdev", 23.0423, 72.5097, 0.7, 0.03),
    ("AMD", "Bopal", 23.0300, 72.4750, 0.7, 0.10),
    ("AMD", "Maninagar", 22.9962, 72.6030, 0.9, 0.02),
    ("AMD", "Paldi", 23.0130, 72.5600, 0.6, 0.01),
]

# --------------------------------------------------------------------------
# City climate & calendar
# --------------------------------------------------------------------------
# probability that a given day has rain, by city and month
RAIN_PROB = {
    "BLR": {1: .02, 2: .03, 3: .08, 4: .18, 5: .33, 6: .42},
    "MUM": {1: .00, 2: .00, 3: .01, 4: .01, 5: .04, 6: .00},   # June handled by monsoon onset
    "DEL": {1: .07, 2: .06, 3: .05, 4: .04, 5: .07, 6: .18},
    "HYD": {1: .01, 2: .01, 3: .03, 4: .06, 5: .08, 6: .35},
    "PUN": {1: .00, 2: .01, 3: .02, 4: .05, 5: .08, 6: .50},
    "CHE": {1: .05, 2: .02, 3: .02, 4: .03, 5: .05, 6: .12},
    "KOL": {1: .02, 2: .04, 3: .06, 4: .20, 5: .26, 6: .45},
    "AMD": {1: .00, 2: .00, 3: .01, 4: .01, 5: .02, 6: .15},
}
HEAVY_SHARE = {"BLR": .35, "MUM": .55, "DEL": .30, "HYD": .35, "PUN": .40, "CHE": .30, "KOL": .45, "AMD": .30}
MONSOON_ONSET = {"MUM": pd.Timestamp("2026-06-09")}    # after this, ~85% of days are rainy
HEATWAVE_PROB = {
    "DEL": {4: .15, 5: .45, 6: .35}, "AMD": {4: .30, 5: .55, 6: .25}, "HYD": {4: .20, 5: .40},
    "CHE": {5: .35, 6: .20}, "KOL": {4: .10, 5: .15}, "PUN": {4: .05, 5: .05},
}
FOG_PROB = {"DEL": {1: .45, 2: .15}}

# Regional festivals: date -> {city: multiplier}; "ALL" applies everywhere not listed
FESTIVALS = {
    "2026-01-14": {"ALL": 1.15, "CHE": 1.40, "AMD": 1.40},               # Sankranti / Pongal / Uttarayan
    "2026-03-04": {"ALL": 1.20, "DEL": 1.45, "KOL": 1.30},               # Holi / Dol Jatra
    "2026-03-19": {"ALL": 1.05, "BLR": 1.30, "HYD": 1.30, "MUM": 1.30, "PUN": 1.30},  # Ugadi / Gudi Padwa
    "2026-03-20": {"ALL": 1.10, "HYD": 1.35},                            # Eid al-Fitr
    "2026-04-14": {"ALL": 1.00, "CHE": 1.25},                            # Puthandu
    "2026-04-15": {"ALL": 1.00, "KOL": 1.35},                            # Poila Baisakh
}

# --------------------------------------------------------------------------
# Catalogue and shopping missions
# --------------------------------------------------------------------------
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

MISSIONS = {
    "breakfast": {"core": ["P001", "P003", "P005", "P006"], "core_p": [0.85, 0.75, 0.55, 0.35],
                  "extra": ["P007", "P015", "P029", "P004", "P002"],
                  "hours": {range(6, 11): 5.0, range(11, 13): 1.0, range(20, 23): 0.8}},
    "evening_snacks": {"core": ["P019", "P025", "P021", "P022"], "core_p": [0.75, 0.7, 0.4, 0.35],
                       "extra": ["P020", "P024", "P026", "P023", "P027"],
                       "hours": {range(16, 19): 2.0, range(19, 24): 3.5, range(0, 2): 2.0}},
    "quick_meal": {"core": ["P032", "P033", "P034", "P036"], "core_p": [0.75, 0.35, 0.3, 0.3],
                   "extra": ["P035", "P025", "P001", "P005"],
                   "hours": {range(12, 15): 2.0, range(20, 24): 2.5, range(0, 3): 2.5}},
    "cooking": {"core": ["P010", "P011", "P013", "P014"], "core_p": [0.8, 0.75, 0.55, 0.45],
                "extra": ["P012", "P008", "P017", "P018", "P042", "P041", "P044"],
                "hours": {range(8, 13): 3.0, range(16, 20): 2.5}},
    "stock_up": {"core": ["P041", "P042", "P043", "P044", "P045"], "core_p": [0.5, 0.5, 0.4, 0.4, 0.4],
                 "extra": ["P046", "P030", "P047", "P048"],
                 "hours": {range(9, 13): 2.0, range(15, 21): 1.5}},
    "household": {"core": ["P047", "P048", "P049", "P050", "P051"], "core_p": [0.45, 0.45, 0.4, 0.3, 0.35],
                  "extra": ["P056", "P053"], "hours": {range(9, 22): 1.0}},
    "personal_care": {"core": ["P052", "P053", "P054", "P055", "P056"], "core_p": [0.4, 0.4, 0.35, 0.3, 0.3],
                      "extra": ["P059", "P051"], "hours": {range(8, 23): 1.0}},
    "ice_cream": {"core": ["P037", "P038", "P039"], "core_p": [0.6, 0.5, 0.35],
                  "extra": ["P022", "P025"], "hours": {range(13, 17): 1.5, range(17, 24): 2.5}},
    "cold_drinks": {"core": ["P027", "P026", "P028", "P025"], "core_p": [0.7, 0.5, 0.45, 0.3],
                    "extra": ["P039", "P031"], "hours": {range(11, 18): 3.0, range(18, 22): 1.5}},
    "baby": {"core": ["P057", "P058"], "core_p": [0.8, 0.6], "extra": ["P001", "P055"],
             "hours": {range(0, 24): 1.0}},
    "fruits_healthy": {"core": ["P015", "P016", "P007", "P017"], "core_p": [0.6, 0.5, 0.4, 0.3],
                       "extra": ["P027", "P001"], "hours": {range(7, 12): 2.0, range(16, 20): 1.5}},
    "unwell": {"core": ["P059", "P060", "P026"], "core_p": [0.7, 0.4, 0.4], "extra": ["P027", "P017"],
               "hours": {range(0, 24): 1.0}},
}
MISSION_BASE_SHARE = {
    "breakfast": 0.17, "evening_snacks": 0.17, "quick_meal": 0.12, "cooking": 0.15, "stock_up": 0.06,
    "household": 0.07, "personal_care": 0.07, "ice_cream": 0.05, "cold_drinks": 0.02, "baby": 0.03,
    "fruits_healthy": 0.07, "unwell": 0.03,
}
# months when ice cream / cold drinks peak, by city
SUMMER = {
    "BLR": {3: 1.5, 4: 2.6, 5: 2.4}, "MUM": {4: 2.2, 5: 2.6}, "DEL": {4: 1.8, 5: 2.8, 6: 2.8},
    "HYD": {3: 1.6, 4: 2.6, 5: 2.8}, "PUN": {4: 2.2, 5: 2.4}, "CHE": {4: 2.2, 5: 2.8, 6: 2.4},
    "KOL": {4: 2.2, 5: 2.6, 6: 2.0}, "AMD": {4: 2.4, 5: 3.0, 6: 2.4},
}

HOUR_PROFILE = np.array([
    1.0, 0.6, 0.3, 0.15, 0.1, 0.2, 1.5, 3.5, 5.5, 6.0, 5.0, 4.2,
    4.0, 4.0, 3.2, 3.0, 3.6, 4.8, 6.8, 8.6, 9.6, 9.0, 6.2, 3.0,
])
PEAK_TRAFFIC_HOURS = set(range(8, 11)) | set(range(17, 22))
ORDERS_PER_RIDER_HOUR = 2.2
PRICE = {p[0]: p[3] for p in PRODUCTS}
ALL_SKUS = [p[0] for p in PRODUCTS]
MISSION_NAMES = list(MISSIONS)


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


MISSION_HOUR_W = np.array([hours_weight(MISSIONS[m]["hours"]) for m in MISSION_NAMES])
MISSION_SHARE = np.array([MISSION_BASE_SHARE[m] for m in MISSION_NAMES])
IDX = {m: i for i, m in enumerate(MISSION_NAMES)}


# --------------------------------------------------------------------------
# Calendar and weather per city
# --------------------------------------------------------------------------
def build_city_calendar(city: str):
    n = len(DAYS)
    months = DAYS.month.to_numpy()
    dow_mult = np.array([0.95, 0.95, 0.97, 1.0, 1.06, 1.2, 1.24])  # Mon..Sun

    rain_p = np.array([RAIN_PROB[city].get(m, 0) for m in months], dtype=float)
    if city in MONSOON_ONSET:
        rain_p = np.where(DAYS >= MONSOON_ONSET[city], 0.85, rain_p)
    rain_day = rng.random(n) < rain_p
    heat_day = rng.random(n) < np.array([HEATWAVE_PROB.get(city, {}).get(m, 0) for m in months])
    fog_day = rng.random(n) < np.array([FOG_PROB.get(city, {}).get(m, 0) for m in months])

    day_weight = dow_mult[DAYS.dayofweek] * (1 + 0.035 * (months - 1)) * np.where(rain_day, 1.08, 1.0)
    fest = np.array([FESTIVALS.get(str(d.date()), {}) for d in DAYS])
    day_weight *= np.array([f.get(city, f.get("ALL", 1.0)) if f else 1.0 for f in fest])

    weather = np.full((n, 24), "Clear", dtype=object)
    weather[rng.random((n, 24)) < 0.25] = "Cloudy"
    hour_w = np.tile(HOUR_PROFILE, (n, 1)).astype(float)
    for i in range(n):
        if fog_day[i]:
            for h in range(4, 11):
                weather[i, h] = "Fog"
        if heat_day[i]:
            for h in range(12, 18):
                weather[i, h] = "Heatwave"
                hour_w[i, h] *= 1.10
        if rain_day[i]:
            monsoon = city in MONSOON_ONSET and DAYS[i] >= MONSOON_ONSET[city]
            start = int(rng.integers(6, 18)) if monsoon else int(rng.integers(14, 20))
            dur = int(rng.integers(4, 10)) if monsoon else int(rng.integers(2, 6))
            heavy = rng.random() < (0.55 if monsoon else HEAVY_SHARE[city])
            for h in range(start, min(start + dur, 24)):
                weather[i, h] = "Heavy Rain" if heavy else "Rain"
                hour_w[i, h] *= 1.25 if heavy else 1.18
    hour_w /= hour_w.sum(axis=1, keepdims=True)

    weather_df = pd.DataFrame({
        "city_code": city,
        "date": np.repeat(DAYS.date, 24),
        "hour": np.tile(np.arange(24), n),
        "condition": weather.ravel(),
    })
    return day_weight, weather, hour_w, weather_df


# --------------------------------------------------------------------------
# Customers and candidate orders
# --------------------------------------------------------------------------
def build_customers(city: dict, stores: pd.DataFrame, areas: pd.DataFrame, id_offset: int):
    n = int(city["n_customers"])
    a = areas[areas.city_code == city["city_code"]].reset_index(drop=True)
    s = stores[stores.city_code == city["city_code"]].reset_index(drop=True)
    area_idx = rng.choice(len(a), size=n, p=a.weight / a.weight.sum())
    lat = a.lat.to_numpy()[area_idx] + rng.normal(0, 0.0055, n)
    lon = a.lon.to_numpy()[area_idx] + rng.normal(0, 0.0055, n)

    total_days = (END - START).days
    existing = rng.random(n) < city["existing_share"]
    growth = a.growth.to_numpy()[area_idx]
    late_skew = rng.beta(1 + growth * 25, 1.3, n)
    signup_offset = np.where(existing, -rng.integers(30, 600, n), (late_skew * total_days).astype(int))
    signup = START + pd.to_timedelta(signup_offset, unit="D")

    d = haversine_km(lat[:, None], lon[:, None], s.lat.to_numpy()[None, :], s.lon.to_numpy()[None, :])
    nearest = d.argmin(axis=1)
    road = city["road_factor"]
    road_km = d[np.arange(n), nearest] * rng.uniform(road - 0.10, road + 0.10, n) + 0.15

    return pd.DataFrame({
        "customer_id": [f"C{id_offset + i:07d}" for i in range(n)],
        "city_code": city["city_code"],
        "area": a.area.to_numpy()[area_idx],
        "lat": lat.round(5), "lon": lon.round(5),
        "signup_date": signup.date,
        "home_store_id": s.store_id.to_numpy()[nearest],
        "road_km": road_km.round(2),
        "order_rate": rng.gamma(1.15, 0.047 / 1.15, n),
        "segment": rng.choice(["Student", "Working Professional", "Family"], n, p=[0.2, 0.5, 0.3]),
    })


def candidate_orders(cust, day_weight, hour_w):
    w = day_weight / day_weight.mean()
    cumw = np.concatenate([[0], np.cumsum(w)])
    start_idx = np.clip((pd.to_datetime(cust.signup_date) - START).dt.days.to_numpy(), 0, len(DAYS) - 1)
    rows_c, rows_d = [], []
    for ci, (s, rate) in enumerate(zip(start_idx, cust.order_rate.to_numpy())):
        k = rng.poisson(rate * (cumw[-1] - cumw[s]))
        if k == 0:
            continue
        p = w[s:] / w[s:].sum()
        rows_c.extend([ci] * k)
        rows_d.extend(rng.choice(np.arange(s, len(DAYS)), size=k, p=p).tolist())
    rows_c, rows_d = np.array(rows_c), np.array(rows_d)
    cumh = np.cumsum(hour_w, axis=1)
    u = rng.random(len(rows_d))
    hours = np.clip(np.array([np.searchsorted(cumh[d], x) for d, x in zip(rows_d, u)]), 0, 23)
    ts = (pd.to_datetime(DAYS[rows_d]) + pd.to_timedelta(hours, "h")
          + pd.to_timedelta(rng.integers(0, 60, len(rows_d)), "m")
          + pd.to_timedelta(rng.integers(0, 60, len(rows_d)), "s"))
    cand = pd.DataFrame({"cust_idx": rows_c, "day_idx": rows_d, "hour": hours, "order_ts": ts})
    return cand.sort_values("order_ts").reset_index(drop=True)


# --------------------------------------------------------------------------
# Baskets and stockouts
# --------------------------------------------------------------------------
def mission_probs(city, hour, month, weekend, segment, cond):
    p = MISSION_SHARE * MISSION_HOUR_W[:, hour]
    s = SUMMER[city].get(month, 1.0)
    p[IDX["ice_cream"]] *= s
    p[IDX["cold_drinks"]] *= s
    if cond == "Heatwave":
        p[IDX["ice_cream"]] *= 2.0
        p[IDX["cold_drinks"]] *= 3.0
    if cond in ("Rain", "Heavy Rain"):
        p[IDX["quick_meal"]] *= 1.5
        p[IDX["evening_snacks"]] *= 1.3
    if weekend:
        p[IDX["evening_snacks"]] *= 1.35
        p[IDX["stock_up"]] *= 1.4
    if segment == "Family":
        p[IDX["baby"]] *= 3.0
        p[IDX["cooking"]] *= 1.4
        p[IDX["stock_up"]] *= 1.5
    elif segment == "Student":
        p[IDX["quick_meal"]] *= 1.8
        p[IDX["evening_snacks"]] *= 1.4
        p[IDX["stock_up"]] *= 0.3
        p[IDX["baby"]] *= 0.05
    return p / p.sum()


def build_basket(mission, basket_mult):
    m = MISSIONS[mission]
    items = [s for s, pr in zip(m["core"], m["core_p"]) if rng.random() < min(pr * basket_mult, 0.97)]
    if not items:
        items = [m["core"][0]]
    for s in m["extra"]:
        if rng.random() < 0.18 * basket_mult:
            items.append(s)
    for s in rng.choice(ALL_SKUS, size=rng.choice([0, 1, 2], p=[0.55, 0.32, 0.13]), replace=False):
        items.append(s)
    seen, basket = set(), []
    for s in items:
        if s not in seen:
            seen.add(s)
            basket.append((s, 1 if rng.random() < 0.82 else int(rng.integers(2, 4))))
    return basket


SMALL_FREEZER_STORES = {"BLR05", "BLR10", "MUM05", "AMD03"}
LATE_DAIRY_STORES = {"BLR07", "BLR08", "PUN03", "DEL04"}


def stockout_prob(sku, store, city, month, hour, cond):
    p = 0.018
    if sku in ("P013", "P014"):
        p = 0.11
    if sku in ("P037", "P038", "P039"):
        hot = SUMMER[city].get(month, 1.0) >= 2.2
        if store in SMALL_FREEZER_STORES and hot:
            p = 0.30
        elif hot or cond == "Heatwave":
            p = 0.06
    if sku in ("P027", "P028") and cond == "Heatwave":
        p = max(p, 0.08)
    if sku in ("P001", "P002", "P003", "P004") and store in LATE_DAIRY_STORES and 6 <= hour <= 9:
        p = 0.17
    if sku == "P016" and month in (5, 6):
        p = 0.08
    return p


# --------------------------------------------------------------------------
# Operations simulation (one city at a time)
# --------------------------------------------------------------------------
def rider_schedule(cand_store, cand, stores_city, weather, survival=0.86):
    """Riders per store/day/hour: planned from average demand x staffing level,
    then reduced by heatwaves, heavy rain and planted incidents."""
    tmp = pd.DataFrame({"store_id": cand_store, "weekend": (cand.order_ts.dt.dayofweek >= 5).to_numpy(),
                        "hour": cand.hour.to_numpy()})
    counts = tmp.groupby(["store_id", "weekend", "hour"]).size().rename("n").reset_index()
    n_weekend = int((DAYS.dayofweek >= 5).sum())
    counts["per_day"] = counts.n / np.where(counts.weekend, n_weekend, len(DAYS) - n_weekend) * survival
    plan = {(r.store_id, r.weekend, r.hour): r.per_day for r in counts.itertuples()}
    staffing = dict(zip(stores_city.store_id, stores_city.staffing))

    rows = []
    for di, d in enumerate(DAYS):
        wk = d.dayofweek >= 5
        for sid in stores_city.store_id:
            for h in range(24):
                st = staffing[sid]
                for inc_store, s0, s1, level in INCIDENTS:
                    if sid == inc_store and s0 <= d <= s1:
                        st = level
                cond = weather[di, h]
                if cond == "Heatwave":
                    st *= 0.80      # fewer riders log in during midday heat
                elif cond == "Heavy Rain":
                    st *= 0.85
                riders = plan.get((sid, wk, h), 0.0) / ORDERS_PER_RIDER_HOUR * st + rng.normal(0, 0.35)
                rows.append((d.date(), h, sid, max(1, int(round(riders)))))
    return pd.DataFrame(rows, columns=["date", "hour", "store_id", "riders_on_shift"])


def simulate_city(city: dict, cust, cand, stores_city, weather):
    code = city["city_code"]
    n = len(cand)
    ci = cand.cust_idx.to_numpy()
    cust_store = cust.home_store_id.to_numpy()[ci]
    dist = cust.road_km.to_numpy()[ci] * rng.uniform(0.95, 1.08, n)
    segment = cust.segment.to_numpy()[ci]
    months = cand.order_ts.dt.month.to_numpy()
    weekend = (cand.order_ts.dt.dayofweek >= 5).to_numpy()
    hours = cand.hour.to_numpy()
    cond = weather[cand.day_idx.to_numpy(), hours]
    pick_pen = dict(zip(stores_city.store_id, stores_city.pick_penalty))

    baskets = []
    for i in range(n):
        p = mission_probs(code, hours[i], months[i], weekend[i], segment[i], cond[i])
        b = build_basket(MISSION_NAMES[rng.choice(len(MISSION_NAMES), p=p)], city["basket_mult"])
        baskets.append([(s, q, rng.random() >= stockout_prob(s, cust_store[i], code, months[i], hours[i], cond[i]))
                        for s, q in b])
    n_items = np.array([sum(q for _, q, ok in b if ok) for b in baskets])
    n_missing = np.array([sum(1 for _, _, ok in b if not ok) for b in baskets])
    n_lines = np.array([len(b) for b in baskets])

    e_pick = np.exp(rng.normal(0, 0.25, n))
    e_wait = np.exp(rng.normal(0, 0.40, n))
    e_trav = np.exp(rng.normal(0, 0.14, n))
    u_cancel, u_churn = rng.random(n), rng.random(n)

    peak = np.isin(hours, list(PEAK_TRAFFIC_HOURS))
    rain = np.isin(cond, ["Rain", "Heavy Rain"])
    speed = (city["speed_min_per_km"] * np.where(peak, 1.25, 1.0) * np.where(rain, 1.32, 1.0)
             * np.where(cond == "Heavy Rain", 1.12, 1.0) * np.where(cond == "Fog", 1.25, 1.0)
             * np.where(cond == "Heatwave", 1.06, 1.0) * np.where(weekend & ~peak, 0.95, 1.0))
    travel = (0.8 + dist * speed) * e_trav
    pick = (1.1 + 0.32 * np.maximum(n_items, 1) + np.array([pick_pen[s] for s in cust_store]) + 0.35 * peak) * e_pick
    promised = np.where(dist <= 1.5, 10, np.where(dist <= 2.5, 12, np.where(dist <= 3.5, 15, 18)))

    sched = rider_schedule(cust_store, cand, stores_city, weather)
    sched_key = {(r.date, r.hour, r.store_id): r.riders_on_shift for r in sched.itertuples()}
    dates = cand.order_ts.dt.date.to_numpy()
    riders = np.array([sched_key[(dates[i], hours[i], cust_store[i])] for i in range(n)])
    key = pd.Series(list(zip(dates, hours, cust_store)))

    def run_pass(alive):
        orders_in_hour = key.map(key[alive].value_counts()).fillna(1).to_numpy()
        util = orders_in_hour / (riders * ORDERS_PER_RIDER_HOUR)
        wait = (0.5 + 5.5 * np.maximum(0, util - 0.75) ** 1.4) * e_wait
        total = pick + wait + travel
        late_by = total - promised
        late = late_by > 0
        all_missing = n_missing == n_lines
        cancelled = u_cancel < (0.018 + 0.55 * all_missing + 0.07 * (util > 1.35) + 0.03 * (n_missing > 0))
        new_alive = np.ones(n, dtype=bool)
        churned = set()
        for i in range(n):
            c = ci[i]
            if c in churned:
                new_alive[i] = False
                continue
            pc = 0.14 if cancelled[i] else (0.09 + 0.018 * min(late_by[i], 12) if late[i] else 0.022)
            if n_missing[i] > 0:
                pc += 0.05
            if u_churn[i] < pc:
                churned.add(c)
        return new_alive, orders_in_hour, util, wait, total, late, cancelled, all_missing

    alive = np.ones(n, dtype=bool)
    for _ in range(3):
        alive, *_ = run_pass(alive)
    _, orders_in_hour, util, wait, total, late, cancelled, all_missing = run_pass(alive)
    keep = np.where(alive)[0]

    c = cand.iloc[keep].reset_index(drop=True)
    ts = c.order_ts
    pick_k, wait_k, travel_k = pick[keep], wait[keep], travel[keep]
    canc_k = cancelled[keep]
    packed = ts + pd.to_timedelta(pick_k, "m")
    dispatched = packed + pd.to_timedelta(wait_k, "m")
    delivered = dispatched + pd.to_timedelta(travel_k, "m")
    m = len(c)

    item_totals = np.array([sum(q * PRICE[s] for s, q, ok in baskets[i] if ok) for i in keep], dtype=float)
    coupon = rng.random(m) < 0.28
    discount = np.where(coupon, np.minimum(np.round(item_totals * 0.10), 75), 0)
    reasons = np.where(all_missing[keep], "Items unavailable",
                       np.where(util[keep] > 1.35, "Delivery taking too long",
                                rng.choice(["Changed mind", "Payment failed", "Ordered by mistake"], m, p=[0.5, 0.3, 0.2])))
    late_by = total[keep] - promised[keep]
    rating = (4.75 - 1.25 * late[keep] - 0.07 * np.clip(late_by, 0, 20) - 0.85 * (n_missing[keep] > 0)
              + rng.normal(0, 0.45, m))
    rating = np.clip(np.round(rating), 1, 5)
    rated = rng.random(m) < 0.55

    orders = pd.DataFrame({
        "customer_id": cust.customer_id.to_numpy()[c.cust_idx],
        "store_id": cust_store[keep],
        "order_ts": ts,
        "packed_ts": packed.where(~canc_k),
        "dispatched_ts": dispatched.where(~canc_k),
        "delivered_ts": delivered.where(~canc_k),
        "promised_eta_min": promised[keep],
        "distance_km": dist[keep].round(2),
        "weather": cond[keep],
        "riders_on_shift": riders[keep],
        "store_orders_in_hour": orders_in_hour[keep].astype(int),
        "item_lines": n_lines[keep],
        "items_missing": n_missing[keep],
        "item_total": np.where(canc_k, 0, item_totals).round(2),
        "discount": np.where(canc_k, 0, discount),
        "delivery_fee": np.where(canc_k, 0, np.where(item_totals >= 199, 0, 25)),
        "small_cart_fee": np.where(canc_k, 0, np.where(item_totals < 99, 15, 0)),
        "payment_method": rng.choice(["UPI", "Card", "Cash on Delivery", "Wallet"], m, p=[0.68, 0.14, 0.12, 0.06]),
        "status": np.where(canc_k, "Cancelled", "Delivered"),
        "cancel_reason": np.where(canc_k, reasons, None),
        "rating": np.where(rated & ~canc_k, rating, np.nan),
    })
    orders["order_value"] = (orders.item_total - orders.discount + orders.delivery_fee + orders.small_cart_fee).round(2)
    order_baskets = [baskets[i] for i in keep]
    return orders, order_baskets, sched


def inject_quality_issues(o: pd.DataFrame) -> pd.DataFrame:
    """Simulate a messy production export."""
    o = o.copy()
    n = len(o)
    idx = rng.choice(n, int(n * 0.006), replace=False)
    half = len(idx) // 2
    o.loc[idx[:half], "store_id"] = o.loc[idx[:half], "store_id"].str.lower()
    o.loc[idx[half:], "store_id"] = " " + o.loc[idx[half:], "store_id"]
    idx = rng.choice(n, int(n * 0.01), replace=False)
    o.loc[idx, "payment_method"] = o.loc[idx, "payment_method"].replace({"Cash on Delivery": "COD", "UPI": "upi"})
    delivered = o.index[o.status == "Delivered"]
    bad = rng.choice(delivered, 240, replace=False)
    o.loc[bad[:140], "delivered_ts"] = o.loc[bad[:140], "dispatched_ts"] - pd.to_timedelta(rng.integers(1, 6, 140), "m")
    o.loc[bad[140:], "delivered_ts"] = o.loc[bad[140:], "dispatched_ts"] + pd.to_timedelta(rng.integers(150, 300, 100), "m")
    idx = rng.choice(n, int(n * 0.003), replace=False)
    o.loc[idx, "distance_km"] = np.nan
    dups = o.sample(frac=0.004, random_state=SEED)
    return pd.concat([o, dups]).sort_values("order_ts", kind="stable").reset_index(drop=True)


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stores = pd.DataFrame(STORES, columns=["store_id", "city_code", "locality", "lat", "lon", "area_sqft",
                                           "opened_on", "pick_penalty", "staffing"])
    areas = pd.DataFrame(AREAS, columns=["city_code", "area", "lat", "lon", "weight", "growth"])

    all_orders, all_baskets, all_shifts, all_weather, all_customers = [], [], [], [], []
    offset = 1
    for city in CITIES.to_dict("records"):
        code = city["city_code"]
        day_weight, weather, hour_w, weather_df = build_city_calendar(code)
        cust = build_customers(city, stores, areas, offset)
        offset += len(cust)
        cand = candidate_orders(cust, day_weight, hour_w)
        orders, baskets, sched = simulate_city(city, cust, cand, stores[stores.city_code == code], weather)
        print(f"  {city['city_name']:<10} customers {len(cust):>6,}  orders {len(orders):>7,}")
        all_orders.append(orders)
        all_baskets.extend(baskets)
        all_shifts.append(sched)
        all_weather.append(weather_df)
        all_customers.append(cust)

    orders = pd.concat(all_orders, ignore_index=True)
    orders["_basket"] = np.arange(len(orders))
    orders = orders.sort_values(["order_ts", "store_id"], kind="stable").reset_index(drop=True)
    orders.insert(0, "order_id", [f"ORD{26000000 + i}" for i in range(len(orders))])
    for col in ["order_ts", "packed_ts", "dispatched_ts", "delivered_ts"]:
        orders[col] = orders[col].dt.floor("s")

    item_rows = []
    for oid, bi in zip(orders.order_id.to_numpy(), orders._basket.to_numpy()):
        for line, (sku, q, ok) in enumerate(all_baskets[bi], start=1):
            item_rows.append((oid, line, sku, q, PRICE[sku], int(ok)))
    items = pd.DataFrame(item_rows, columns=["order_id", "line_no", "sku_id", "quantity", "unit_price", "fulfilled"])
    orders = orders.drop(columns="_basket")
    orders_raw = inject_quality_issues(orders)

    customers = pd.concat(all_customers, ignore_index=True)
    stores = stores.merge(CITIES[["city_code", "city_name"]], on="city_code")
    stores["store_name"] = "DS " + stores.locality
    for old in RAW_DIR.glob("*.csv"):
        old.unlink()
    CITIES[["city_code", "city_name", "state", "lat", "lon", "road_factor"]].to_csv(RAW_DIR / "cities.csv", index=False)
    stores[["store_id", "store_name", "city_code", "locality", "lat", "lon", "area_sqft", "opened_on"]].to_csv(
        RAW_DIR / "stores.csv", index=False)
    pd.DataFrame(PRODUCTS, columns=["sku_id", "product_name", "category", "mrp"]).to_csv(RAW_DIR / "products.csv", index=False)
    pq = dict(index=False, compression="zstd")
    customers[["customer_id", "city_code", "area", "lat", "lon", "signup_date", "segment"]].to_parquet(
        RAW_DIR / "customers.parquet", **pq)
    orders_raw.to_parquet(RAW_DIR / "orders.parquet", **pq)
    items.to_parquet(RAW_DIR / "order_items.parquet", **pq)
    pd.concat(all_shifts, ignore_index=True).to_parquet(RAW_DIR / "rider_shifts.parquet", **pq)
    pd.concat(all_weather, ignore_index=True).to_parquet(RAW_DIR / "weather_hourly.parquet", **pq)

    d = orders[orders.status == "Delivered"]
    dt = (d.delivered_ts - d.order_ts).dt.total_seconds() / 60
    print(f"orders: {len(orders):,} (raw with dups: {len(orders_raw):,}) | items: {len(items):,} | "
          f"customers: {len(customers):,} | stores: {len(stores)}")
    print(f"avg delivery {dt.mean():.1f} min | late rate {(dt > d.promised_eta_min).mean():.1%} | "
          f"cancel rate {(orders.status == 'Cancelled').mean():.1%}")


if __name__ == "__main__":
    main()
