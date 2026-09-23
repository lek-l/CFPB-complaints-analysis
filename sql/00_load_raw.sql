-- 00_load_raw.sql
-- Loads the CFPB CSV into a raw staging table, exactly as published.
-- Every column is read as VARCHAR on purpose: type conversion happens in the
-- cleaning step (01_clean.sql), where each decision is explicit and documented,
-- instead of letting the CSV sniffer guess (e.g. ZIP codes like "07030" would
-- otherwise lose their leading zero, and "XX" placeholders would break parsing).
--
-- Run from the project root:  duckdb data/complaints.duckdb < sql/00_load_raw.sql

CREATE OR REPLACE TABLE raw_complaints AS
SELECT *
FROM read_csv(
    'data/raw/complaints.csv',
    header         = true,
    all_varchar    = true,   -- no type guessing
    normalize_names = true,  -- "Date received" -> date_received, etc.
    quote          = '"',
    escape         = '"'     -- narratives contain embedded quotes and newlines
);

-- Sanity checks
SELECT COUNT(*) AS row_count FROM raw_complaints;
DESCRIBE raw_complaints;
