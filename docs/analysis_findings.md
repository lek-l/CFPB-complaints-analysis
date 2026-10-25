# SQL Analysis: Findings

Snapshot 2026-09-22 · Analysis window Jan 2018 – Aug 2026 (16,586,389 complaints).
Every number below comes from a CSV in `results/`, produced by `python notebooks/03_run_analysis.py` from the queries in `sql/analysis/`.

## Q1. Products and trends (`10_product_trends.sql`)

- **Credit reporting is 84.8% of all complaints** (14.06M of 16.59M). Credit-reporting volume grew **43x from 2018 to 2025** (111,596 → 4,810,301), and it is still up **47.2%** in Jan–Aug 2026 vs Jan–Aug 2025. *(q1a, q1c, q1d)*
- **Excluding the three credit bureaus**, the top products are debt collection (27.1%), credit reporting complaints about other companies (26.6%), checking/savings (12.2%) and credit cards (11.8%). *(q1a)*
- Consumer banking complaints are also rising fast, just less dramatically. From 2018 to 2025, checking/savings grew **4.0x** (21,207 → 84,195), credit cards **3.9x** (22,960 → 89,978) and debt collection **5.5x**. **Mortgage is the exception, roughly flat** (24,564 → 24,697). *(q1c)*
- Within debt collection, **44.4% of consumers answer "I do not know"** for the type of debt, which suggests many don't recognize the debt being collected. *(q1b)*

## Q2. Company response performance (`11_company_response.sql`)

- Timeliness hardly separates companies: 99.4% of all complaints get a timely response. The worst performers with 1,000+ complaints are Capital Accounts (52.4% timely) and student-loan servicer **MOHELA (64.2% on 28,867 complaints, 10,348 late)**. *(q2a)*
- Relief is the more telling measure. Among the 295 non-bureau companies with 1,000+ closed complaints, the **median company gives relief on only 1.0%** of complaints. **71 companies gave no relief at all**, and 179 gave relief on under 5%. *(q2c)*
- The largest company with zero relief is **Early Warning Services (the Zelle operator): 36,481 closed complaints, none with relief**. *(q2b)*
- The credit bureaus report 42.0% relief, but only **0.01% monetary**. Their "relief" is correcting a credit report. Non-bureau companies give monetary relief on 5.15% of closed complaints. *(q2d)*

## Q3. Geography (`12_geography.sql`, 2025 complaints vs Census 2025 population)

- **The South has the most complaints per resident: 2,358 per 100K**, against 978–1,340 in the other regions. That holds even without the bureaus (301 vs 168–191). *(q3b)*
- **Georgia ranks #1 per capita**: 3,777 per 100K overall and 531 without the bureaus. Mississippi, Florida and Louisiana follow. Vermont and South Dakota are lowest (~173). *(q3a)*
- Complaints are concentrated: **Florida and Texas alone account for 29.2%** of 2025 complaints, and the top 10 states for 69.3%. *(q3c)*

## Q4. Regions vs peers (`13_peer_benchmark.sql`)

Peers: Fifth Third, Huntington, KeyCorp, M&T, Citizens.

- **Response performance:** Regions is timely on 99.96% of complaints and gives relief on **25.1%, ranking #2 of 6**. The peer average is 21.1% (Regions is 4.1 points above it, computed on unrounded rates). Only Huntington is higher, at 31.6%. *(q4a)*
- **Product mix:** Regions over-indexes on **checking/savings (55.3% of its complaints vs 47.8% for peers)** and under-indexes on mortgage (8.4% vs 17.9%). *(q4b)*
- **Overdraft stands out.** "Problem caused by your funds being low" (overdraft/NSF fees) is Regions' **#2 issue at 8.0%**, and it isn't in any peer's top 3. In 2025 it was **10.1% of Regions' complaints vs 4.0% for peers**, up from 5.5% in 2023. This comes after the CFPB's $191M surprise-overdraft order against Regions in Sept 2022. *(q4c, q4e)*
- **Volume growth:** Regions' 2025 complaints are at 203% of their 2018 level (2018 = 100), in the middle of the peer range of 136–283. *(q4d)*

## Q5. Monthly trends (`14_monthly_trends.sql`)

