-- 15_root_causes.sql
-- Business question 6 (LLM text analysis): what actually goes wrong, according
-- to consumers' own words, and which root causes get resolved?
--
-- Input: results/llm_classifications.csv (one row per sampled complaint, from
-- notebooks/05_classify_narratives.py), joined to the star schema on complaint_id.
-- Market-wide shares use ONLY the random market sample (in_market_sample) so the
-- oversampled peer banks don't skew them; bank comparisons use the peer sample.

-- @query: q6a_root_causes_market
-- Root-cause share across core consumer-banking complaints, with a 95%
-- confidence interval (normal approximation), and what happened to them.
WITH labeled AS (
    SELECT l.*, f.relief_flag, f.monetary_relief_flag, f.closed_flag
    FROM read_csv('results/llm_classifications.csv') l
    JOIN fact_complaints f USING (complaint_id)
    WHERE l.in_market_sample
),
by_cause AS (
    SELECT root_cause,
           COUNT(*)                                          AS complaints,
           AVG(relief_flag)                                  AS relief_rate,
           SUM(monetary_relief_flag) / SUM(closed_flag)      AS monetary_rate,
           AVG(CAST(contacted_company_multiple_times AS INT)) AS repeat_contact_rate,
           AVG(CAST(mentions_financial_loss AS INT))         AS financial_loss_rate
    FROM labeled
    GROUP BY root_cause
)
SELECT root_cause,
       complaints,
       ROUND(100.0 * complaints / SUM(complaints) OVER (), 1)                  AS share_pct,
       ROUND(100 * 1.96 * SQRT((complaints / SUM(complaints) OVER ())
             * (1 - complaints / SUM(complaints) OVER ()) / SUM(complaints) OVER ()), 1) AS ci95_pts,
       ROUND(100 * relief_rate, 1)                                             AS relief_pct,
       ROUND(100 * monetary_rate, 1)                                           AS monetary_relief_pct,
       ROUND(100 * repeat_contact_rate, 1)                                     AS contacted_multiple_times_pct,
       ROUND(100 * financial_loss_rate, 1)                                     AS financial_loss_pct
FROM by_cause
ORDER BY complaints DESC;

-- @query: q6b_root_causes_by_product
-- Top 3 root causes within each product (market sample).
WITH labeled AS (
    SELECT l.root_cause, p.product_group
    FROM read_csv('results/llm_classifications.csv') l
    JOIN fact_complaints f USING (complaint_id)
    JOIN dim_product p ON p.product_key = f.product_key
    WHERE l.in_market_sample
),
counts AS (
    SELECT product_group, root_cause, COUNT(*) AS complaints
    FROM labeled
    GROUP BY ALL
)
SELECT product_group,
       root_cause,
       complaints,
       ROUND(100.0 * complaints / SUM(complaints) OVER (PARTITION BY product_group), 1) AS pct_of_product,
       ROW_NUMBER() OVER (PARTITION BY product_group ORDER BY complaints DESC)          AS rank_in_product
FROM counts
QUALIFY rank_in_product <= 3
ORDER BY product_group, rank_in_product;

-- @query: q6c_peer_root_cause_mix
-- Root-cause mix for Regions vs the average of its 5 peers (peer sample).
-- Positive gap = Regions' complaints are more often about that root cause.
WITH mix AS (
    SELECT c.bank_short_name AS bank, c.peer_role, l.root_cause,
           COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY c.bank_short_name) AS share
    FROM read_csv('results/llm_classifications.csv') l
    JOIN fact_complaints f USING (complaint_id)
    JOIN dim_company c ON c.company_key = f.company_key
    WHERE l.in_peer_sample
    GROUP BY c.bank_short_name, c.peer_role, l.root_cause
)
SELECT root_cause,
       ROUND(100 * COALESCE(MAX(share) FILTER (WHERE bank = 'Regions'), 0), 1)             AS regions_pct,
       ROUND(100 * COALESCE(SUM(share) FILTER (WHERE peer_role = 'Peer'), 0) / 5, 1)       AS peer_avg_pct,
       ROUND(100 * (COALESCE(MAX(share) FILTER (WHERE bank = 'Regions'), 0)
                    - COALESCE(SUM(share) FILTER (WHERE peer_role = 'Peer'), 0) / 5), 1)   AS gap_pts
FROM mix
GROUP BY root_cause
ORDER BY regions_pct DESC;

-- @query: q6d_repeat_contact_by_bank
-- "Contacted the company multiple times before complaining" is a proxy for
-- failed first-contact resolution. Compare banks, alongside relief rate.
SELECT c.bank_short_name                                          AS bank,
       COUNT(*)                                                   AS sampled_complaints,
       ROUND(100 * AVG(CAST(l.contacted_company_multiple_times AS INT)), 1) AS contacted_multiple_times_pct,
       ROUND(100 * AVG(CAST(l.mentions_financial_loss AS INT)), 1)          AS financial_loss_pct,
       ROUND(100 * AVG(f.relief_flag), 1)                         AS relief_pct
FROM read_csv('results/llm_classifications.csv') l
JOIN fact_complaints f USING (complaint_id)
JOIN dim_company c ON c.company_key = f.company_key
WHERE l.in_peer_sample
GROUP BY c.bank_short_name
ORDER BY contacted_multiple_times_pct DESC;
