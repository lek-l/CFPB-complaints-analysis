"""Classify the narrative sample into root causes with an LLM.

    python notebooks/05_classify_narratives.py --provider claude --dry-run   # cost estimate, no API calls
    python notebooks/05_classify_narratives.py --provider claude --limit 50  # small pilot first
    python notebooks/05_classify_narratives.py --provider claude             # full sample
    python notebooks/05_classify_narratives.py --provider groq

Results append to data/llm/classifications_<provider>.jsonl, one line per
complaint. Rerunning skips complaints already classified successfully, so an
interrupted run (or one with a few errors) resumes instead of paying twice.
After the run, the labels (no narrative text) are exported to
results/llm_classifications.csv for analysis and the dashboard.
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from llm.taxonomy import SYSTEM_PROMPT, user_message  # noqa: E402

SAMPLE = ROOT / "data" / "llm" / "sample.parquet"

# Batch prices per 1M tokens (input, output). Claude Batches are 50% of list price.
PRICES = {
    "claude-opus-5": (2.50, 12.50),
    "claude-haiku-4-5": (0.50, 2.50),
}


def load_done(path: Path) -> set[int]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if "error" not in rec:
            done.add(rec["complaint_id"])
    return done


def export(path: Path) -> None:
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    df = pd.DataFrame(recs)
    # Keep the latest successful record per complaint (a retry may follow an error)
    ok = df[df.get("error").isna()] if "error" in df else df
    ok = ok.drop_duplicates("complaint_id", keep="last")
    sample = pd.read_parquet(SAMPLE, columns=["complaint_id", "in_market_sample", "in_peer_sample", "truncated"])
    out = sample.merge(ok.drop(columns=[c for c in ("error",) if c in ok]), on="complaint_id", how="inner")
    out.to_csv(ROOT / "results" / "llm_classifications.csv", index=False)
    errors = df["error"].notna().sum() if "error" in df else 0
    print(f"Exported {len(out):,} classifications to results/llm_classifications.csv "
          f"({errors} error rows in the log)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["claude", "groq"], required=True)
    ap.add_argument("--limit", type=int, help="classify at most N (pilot runs)")
    ap.add_argument("--dry-run", action="store_true", help="estimate cost and show one prompt; no API calls")
    args = ap.parse_args()

    log = ROOT / "data" / "llm" / f"classifications_{args.provider}.jsonl"
    sample = pd.read_parquet(SAMPLE)
    todo = sample[~sample["complaint_id"].isin(load_done(log))]
    if args.limit:
        todo = todo.head(args.limit)
    rows = todo[["complaint_id", "narrative", "product"]].to_dict("records")

    if args.dry_run:
        in_tok = sum(len(SYSTEM_PROMPT) + len(user_message(r["narrative"], r["product"])) for r in rows) / 4
        out_tok = len(rows) * 250  # JSON answer plus a little thinking, estimated
        print(f"{len(rows):,} complaints to classify, ~{in_tok / 1e6:.1f}M input tokens, ~{out_tok / 1e6:.1f}M output tokens")
        for model, (pin, pout) in PRICES.items():
            print(f"  {model:<18} ~${in_tok / 1e6 * pin + out_tok / 1e6 * pout:,.0f} (Batch API)")
        print("  Groq: check console.groq.com for pricing and your plan's daily token limit before a full run.")
        if rows:
            print("\n--- Example user message ---\n" + user_message(rows[0]["narrative"], rows[0]["product"])[:1200])
        return

    if args.provider == "claude":
        from llm.claude_backend import classify
    else:
        from llm.groq_backend import classify

    with open(log, "a", encoding="utf-8") as f:
        for i, rec in enumerate(classify(rows), 1):
            f.write(json.dumps(rec) + "\n")
            f.flush()
            if i % 250 == 0:
                print(f"  {i:,} / {len(rows):,} written", flush=True)
    export(log)


if __name__ == "__main__":
    main()
