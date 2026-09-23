-- 10_product_trends.sql
-- Business question 1: Which products and sub-products get the most
-- complaints, and how is that trending year over year?
--
-- Scope: analysis window (Jan 2018 - Aug 2026). YoY uses full calendar years
-- 2018-2025; 2026 is compared year-to-date (Jan-Aug) against Jan-Aug 2025.
-- Credit-bureau complaints are reported both included and excluded because
-- they are ~80% of volume and would otherwise hide every other trend.

-- @query: q1a_product_volume
-- Complaint volume and share by product group, with and without the bureaus.
WITH base AS (
    SELECT p.product_group, c.is_credit_bureau
    FROM fact_complaints f
    JOIN dim_product p USING (product_key)
    JOIN dim_company c USING (company_key)
    WHERE f.in_analysis_window
),
by_product AS (
    SELECT product_group,
           COUNT(*)                                       AS complaints,
           COUNT(*) FILTER (WHERE NOT is_credit_bureau)   AS complaints_excl_bureaus
    FROM base
    GROUP BY product_group
)
SELECT product_group,
       complaints,
       ROUND(100.0 * complaints / SUM(complaints) OVER (), 1)                           AS pct_of_all,
       complaints_excl_bureaus,
       ROUND(100.0 * complaints_excl_bureaus / SUM(complaints_excl_bureaus) OVER (), 1) AS pct_excl_bureaus,
       RANK() OVER (ORDER BY complaints_excl_bureaus DESC)                              AS rank_excl_bureaus
FROM by_product
ORDER BY complaints DESC;

-- @query: q1b_top_subproducts
-- Top 3 sub-products within each product group (bureaus excluded), and each
-- sub-product's share of its group.
WITH counts AS (
    SELECT p.product_group, p.subproduct, COUNT(*) AS complaints
    FROM fact_complaints f
    JOIN dim_product p USING (product_key)
    JOIN dim_company c USING (company_key)
    WHERE f.in_analysis_window AND NOT c.is_credit_bureau
    GROUP BY ALL
)
SELECT product_group,
       subproduct,
       complaints,
       ROUND(100.0 * complaints / SUM(complaints) OVER (PARTITION BY product_group), 1) AS pct_of_group,
       ROW_NUMBER() OVER (PARTITION BY product_group ORDER BY complaints DESC)          AS rank_in_group,
       SUM(complaints) OVER (PARTITION BY product_group)                                AS group_total
FROM counts
QUALIFY rank_in_group <= 3
ORDER BY group_total DESC, rank_in_group;

-- @query: q1c_product_yoy
-- Year-over-year change by product group, full years 2018-2025 (all companies).
WITH yearly AS (
    SELECT p.product_group, d.year, COUNT(*) AS complaints
    FROM fact_complaints f
    JOIN dim_product p ON p.product_key = f.product_key
    JOIN dim_date d    ON d.date_key = f.date_received_key
    WHERE d.year BETWEEN 2018 AND 2025
    GROUP BY ALL
)
SELECT product_group,
       year,
       complaints,
       LAG(complaints) OVER w                                                           AS prior_year,
       ROUND(100.0 * (complaints - LAG(complaints) OVER w) / LAG(complaints) OVER w, 1) AS yoy_pct,
       -- growth multiple vs 2018 summarizes the long-run trend in one number
       ROUND(complaints / FIRST_VALUE(complaints) OVER w, 2)                            AS x_vs_2018
FROM yearly
WINDOW w AS (PARTITION BY product_group ORDER BY year)
ORDER BY product_group, year;

-- @query: q1d_ytd_2026_vs_2025
-- Most recent trend: Jan-Aug 2026 vs Jan-Aug 2025, by product group.
WITH ytd AS (
    SELECT p.product_group,
           COUNT(*) FILTER (WHERE d.year = 2025) AS ytd_2025,
           COUNT(*) FILTER (WHERE d.year = 2026) AS ytd_2026
    FROM fact_complaints f
    JOIN dim_product p ON p.product_key = f.product_key
    JOIN dim_date d    ON d.date_key = f.date_received_key
    WHERE d.year IN (2025, 2026) AND d.month_num <= 8
    GROUP BY p.product_group
)
SELECT product_group, ytd_2025, ytd_2026,
       ROUND(100.0 * (ytd_2026 - ytd_2025) / NULLIF(ytd_2025, 0), 1) AS ytd_change_pct
FROM ytd
ORDER BY ytd_2026 DESC;
