"""Download the CFPB complaint narratives archive to data/raw/narratives/.

The CFPB stopped publishing narratives in the live database on 2026-08-14 and
moved every previously published narrative to its FOIA Reading Room:
https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/

The archive is split into 21 exports; we take the 20 covering May 2018 onward
(the analysis window starts Jan 2018; the Dec 2011 - Apr 2018 export is skipped
to save ~1 GB, so Jan-Apr 2018 narratives are not in the sample frame).
Each export is the full complaint record plus the narrative column, joined to
our star schema on complaint_id.

Usage:  python data/download_narratives.py   (~1.2 GB zipped, skips files already present)
"""
from pathlib import Path
import zipfile

import requests

BASE = "https://files.consumerfinance.gov/f/documents/"
EXPORTS = [
    "2_May_2018_through_April_2021", "3_May_2021_through_October_2022",
    "4_November_2022_through_August_2023", "5_September_2023_through_March_2024",
    "6_April_2024_through_July_2024", "7_August_2024_through_October_2024",
    "8_November_2024_through_December_2024", "9_January_2025_through_February_2025",
    "10_March_2025_through_April_2025", "11_May_2025_through_June_2025",
    "12_July_2025_through_August_2025", "13_September_2025_through_October_2025",
    "14_November_2025_through_December_2025", "15_January_2026_through_February_2026",
    "16_March_2026", "17_April_2026", "18_May_2026", "19_June_2026", "20_July_2026",
    "21_August_2026",
]
OUT = Path(__file__).resolve().parent / "raw" / "narratives"

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(EXPORTS, 1):
        csv_path = OUT / f"CCDB_Export_{name}.csv"
        if csv_path.exists():
            print(f"[{i:2}/{len(EXPORTS)}] {csv_path.name} already present")
            continue
        zip_path = OUT / f"CCDB_Export_{name}.zip"
        with requests.get(f"{BASE}CCDB_Export_{name}.zip", stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(OUT)
        zip_path.unlink()
        print(f"[{i:2}/{len(EXPORTS)}] {csv_path.name} ({csv_path.stat().st_size / 1e9:.2f} GB)", flush=True)
