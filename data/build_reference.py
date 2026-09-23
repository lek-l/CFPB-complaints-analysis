"""Build data/reference/state_population.csv from Census Bureau population estimates.

Source: U.S. Census Bureau, Vintage 2025 state population estimates (NST-EST2025-ALLDATA)
https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/

The output is small, so it is committed to the repo; rerun this only to refresh it.
Usage:  python data/build_reference.py
"""
from pathlib import Path

import pandas as pd

URL = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/state/totals/NST-EST2025-ALLDATA.csv"
OUT = Path(__file__).resolve().parent / "reference" / "state_population.csv"

FIPS_TO_CODE = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
    "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
    "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
    "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY", "72": "PR",
}
REGION_NAMES = {"1": "Northeast", "2": "Midwest", "3": "South", "4": "West", "X": "Territory"}

if __name__ == "__main__":
    df = pd.read_csv(URL, dtype=str)
    df = df[df["SUMLEV"] == "040"]  # 040 = state-level rows (includes DC and Puerto Rico)
    out = pd.DataFrame({
        "state_code": df["STATE"].map(FIPS_TO_CODE),
        "state_name": df["NAME"],
        "census_region": df["REGION"].map(REGION_NAMES),
        "population_2025": df["POPESTIMATE2025"].astype(int),
    }).sort_values("state_code")
    assert out["state_code"].notna().all() and len(out) == 52, "expected 50 states + DC + PR"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"Wrote {len(out)} rows to {OUT}")
