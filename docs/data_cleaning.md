# Data Cleaning & Modeling Decisions

Snapshot: CFPB Consumer Complaint Database, downloaded 2026-09-22 (17,914,393 complaints, 2011-12-01 to 2026-09-22).
Pipeline: `data/download_data.py` → `sql/00_load_raw.sql` → `sql/01_clean.sql` → `sql/02_schema.sql` → `sql/03_validate.sql` (run all with `python run_pipeline.py`).

**Principle:** no rows are deleted. Every exclusion is a flag (`in_analysis_window`, `is_credit_bureau`, `is_state`), so any decision can be reversed or tested without reloading.

## Decision log

| # | Issue found in profiling | Decision | Why |
|---|---|---|---|
| D0 | CSV type sniffing can corrupt values (ZIP leading zeros, `XX` placeholders) | Load raw as all-VARCHAR, cast explicitly in `01_clean.sql` | Keeps raw data untouched; every type conversion is visible and reviewable |
| D1 | Dates are ISO strings; 0 unparseable | Strict `CAST(... AS DATE)` | A strict cast fails loudly if a future snapshot has bad dates, instead of silently producing NULLs |
| D2 | Some labels use curly apostrophes (’) | Normalize to straight `'` | Consistent filtering and matching |
| D3 | 7,050 complaints "sent to company" before they were received | Keep rows, set `days_to_company` NULL, flag `is_date_anomaly` | Can't tell which date is wrong; dropping them would bias volume counts |
| D4 | 2026 is partial; the CFPB overhauled product/response categories in April 2017 | Analysis window = Jan 2018 – Aug 2026 (16,586,389 complaints) | Full years with a consistent taxonomy; ends at the last complete month so MoM trends aren't distorted |
| D5 | 21 product values that are really ~12 products (renames and splits over time) | Map to a standard `product_group`; split legacy "Credit card or prepaid card" and "Consumer Loan" by sub-product | Lets year-over-year trends run across taxonomy changes; the original value is kept in `dim_product.product_original` |
| D6 | Missing sub-product (1.3%), sub-issue (5.2%), issue (6 rows) | Label as `Not specified` | Mostly products with no sub-categories, not lost data; NULL keys would also silently drop rows from joins (validation caught 6 such rows) |
| D7 | 8,120 raw company spellings, including case variants and branch suffixes ("HUNTINGTON NATIONAL BANK, THE - FIRSTMERIT BANK, N.A. BRANCH") | Group on upper-case, whitespace-collapsed name with `- … BRANCH` removed → 8,111 companies. Display name = most common raw spelling | Merges true duplicates without hand-maintained lists; conservative (only branch suffixes are stripped) to avoid merging distinct firms |
| D8 | Credit bureaus (TransUnion, Equifax, Experian) = 78% of all complaints; 91% of 2026 complaints are credit reporting | Keep, flag `is_credit_bureau`; bank-focused analysis excludes them | Otherwise every ranking just shows the three bureaus; the bureau surge is itself a finding, reported separately |
| D9 | 71 "state" values: 50 states + DC, PR, territories, military (AA/AE/AP), one spelled-out name, 0.4% missing | Map the spelled-out value to `UM`; classify all codes in `dim_geography`; missing → `NA` | Per-capita metrics only use the 50 states + DC (`is_state`) |
| D10 | Per-capita needs population | Census Vintage 2025 state estimates (`data/reference/state_population.csv`) | Official source; using 2025 population for all years is a documented simplification (state populations shift only a few % over the window) |
| D11 | ZIPs are masked (`770XX`) or withheld (`XXXXX`, 139K rows) | Keep the 3-digit prefix (`zip3`); else NULL | Only the prefix is reliable |
| D12 | "Closed without relief" was retired on 2017-04-21 (17,867 rows total); replaced by "Closed with explanation" | Consistent `relief_outcome`: **Relief** (monetary, non-monetary, legacy "with relief") / **No relief** (explanation, legacy "without relief", "Closed") / **Untimely response** / **In progress** | Makes the "closed without relief" question answerable across all years. Relief rate = Relief ÷ (Relief + No relief); in-progress (625K) and untimely complaints are excluded from the denominator |
| D13 | Timely response is 99.4% "Yes" | Store as 0/1 `timely_flag` | Little variation, so relief rate becomes the more discriminating outcome metric |
| D14 | Tags: 95.5% empty; one value combines both tags | Split into `is_servicemember`, `is_older_american` | "Older American, Servicemember" complaints count in both segments |

## Peer group (Regions benchmark)

Regions Financial plus five similar-size super-regional banks: Fifth Third, Huntington, KeyCorp, M&T, Citizens. Truist was excluded because it is roughly 3x Regions' size. Because complaint volume scales with customer base, the benchmark compares **rates and mix** (timely %, relief %, top issues, product share) rather than raw counts.

## Star schema

| Table | Grain | Rows |
|---|---|---|
| `fact_complaints` | one complaint | 17,914,393 |
| `dim_company` | one cleaned company (bureau flag, peer role) | 8,111 |
| `dim_product` | product group × original product × sub-product | 127 |
| `dim_issue` | issue × sub-issue | 441 |
| `dim_geography` | state / territory code (population, region, `is_state`) | 64 |
| `dim_date` | one calendar day, 2011-12-01 to 2026-12-31 | 5,510 |

Outcome flags are stored as 0/1 integers so a rate is just an average (`AVG` in SQL, `AVERAGE` in DAX).

## Automated tests (`sql/03_validate.sql`)

Fact row count equals raw row count · unique complaint IDs · no orphan dates or states · 51 states with population · every product and response mapped · exactly 6 peer banks and 3 bureaus · `relief_flag` only on closed complaints. `run_pipeline.py` fails if any test fails.
