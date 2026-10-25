-- 17_early_warning.sql
-- Complaint early-warning system: flag company-months where complaint volume
-- jumps far above that company's own recent norm, the kind of monitoring a
-- bank's compliance team runs to catch emerging problems early.
--
-- Rule (all must hold):
--   * baseline = mean and standard deviation of the company's previous 12
--     months (current month excluded, so a spike can't hide itself);
--   * z-score = (this month - baseline mean) / baseline std >= 3;
--   * at least 3x the baseline mean. Without this, industry-wide growth makes
--     dozens of companies look "unusual" at once (270 alerts vs 38; Jan 2025
--     alone dropped from 46 to 5), so the alerts stop being actionable;
--   * at least 200 complaints this month (filters out tiny companies whose
--     counts jump from 2 to 20);
--   * at least 6 months of history in the baseline.
-- Scope: non-bureau companies, complete months in the analysis window.
-- A month spine fills zero-complaint months so baselines aren't inflated.

-- @query: q7a_complaint_alerts
WITH active AS (
    -- companies large enough to matter: 1,000+ complaints in the window
    SELECT f.company_key
    FROM fact_complaints f
    JOIN dim_company c USING (company_key)
    WHERE f.in_analysis_window AND NOT c.is_credit_bureau
      -- CFPB placeholder for unnamed student-loan servicers, not a real company
      AND c.company_name <> 'Servicer under contract with Federal Student Aid'
    GROUP BY f.company_key
    HAVING COUNT(*) >= 1000
),
months AS (
    SELECT DISTINCT month_start FROM dim_date WHERE in_analysis_window
),
spine AS (
    SELECT a.company_key, m.month_start FROM active a CROSS JOIN months m
),
monthly AS (
    SELECT f.company_key, d.month_start, COUNT(*) AS complaints
    FROM fact_complaints f
    JOIN dim_date d ON d.date_key = f.date_received_key
    WHERE f.in_analysis_window AND f.company_key IN (SELECT company_key FROM active)
    GROUP BY ALL
),
series AS (
    SELECT s.company_key, s.month_start, COALESCE(m.complaints, 0) AS complaints
    FROM spine s LEFT JOIN monthly m USING (company_key, month_start)
),
scored AS (
    SELECT company_key, month_start, complaints,
           AVG(complaints)         OVER w AS baseline_mean,
           STDDEV_SAMP(complaints) OVER w AS baseline_std,
           COUNT(*)                OVER w AS baseline_months
    FROM series
    WINDOW w AS (PARTITION BY company_key ORDER BY month_start
                 ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING)
)
SELECT strftime(s.month_start, '%Y-%m')                              AS month,
       c.company_name,
       s.complaints,
       ROUND(s.baseline_mean, 0)                                     AS baseline_mean,
       ROUND(s.complaints / NULLIF(s.baseline_mean, 0), 1)           AS times_baseline,
       -- floor the std at 1 so a perfectly flat baseline can't divide by zero
       ROUND((s.complaints - s.baseline_mean) / GREATEST(s.baseline_std, 1), 1) AS z_score
FROM scored s
JOIN dim_company c USING (company_key)
WHERE s.baseline_months >= 6
  AND s.complaints >= 200
  AND s.complaints >= 3 * s.baseline_mean
  AND (s.complaints - s.baseline_mean) / GREATEST(s.baseline_std, 1) >= 3
ORDER BY s.month_start, z_score DESC;

-- @query: q7b_alerts_per_month
-- How noisy is the rule? A useful monitor flags a handful of cases, not
-- dozens a month. Divides by the months actually covered (2026 = Jan-Aug).
WITH alerts AS (
    SELECT LEFT(month, 4) AS year, COUNT(*) AS alerts, COUNT(DISTINCT month) AS months_with_alerts
    FROM read_csv('results/q7a_complaint_alerts.csv')
    GROUP BY 1
),
covered AS (
    SELECT CAST(year AS VARCHAR) AS year, COUNT(DISTINCT month_start) AS months
    FROM dim_date WHERE in_analysis_window GROUP BY 1
)
SELECT c.year,
       COALESCE(a.alerts, 0)                                AS alerts,
       COALESCE(a.months_with_alerts, 0)                    AS months_with_alerts,
       c.months                                             AS months_covered,
       ROUND(COALESCE(a.alerts, 0) / c.months, 2)           AS avg_alerts_per_month
FROM covered c LEFT JOIN alerts a USING (year)
ORDER BY c.year;
