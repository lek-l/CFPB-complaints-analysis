"""Build data/reference/bank_financials.csv: year-end deposits and assets for the peer banks.

Source: FDIC BankFind Suite API (https://api.fdic.gov/banks/), quarterly Call
Report data. We take each bank's Dec 31 report for 2018-2025.

Why: complaint volume grows with a bank's customer base, so raw counts can't be
compared across banks of different sizes. Dividing by deposits ("complaints per
$1B of deposits") is a standard size normalization in bank analysis.

Caveat: CFPB complaints are filed against the holding company (e.g. "REGIONS
FINANCIAL CORPORATION") while FDIC data is for the bank subsidiary. For these
six companies the bank holds nearly all deposits, so the match is close.
Usage:  python data/build_bank_financials.py
"""
from pathlib import Path

import pandas as pd
import requests

API = "https://api.fdic.gov/banks/financials"
OUT = Path(__file__).resolve().parent / "reference" / "bank_financials.csv"

# FDIC certificate numbers, looked up via api.fdic.gov/banks/institutions (2026-10-24)
BANKS = {
    "Regions": 12368,       # Regions Bank
    "Fifth Third": 6672,    # Fifth Third Bank, National Association
    "Huntington": 6560,     # The Huntington National Bank
    "KeyCorp": 17534,       # KeyBank National Association
    "M&T": 588,             # Manufacturers and Traders Trust Company
    "Citizens": 57957,      # Citizens Bank, National Association
}
YEARS = range(2018, 2026)

if __name__ == "__main__":
    rows = []
    for bank, cert in BANKS.items():
        dates = " OR ".join(f"REPDTE:{y}1231" for y in YEARS)
        resp = requests.get(API, params={
            "filters": f"CERT:{cert} AND ({dates})",
            "fields": "CERT,REPDTE,DEP,ASSET",
            "limit": 50,
        }, timeout=60)
        resp.raise_for_status()
        for rec in resp.json()["data"]:
            d = rec["data"]
            rows.append({
                "bank_short_name": bank,
                "fdic_cert": cert,
                "year": int(str(d["REPDTE"])[:4]),
                # FDIC reports amounts in thousands of dollars
                "deposits_billions": round(d["DEP"] / 1e6, 2),
                "assets_billions": round(d["ASSET"] / 1e6, 2),
            })
    df = pd.DataFrame(rows).sort_values(["bank_short_name", "year"])
    missing = {(b, y) for b in BANKS for y in YEARS} - set(zip(df.bank_short_name, df.year))
    assert not missing, f"missing FDIC reports: {sorted(missing)}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(df.pivot(index="year", columns="bank_short_name", values="deposits_billions").to_string())
    print(f"Wrote {len(df)} rows to {OUT}")
