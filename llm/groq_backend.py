"""Classify narratives with an open-weight model hosted on Groq.

Default model: openai/gpt-oss-120b (checked 2026-09-26): it supports strict
structured outputs on Groq and costs $0.15 / $0.60 per 1M input / output
tokens on the Developer plan. Llama 3.3 70B is now Enterprise-only on Groq.
The free plan's daily token cap (200K tokens/day per model) is far below this
job (~10M tokens), so a full run needs the Developer plan.

Requests run one at a time; results stream back as they finish, so an
interrupted run resumes where it stopped (see notebooks/05_classify_narratives.py).

Credentials: GROQ_API_KEY env var.
Model: GROQ_MODEL env var. Current models: https://console.groq.com/docs/models
"""
import json
import os
import time
from collections.abc import Iterable

from groq import Groq, RateLimitError

from llm.taxonomy import OUTPUT_SCHEMA, SYSTEM_PROMPT, Classification, user_message

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
PAUSE_SECONDS = float(os.environ.get("GROQ_PAUSE_SECONDS", "0.2"))


def _request(client: Groq, narrative: str, product: str):
    kwargs = dict(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message(narrative, product)},
        ],
        # Strict mode = constrained decoding: every answer matches the schema
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "complaint_classification", "strict": True, "schema": OUTPUT_SCHEMA},
        },
    )
    if MODEL.startswith("openai/gpt-oss"):
        # Reasoning model: a simple classification needs little reasoning, and
        # reasoning tokens are billed as output. Leave the reasoning text out of
        # the response since only the JSON answer is used.
        kwargs.update(reasoning_effort="low", include_reasoning=False)
    return client.chat.completions.create(**kwargs)


def classify(rows: Iterable[dict]) -> Iterable[dict]:
    client = Groq()
    for r in rows:
        out = {"complaint_id": int(r["complaint_id"]), "model": MODEL}
        for attempt in range(6):
            try:
                resp = _request(client, r["narrative"], r["product"])
                break
            except RateLimitError:
                time.sleep(min(60, 5 * 2 ** attempt))  # back off, then retry
        else:
            out["error"] = "rate_limited"
            yield out
            continue
        text = resp.choices[0].message.content or ""
        try:
            # Validate anyway: a wrong label or missing field becomes an error row
            out.update(Classification.model_validate(json.loads(text)).model_dump())
        except (json.JSONDecodeError, ValueError) as e:
            out["error"] = f"invalid_output: {e}"[:200]
        out["input_tokens"] = resp.usage.prompt_tokens
        out["output_tokens"] = resp.usage.completion_tokens
        yield out
        time.sleep(PAUSE_SECONDS)
