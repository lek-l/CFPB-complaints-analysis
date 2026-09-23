-- 02_schema.sql
-- Builds the star schema from stg_complaints:
--
--              dim_date     dim_company
--                  \            /
--   dim_product -- fact_complaints -- dim_geography
--                       |
--                   dim_issue
--
-- Dimensions use integer surrogate keys (smaller, faster joins in Power BI);
-- dim_geography keeps the USPS state code as its key because it is already a
-- stable, human-readable identifier.

-- dim_company ---------------------------------------------------------------
-- One row per cleaned company. Display name = the most common raw spelling of
-- that company, which avoids hand-maintained title-casing ("N.A.", "JPMorgan").
CREATE OR REPLACE TABLE dim_company AS
WITH spellings AS (
    SELECT company_key_name, company_raw, COUNT(*) AS n
    FROM stg_complaints
    GROUP BY ALL
),
companies AS (
    SELECT company_key_name,
           arg_max(company_raw, n) AS company_name,
           SUM(n)                  AS total_complaints
    FROM spellings
    GROUP BY company_key_name
),
-- Peer set for the Regions benchmark: similar-size super-regional banks.
-- Truist is excluded (roughly 3x Regions' size); keys verified in 03_validate.sql.
peers(company_key_name, bank_short_name, peer_role) AS (
    VALUES ('REGIONS FINANCIAL CORPORATION',     'Regions',     'Focal'),
           ('FIFTH THIRD FINANCIAL CORPORATION', 'Fifth Third', 'Peer'),
           ('HUNTINGTON NATIONAL BANK, THE',     'Huntington',  'Peer'),
           ('KEYCORP',                           'KeyCorp',     'Peer'),
           ('M&T BANK CORPORATION',              'M&T',         'Peer'),
           ('CITIZENS FINANCIAL GROUP, INC.',    'Citizens',    'Peer')
)
SELECT
    CAST(ROW_NUMBER() OVER (ORDER BY c.company_key_name) AS INTEGER) AS company_key,
    c.company_name,
    c.company_key_name,
    -- The three nationwide credit bureaus are ~78% of all complaints; flag them
    -- so bank-focused analysis can exclude them.
    c.company_key_name IN ('TRANSUNION INTERMEDIATE HOLDINGS, INC.',
                           'EQUIFAX, INC.',
                           'EXPERIAN INFORMATION SOLUTIONS INC.') AS is_credit_bureau,
    p.bank_short_name,
    p.peer_role,
    c.total_complaints
FROM companies c
LEFT JOIN peers p USING (company_key_name);

-- dim_product ---------------------------------------------------------------
CREATE OR REPLACE TABLE dim_product AS
SELECT
    CAST(ROW_NUMBER() OVER (ORDER BY product_group, product, subproduct) AS INTEGER) AS product_key,
    product_group,
    product    AS product_original,
    subproduct
FROM (SELECT DISTINCT product_group, product, subproduct FROM stg_complaints);

-- dim_issue -----------------------------------------------------------------
CREATE OR REPLACE TABLE dim_issue AS
SELECT
    CAST(ROW_NUMBER() OVER (ORDER BY issue, subissue) AS INTEGER) AS issue_key,
    issue,
    subissue
FROM (SELECT DISTINCT issue, subissue FROM stg_complaints);

-- dim_geography -------------------------------------------------------------
-- 50 states + DC + PR come from Census population estimates (Vintage 2025).
-- Per-capita metrics use 2025 population for all years: a documented
-- simplification, since state populations move only a few % over the window.
-- Other codes in the data (territories, military APO/FPO) are kept but have
-- no population and is_state = FALSE, so they drop out of per-capita views.
CREATE OR REPLACE TABLE dim_geography AS
WITH census AS (
    SELECT * FROM read_csv('data/reference/state_population.csv', header = true)
),
other_codes(state_code, state_name, census_region) AS (
    VALUES ('AA', 'Armed Forces Americas',          'Military'),
           ('AE', 'Armed Forces Europe',            'Military'),
           ('AP', 'Armed Forces Pacific',           'Military'),
           ('AS', 'American Samoa',                 'Territory'),
           ('GU', 'Guam',                           'Territory'),
           ('MP', 'Northern Mariana Islands',       'Territory'),
           ('VI', 'U.S. Virgin Islands',            'Territory'),
           ('UM', 'U.S. Minor Outlying Islands',    'Territory'),
           ('FM', 'Micronesia',                     'Freely associated state'),
           ('MH', 'Marshall Islands',               'Freely associated state'),
           ('PW', 'Palau',                          'Freely associated state')
)
SELECT state_code, state_name, census_region,
       CAST(population_2025 AS BIGINT)            AS population_2025,
       state_code NOT IN ('PR')                   AS is_state      -- 50 states + DC
FROM census
UNION ALL
SELECT state_code, state_name, census_region, NULL, FALSE
FROM other_codes
UNION ALL
SELECT 'NA', 'Not provided', 'Unknown', NULL, FALSE;   -- 0.4% of complaints

-- dim_date ------------------------------------------------------------------
-- Continuous calendar (no gaps), required for Power BI time intelligence.
CREATE OR REPLACE TABLE dim_date AS
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER)       AS date_key,
    CAST(d AS DATE)                              AS date,
    year(d)                                      AS year,
    quarter(d)                                   AS quarter,
    'Q' || quarter(d)                            AS quarter_label,
    month(d)                                     AS month_num,
    strftime(d, '%b')                            AS month_name,
    CAST(date_trunc('month', d) AS DATE)         AS month_start,
    strftime(d, '%Y-%m')                         AS year_month,
    isodow(d)                                    AS day_of_week,     -- 1 = Monday
    d <= DATE '2026-08-31'                       AS is_complete_month,
    d BETWEEN DATE '2018-01-01' AND DATE '2026-08-31' AS in_analysis_window
