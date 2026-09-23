"""Deeper data-quality checks on raw_complaints that drive the cleaning decisions."""
import duckdb

con = duckdb.connect("data/complaints.duckdb", read_only=True)


def q(sql: str) -> None:
    print(con.sql(sql).df().to_string(index=False), "\n")


q("SELECT LEFT(date_received,4) yr, COUNT(*) n, ROUND(100.0*COUNT(*) FILTER (WHERE product ILIKE 'credit report%')/COUNT(*),1) pct_credit_reporting FROM raw_complaints GROUP BY 1 ORDER BY 1")
q("SELECT product, COUNT(*) n FROM raw_complaints GROUP BY 1 ORDER BY 2 DESC")
q("SELECT company, COUNT(*) n FROM raw_complaints GROUP BY 1 ORDER BY 2 DESC LIMIT 12")
q(r"""SELECT company, COUNT(*) n FROM raw_complaints
     WHERE regexp_matches(company, '(?i)regions|truist|fifth third|huntington|keycorp|keybank|m&t|citizens financial|pnc|u\.s\. bancorp|synovus|first horizon')
     GROUP BY 1 ORDER BY 2 DESC""")
q("SELECT company_response_to_consumer, COUNT(*) n FROM raw_complaints GROUP BY 1 ORDER BY 2 DESC")
q("SELECT timely_response, COUNT(*) n FROM raw_complaints GROUP BY 1 ORDER BY 2 DESC")
q("SELECT submitted_via, COUNT(*) n FROM raw_complaints GROUP BY 1 ORDER BY 2 DESC")
q("SELECT tags, COUNT(*) n FROM raw_complaints GROUP BY 1 ORDER BY 2 DESC")
q("SELECT state, COUNT(*) n FROM raw_complaints GROUP BY 1 ORDER BY 2 ASC LIMIT 25")
q("SELECT zip_code, COUNT(*) n FROM raw_complaints WHERE NOT regexp_full_match(COALESCE(zip_code,''), '[0-9]{5}') GROUP BY 1 ORDER BY 2 DESC LIMIT 8")
q("""SELECT COUNT(*) - COUNT(DISTINCT complaint_id) AS dup_ids,
            COUNT(*) FILTER (WHERE TRY_CAST(date_received AS DATE) IS NULL) AS bad_dates,
            COUNT(*) FILTER (WHERE TRY_CAST(date_sent_to_company AS DATE) < TRY_CAST(date_received AS DATE)) AS sent_before_received
     FROM raw_complaints""")
