"""
MeterFlow ticket extractor.

Turns one raw customer support email into a validated `SupportTicket`.
Future routing, triage, and reply layers depend on this contract — change
the schema here, not in the prompt strings of downstream code.
"""

from __future__ import annotations

import os
import re
from typing import Literal

import anthropic
from pydantic import BaseModel, ValidationError

MODEL = "claude-haiku-4-5-20251001"


class SupportTicket(BaseModel):
    customer_id: str
    severity: Literal["low", "medium", "high", "critical"]
    issue_type: Literal["billing", "auth", "api_error", "quota", "other"]
    billing_period: str | None
    summary: str
    requested_action: str


SYSTEM = """You are MeterFlow's support triage extractor. Your only job is to
read one customer email and emit a single JSON object matching the schema
below. Do not chat, do not explain, do not add commentary.

<schema>
{
  "customer_id":      "string — the account id from the email (e.g. A-1042, N-7781, C-3310). If absent, use 'unknown'.",
  "severity":         "one of: low | medium | high | critical",
  "issue_type":       "one of: billing | auth | api_error | quota | other",
  "billing_period":   "string like 'May 2026' or null if not mentioned",
  "summary":          "one short sentence",
  "requested_action": "what the human agent should do next, one short sentence"
}
</schema>

<example>
<email>
From: ops@bluefish.test
Subject: invoice question — account B-2201

Our April invoice shows 12.4M events but we only sent ~9M. Please review.
</email>
<ticket_json>
{"customer_id": "B-2201", "severity": "medium", "issue_type": "billing", "billing_period": "April 2026", "summary": "Customer disputes April event count on invoice.", "requested_action": "Pull raw event counts for B-2201 in April and compare to billed total."}
</ticket_json>
</example>

Severity rubric: production-down or revenue-impacting = high or critical;
single user friction = low or medium. When in doubt, pick the lower one.

Emit ONLY the JSON wrapped in <ticket_json>...</ticket_json>. Nothing else."""


_TICKET_TAG = re.compile(r"<ticket_json>(.*?)</ticket_json>", re.DOTALL)


def extract_ticket(raw_email: str, client: anthropic.Anthropic | None = None) -> SupportTicket:
    """Extract a validated SupportTicket from one raw customer email.

    Raises ValueError if the model omits the <ticket_json> wrapper or the
    payload fails Pydantic validation. Callers should treat both as
    extraction failures and route to a human reviewer.
    """
    client = client or anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    r = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        temperature=0,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"<email>\n{raw_email}\n</email>"}],
    )
    text = r.content[0].text
    m = _TICKET_TAG.search(text)
    if not m:
        raise ValueError(f"No <ticket_json> tags in model output:\n{text}")
    payload = m.group(1).strip()
    try:
        return SupportTicket.model_validate_json(payload)
    except ValidationError as e:
        raise ValueError(f"Schema validation failed.\nPayload: {payload}\nError: {e}") from e
