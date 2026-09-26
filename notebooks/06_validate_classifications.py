"""Validate the LLM root-cause labels.

    python notebooks/06_validate_classifications.py make-review   # 1. build a blind review sheet
    (open validation/review_blind.csv, fill human_root_cause for every row)
    python notebooks/06_validate_classifications.py score         # 2. compare human vs LLM labels
    python notebooks/06_validate_classifications.py consistency   # automatic check vs CFPB issue field

Design choices
- Blind review: the sheet shows only the narrative. The LLM's answers sit in a
  separate key file, so the human label is not anchored on the model's.
- Stratified by predicted label (at least 12 per label, rest random) so rare
  labels are checked too; overall accuracy is then re-weighted by how common
  each predicted label is in the full sample, so the headline number reflects
  the real label mix, not the review design.
- Cohen's kappa reports agreement beyond chance, the standard for comparing
  two annotators.
"""
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, cohen_kappa_score, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from llm.taxonomy import ROOT_CAUSES  # noqa: E402

VAL = ROOT / "validation"
N_REVIEW, MIN_PER_LABEL, SEED = 200, 12, 42


def load_classified() -> pd.DataFrame:
    labels = pd.read_csv(ROOT / "results" / "llm_classifications.csv")
    sample = pd.read_parquet(ROOT / "data" / "llm" / "sample.parquet",
                             columns=["complaint_id", "narrative", "product"])
    return labels.merge(sample, on="complaint_id")


def make_review() -> None:
    df = load_classified()
    parts = [g.sample(min(len(g), MIN_PER_LABEL), random_state=SEED) for _, g in df.groupby("root_cause")]
    picked = pd.concat(parts)
    rest = df.drop(picked.index).sample(max(0, N_REVIEW - len(picked)), random_state=SEED)
    review = pd.concat([picked, rest]).sample(frac=1, random_state=SEED).reset_index(drop=True)
    review["review_id"] = range(1, len(review) + 1)

    VAL.mkdir(exist_ok=True)
    blind = review[["review_id", "product", "narrative"]].assign(human_root_cause="", human_notes="")
    blind.to_csv(VAL / "review_blind.csv", index=False, encoding="utf-8-sig")  # BOM so Excel shows text correctly
    review[["review_id", "complaint_id", "root_cause", "confidence"]].to_csv(VAL / "review_key.csv", index=False)
    print(f"Wrote {len(blind)} rows to validation/review_blind.csv (do NOT open review_key.csv until you finish).")
    print("Allowed labels:", ", ".join(ROOT_CAUSES))


def score() -> None:
    blind = pd.read_csv(VAL / "review_blind.csv", encoding="utf-8-sig")
    key = pd.read_csv(VAL / "review_key.csv")
    df = blind.merge(key, on="review_id")
    df["human_root_cause"] = df["human_root_cause"].astype(str).str.strip()
    invalid = df[~df["human_root_cause"].isin(ROOT_CAUSES)]
    if len(invalid):
        sys.exit(f"{len(invalid)} rows have a blank or unknown human_root_cause, e.g. review_id "
                 f"{invalid['review_id'].head(5).tolist()}. Fix them and rerun.")

    y_true, y_pred = df["human_root_cause"], df["root_cause"]
    labels = list(ROOT_CAUSES)
    raw_acc = accuracy_score(y_true, y_pred)
    kappa = cohen_kappa_score(y_true, y_pred)

    # Re-weight: precision of each predicted label x that label's share of the full sample
    share = pd.read_csv(ROOT / "results" / "llm_classifications.csv")["root_cause"].value_counts(normalize=True)
    precision = df.assign(ok=y_true == y_pred).groupby("root_cause")["ok"].mean()
    weighted_acc = float((precision * share.reindex(precision.index).fillna(0)).sum()
                         / share.reindex(precision.index).fillna(0).sum())

    print(f"Reviewed: {len(df)}   Raw accuracy: {raw_acc:.1%}   Weighted accuracy: {weighted_acc:.1%}   "
          f"Cohen's kappa: {kappa:.2f}")
    print(classification_report(y_true, y_pred, labels=labels, zero_division=0))
    for conf in ("high", "medium", "low"):
        sub = df[df["confidence"] == conf]
        if len(sub):
            print(f"  accuracy when model confidence = {conf:<6}: {(sub.human_root_cause == sub.root_cause).mean():.1%} (n={len(sub)})")

    cm = pd.DataFrame(confusion_matrix(y_true, y_pred, labels=labels), index=labels, columns=labels)
    cm.to_csv(ROOT / "results" / "llm_validation_confusion.csv")
    pd.DataFrame([{"reviewed": len(df), "raw_accuracy": round(raw_acc, 3),
                   "weighted_accuracy": round(weighted_acc, 3), "cohens_kappa": round(kappa, 3)}]
                 ).to_csv(ROOT / "results" / "llm_validation_summary.csv", index=False)
    print("Saved results/llm_validation_summary.csv and results/llm_validation_confusion.csv")


# CFPB issues whose meaning maps cleanly to exactly one root cause. Agreement on
# these is a free, automatic sanity check over the whole sample (no human labels).
# Deliberately left out: broad issues such as "Managing an account" (the most
# common issue in the sample, which is the gap the LLM labels fill) and
# ambiguous ones such as "Problem with a lender or other company charging your
# account" (can be a fee or an unauthorized debit).
ISSUE_MAP = {
    "Problem caused by your funds being low": "fees_and_charges",
    "Fees or interest": "fees_and_charges",
    "Fraud or scam": "fraud_and_unauthorized",
    "Struggling to pay mortgage": "loan_servicing",
    "Attempts to collect debt not owed": "debt_collection_conduct",
    "Written notification about debt": "debt_collection_conduct",
    "False statements or representation": "debt_collection_conduct",
}


def consistency() -> None:
    import duckdb
    con = duckdb.connect(str(ROOT / "data" / "complaints.duckdb"), read_only=True)
    issues = con.sql("""
        SELECT s.complaint_id, i.issue
        FROM fact_complaints f JOIN dim_issue i USING (issue_key)
        JOIN llm_sample s USING (complaint_id)
    """).df()
    df = pd.read_csv(ROOT / "results" / "llm_classifications.csv").merge(issues, on="complaint_id")
    df["expected"] = df["issue"].map(ISSUE_MAP)
    checked = df[df["expected"].notna()]
    agree = (checked["expected"] == checked["root_cause"]).mean()
    print(f"Complaints with an unambiguous CFPB issue: {len(checked):,}   LLM agrees: {agree:.1%}")
    print(checked.assign(agree=checked["expected"] == checked["root_cause"])
          .groupby("issue")["agree"].agg(["count", "mean"]).round(3).to_string())
    pd.DataFrame([{"checked": len(checked), "agreement": round(agree, 3)}]).to_csv(
        ROOT / "results" / "llm_issue_consistency.csv", index=False)


if __name__ == "__main__":
    commands = {"make-review": make_review, "score": score, "consistency": consistency}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(f"usage: python notebooks/06_validate_classifications.py [{' | '.join(commands)}]")
    commands[sys.argv[1]]()
