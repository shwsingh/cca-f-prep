"""
MeterFlow inbound email pipeline (Week 1 integration).

Composition seam:
    raw_email → extract_tickets_with_usage    (Day 5)
              → severity_rank sort
              → fan out: run_conversation     (Day 4) per ticket
              → BatchResult with token + cost rollup

Per-ticket isolation: one conversation hitting anthropic.APIError must NOT
kill the batch. Errored conversations are counted, not raised. Extraction
failure is the only state where we can't proceed — surfaced via
BatchResult.extraction_failed=True with empty ticket and conversation lists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import anthropic

from meterflow.agents import ConversationState, run_conversation
from meterflow.extractors import SupportTicket, extract_tickets_with_usage

# Haiku 4.5 pricing — keep aligned with the MODEL constant in the
# extractor and agent modules. When we move to a tiered model strategy
# (e.g. haiku for extraction, sonnet for resolution) this constant
# splits into per-call estimates.
COST_IN_PER_MTOK = 1.0
COST_OUT_PER_MTOK = 5.0


# Canned scripted customer replies per issue_type. The point isn't realism —
# it's that the pipeline drives a different conversation shape for each
# issue type, so the per-ticket fan-out is observable in the day script.
# Real customer turns will come from the support inbox in Week 3.
CANNED_REPLIES: dict[str, list[str]] = {
    "billing": [
        "Yes, please confirm and process the refund.",
        "How long until it shows on my card?",
        "Thanks, that works.",
    ],
    "auth": [
        "Yes, our team is locked out — what's the fix?",
        "We'll try that. Is there a workaround in the meantime?",
        "Okay, we're back in. Thanks.",
    ],
    "api_error": [
        "Yes, we need an RCA and an ETA on the fix.",
        "Are other customers affected?",
        "Got it — send the RCA when ready.",
    ],
    "quota": [
        "Can you confirm the actual quota status?",
        "What are our options — overage billing or upgrade?",
        "Okay, let's upgrade. Send the link.",
    ],
    "other": [
        "Can you point me to the correct docs?",
        "Thanks — anything else I should know?",
        "Got it.",
    ],
}

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def severity_rank(ticket: SupportTicket) -> int:
    """Lower rank = higher priority. Critical resolves first; unknown
    severities sort last so the pipeline keeps moving."""
    return _SEVERITY_ORDER.get(ticket.severity, 99)


@dataclass
class BatchResult:
    email_id: str
    tickets: list[SupportTicket] = field(default_factory=list)
    conversations: list[ConversationState] = field(default_factory=list)
    extraction_failed: bool = False
    errored_count: int = 0
    extraction_input_tokens: int = 0
    extraction_output_tokens: int = 0

    @property
    def total_input_tokens(self) -> int:
        return self.extraction_input_tokens + sum(
            c.total_input_tokens for c in self.conversations
        )

    @property
    def total_output_tokens(self) -> int:
        return self.extraction_output_tokens + sum(
            c.total_output_tokens for c in self.conversations
        )

    @property
    def cost_usd(self) -> float:
        return (
            self.total_input_tokens / 1_000_000 * COST_IN_PER_MTOK
            + self.total_output_tokens / 1_000_000 * COST_OUT_PER_MTOK
        )

    @property
    def resolved_count(self) -> int:
        return sum(1 for c in self.conversations if c.resolved)


def process_email(
    raw_email: str,
    email_id: str,
    client: anthropic.Anthropic | None = None,
) -> BatchResult:
    """Run one inbound email end-to-end.

    Never raises on per-ticket errors — BatchResult is the contract;
    extraction_failed and errored_count are how partial failures surface.
    Callers that want fail-loud semantics should branch on those fields.
    """
    client = client or anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # 1. Extract — extraction failure is the ONE case where we can't proceed.
    try:
        tickets, ext_usage = extract_tickets_with_usage(raw_email, client=client)
    except (ValueError, anthropic.APIError) as e:
        print(f"  ⚠️  [{email_id}] extraction failed: {e}")
        return BatchResult(email_id=email_id, extraction_failed=True)

    result = BatchResult(
        email_id=email_id,
        extraction_input_tokens=ext_usage["input_tokens"],
        extraction_output_tokens=ext_usage["output_tokens"],
    )

    # 2. Sort by severity — high/critical resolve before low/medium.
    result.tickets = sorted(tickets, key=severity_rank)

    # 3. Fan out — per-ticket isolation so one bad conversation doesn't
    #    kill the batch. Errored conversations are counted, not raised.
    for t in result.tickets:
        script = CANNED_REPLIES.get(t.issue_type, CANNED_REPLIES["other"])
        try:
            state = run_conversation(t, script, client=client)
            result.conversations.append(state)
        except anthropic.APIError as e:
            result.errored_count += 1
            print(
                f"  ⚠️  [{email_id}] conversation for "
                f"{t.customer_id}/{t.issue_type} errored: {e}"
            )

    return result
