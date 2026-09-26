"""Root-cause taxonomy, prompt, and output schema for classifying complaint narratives.

Provider-neutral: both llm/claude_backend.py and llm/groq_backend.py import from
here, so every model sees the identical instructions and must return the same
fields. Changing a label or definition here changes it everywhere.

Why a root-cause taxonomy (not the CFPB "issue" field)? The issue is a menu
choice the consumer picks when filing ("Managing an account"), which is broad
and product-specific. The narrative says what actually went wrong ("the bank
froze my account for 3 weeks and nobody would tell me why"), which is what a
bank can act on. The labels are cross-product so they can be compared across
banks and products.
"""
from typing import Literal

from pydantic import BaseModel, Field

ROOT_CAUSES: dict[str, str] = {
    "fees_and_charges": (
        "Overdraft/NSF fees, maintenance or service fees, late fees, interest charges or "
        "other fees the consumer disputes or did not expect."
    ),
    "fraud_and_unauthorized": (
        "Unauthorized transactions, scams, identity theft, account takeover, and how the "
        "company handled the resulting fraud claim or dispute."
    ),
    "account_access_and_closure": (
        "Frozen or held funds, account restricted or closed by the company, consumer cannot "
        "access or withdraw their money."
    ),
    "payment_and_transaction_errors": (
        "Payments, deposits, or transfers that were delayed, not posted, misapplied, or "
        "processed incorrectly (excluding fraud)."
    ),
    "loan_servicing": (
        "Mortgage or loan servicing: escrow, modification, forbearance, foreclosure, payoff, "
        "servicing transfer, how payments are applied to a loan."
    ),
    "credit_reporting_by_company": (
        "The company reported inaccurate information to credit bureaus or will not correct it."
    ),
    "misleading_terms_or_promotions": (
        "Promised bonuses, rewards, rates, or terms not honored; unclear or misleading "
        "disclosures; unexpected rate or term changes."
    ),
    "customer_service_failure": (
        "The main problem is the service itself: no response, repeated transfers or "
        "runaround, rude staff, unresolved after many contacts, when no more specific "
        "cause above applies."
    ),
    "debt_collection_conduct": (
        "Collection of a debt the consumer disputes or does not recognize, harassing calls, "
        "threats, or improper collection practices."
    ),
    "other": "None of the above clearly applies.",
}

RootCause = Literal[
    "fees_and_charges", "fraud_and_unauthorized", "account_access_and_closure",
    "payment_and_transaction_errors", "loan_servicing", "credit_reporting_by_company",
    "misleading_terms_or_promotions", "customer_service_failure", "debt_collection_conduct",
    "other",
]


class Classification(BaseModel):
    """What the model must return for each narrative."""
    root_cause: RootCause
    contacted_company_multiple_times: bool = Field(
        description="Narrative says the consumer contacted the company more than once before complaining."
    )
    mentions_financial_loss: bool = Field(
        description="Narrative states the consumer lost money or was charged money they believe they do not owe."
    )
    mentions_legal_or_regulatory_action: bool = Field(
        description="Narrative mentions a lawyer, lawsuit, attorney general, regulator (other than this CFPB complaint), or BBB."
    )
    confidence: Literal["high", "medium", "low"]
    summary: str = Field(description="One sentence, at most 25 words, stating what went wrong.")


# JSON Schema used for structured outputs. additionalProperties=false and every
# field required, so any response that parses is complete.
OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string", "enum": list(ROOT_CAUSES)},
        "contacted_company_multiple_times": {"type": "boolean"},
        "mentions_financial_loss": {"type": "boolean"},
        "mentions_legal_or_regulatory_action": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "summary": {"type": "string"},
    },
    "required": [
        "root_cause", "contacted_company_multiple_times", "mentions_financial_loss",
        "mentions_legal_or_regulatory_action", "confidence", "summary",
    ],
    "additionalProperties": False,
}

_label_lines = "\n".join(f"- {name}: {definition}" for name, definition in ROOT_CAUSES.items())

SYSTEM_PROMPT = f"""You classify consumer complaints filed with the U.S. Consumer Financial Protection Bureau (CFPB) about banks and financial companies. The results feed a customer-experience analysis, so the label should capture the underlying problem the company would need to fix.

Pick exactly one root_cause: the single problem that best explains why the consumer complained. If several are mentioned, choose the one the consumer is primarily asking to have fixed. Use customer_service_failure only when poor service is itself the main complaint, not when it accompanies a more specific problem.

Root causes:
{_label_lines}

Also report:
- contacted_company_multiple_times, mentions_financial_loss, mentions_legal_or_regulatory_action: true only if the narrative states it.
- confidence: how clearly the narrative supports the root_cause you chose.
- summary: one plain sentence (max 25 words) of what went wrong.

The narratives are redacted by the CFPB: "XXXX" replaces names, dates, and account numbers. Treat it as unknown, not as meaningful content. Classify based only on what the narrative says.

Respond with a JSON object containing exactly these fields: root_cause, contacted_company_multiple_times, mentions_financial_loss, mentions_legal_or_regulatory_action, confidence, summary."""

# Narratives longer than this are cut (and flagged `truncated` in the output)
# so a handful of multi-page narratives can't dominate cost. The opening of a
# complaint almost always states the core problem.
MAX_NARRATIVE_CHARS = 6000


def user_message(narrative: str, product: str) -> str:
    text = narrative[:MAX_NARRATIVE_CHARS]
    return f"Product (as selected by the consumer): {product}\n\nComplaint narrative:\n{text}"
