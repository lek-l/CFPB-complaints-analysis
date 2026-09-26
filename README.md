# Consumer Financial Complaints Analysis

An end-to-end analytics project on the **CFPB Consumer Complaint Database**: 17.9M complaints about U.S. banks and financial companies, taken from raw download to a tested star-schema database, SQL analysis, an interactive Power BI dashboard, and LLM classification of complaint narratives. It includes a peer benchmark of **Regions Bank** against five similar regional banks.

**Stack:** Python (pandas) · SQL (DuckDB) · Power BI + DAX · LLM API (Claude or Llama via Groq) · Parquet · Git

> **Status:** the data pipeline, SQL analysis, dashboard data model and LLM pipeline are complete. The dashboard pages and the LLM classification run are in progress.

---

## Business questions

1. Which products and sub-products get the most complaints, and how is that trending year over year?
2. Which companies have the worst timely-response rates and the most complaints closed without relief?
3. How are complaints distributed geographically, by state and per capita?
4. How does Regions Bank compare with similar regional banks on volume, top issues and response performance?
5. What are the month-over-month trends, with rolling averages?
6. *(LLM)* What root causes do consumers describe in their own words, and which get resolved?

## Key findings

Analysis window: Jan 2018 – Aug 2026, 16,586,389 complaints. Details and the query behind every number: [docs/analysis_findings.md](docs/analysis_findings.md).

**1. Overdraft complaints at Regions are 2.5x the peer rate and rising again**: 10.1% of Regions' 2025 complaints vs. 4.0% for peers, up from 5.5% in 2023, despite the CFPB's $191M overdraft order in 2022.

![Overdraft share, Regions vs peers](images/overdraft_share.png)

**2. Regions handles complaints well**: it ranks #2 of 6 on relief rate (25.1% vs. a 21.1% peer average) and responds on time to 99.96% of complaints.

![Relief rate by bank](images/peer_relief_rate.png)

**3. Complaints about banks and lenders more than doubled since mid-2024**: excluding the three credit bureaus, the 12-month average rose from 30K to 71K complaints per month. A one-month spike in Jan 2025 peaked the day after the CFPB's $175M order against Cash App.

![Monthly complaint trend](images/trend_monthly.png)

**Also:**
- Credit reporting is **84.8%** of all complaints and grew **43x** from 2018 to 2025. The three credit bureaus alone account for **81.2%** of complaints, so bank-focused views exclude them.
- Relief is rare: among 295 non-bureau companies with 1,000+ closed complaints, the **median company gives relief on 1.0%**, and **71 gave none**.
- The **South has the most complaints per resident** (2,358 per 100K in 2025), and **Georgia ranks #1**.

Stakeholder summary with recommendations: [docs/stakeholder_brief.md](docs/stakeholder_brief.md)

## Dashboard

Four interactive Power BI pages (Executive Overview, Product & Issue Trends, Company Benchmarking, Geographic View) with synced filters for date range, company type, company, product and state. File: [dashboard/cfpb_complaints.pbix](dashboard/cfpb_complaints.pbix); build guide: [dashboard/POWERBI_GUIDE.md](dashboard/POWERBI_GUIDE.md).

<!-- Add page screenshots here once the pages are built: images/dashboard_overview.png, etc. -->

**29 DAX measures** ([dashboard/measures.dax](dashboard/measures.dax)) cover timely-response %, relief rate, YoY and MoM change, 3- and 12-month rolling averages, annualized complaints per 100K residents, and peer-average benchmarks. The build guide checks the measures against the SQL results page by page.

## LLM root-cause analysis

The CFPB stopped publishing complaint narratives on 2026-08-14 and moved them to a FOIA archive. This project downloads that archive (3.56M narratives), draws a stratified sample of **10,162** (6,000 market-wide plus 700 per peer bank), and classifies each into one of **10 root causes** using structured LLM output. A **blind human review** of 200 complaints (accuracy, Cohen's kappa) and an automatic consistency check against the CFPB's own issue field validate the labels. Method: [docs/llm_methodology.md](docs/llm_methodology.md).

<!-- Add root-cause findings and validation metrics here after the classification run. -->

## How it works

```
CFPB CSV (5.4 GB) ─► DuckDB raw table ─► typed & cleaned staging ─► star schema ─► 10 data-quality tests
                                                                         │
                          ┌──────────────────────────────────────────────┼────────────────────────┐
                          ▼                                              ▼                        ▼
               SQL analysis (18 queries)               Parquet export (2.4M-row monthly     LLM classification
               → results/*.csv                         aggregate) → Power BI dashboard      of narrative sample
```

**Star schema:** `fact_complaints` (one row per complaint) joined to `dim_company`, `dim_product`, `dim_issue`, `dim_geography` (with Census 2025 population) and `dim_date`.

**Main design decisions** (full log: [docs/data_cleaning.md](docs/data_cleaning.md)):
- **DuckDB**: a columnar engine suited to large scans and aggregations. It installs with `pip`, and the SQL carries over to Postgres or Snowflake.
- **Raw data loaded as text**, then converted to proper types in a documented cleaning step, so nothing gets silently corrupted (e.g. ZIP codes losing leading zeros).
- **Flags instead of deletions**: bureaus, the analysis window and territories are flagged, so every choice is reversible.
- **A consistent relief outcome** across the CFPB's 2017 change to response categories, which made "closed without relief" answerable across all years.
- **Rates, mix and growth indexes** for the peer benchmark, since banks differ in size.
- **Validation tests** run before every export; one caught a join that was silently dropping records.

## Reproduce it

Requires Python 3.10+ and about 20 GB of free disk space.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

python data/download_data.py      # complaints CSV (330 MB zipped)
python data/build_reference.py    # Census population (already committed)
python run_pipeline.py            # load, clean, model, test, export for Power BI
python notebooks/03_run_analysis.py   # all SQL analysis -> results/
python notebooks/07_readme_charts.py  # README charts -> images/

# LLM text analysis (optional; needs ANTHROPIC_API_KEY or GROQ_API_KEY)
python data/download_narratives.py
python notebooks/04_build_narrative_sample.py
python notebooks/05_classify_narratives.py --provider claude --dry-run
python notebooks/05_classify_narratives.py --provider claude
python notebooks/06_validate_classifications.py make-review
```

Then open `dashboard/cfpb_complaints.pbix` in Power BI Desktop and refresh.

## Repository structure

```
data/         download scripts, Census reference data (raw data is gitignored)
sql/          00-04 pipeline (load, clean, schema, tests, export); analysis/ business-question queries
notebooks/    profiling, analysis runner, LLM sample / classification / validation, chart rendering
llm/          provider-neutral taxonomy and prompt; Claude and Groq backends
dashboard/    Power BI report, DAX measures, theme, build guide
results/      CSV output of every analysis query
docs/         cleaning decisions, findings, LLM method, stakeholder brief
images/       charts and dashboard screenshots
```

## Data notes

- Source: [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/), snapshot downloaded 2026-09-22; narratives from the CFPB's FOIA Reading Room archive.
- Complaints are **unverified consumer submissions**. They show where customers report problems, not confirmed misconduct.
- Complaint volume partly reflects a company's customer base, so cross-company comparisons use rates and mix.
