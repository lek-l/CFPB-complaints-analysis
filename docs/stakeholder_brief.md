# Consumer Complaint Benchmark: Regions Bank vs. Peers

**To:** Consumer Banking & Customer Experience leadership · **From:** Lekha · **Data:** CFPB Consumer Complaint Database, Jan 2018 – Aug 2026 (snapshot 2026-09-22)
**Peers:** Fifth Third, Huntington, KeyCorp, M&T, Citizens (similar-size regional banks)

## Summary

Regions resolves complaints well: it ranks #2 of 6 on relief and answers on time 99.96% of the time. The opportunity is in **why customers complain**, above all overdraft. Overdraft complaints are 2.5x the peer rate and have risen for two years in a row.

## Key findings

**1. Overdraft complaints are 2.5x the peer rate, and rising again.**
"Problem caused by your funds being low" (overdraft/NSF) was **10.1% of Regions' complaints in 2025 vs. 4.0% for peers**, up from 5.5% in 2023. Adjusted for bank size, the gap widens to **2.7x (0.85 vs. 0.32 overdraft complaints per $1B of deposits)**, and it is statistically significant (p < 0.001). It is Regions' #2 complaint issue (8.0% since 2018) and isn't in any peer's top 3. The rise follows the CFPB's $191M surprise-overdraft order against Regions in September 2022.

**2. Complaint handling is a strength; complaint volume is concentrated in checking accounts.**
Regions resolves **25.1% of closed complaints with relief vs. a 21.1% peer average (#2 of 6)**, and per $1B of deposits its overall complaint volume is in line with peers. But **55.3% of Regions' complaints concern checking/savings accounts vs. 47.8% for peers**, and "Managing an account" alone is 32.7% of Regions' complaints.

**3. Industry-wide complaint volume is surging, and regulatory news drives spikes.**
Excluding the credit bureaus, the 12-month average of complaints industry-wide **more than doubled from 30K to 71K per month** between Jul 2024 and Aug 2026. In January 2025 volume doubled in a single month. Four companies drove 76% of that jump, and it peaked the day after the CFPB's $175M order against Cash App. Complaint volume can move sharply with news, not only with service quality.

## Recommendations

1. **Run an overdraft deep-dive with a peer-parity target.** Review the overdraft complaints by root cause (fee disclosure, transaction ordering, posting timing) to find the specific practice driving them. Target: bring the overdraft share from 10.1% toward the 4.0% peer level, tracked quarterly.
2. **Prioritize the checking-account experience.** "Managing an account" is a catch-all category. Analyze the complaint narratives (for example with text classification) to split it into specific causes such as frozen funds, closures and fees, then assign owners to the top two.
3. **Adopt early-warning monitoring.** This project includes a working rule: flag a company-month at 3x its 12-month norm and 3+ standard deviations above it. Back-tested, it raised 38 alerts in 80 months (about one every two months) and caught all four companies behind the January 2025 industry surge. Pair it with response playbooks for regulatory announcements affecting Regions or its peers.

*Method and caveats: complaints are unverified consumer submissions; comparisons use rates and mix rather than raw counts because the banks differ in size. Full analysis and SQL: see the project README.*
