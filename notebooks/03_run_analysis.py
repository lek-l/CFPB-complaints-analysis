"""Run every query in sql/analysis/ and save each result to results/<query>.csv.

Each query in a .sql file starts with a `-- @query: <name>` marker; the name
becomes the output file name.
Usage:  python notebooks/03_run_analysis.py
"""
import os
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"


def split_queries(sql: str) -> list[tuple[str, str]]:
    parts = re.split(r"^-- @query:\s*(\w+)\s*$", sql, flags=re.MULTILINE)
    return [(parts[i], parts[i + 1].strip().rstrip(";")) for i in range(1, len(parts), 2)]


if __name__ == "__main__":
    os.chdir(ROOT)  # queries read files such as results/q7a_complaint_alerts.csv by relative path
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect(str(ROOT / "data" / "complaints.duckdb"), read_only=True)
    for sql_file in sorted((ROOT / "sql" / "analysis").glob("*.sql")):
        for name, query in split_queries(sql_file.read_text(encoding="utf-8")):
            df = con.sql(query).df()
            df.to_csv(OUT / f"{name}.csv", index=False)
            print(f"{sql_file.name:<26} {name:<28} {len(df):>4} rows")
