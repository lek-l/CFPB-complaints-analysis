-- 04_export_powerbi.sql
-- Exports the star schema to Parquet for Power BI (dashboard/data/).
--
-- Why an aggregate fact table instead of 16.6M complaint rows:
--   * The dashboard never shows individual complaints; every visual is a
--     count or a rate by month, company, product, issue or state.
--   * Pre-aggregating to month x company x product x issue x state cuts rows
--     ~6x (16.6M -> ~2.6M), keeping the model well under Power BI's 1 GB
--     publish limit and making slicers fast.
--   * Rates stay exact because we store numerators and denominators as
--     counts (timely_count / complaints, relief_count / closed_count), never
--     pre-computed percentages that can't be re-aggregated.
-- Scope: analysis window only (Jan 2018 - Aug 2026).
-- Types are cast to INTEGER/BIGINT/VARCHAR/DATE because Power BI does not
-- read DuckDB's TINYINT/HUGEINT reliably.

COPY (
    SELECT
        CAST(strftime(d.month_start, '%Y%m%d') AS INTEGER) AS month_key,
        f.company_key,
        f.product_key,
        f.issue_key,
        f.state_code,
        CAST(COUNT(*) AS INTEGER)                    AS complaints,
        CAST(SUM(f.timely_flag) AS INTEGER)          AS timely_count,
        CAST(SUM(f.closed_flag) AS INTEGER)          AS closed_count,
        CAST(COALESCE(SUM(f.relief_flag), 0) AS INTEGER) AS relief_count,
        CAST(SUM(f.monetary_relief_flag) AS INTEGER) AS monetary_relief_count
    FROM fact_complaints f
    JOIN dim_date d ON d.date_key = f.date_received_key
    WHERE f.in_analysis_window
    GROUP BY ALL
) TO 'dashboard/data/fact_complaints_monthly.parquet' (FORMAT parquet, COMPRESSION snappy);

-- Companies: only those with complaints in the window; add a single
-- company_type column so one slicer can include/exclude bureaus and peers.
COPY (
    SELECT c.company_key,
           c.company_name,
           COALESCE(c.bank_short_name, c.company_name) AS company_label,
           c.is_credit_bureau,
           c.peer_role,
           CASE WHEN c.is_credit_bureau        THEN 'Credit bureau'
                WHEN c.peer_role IS NOT NULL   THEN 'Regions peer group'
                ELSE 'Other company' END      AS company_type
    FROM dim_company c
    WHERE c.company_key IN (SELECT company_key FROM fact_complaints WHERE in_analysis_window)
) TO 'dashboard/data/dim_company.parquet' (FORMAT parquet, COMPRESSION snappy);

COPY (SELECT product_key, product_group, product_original, subproduct FROM dim_product)
    TO 'dashboard/data/dim_product.parquet' (FORMAT parquet, COMPRESSION snappy);

COPY (SELECT issue_key, issue, subissue FROM dim_issue)
    TO 'dashboard/data/dim_issue.parquet' (FORMAT parquet, COMPRESSION snappy);

COPY (SELECT state_code, state_name, census_region, population_2025, is_state FROM dim_geography)
    TO 'dashboard/data/dim_geography.parquet' (FORMAT parquet, COMPRESSION snappy);

-- Date table: whole calendar years 2018-2026 (Power BI time intelligence
-- requires a continuous range covering full years).
COPY (
    SELECT date_key, date, CAST(year AS INTEGER) AS year, CAST(quarter AS INTEGER) AS quarter,
           quarter_label, CAST(month_num AS INTEGER) AS month_num, month_name,
           month_start, year_month, is_complete_month
    FROM dim_date
    WHERE date BETWEEN DATE '2018-01-01' AND DATE '2026-12-31'
) TO 'dashboard/data/dim_date.parquet' (FORMAT parquet, COMPRESSION snappy);