- Monthly volume reached **659,049 in Aug 2026**, with a 12-month rolling average of 572,926. Excluding the bureaus, the 12-month rolling average **more than doubled** from 30,414 (Jul 2024) to 70,948 (Aug 2026). *(q5)*
- **January 2025 spike:** non-bureau complaints reached 123,553, about double the months around it. Four companies account for 76% of the increase: Block/Cash App (+30,953), Early Warning/Zelle (+16,767), Navy Federal (+7,429) and Capital One (+5,714). Non-bureau complaints peaked on Jan 17 (20,877 in one day), the day after the **CFPB's $175M Cash App order on Jan 16, 2025**. The timing suggests enforcement news can trigger complaint surges (a correlation in timing, not proof of cause). *(q5, q5b)*

## Q7. Early-warning alerts (`17_early_warning.sql`)

- **Rule:** flag a company-month when complaints are at least 3x the company's own 12-month average, at least 3 standard deviations above it (z-score ≥ 3), and at least 200 complaints. It covers non-bureau companies with 1,000+ complaints.
- **38 alerts in the 80 months from 2020 to Aug 2026, about one every two months**, a workload a monitoring team could actually follow up on. Without the 3x condition the same rule fires 270 times, because industry-wide growth makes dozens of companies look unusual at once. *(q7a, q7b)*
- **Back-test:** in January 2025 it flags all four companies behind the surge: Block/Cash App (109x its normal level), Early Warning/Zelle (60x), Navy Federal (13x) and Capital One (4.5x), plus CBC Companies. No peer bank triggered an alert. *(q7a)*

## Q8. Size-adjusted benchmark (`16_size_adjusted_benchmark.sql`, FDIC deposits)

- **Overall complaint burden is about average:** in 2025 Regions had **8.43 complaints per $1B of deposits vs. a 7.86 peer average** (1.07x, #4 of 6). Peers range from 5.23 (KeyCorp) to 10.83 (Citizens). *(q8b)*
- **Overdraft burden is not average:** **0.85 overdraft complaints per $1B of deposits vs. 0.32 for peers, 2.7x**. That's a larger gap than the share-based comparison in Q4. *(q8b)*
- Regions' overall burden rose from 5.68 per $1B (2018) to 8.43 (2025), with most of the increase after 2023. *(q8a)*

## Q9. Statistical significance (`notebooks/08_significance_tests.py`)

Two-proportion z-tests with Wilson 95% confidence intervals, Regions vs. the five peers pooled. *(q9)*

| Comparison | Regions | Peers | p-value | Significant? |
|---|---|---|---|---|
| Overdraft share of complaints, 2025 | 10.1% | 4.0% | 5 × 10⁻¹⁸ | Yes |
| Relief rate, Jan 2018 – Aug 2026 | 25.1% | 19.4% | 3 × 10⁻²⁸ | Yes |
| Monetary relief rate | 15.2% | 13.7% | 0.0007 | Yes |
| Relief rate vs. KeyCorp alone (Holm-adjusted) | 25.1% | 23.7% | 0.053 | **No** |
| Complaints per $1B deposits, 2025 (rate ratio 1.06, CI 0.99–1.13) | | | 0.074 | **No** |

- The **overdraft gap and the relief-rate lead are statistically robust**. Regions' lead over KeyCorp specifically is not, and its overall size-adjusted complaint burden is in line with peers.
- "Peers pooled" weights each peer by its complaint count (19.4% relief), while the 21.1% peer average elsewhere weights the five banks equally. Both point the same way.

## Caveats

- Complaints are unverified consumer submissions, and volume partly reflects customer-base size. That's why the peer benchmark uses rates and mix rather than raw counts.
- Per-capita figures use the 2025 population for 2025 complaints only.
- Size-adjusted rates divide holding-company complaints by bank-subsidiary deposits (FDIC); Citizens' 2018 deposits predate a 2019 charter consolidation.
- Significance tests treat complaints as independent observations; they show a gap is unlikely to be noise, not what causes it.
- "Servicer under contract with Federal Student Aid" is a CFPB placeholder rather than a real company, so it is excluded from the timeliness ranking.
