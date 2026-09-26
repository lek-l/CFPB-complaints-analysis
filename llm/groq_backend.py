"""Classify narratives with an open-weight Llama model hosted on Groq.

Groq has no batch discount, so requests run one at a time with a short pause
to stay under free-tier rate limits; results stream back as they finish, so an
interrupted run resumes where it stopped (see notebooks/05_classify_narratives.py).

Credentials: GROQ_API_KEY env var.
Model: GROQ_MODEL env var, default llama-3.3-70b-versatile. Check
https://console.groq.com/docs/models for current model names.
"""
import json
import os
import time
from collections.abc import Iterable

from groq import Groq, RateLimitError

from llm.taxonomy import SYSTEM_PROMPT, Classification, user_message

MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
PAUSE_SECONDS = float(os.environ.get("GROQ_PAUSE_SECONDS", "0.5"))


def classify(rows: Iterable[dict]) -> Iterable[dict]:
    client = Groq()
    for r in rows:
        out = {"complaint_id": int(r["complaint_id"]), "model": MODEL}
        for attempt in range(6):
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    temperature=0,  # deterministic labels
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message(r["narrative"], r["product"])},
                    ],
                )
                break
            except RateLimitError:
                time.sleep(min(60, 5 * 2 ** attempt))  # back off, then retry
        else:
            out["error"] = "rate_limited"
            yield out
            continue
        text = resp.choices[0].message.content or ""
        try:
            # Groq's JSON mode guarantees valid JSON but not our schema, so
            # validate it here; a wrong label or missing field is an error row.
            out.update(Classification.model_validate(json.loads(text)).model_dump())
        except (json.JSONDecodeError, ValueError) as e:
            out["error"] = f"invalid_output: {e}"[:200]
        out["input_tokens"] = resp.usage.prompt_tokens
        out["output_tokens"] = resp.usage.completion_tokens
        yield out
        time.sleep(PAUSE_SECONDS)
