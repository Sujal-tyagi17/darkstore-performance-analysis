"""
Run the full pipeline end to end.

    python run_all.py            # build warehouse + analysis + Power BI export (uses committed raw data)
    python run_all.py --regen    # also regenerate the synthetic raw data first (seeded, reproducible)
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ("Build DuckDB warehouse + SQL analysis", "src/build_warehouse.py"),
    ("Python analysis, models and charts", "src/analysis.py"),
    ("Export star schema for Power BI", "src/export_powerbi.py"),
]

if __name__ == "__main__":
    steps = STEPS
    if "--regen" in sys.argv:
        steps = [("Generate synthetic raw data", "src/generate_data.py")] + STEPS
    for title, script in steps:
        print(f"\n=== {title} ===", flush=True)
        subprocess.run([sys.executable, str(ROOT / script)], check=True, cwd=ROOT)
    print("\nDone. Launch the dashboard with:  streamlit run dashboard/app.py")
