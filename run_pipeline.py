"""Build the analytics database end to end: raw load -> clean -> star schema -> tests.

Prerequisites:  python data/download_data.py
Usage:          python run_pipeline.py              (full rebuild, ~2-3 min)
                python run_pipeline.py --skip-raw   (reuse the loaded raw table)
"""
import os
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "complaints.duckdb"
STEPS = ["00_load_raw.sql", "01_clean.sql", "02_schema.sql"]


def main() -> None:
    os.chdir(ROOT)  # SQL files use paths relative to the project root
    steps = STEPS[1:] if "--skip-raw" in sys.argv else STEPS
    con = duckdb.connect(str(DB_PATH))
    for step in steps:
        start = time.time()
        con.execute((ROOT / "sql" / step).read_text())
        print(f"{step:<18} done in {time.time() - start:5.1f}s")

    results = con.sql((ROOT / "sql" / "03_validate.sql").read_text()).fetchall()
    for test, failed in results:
        print(f"  [{'PASS' if failed == 0 else 'FAIL'}] {test}" + (f" ({failed} rows)" if failed else ""))
    if any(failed for _, failed in results):
        sys.exit("Validation failed.")

    for table in ["fact_complaints", "dim_company", "dim_product", "dim_issue", "dim_geography", "dim_date"]:
        print(f"{table:<16} {con.sql(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:>12,} rows")


if __name__ == "__main__":
    main()
