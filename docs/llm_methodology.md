# LLM Root-Cause Classification: Method

**Goal:** turn free-text complaint narratives into a small set of *root causes* a bank can act on, and check that the labels can be trusted.

## Why this adds something the structured data can't

Consumers pick an "issue" from a menu when they file. The most common issue in our sample, **"Managing an account" (2,220 of 10,162 sampled complaints)**, says nothing about what went wrong. The narrative does, for example "the bank froze my account for 3 weeks and nobody would tell me why". The LLM reads the narrative and assigns one of 10 cross-product root causes.

## Data source

The CFPB stopped publishing narratives in its live database on 2026-08-14 and moved all previously published ones to its [FOIA Reading Room narratives archive](https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/). `data/download_narratives.py` downloads the 20 exports covering May 2018 onward (1.2 GB zipped). They join to the star schema on `complaint_id`:

- 3,559,841 narratives; all but 6 link to a complaint in `fact_complaints`.
- Narratives exist only where the consumer opted in: about half of non-bureau complaints in 2019–2025, and only 19% in 2026, because publication stopped mid-year.
- Jan–Apr 2018 narratives are not in the sample frame (that export was skipped to save ~1 GB).

## Sample design (`notebooks/04_build_narrative_sample.py`)

A seeded, stratified sample of **10,162 complaints**:

| Frame | Size | Used for |
|---|---|---|
| **Market sample**: random non-bureau complaints about checking/savings, credit cards, mortgages and money transfer | 6,000 | Market-wide root-cause shares |
| **Peer sample**: random complaints per bank for Regions + 5 peers | 700 × 6 = 4,200 | Comparing root-cause mix between banks |

38 complaints fall in both frames. Market-wide numbers use only the market sample, so the oversampled peer banks don't bias them. 157 narratives (1.5%) longer than 6,000 characters are truncated and flagged `truncated`.

## Taxonomy (`llm/taxonomy.py`)

10 root causes, each with a written definition the model sees: fees & charges · fraud & unauthorized · account access & closure · payment & transaction errors · loan servicing · credit reporting by the company · misleading terms & promotions · customer-service failure · debt-collection conduct · other.

The model also returns three yes/no flags (contacted the company multiple times, financial loss, legal/regulatory action mentioned), a confidence level and a one-sentence summary. The flags support a **first-contact resolution** proxy: how often consumers say they already contacted the bank before going to the CFPB.

Design choices:
- **One primary label per complaint**, the problem the consumer mainly wants fixed. This keeps shares summing to 100% and makes validation unambiguous.
- **"Customer-service failure" only when service is the main problem**, not whenever it's mentioned, so it doesn't absorb everything.
- **Structured output:** every answer must match a JSON schema, with a fixed label list and all fields required. Anything that doesn't parse is logged as an error row, not guessed.

## Models and cost (`notebooks/05_classify_narratives.py`)

The pipeline supports two providers with the identical prompt and schema:

| Provider | How it runs | Estimated cost, full sample |
|---|---|---|
| Claude (`llm/claude_backend.py`) | Message Batches API (50% discount), structured outputs | ~$58 on Claude Opus 5, ~$12 on Claude Haiku 4.5 (dry-run estimate) |
| Groq + Llama (`llm/groq_backend.py`) | One request at a time, JSON mode, temperature 0 | See Groq pricing and your plan's daily token limit |

`--dry-run` prints the estimate without calling any API; `--limit 50` runs a pilot. Results are appended to a log and the script resumes after interruptions without paying twice.

## Validation (`notebooks/06_validate_classifications.py`)

1. **Blind human review (200 complaints).** The review sheet shows only the narrative, and the model's labels sit in a separate key file, so the human label isn't anchored on the model's. The sheet is stratified with at least 12 complaints per predicted label so rare labels get checked too.
2. **Metrics:** raw accuracy; accuracy re-weighted by how common each label is in the full sample (corrects for the stratified review); **Cohen's kappa** (agreement beyond chance); precision and recall per label; accuracy by model confidence.
3. **Automatic consistency check** on complaints whose CFPB issue maps unambiguously to one root cause (e.g. "Problem caused by your funds being low" → fees & charges). No human labels needed, and it covers the whole sample.

Results go to `results/llm_validation_summary.csv`, `results/llm_validation_confusion.csv` and `results/llm_issue_consistency.csv`.

## Limitations

- Narratives are self-selected: only consumers who opted to publish are represented.
- One label per complaint simplifies complaints with several problems.
- The model can be wrong. The validation step measures how often, and the results should be read with that error rate in mind.