FROM range(DATE '2011-12-01', DATE '2026-12-31' + INTERVAL 1 DAY, INTERVAL 1 DAY) AS t(d);

-- fact_complaints -----------------------------------------------------------
-- Grain: one row per complaint. Outcome flags are stored as 0/1 integers so
-- rates are simple averages (AVERAGE in DAX, AVG in SQL).
CREATE OR REPLACE TABLE fact_complaints AS
SELECT
    s.complaint_id,
    CAST(strftime(s.date_received, '%Y%m%d') AS INTEGER)        AS date_received_key,
    CAST(strftime(s.date_sent_to_company, '%Y%m%d') AS INTEGER) AS date_sent_key,
    c.company_key,
    p.product_key,
    i.issue_key,
    COALESCE(s.state_code, 'NA')                                AS state_code,
    s.zip3,
    s.submitted_via,
    s.company_response,
    s.relief_outcome,
    s.company_public_response,
    CAST(s.is_timely AS TINYINT)                                AS timely_flag,
    -- Closed = has a final outcome; relief rate denominator.
    CAST(s.relief_outcome IN ('Relief', 'No relief') AS TINYINT) AS closed_flag,
    CASE WHEN s.relief_outcome IN ('Relief', 'No relief')
         THEN CAST(s.relief_outcome = 'Relief' AS TINYINT) END   AS relief_flag,
    CAST(s.is_monetary_relief AS TINYINT)                       AS monetary_relief_flag,
    s.days_to_company,
    s.is_date_anomaly,
    s.in_analysis_window,
    s.is_servicemember,
    s.is_older_american
FROM stg_complaints s
JOIN dim_company c ON c.company_key_name = s.company_key_name
JOIN dim_product p ON p.product_group = s.product_group
                  AND p.product_original = s.product
                  AND p.subproduct = s.subproduct
JOIN dim_issue   i ON i.issue = s.issue AND i.subissue = s.subissue;
