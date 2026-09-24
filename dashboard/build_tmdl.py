"""Generate dashboard/measures.tmdl from dashboard/measures.dax.

The .tmdl script adds every measure to the _Measures table in one step:
Power BI Desktop > TMDL view > paste > Apply. measures.dax stays the single
source of truth; formats and display folders are assigned here.
Usage:  python dashboard/build_tmdl.py
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

FOLDERS = {
    "Counts": ["Complaints", "Timely Responses", "Closed Complaints", "Relief Complaints",
               "Monetary Relief Complaints"],
    "Response rates": ["Timely Response %", "Relief Rate %", "No Relief Rate %", "Monetary Relief %"],
    "Time": ["Complaints PY", "Complaints YoY %", "Complaints PM", "Complaints MoM %",
             "Complaints 3M Avg", "Complaints 12M Avg", "Latest Data Month",
             "Complaints Latest Month", "Complaints Index (2018 = 100)"],
    "Geography": ["Population", "Months Selected", "Complaints per 100K (annualized)"],
    "Market": ["Credit Bureau Share %", "Share of Company Complaints %"],
    "Peers": ["Peer Avg Relief Rate %", "Relief Rate vs Peer Avg", "Overdraft Share %",
              "Overdraft Share % (Regions)", "Overdraft Share % (Peers)", "Bar Color (Regions Highlight)"],
}


def format_string(name: str) -> str | None:
    if name.endswith("%") or name.startswith("Overdraft Share %") or name == "Relief Rate vs Peer Avg":
        return "0.0%"
    if name == "Latest Data Month":
        return "mmm yyyy"
    if name == "Bar Color (Regions Highlight)":
        return None
    return "#,0"


def parse_measures(dax: str) -> list[tuple[str, str]]:
    measures, name, body = [], None, []
    for line in dax.splitlines() + [""]:
        stripped = line.strip()
        if name is None:
            if stripped.endswith(" =") and not stripped.startswith("//"):
                name, body = stripped[:-2].strip(), []
        elif stripped == "":
            measures.append((name, "\n".join(body)))
            name = None
        elif not stripped.startswith("//"):
            body.append(line.rstrip())
    return measures


if __name__ == "__main__":
    measures = parse_measures((HERE / "measures.dax").read_text(encoding="utf-8"))
    folder_of = {m: f for f, names in FOLDERS.items() for m in names}
    missing = [n for n, _ in measures if n not in folder_of]
    assert not missing, f"no display folder for: {missing}"

    out = ["createOrReplace", "", "\tref table _Measures", ""]
    for name, expr in measures:
        out.append(f"\t\tmeasure '{name}' = ```")
        out += [f"\t\t\t\t{l}" for l in expr.splitlines()]
        out.append("\t\t\t\t```")
        if fmt := format_string(name):
            out.append(f"\t\t\tformatString: {fmt}")
        out.append(f"\t\t\tdisplayFolder: {folder_of[name]}")
        out.append("")
    (HERE / "measures.tmdl").write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {len(measures)} measures to dashboard/measures.tmdl")
