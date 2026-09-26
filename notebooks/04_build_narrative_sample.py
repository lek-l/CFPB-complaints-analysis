"""Load the narratives archive, link it to the star schema, and draw the LLM sample.

Steps
1. Load every archive CSV into a `narratives` table (complaint_id -> text).
2. Report coverage: narratives exist only when the consumer opted to publish one.
3. Draw a reproducible (seeded) stratified sample of ~10K narratives:
   - market sample: 6,000 random non-bureau complaints about the four core
     consumer-banking products, for market-wide root-cause shares;
   - peer sample: up to 700 per bank for Regions and its 5 peers, so each bank
     has enough narratives to compare root-cause mix.
   A complaint can be in both; flags record which frame(s) it came from, so
   market-level estimates use only the market sample (no peer oversampling bias).
4. Save the sample to data/llm/sample.parquet (gitignored; contains text).

Usage:  python notebooks/04_build_narrative_sample.py
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SEED = 0.42          # DuckDB setseed() takes a value in [0, 1]
MARKET_N = 6000
PEER_N_PER_BANK = 700
MARKET_PRODUCTS = ("Checking or savings account", "Credit card", "Mortgage",
                   "Money transfer or virtual currency")

con = duckdb.connect(str(ROOT / "data" / "complaints.duckdb"))

# 1. Load narratives (union_by_name tolerates column-order differences between exports)
con.execute(f"""
CREATE OR REPLACE TABLE narratives AS
SELECT CAST(complaint_id AS BIGINT) AS complaint_id,
       any_value(consumer_complaint_narrative) AS narrative
FROM read_csv('{(ROOT / "data/raw/narratives/*.csv").as_posix()}',
              header = true, all_varchar = true, normalize_names = true,
              union_by_name = true, quote = '"', escape = '"')
WHERE consumer_complaint_narrative IS NOT NULL AND TRIM(consumer_complaint_narrative) <> ''
GROUP BY complaint_id
""")

# 2. Coverage
print(con.sql("""
SELECT COUNT(*) AS narratives,
       COUNT(f.complaint_id) AS linked_to_fact,
       ROUND(AVG(LENGTH(n.narrative))) AS avg_chars,
       ROUND(100.0 * COUNT(*) FILTER (WHERE LENGTH(n.narrative) > 6000) / COUNT(*), 1) AS pct_over_6000_chars
FROM narratives n LEFT JOIN fact_complaints f USING (complaint_id)
"""))
print(con.sql("""
SELECT d.year,
       COUNT(*) AS complaints,
       COUNT(n.complaint_id) AS with_narrative,
       ROUND(100.0 * COUNT(n.complaint_id) / COUNT(*), 1) AS pct_with_narrative,
       ROUND(100.0 * COUNT(n.complaint_id) FILTER (WHERE NOT c.is_credit_bureau)
             / COUNT(*) FILTER (WHERE NOT c.is_credit_bureau), 1) AS pct_non_bureau
FROM fact_complaints f
JOIN dim_date d    ON d.date_key = f.date_received_key
JOIN dim_company c ON c.company_key = f.company_key
LEFT JOIN narratives n USING (complaint_id)
WHERE f.in_analysis_window
GROUP BY d.year ORDER BY d.year
"""))

# 3. Sample frames
con.execute(f"SELECT setseed({SEED})")
con.execute(f"""
CREATE OR REPLACE TABLE llm_sample AS
WITH frame AS (
    SELECT f.complaint_id, n.narrative, p.product_original AS product, p.product_group,
           c.company_name, c.bank_short_name, c.peer_role, c.is_credit_bureau
    FROM fact_complaints f
    JOIN narratives n  USING (complaint_id)
    JOIN dim_product p ON p.product_key = f.product_key
    JOIN dim_company c ON c.company_key = f.company_key
    WHERE f.in_analysis_window
),
market AS (
    SELECT complaint_id FROM frame
    WHERE NOT is_credit_bureau AND product_group IN {MARKET_PRODUCTS}
    ORDER BY random() LIMIT {MARKET_N}
),
peer AS (
    SELECT complaint_id FROM frame
    WHERE peer_role IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (PARTITION BY bank_short_name ORDER BY random()) <= {PEER_N_PER_BANK}
)
SELECT fr.*,
       fr.complaint_id IN (SELECT complaint_id FROM market) AS in_market_sample,
       fr.complaint_id IN (SELECT complaint_id FROM peer)   AS in_peer_sample,
       LENGTH(fr.narrative) > 6000                          AS truncated
FROM frame fr
WHERE fr.complaint_id IN (SELECT complaint_id FROM market UNION SELECT complaint_id FROM peer)
""")
print(con.sql("""
SELECT COUNT(*) AS sample_size,
       COUNT(*) FILTER (WHERE in_market_sample) AS market,
       COUNT(*) FILTER (WHERE in_peer_sample) AS peer,
       COUNT(*) FILTER (WHERE in_market_sample AND in_peer_sample) AS both_frames,
       COUNT(*) FILTER (WHERE truncated) AS truncated,
       ROUND(SUM(LENGTH(narrative)) / 4) AS approx_narrative_tokens
FROM llm_sample
"""))
print(con.sql("""
SELECT bank_short_name, COUNT(*) AS in_peer_sample
FROM llm_sample WHERE in_peer_sample GROUP BY 1 ORDER BY 1
"""))

# 4. Export for the classifier
out = ROOT / "data" / "llm"
out.mkdir(parents=True, exist_ok=True)
con.execute(f"COPY llm_sample TO '{(out / 'sample.parquet').as_posix()}' (FORMAT parquet)")
print(f"Wrote {out / 'sample.parquet'}")
