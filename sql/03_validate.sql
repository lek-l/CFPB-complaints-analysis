-- 03_validate.sql
-- Data-quality tests for the star schema. Each row is one test; failed_rows
-- must be 0. run_pipeline.py stops with an error if any test fails.

SELECT 'fact row count equals raw row count' AS test,
       ABS((SELECT COUNT(*) FROM fact_complaints) - (SELECT COUNT(*) FROM raw_complaints)) AS failed_rows
UNION ALL
SELECT 'complaint_id is unique',
       COUNT(*) - COUNT(DISTINCT complaint_id) FROM fact_complaints
UNION ALL
SELECT 'every fact date has a dim_date row',
       COUNT(*) FROM fact_complaints f
       LEFT JOIN dim_date d ON d.date_key = f.date_received_key WHERE d.date_key IS NULL
UNION ALL
SELECT 'every fact state has a dim_geography row',
       COUNT(*) FROM fact_complaints f
       LEFT JOIN dim_geography g USING (state_code) WHERE g.state_code IS NULL
UNION ALL
SELECT 'dim_geography has 51 states (50 + DC) with population',
       ABS(51 - COUNT(*)) FROM dim_geography WHERE is_state AND population_2025 > 0
UNION ALL
SELECT 'every raw product is mapped (no Other fallback surprises)',
       COUNT(*) FROM dim_product
       WHERE product_group = 'Other financial service' AND product_original <> 'Other financial service'
UNION ALL
SELECT 'every company response is mapped to an outcome',
       COUNT(*) FROM fact_complaints WHERE relief_outcome IS NULL AND company_response IS NOT NULL
UNION ALL
SELECT 'peer group has exactly 6 banks (Regions + 5 peers)',
       ABS(6 - COUNT(*)) FROM dim_company WHERE peer_role IS NOT NULL
UNION ALL
SELECT 'exactly 3 credit bureaus flagged',
       ABS(3 - COUNT(*)) FROM dim_company WHERE is_credit_bureau
UNION ALL
SELECT 'relief_flag only set on closed complaints',
       COUNT(*) FROM fact_complaints WHERE (relief_flag IS NOT NULL) <> (closed_flag = 1);
