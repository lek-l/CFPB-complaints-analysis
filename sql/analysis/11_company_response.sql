-- 11_company_response.sql
-- Business question 2: Which companies have the worst timely-response rates
-- and the most "closed without relief" outcomes?
--
-- "Closed without relief" = relief_outcome 'No relief' (docs D12: the literal
-- CFPB category was retired in 2017; 'Closed with explanation' replaced it).
-- No-relief rate = No relief / (Relief + No relief).
-- Minimum volume: 1,000 complaints in the window, so a company with a handful
-- of complaints can't top the ranking by chance.

-- @query: q2a_lowest_timely
-- The 15 companies with the lowest timely-response rates.
WITH company_stats AS (
    SELECT c.company_name,
           COUNT(*)                                  AS complaints,
           COUNT(*) FILTER (WHERE f.timely_flag = 0) AS untimely,
           AVG(f.timely_flag)                        AS timely_rate
    FROM fact_complaints f
    JOIN dim_company c USING (company_key)
    WHERE f.in_analysis_window
      -- CFPB placeholder for unnamed federal student-loan servicers, not a
      -- real company: all 7,437 of its complaints are "Untimely response".
      AND c.company_name <> 'Servicer under contract with Federal Student Aid'
    GROUP BY c.company_name
    HAVING COUNT(*) >= 1000
)
SELECT company_name,
       complaints,
       untimely,
       ROUND(100 * timely_rate, 1)            AS timely_pct,
       RANK() OVER (ORDER BY timely_rate)     AS worst_rank,
       COUNT(*) OVER ()                       AS companies_ranked
FROM company_stats
QUALIFY worst_rank <= 15
ORDER BY worst_rank;

-- @query: q2b_highest_no_relief
-- The 15 companies with the highest share of closed complaints ending without
-- relief, alongside how often they gave monetary relief.
WITH company_stats AS (
    SELECT c.company_name,
           SUM(f.closed_flag)                                AS closed_complaints,
           SUM(f.closed_flag) - SUM(f.relief_flag)           AS closed_no_relief,
           AVG(f.relief_flag)                                AS relief_rate,  -- NULLs (not closed) ignored
           SUM(f.monetary_relief_flag) / SUM(f.closed_flag)  AS monetary_rate
    FROM fact_complaints f
    JOIN dim_company c USING (company_key)
    WHERE f.in_analysis_window
    GROUP BY c.company_name
    HAVING SUM(f.closed_flag) >= 1000
)
SELECT company_name,
       closed_complaints,
       closed_no_relief,
       ROUND(100 * (1 - relief_rate), 1)      AS no_relief_pct,
       ROUND(100 * monetary_rate, 1)          AS monetary_relief_pct,
       -- 71 companies tie at 0% relief; break ties by volume so the list
       -- surfaces the largest zero-relief companies first
       ROW_NUMBER() OVER (ORDER BY relief_rate, closed_no_relief DESC) AS worst_rank,
       COUNT(*) OVER ()                       AS companies_ranked
FROM company_stats
QUALIFY worst_rank <= 15
ORDER BY worst_rank;

-- @query: q2c_relief_distribution
-- Context for q2b: the spread of relief rates across qualifying non-bureau
-- companies, so "worst" can be read against the typical company.
WITH company_stats AS (
    SELECT c.company_key, AVG(f.relief_flag) AS relief_rate
    FROM fact_complaints f
    JOIN dim_company c USING (company_key)
    WHERE f.in_analysis_window AND NOT c.is_credit_bureau
    GROUP BY c.company_key
    HAVING SUM(f.closed_flag) >= 1000
)
SELECT COUNT(*)                                          AS companies,
       ROUND(100 * quantile_cont(relief_rate, 0.25), 1)  AS p25_relief_pct,
       ROUND(100 * median(relief_rate), 1)               AS median_relief_pct,
       ROUND(100 * quantile_cont(relief_rate, 0.75), 1)  AS p75_relief_pct,
       COUNT(*) FILTER (WHERE relief_rate = 0)           AS companies_zero_relief,
       COUNT(*) FILTER (WHERE relief_rate < 0.05)        AS companies_under_5pct_relief
FROM company_stats;

-- @query: q2d_relief_bureaus_vs_others
-- Relief means different things by company type: for the credit bureaus it is
-- almost always non-monetary (correcting a report), so compare the two groups.
SELECT CASE WHEN c.is_credit_bureau THEN 'Credit bureaus' ELSE 'All other companies' END AS company_type,
       SUM(f.closed_flag)                                                 AS closed_complaints,
       ROUND(100 * AVG(f.relief_flag), 1)                                 AS relief_pct,
       ROUND(100 * SUM(f.monetary_relief_flag) / SUM(f.closed_flag), 2)   AS monetary_relief_pct
FROM fact_complaints f
JOIN dim_company c USING (company_key)
WHERE f.in_analysis_window
GROUP BY company_type
ORDER BY company_type;
