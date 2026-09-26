"""Render the static charts used in the README (images/*.png) from results/*.csv.

Colors follow dashboard/theme.json: one blue for the focus series, gray for
context, light gridlines, and the title states the takeaway.
Usage:  python notebooks/07_readme_charts.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES, IMG = ROOT / "results", ROOT / "images"
BLUE, LIGHT_BLUE, GRAY = "#2a78d6", "#86b6ef", "#898781"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#fcfcfb"

plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
})


def finish(fig, ax, title: str, subtitle: str, name: str) -> None:
    ax.set_title(title, loc="left", fontsize=13, fontweight="semibold", pad=24)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9.5, color=INK2)
    fig.text(0.01, 0.01, "Source: CFPB Consumer Complaint Database, snapshot 2026-09-22", fontsize=8, color=GRAY)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(IMG / name, dpi=160)
    plt.close(fig)
    print(f"images/{name}")


IMG.mkdir(exist_ok=True)

# 1. Monthly trend, excluding the credit bureaus
m = pd.read_csv(RES / "q5_monthly_trends.csv", parse_dates=["month"])
fig, ax = plt.subplots(figsize=(9, 4.2))
ax.plot(m["month"], m["complaints_excl_bureaus"] / 1000, color=LIGHT_BLUE, lw=1.5, label="Monthly complaints")
ax.plot(m["month"], m["rolling_12m_excl_bureaus"] / 1000, color=BLUE, lw=2.5, label="12-month average")
spike = m.loc[m["complaints_excl_bureaus"].idxmax()]
ax.annotate(f"Jan 2025: {spike.complaints_excl_bureaus / 1000:.0f}K\n(Cash App, Zelle surge)",
            (spike.month, spike.complaints_excl_bureaus / 1000), xytext=(-150, -10),
            textcoords="offset points", fontsize=9, color=INK2, arrowprops={"arrowstyle": "-", "color": GRAY})
last = m.iloc[-1]
ax.text(last.month, last.rolling_12m_excl_bureaus / 1000 + 6, f"{last.rolling_12m_excl_bureaus / 1000:.0f}K",
        color=BLUE, fontsize=9, ha="right", fontweight="semibold")
ax.set_ylabel("Complaints (thousands)")
ax.set_ylim(0, None)
ax.legend(frameon=False, loc="upper left")
finish(fig, ax, "Complaints about banks and lenders more than doubled since mid-2024",
       "Monthly complaints excluding the three credit bureaus, Jan 2018 - Aug 2026", "trend_monthly.png")

# 2. Relief rate: Regions vs peers (focus + context)
s = pd.read_csv(RES / "q4a_scorecard.csv").sort_values("relief_pct")
fig, ax = plt.subplots(figsize=(8, 3.6))
colors = [BLUE if b == "Regions" else "#c3c2b7" for b in s["bank"]]
ax.barh(s["bank"], s["relief_pct"], color=colors, height=0.6)
peer_avg = s["peer_avg_relief_pct"].iloc[0]  # exact average from SQL, not a mean of rounded values
ax.axvline(peer_avg, color=INK2, lw=1, ls="--")
ax.set_ylim(-1.2, len(s) - 0.5)  # room under the bars for the average label
ax.text(peer_avg + 0.4, -0.95, f"Peer average {peer_avg:.1f}%", fontsize=9, color=INK2)
for y, v in enumerate(s["relief_pct"]):
    ax.text(v + 0.4, y, f"{v:.1f}%", va="center", fontsize=9, color=INK)
ax.set_xlabel("Closed complaints resolved with relief (%)")
ax.grid(axis="y", visible=False)
finish(fig, ax, "Regions ranks #2 of 6 peer banks on relief rate",
       "Share of closed complaints resolved with monetary or non-monetary relief, Jan 2018 - Aug 2026",
       "peer_relief_rate.png")

# 3. Overdraft share: Regions vs peers by year
o = pd.read_csv(RES / "q4e_overdraft_trend.csv")
o = o[o["year"] <= 2025]
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.plot(o["year"], o["regions_pct"], color=BLUE, lw=2.5, marker="o", ms=5)
ax.plot(o["year"], o["peers_pct"], color=GRAY, lw=2, marker="o", ms=5)
end = o.iloc[-1]
ax.text(end.year + 0.15, end.regions_pct, f"Regions {end.regions_pct:.1f}%", va="center", color=BLUE, fontweight="semibold")
ax.text(end.year + 0.15, end.peers_pct, f"Peers {end.peers_pct:.1f}%", va="center", color=INK2)
ax.axvline(2022.7, color=GRID, lw=1)
ax.text(2022.75, ax.get_ylim()[1] * 0.95, "CFPB $191M\noverdraft order\n(Sep 2022)", fontsize=8.5, color=INK2, va="top")
ax.set_xlim(2017.7, 2026.2)
ax.set_xticks(range(2018, 2026))
ax.set_ylim(0, None)
ax.set_ylabel("Share of the bank's complaints (%)")
finish(fig, ax, "Overdraft complaints at Regions are 2.5x the peer rate and rising again",
       "'Problem caused by your funds being low' as a share of each bank's complaints, by year", "overdraft_share.png")
