-- 14_monthly_trends.sql
-- Business question 5: Month-over-month complaint trends with rolling averages.
--
-- A month spine from dim_date guarantees every month appears even with zero
-- complaints, so LAG and the rolling windows never silently skip a gap.
-- Shown for all complaints and excluding the credit bureaus.

-- @query: q5_monthly_trends
WITH months AS (
    SELECT DISTINCT month_start
    FROM dim_date
    WHERE in_analysis_window
),
monthly AS (
    SELECT d.month_start,
           COUNT(*)                                       AS complaints,
           COUNT(*) FILTER (WHERE NOT c.is_credit_bureau) AS complaints_excl_bureaus
    FROM fact_complaints f
    JOIN dim_date d    ON d.date_key = f.date_received_key
    JOIN dim_company c ON c.company_key = f.company_key
    WHERE f.in_analysis_window
    GROUP BY d.month_start
),
filled AS (
    SELECT m.month_start,
           COALESCE(x.complaints, 0)              AS complaints,
           COALESCE(x.complaints_excl_bureaus, 0) AS complaints_excl_bureaus
    FROM months m
    LEFT JOIN monthly x USING (month_start)
)
SELECT strftime(month_start, '%Y-%m')                                                        AS month,
       complaints,
       ROUND(100.0 * (complaints - LAG(complaints) OVER w) / LAG(complaints) OVER w, 1)      AS mom_pct,
       ROUND(AVG(complaints) OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0)          AS rolling_3m,
       ROUND(AVG(complaints) OVER (w ROWS BETWEEN 11 PRECEDING AND CURRENT ROW), 0)         AS rolling_12m,
       ROUND(100.0 * (complaints - LAG(complaints, 12) OVER w) / LAG(complaints, 12) OVER w, 1) AS yoy_same_month_pct,
       complaints_excl_bureaus,
       ROUND(100.0 * (complaints_excl_bureaus - LAG(complaints_excl_bureaus) OVER w)
             / LAG(complaints_excl_bureaus) OVER w, 1)                                       AS mom_pct_excl_bureaus,
       ROUND(AVG(complaints_excl_bureaus) OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0)  AS rolling_3m_excl_bureaus,
       ROUND(AVG(complaints_excl_bureaus) OVER (w ROWS BETWEEN 11 PRECEDING AND CURRENT ROW), 0) AS rolling_12m_excl_bureaus
FROM filled
WINDOW w AS (ORDER BY month_start)
ORDER BY month_start;

-- @query: q5b_jan2025_spike_drivers
-- Drill-down from q5: non-bureau complaints doubled in Jan 2025 (123,553 vs
-- ~60K in surrounding months). Which companies drove the jump vs Dec 2024?
-- (Non-bureau complaints peaked on Jan 17, the day after the CFPB's Jan 16, 2025
-- $175M order against Block/Cash App.)
WITH by_company AS (
    SELECT c.company_name,
           COUNT(*) FILTER (WHERE d.year_month = '2024-12') AS dec_2024,
           COUNT(*) FILTER (WHERE d.year_month = '2025-01') AS jan_2025,
           COUNT(*) FILTER (WHERE d.year_month = '2025-02') AS feb_2025
    FROM fact_complaints f
    JOIN dim_company c ON c.company_key = f.company_key
    JOIN dim_date d    ON d.date_key = f.date_received_key
    WHERE NOT c.is_credit_bureau AND d.year_month IN ('2024-12', '2025-01', '2025-02')
    GROUP BY c.company_name
)
SELECT company_name, dec_2024, jan_2025, feb_2025,
       jan_2025 - dec_2024                                                     AS increase,
       ROUND(100.0 * (jan_2025 - dec_2024) / SUM(jan_2025 - dec_2024) OVER (), 1) AS pct_of_total_increase
FROM by_company
QUALIFY ROW_NUMBER() OVER (ORDER BY jan_2025 - dec_2024 DESC) <= 5
ORDER BY increase DESC;
