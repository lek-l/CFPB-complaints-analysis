"""Download the CFPB Consumer Complaint Database and unzip it to data/raw/.

Source: https://www.consumerfinance.gov/data-research/consumer-complaints/
The CFPB republishes the full file daily; we record the download date so the
analysis is reproducible against a known snapshot.

Usage:  python data/download_data.py
"""
from datetime import date
from pathlib import Path
import zipfile

import requests
from tqdm import tqdm

URL = "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"
RAW_DIR = Path(__file__).resolve().parent / "raw"
ZIP_PATH = RAW_DIR / "complaints.csv.zip"
CSV_PATH = RAW_DIR / "complaints.csv"


def download() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with requests.get(URL, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        with open(ZIP_PATH, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc="Downloading") as bar:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                bar.update(len(chunk))


def unzip() -> None:
    with zipfile.ZipFile(ZIP_PATH) as z:
        z.extractall(RAW_DIR)
    ZIP_PATH.unlink()  # keep only the CSV


if __name__ == "__main__":
    if CSV_PATH.exists():
        print(f"{CSV_PATH} already exists; delete it to re-download.")
    else:
        download()
        unzip()
        (RAW_DIR / "SNAPSHOT_DATE.txt").write_text(date.today().isoformat())
        print(f"Done: {CSV_PATH} ({CSV_PATH.stat().st_size / 1e9:.2f} GB)")
