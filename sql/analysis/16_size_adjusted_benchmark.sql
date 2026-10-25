-- 16_size_adjusted_benchmark.sql
-- Business question 4, extended: how does Regions compare with peers once
-- bank size is taken into account?
--
-- Complaints per $1B of deposits = complaints in the year / year-end deposits
-- (FDIC Call Reports, data/reference/bank_financials.csv). This is the
-- standard way to compare complaint burden across banks of different sizes.
-- Caveats: CFPB complaints name the holding company while FDIC deposits are
-- the bank subsidiary's; Citizens' 2018 deposits predate a 2019 charter
-- consolidation, so its 2018 rate is overstated.

-- @query: q8a_complaints_per_billion_deposits
WITH complaints AS (
    SELECT c.bank_short_name, d.year,
           COUNT(*) AS complaints,
           COUNT(*) FILTER (WHERE i.issue = 'Problem caused by your funds being low') AS overdraft_complaints
    FROM fact_complaints f
    JOIN dim_company c ON c.company_key = f.company_key
    JOIN dim_date d    ON d.date_key = f.date_received_key
    JOIN dim_issue i   ON i.issue_key = f.issue_key
    WHERE c.peer_role IS NOT NULL AND d.year BETWEEN 2018 AND 2025
    GROUP BY ALL
)
SELECT c.bank_short_name AS bank,
       c.year,
       c.complaints,
       b.deposits_billions,
       ROUND(c.complaints / b.deposits_billions, 2)           AS complaints_per_bn_deposits,
       ROUND(c.overdraft_complaints / b.deposits_billions, 3) AS overdraft_per_bn_deposits
FROM complaints c
JOIN read_csv('data/reference/bank_financials.csv') b
  ON b.bank_short_name = c.bank_short_name AND b.year = c.year
ORDER BY bank, year;

-- @query: q8b_size_adjusted_scorecard
-- 2025 (latest full year) and 2018-2025 pooled rates, with Regions' gap vs
-- the simple average of the 5 peers.
WITH complaints AS (
    SELECT c.bank_short_name, c.peer_role, d.year, COUNT(*) AS complaints,
           COUNT(*) FILTER (WHERE i.issue = 'Problem caused by your funds being low') AS overdraft
    FROM fact_complaints f
    JOIN dim_company c ON c.company_key = f.company_key
    JOIN dim_date d    ON d.date_key = f.date_received_key
    JOIN dim_issue i   ON i.issue_key = f.issue_key
    WHERE c.peer_role IS NOT NULL AND d.year BETWEEN 2018 AND 2025
    GROUP BY ALL
),
joined AS (
    SELECT c.*, b.deposits_billions
    FROM complaints c
    JOIN read_csv('data/reference/bank_financials.csv') b
      ON b.bank_short_name = c.bank_short_name AND b.year = c.year
),
per_bank AS (
    SELECT bank_short_name AS bank, peer_role,
           SUM(complaints) FILTER (WHERE year = 2025) / SUM(deposits_billions) FILTER (WHERE year = 2025) AS rate_2025,
           SUM(complaints) / SUM(deposits_billions)                                                   AS rate_2018_2025,
           SUM(overdraft) FILTER (WHERE year = 2025) / SUM(deposits_billions) FILTER (WHERE year = 2025) AS overdraft_rate_2025
    FROM joined
    GROUP BY ALL
),
peer_avg AS (
    SELECT AVG(rate_2025) AS r25, AVG(rate_2018_2025) AS rall, AVG(overdraft_rate_2025) AS od25
    FROM per_bank WHERE peer_role = 'Peer'
)
SELECT p.bank,
       ROUND(p.rate_2025, 2)                       AS complaints_per_bn_2025,
       ROUND(p.rate_2025 / a.r25, 2)               AS ratio_to_peer_avg_2025,
       ROUND(p.rate_2018_2025, 2)                  AS complaints_per_bn_2018_2025,
       ROUND(p.overdraft_rate_2025, 3)             AS overdraft_per_bn_2025,
       ROUND(p.overdraft_rate_2025 / a.od25, 2)    AS overdraft_ratio_to_peer_avg_2025,
       RANK() OVER (ORDER BY p.rate_2025)          AS rank_lowest_burden_2025
FROM per_bank p CROSS JOIN peer_avg a
ORDER BY p.rate_2025;
