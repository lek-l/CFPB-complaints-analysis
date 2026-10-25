"""Are Regions' differences from its peers statistically significant?

Tests (Regions vs the five peers pooled, unless noted):
  1. Relief rate (relief / closed complaints), Jan 2018 - Aug 2026
  2. Monetary relief rate, same window
  3. Overdraft share of complaints, 2025 and 2018-2025
  4. Relief rate, Regions vs each peer separately (Holm-corrected, since five
     comparisons raise the chance of a false positive)
  5. Complaints per $1B deposits, 2025: rate ratio with a 95% CI (Poisson)

Method: two-proportion z-test with Wilson 95% confidence intervals for each
group's rate. Complaints are an observational sample of consumers who chose to
file, so "significant" means the gap is very unlikely to be random noise in
these counts, not that it proves why the gap exists.
Usage:  python notebooks/08_significance_tests.py  -> results/q9_significance_tests.csv
"""
import math
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
con = duckdb.connect(str(ROOT / "data" / "complaints.duckdb"), read_only=True)


def norm_sf(z: float) -> float:
    """Two-sided p-value for a standard normal z."""
    return math.erfc(abs(z) / math.sqrt(2))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def two_prop(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    p1, p2, pooled = k1 / n1, k2 / n2, (k1 + k2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se
    return z, norm_sf(z)


def row(test, group_a, k1, n1, group_b, k2, n2):
    z, p = two_prop(k1, n1, k2, n2)
    lo1, hi1 = wilson(k1, n1)
    lo2, hi2 = wilson(k2, n2)
    return {"test": test, "group_a": group_a, "rate_a_pct": round(100 * k1 / n1, 2),
            "ci95_a": f"{100 * lo1:.1f}-{100 * hi1:.1f}", "n_a": n1,
            "group_b": group_b, "rate_b_pct": round(100 * k2 / n2, 2),
            "ci95_b": f"{100 * lo2:.1f}-{100 * hi2:.1f}", "n_b": n2,
            "diff_pts": round(100 * (k1 / n1 - k2 / n2), 2), "z": round(z, 2), "p_value": p}


counts = con.sql("""
    SELECT c.bank_short_name AS bank, c.peer_role, d.year,
           COUNT(*)                         AS complaints,
           SUM(f.closed_flag)               AS closed,
           SUM(COALESCE(f.relief_flag, 0))  AS relief,
           SUM(f.monetary_relief_flag)      AS monetary,
           COUNT(*) FILTER (WHERE i.issue = 'Problem caused by your funds being low') AS overdraft
    FROM fact_complaints f
    JOIN dim_company c ON c.company_key = f.company_key
    JOIN dim_date d    ON d.date_key = f.date_received_key
    JOIN dim_issue i   ON i.issue_key = f.issue_key
    WHERE f.in_analysis_window AND c.peer_role IS NOT NULL
    GROUP BY ALL
""").df()

reg = counts[counts.bank == "Regions"]
peers = counts[counts.peer_role == "Peer"]
results = []

# 1-2. Relief and monetary relief, whole window
results.append(row("Relief rate (closed complaints), 2018-Aug 2026", "Regions",
                   int(reg.relief.sum()), int(reg.closed.sum()),
                   "Peers pooled", int(peers.relief.sum()), int(peers.closed.sum())))
results.append(row("Monetary relief rate (closed complaints), 2018-Aug 2026", "Regions",
                   int(reg.monetary.sum()), int(reg.closed.sum()),
                   "Peers pooled", int(peers.monetary.sum()), int(peers.closed.sum())))

# 3. Overdraft share
for label, mask_r, mask_p in [("2025", reg.year == 2025, peers.year == 2025),
                              ("2018-2025", reg.year <= 2025, peers.year <= 2025)]:
    r, p = reg[mask_r], peers[mask_p]
    results.append(row(f"Overdraft share of complaints, {label}", "Regions",
                       int(r.overdraft.sum()), int(r.complaints.sum()),
                       "Peers pooled", int(p.overdraft.sum()), int(p.complaints.sum())))

# 4. Relief rate, Regions vs each peer, Holm correction across the 5 tests
pairwise = []
for bank, g in peers.groupby("bank"):
    pairwise.append(row("Relief rate vs each peer (Holm-adjusted p)", "Regions",
                        int(reg.relief.sum()), int(reg.closed.sum()),
                        bank, int(g.relief.sum()), int(g.closed.sum())))
pairwise.sort(key=lambda r: r["p_value"])
running = 0.0
for i, r in enumerate(pairwise):
    running = max(running, min(1.0, r["p_value"] * (len(pairwise) - i)))  # Holm step-down
    r["p_value"] = running
results += pairwise

out = pd.DataFrame(results)

# 5. Complaints per $1B deposits, 2025: Poisson rate ratio Regions / peers pooled
fin = pd.read_csv(ROOT / "data" / "reference" / "bank_financials.csv").query("year == 2025")
dep = fin.set_index("bank_short_name")["deposits_billions"]
k_r = int(reg[reg.year == 2025].complaints.sum())
k_p = int(peers[peers.year == 2025].complaints.sum())
d_r, d_p = dep["Regions"], dep.drop("Regions").sum()
ratio = (k_r / d_r) / (k_p / d_p)
se_log = math.sqrt(1 / k_r + 1 / k_p)
z = math.log(ratio) / se_log
rate_rows = pd.DataFrame([{
    "test": "Complaints per $1B deposits, 2025 (rate ratio)", "group_a": "Regions",
    "rate_a_pct": None, "ci95_a": None, "n_a": k_r, "group_b": "Peers pooled", "rate_b_pct": None,
    "ci95_b": None, "n_b": k_p, "diff_pts": None, "z": round(z, 2), "p_value": norm_sf(z),
    "rate_ratio": round(ratio, 3),
    "rate_ratio_ci95": f"{math.exp(math.log(ratio) - 1.96 * se_log):.3f}-{math.exp(math.log(ratio) + 1.96 * se_log):.3f}",
}])
out = pd.concat([out, rate_rows], ignore_index=True)
out["significant_at_0.05"] = out["p_value"] < 0.05
out["p_value"] = out["p_value"].map(lambda p: f"{p:.2e}" if p < 0.001 else f"{p:.3f}")
out.to_csv(ROOT / "results" / "q9_significance_tests.csv", index=False)

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 20)
print(out.drop(columns=["ci95_a", "ci95_b"]).to_string(index=False))
