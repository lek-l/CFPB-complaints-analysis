-- 01_clean.sql
-- Turns the all-text raw_complaints table into a typed, standardized staging
-- table (stg_complaints). One row per complaint; no rows are dropped here.
-- Filtering (analysis window, credit bureaus) is done with flags so every
-- decision can be reversed downstream. Decision log: docs/data_cleaning.md

CREATE OR REPLACE TABLE stg_complaints AS
WITH typed AS (
    SELECT
        CAST(complaint_id AS BIGINT)                   AS complaint_id,
        -- D1. Dates: the CSV uses ISO yyyy-mm-dd. Profiling found 0 unparseable
        --     values, so a strict CAST is safe (it fails loudly if that changes).
        CAST(date_received AS DATE)                    AS date_received,
        CAST(date_sent_to_company AS DATE)             AS date_sent_to_company,

        -- D2. Text: trim whitespace and normalize curly apostrophes (U+2019,
        --     e.g. "Traveler’s checks") to straight ones so labels match
        --     consistently in filters and joins.
        TRIM(product)                                  AS product,
        REPLACE(TRIM(subproduct), chr(8217), '''')     AS subproduct_raw,
        REPLACE(TRIM(issue), chr(8217), '''')          AS issue,
        REPLACE(TRIM(subissue), chr(8217), '''')       AS subissue_raw,
        TRIM(company)                                  AS company_raw,
        UPPER(TRIM(state))                             AS state_raw,
        TRIM(zip_code)                                 AS zip_code_raw,
        TRIM(submitted_via)                            AS submitted_via,
        TRIM(company_response_to_consumer)             AS company_response,
        NULLIF(TRIM(company_public_response), '')      AS company_public_response,
        timely_response,
        tags
    FROM raw_complaints
)
SELECT
    complaint_id,
    date_received,
    date_sent_to_company,

    -- D3. Delay from CFPB receipt to forwarding. 7,050 rows have a send date
    --     before the receive date (impossible); keep the rows but null the
    --     metric and flag them rather than guess which date is wrong.
    CASE WHEN date_sent_to_company >= date_received
         THEN date_diff('day', date_received, date_sent_to_company) END  AS days_to_company,
    (date_sent_to_company < date_received)                               AS is_date_anomaly,

    -- D4. Analysis window: Jan 2018 (first full year after the CFPB's April
    --     2017 product-taxonomy overhaul) through Aug 2026 (last complete
    --     month of the snapshot). Rows outside the window stay in the table.
    (date_received BETWEEN DATE '2018-01-01' AND DATE '2026-08-31')      AS in_analysis_window,

    -- D5. Product: 21 raw values collapse into 12 comparable groups. Legacy
    --     combined categories are split by sub-product where possible so
    --     trends don't break at taxonomy changes.
    product,
    CASE
        WHEN product ILIKE 'Credit reporting%'                    THEN 'Credit reporting'
        WHEN product = 'Debt collection'                          THEN 'Debt collection'
        WHEN product IN ('Debt or credit management')             THEN 'Debt or credit management'
        WHEN product = 'Mortgage'                                 THEN 'Mortgage'
        WHEN product IN ('Checking or savings account',
                         'Bank account or service')               THEN 'Checking or savings account'
        WHEN product = 'Credit card'                              THEN 'Credit card'
        WHEN product = 'Prepaid card'                             THEN 'Prepaid card'
        WHEN product = 'Credit card or prepaid card'
             AND subproduct_raw ILIKE '%credit card%'             THEN 'Credit card'
        WHEN product = 'Credit card or prepaid card'              THEN 'Prepaid card'
        WHEN product IN ('Money transfer, virtual currency, or money service',
                         'Money transfers', 'Virtual currency')   THEN 'Money transfer or virtual currency'
        WHEN product = 'Student loan'                             THEN 'Student loan'
        WHEN product = 'Vehicle loan or lease'                    THEN 'Vehicle loan or lease'
        WHEN product = 'Consumer Loan'
             AND subproduct_raw ILIKE 'Vehicle%'                  THEN 'Vehicle loan or lease'
        WHEN product IN ('Consumer Loan', 'Payday loan',
                         'Payday loan, title loan, or personal loan',
                         'Payday loan, title loan, personal loan, or advance loan')
                                                                  THEN 'Payday, title or personal loan'
        ELSE 'Other financial service'
    END                                                                   AS product_group,

    -- D6. Missing sub-product (1.3%) / sub-issue (5.2%): these are mostly
    --     products that have no sub-categories, not data loss. Label them so
    --     they show up explicitly in groupings instead of as blanks. Issue is
    --     missing on only 6 rows, but NULLs would silently drop them from the
    --     fact table's dimension joins, so they get the same label.
    COALESCE(NULLIF(subproduct_raw, ''), 'Not specified')                AS subproduct,
    COALESCE(NULLIF(issue, ''), 'Not specified')                         AS issue,
    COALESCE(NULLIF(subissue_raw, ''), 'Not specified')                  AS subissue,

    -- D7. Company: build a grouping key (upper-case, single spaces, branch
    --     suffixes such as "- FIRSTMERIT BANK, N.A. BRANCH" removed).
    --     02_schema.sql picks a display name per key.
    company_raw,
    regexp_replace(
        regexp_replace(UPPER(company_raw), '\s+', ' ', 'g'),
        ' - [^-]*BRANCH$', '')                                            AS company_key_name,

    -- D8. State: keep 2-letter codes; map the one spelled-out value to its
    --     USPS code. Territories and military codes are kept and classified
    --     in dim_geography. 0.4% are missing -> NULL.
    CASE WHEN state_raw = 'UNITED STATES MINOR OUTLYING ISLANDS' THEN 'UM'
         ELSE NULLIF(state_raw, '') END                                  AS state_code,

    -- D9. ZIP: the CFPB masks ZIPs (e.g. "770XX") and uses "XXXXX" when
    --     withheld. Keep only the reliable 3-digit prefix; else NULL.
    CASE WHEN regexp_matches(zip_code_raw, '^[0-9]{3}')
         THEN LEFT(zip_code_raw, 3) END                                   AS zip3,

    submitted_via,

    -- D10. Outcome: the CFPB changed response categories in April 2017, so
    --      "Closed without relief" (last used 2017-04-21) cannot be tracked
    --      over time. Group all categories into one consistent outcome:
    --        Relief     = monetary / non-monetary / legacy "with relief"
    --        No relief  = closed with explanation / legacy "without relief" / "Closed"
    --        Untimely   = company never responded
    --        In progress = not yet resolved, excluded from rate denominators
    company_response,
    CASE
        WHEN company_response IN ('Closed with monetary relief',
                                  'Closed with non-monetary relief',
                                  'Closed with relief')      THEN 'Relief'
        WHEN company_response IN ('Closed with explanation',
                                  'Closed without relief', 'Closed') THEN 'No relief'
        WHEN company_response = 'Untimely response'          THEN 'Untimely response'
        WHEN company_response = 'In progress'                THEN 'In progress'
    END                                                                   AS relief_outcome,
    (company_response = 'Closed with monetary relief')                   AS is_monetary_relief,
    company_public_response,

    -- D11. Yes/No -> BOOLEAN (0 missing values in the source).
    (timely_response = 'Yes')                                            AS is_timely,

    -- D12. Tags (95.5% empty) hold two independent attributes; split them
    --      into booleans so "Older American, Servicemember" counts in both.
    COALESCE(tags ILIKE '%Servicemember%', FALSE)                        AS is_servicemember,
    COALESCE(tags ILIKE '%Older American%', FALSE)                       AS is_older_american
FROM typed;
