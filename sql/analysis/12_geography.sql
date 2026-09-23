-- 12_geography.sql
-- Business question 3: How are complaints distributed geographically, by
-- state and per capita?
--
-- Per-capita uses calendar-year 2025 complaints against the Census 2025
-- population estimate, so numerator and denominator cover the same year.
-- Only the 50 states + DC (is_state) are ranked.

-- @query: q3a_state_per_capita_2025
WITH state_counts AS (
    SELECT g.state_code, g.state_name, g.census_region, g.population_2025,
           COUNT(*)                                       AS complaints,
           COUNT(*) FILTER (WHERE NOT c.is_credit_bureau) AS complaints_excl_bureaus
    FROM fact_complaints f
    JOIN dim_geography g USING (state_code)
    JOIN dim_company c   ON c.company_key = f.company_key
    JOIN dim_date d      ON d.date_key = f.date_received_key
    WHERE d.year = 2025 AND g.is_state
    GROUP BY ALL
)
SELECT state_code,
       state_name,
       census_region,
       population_2025,
       complaints,
       ROUND(100000.0 * complaints / population_2025, 0)                           AS per_100k,
       RANK() OVER (ORDER BY complaints / population_2025 DESC)                    AS rank_per_capita,
       complaints_excl_bureaus,
       ROUND(100000.0 * complaints_excl_bureaus / population_2025, 0)              AS per_100k_excl_bureaus,
       RANK() OVER (ORDER BY complaints_excl_bureaus / population_2025 DESC)       AS rank_per_capita_excl_bureaus,
       RANK() OVER (ORDER BY complaints DESC)                                      AS rank_volume
FROM state_counts
ORDER BY rank_per_capita;

-- @query: q3b_region_per_capita_2025
-- Census region rollup: complaints per 100K residents, 2025.
WITH region_counts AS (
    SELECT g.census_region,
           COUNT(*)                                       AS complaints,
           COUNT(*) FILTER (WHERE NOT c.is_credit_bureau) AS complaints_excl_bureaus
    FROM fact_complaints f
    JOIN dim_geography g USING (state_code)
    JOIN dim_company c   ON c.company_key = f.company_key
    JOIN dim_date d      ON d.date_key = f.date_received_key
    WHERE d.year = 2025 AND g.is_state
    GROUP BY g.census_region
),
region_pop AS (
    SELECT census_region, SUM(population_2025) AS population
    FROM dim_geography
    WHERE is_state
    GROUP BY census_region
)
SELECT census_region,
       population,
       complaints,
       ROUND(100000.0 * complaints / population, 0)              AS per_100k,
       ROUND(100000.0 * complaints_excl_bureaus / population, 0) AS per_100k_excl_bureaus
FROM region_counts
JOIN region_pop USING (census_region)
ORDER BY per_100k DESC;

-- @query: q3c_state_concentration
-- How concentrated is volume? Cumulative share of 2025 complaints, top 10 states.
WITH state_counts AS (
    SELECT g.state_code, COUNT(*) AS complaints
    FROM fact_complaints f
    JOIN dim_geography g USING (state_code)
    JOIN dim_date d ON d.date_key = f.date_received_key
    WHERE d.year = 2025 AND g.is_state
    GROUP BY g.state_code
)
SELECT state_code,
       complaints,
       ROUND(100.0 * SUM(complaints) OVER (ORDER BY complaints DESC ROWS UNBOUNDED PRECEDING)
             / SUM(complaints) OVER (), 1)               AS cumulative_pct,
       ROW_NUMBER() OVER (ORDER BY complaints DESC)      AS state_rank
FROM state_counts
QUALIFY state_rank <= 10
ORDER BY state_rank;
