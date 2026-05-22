from __future__ import annotations

import runpy
from pathlib import Path


HERE = Path(__file__).resolve().parent


SCRIPTS = [
    "01_pattern_mining.py",
    "02_predictive_analysis.py",
    "03_cluster_formation.py",
    "04_rules_mining.py",
    "05_sequence_discovery.py",
    "06_time_series_analysis.py",
    "visualize_clusters.py",
    "visualize_time_series.py",
    "07_build_insight_report.py",
    "08_build_dashboard.py",
]


if __name__ == "__main__":
    for script in SCRIPTS:
        print("\n" + "=" * 90)
        print(f"Running {script}")
        print("=" * 90)
        runpy.run_path(str(HERE / script), run_name="__main__")

    print("\nAll BI demonstrations completed.")
    print("Open outputs/html/index.html in a browser, or run mining/bi_dashboard_server.py.")
