-- 13_peer_benchmark.sql
-- Business question 4: How does Regions Bank compare with similar regional
-- banks on complaint volume, top issues, and response performance?
--
-- Peers (dim_company.peer_role): Fifth Third, Huntington, KeyCorp, M&T,
-- Citizens. The banks differ in size, so the benchmark leans on rates, mix
-- and growth indexes rather than raw counts. "Peer avg" excludes Regions.

-- @query: q4a_scorecard
WITH bank_stats AS (
    SELECT c.bank_short_name                                 AS bank,
           c.peer_role,
           COUNT(*)                                          AS complaints,
           COUNT(*) FILTER (WHERE d.year = 2025)             AS complaints_2025,
           AVG(f.timely_flag)                                AS timely_rate,
           AVG(f.relief_flag)                                AS relief_rate,
           SUM(f.monetary_relief_flag) / SUM(f.closed_flag)  AS monetary_rate
    FROM fact_complaints f
    JOIN dim_company c ON c.company_key = f.company_key
    JOIN dim_date d    ON d.date_key = f.date_received_key
    WHERE f.in_analysis_window AND c.peer_role IS NOT NULL
    GROUP BY ALL
),
peer_avg AS (
    SELECT AVG(relief_rate) AS relief, AVG(monetary_rate) AS monetary
    FROM bank_stats
    WHERE peer_role = 'Peer'
)
SELECT b.bank,
       b.complaints,
       b.complaints_2025,
       ROUND(100 * b.timely_rate, 2)                   AS timely_pct,
       ROUND(100 * b.relief_rate, 1)                   AS relief_pct,
       ROUND(100 * p.relief, 1)                        AS peer_avg_relief_pct,
       ROUND(100 * (b.relief_rate - p.relief), 1)      AS relief_pts_vs_peer_avg,
       ROUND(100 * b.monetary_rate, 1)                 AS monetary_relief_pct,
       ROUND(100 * (b.monetary_rate - p.monetary), 1)  AS monetary_pts_vs_peer_avg,
       RANK() OVER (ORDER BY b.relief_rate DESC)       AS relief_rank
FROM bank_stats b
CROSS JOIN peer_avg p
ORDER BY b.peer_role, b.complaints DESC;

-- @query: q4b_product_mix
-- Share of each bank's complaints by product group, and Regions' gap vs the
-- peer-average share (positive = Regions over-indexes on that product).
WITH mix AS (
    SELECT c.bank_short_name AS bank,
           c.peer_role,
           p.product_group,
           COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY c.bank_short_name) AS share
    FROM fact_complaints f
    JOIN dim_company c USING (company_key)
    JOIN dim_product p USING (product_key)
    WHERE f.in_analysis_window AND c.peer_role IS NOT NULL
    GROUP BY c.bank_short_name, c.peer_role, p.product_group
),
compare AS (
    SELECT product_group,
           COALESCE(MAX(share) FILTER (WHERE bank = 'Regions'), 0) AS regions_share,
           -- divide by 5, not AVG: a peer with no complaints in a product counts as 0%
           COALESCE(SUM(share) FILTER (WHERE peer_role = 'Peer'), 0) / 5 AS peer_avg_share
    FROM mix
    GROUP BY product_group
)
SELECT product_group,
       ROUND(100 * regions_share, 1)                    AS regions_pct,
       ROUND(100 * peer_avg_share, 1)                   AS peer_avg_pct,
       ROUND(100 * (regions_share - peer_avg_share), 1) AS gap_pts
FROM compare
ORDER BY regions_pct DESC, peer_avg_pct DESC, product_group;  -- tie-breakers keep output stable run to run

-- @query: q4c_top_issues
-- Top 3 issues per bank and their share of that bank's complaints.
WITH issue_counts AS (
    SELECT c.bank_short_name AS bank, i.issue, COUNT(*) AS complaints
    FROM fact_complaints f
    JOIN dim_company c USING (company_key)
    JOIN dim_issue i   USING (issue_key)
    WHERE f.in_analysis_window AND c.peer_role IS NOT NULL
    GROUP BY ALL
)
SELECT bank,
       issue,
       complaints,
       ROUND(100.0 * complaints / SUM(complaints) OVER (PARTITION BY bank), 1) AS pct_of_bank,
       ROW_NUMBER() OVER (PARTITION BY bank ORDER BY complaints DESC)          AS issue_rank
FROM issue_counts
QUALIFY issue_rank <= 3
ORDER BY bank, issue_rank;

-- @query: q4d_volume_index
-- Complaint growth indexed to 2018 = 100: a size-neutral way to compare
-- volume trends across banks of different sizes.
WITH yearly AS (
    SELECT c.bank_short_name AS bank, d.year, COUNT(*) AS complaints
    FROM fact_complaints f
    JOIN dim_company c ON c.company_key = f.company_key
    JOIN dim_date d    ON d.date_key = f.date_received_key
    WHERE c.peer_role IS NOT NULL AND d.year BETWEEN 2018 AND 2025
    GROUP BY ALL
)
SELECT bank,
       year,
       complaints,
       ROUND(100.0 * complaints / FIRST_VALUE(complaints) OVER (PARTITION BY bank ORDER BY year), 0) AS index_2018_100
FROM yearly
ORDER BY bank, year;

-- @query: q4e_overdraft_trend
-- Drill-down from q4c: "Problem caused by your funds being low" (overdraft /
-- NSF fees) is Regions' #2 issue but not in any peer's top 3. Track its share
-- of complaints by year for Regions vs the pooled peer group. Context: the
-- CFPB ordered Regions to pay $191M over surprise overdraft fees in Sept 2022.
SELECT d.year,
       COUNT(*) FILTER (WHERE c.bank_short_name = 'Regions' AND i.issue = 'Problem caused by your funds being low') AS regions_overdraft,
       ROUND(100.0 * COUNT(*) FILTER (WHERE c.bank_short_name = 'Regions' AND i.issue = 'Problem caused by your funds being low')
             / COUNT(*) FILTER (WHERE c.bank_short_name = 'Regions'), 1)                                  AS regions_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE c.peer_role = 'Peer' AND i.issue = 'Problem caused by your funds being low')
             / COUNT(*) FILTER (WHERE c.peer_role = 'Peer'), 1)                                           AS peers_pct
FROM fact_complaints f
JOIN dim_company c ON c.company_key = f.company_key
JOIN dim_issue i   ON i.issue_key = f.issue_key
JOIN dim_date d    ON d.date_key = f.date_received_key
WHERE f.in_analysis_window AND c.peer_role IS NOT NULL
GROUP BY d.year
ORDER BY d.year;
