"""Classify narratives with Claude using the Message Batches API.

Batches process asynchronously at 50% of standard token prices, which suits a
one-off job of ~10K classifications. Structured outputs (output_config.format)
constrain every response to the schema in taxonomy.py.

Credentials: the SDK reads ANTHROPIC_API_KEY (or an `ant auth login` profile).
Model: CLAUDE_MODEL env var, default claude-opus-5. For a cheaper run, set
CLAUDE_MODEL=claude-haiku-4-5 (cost estimate printed before submitting).
"""
import json
import os
import time
from collections.abc import Iterable

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from llm.taxonomy import OUTPUT_SCHEMA, SYSTEM_PROMPT, Classification, user_message

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")


def _params(narrative: str, product: str) -> MessageCreateParamsNonStreaming:
    params = MessageCreateParamsNonStreaming(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message(narrative, product)}],
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    )
    # Classification is a simple task: low effort keeps thinking (and cost) small
    # on models that support effort. Haiku 4.5 does not accept the effort setting.
    if not MODEL.startswith("claude-haiku"):
        params["output_config"]["effort"] = "low"
    return params


def classify(rows: Iterable[dict], poll_seconds: int = 60) -> Iterable[dict]:
    """rows: dicts with complaint_id, narrative, product. Yields one result dict per row."""
    client = anthropic.Anthropic()
    requests = [
        Request(custom_id=str(r["complaint_id"]), params=_params(r["narrative"], r["product"]))
        for r in rows
    ]
    if not requests:
        return
    batch = client.messages.batches.create(requests=requests)
    print(f"Submitted batch {batch.id} with {len(requests)} requests ({MODEL})", flush=True)

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        c = batch.request_counts
        print(f"  {batch.processing_status}: {c.succeeded} done, {c.processing} processing", flush=True)
        time.sleep(poll_seconds)

    # Results arrive in any order: key by custom_id, never by position.
    for result in client.messages.batches.results(batch.id):
        out = {"complaint_id": int(result.custom_id), "model": MODEL}
        if result.result.type != "succeeded":
            out["error"] = result.result.type
            yield out
            continue
        message = result.result.message
        if message.stop_reason == "refusal":
            out["error"] = "refusal"
            yield out
            continue
        text = next((b.text for b in message.content if b.type == "text"), "")
        try:
            out.update(Classification.model_validate(json.loads(text)).model_dump())
        except (json.JSONDecodeError, ValueError) as e:
            out["error"] = f"invalid_output: {e}"[:200]
        out["input_tokens"] = message.usage.input_tokens
        out["output_tokens"] = message.usage.output_tokens
        yield out
