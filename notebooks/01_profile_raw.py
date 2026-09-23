"""Profile the raw table so cleaning decisions are driven by the data.

Prints row count, date range, null/blank % per column, and distinct counts.
Usage:  python notebooks/01_profile_raw.py
"""
import duckdb

con = duckdb.connect("data/complaints.duckdb", read_only=True)

print(con.sql("SELECT COUNT(*) AS rows, MIN(date_received) AS first, MAX(date_received) AS last FROM raw_complaints"))

cols = [r[0] for r in con.sql("DESCRIBE raw_complaints").fetchall()]
profile = " UNION ALL ".join(
    f"""SELECT '{c}' AS column_name,
               ROUND(100.0 * COUNT(*) FILTER (WHERE {c} IS NULL OR TRIM({c}) = '') / COUNT(*), 1) AS pct_missing,
               APPROX_COUNT_DISTINCT({c}) AS approx_distinct
        FROM raw_complaints"""
    for c in cols
)
print(con.sql(profile).df().to_string(index=False))
