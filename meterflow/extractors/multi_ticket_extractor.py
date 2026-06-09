"""
MeterFlow multi-ticket extractor.

Same job as ticket_extractor, two differences:
  1. Returns a *list* of SupportTickets — one customer email can legitimately
     report multiple independent issues, and the routing layer needs each
     one as its own ticket so they can be assigned/resolved separately.
  2. Uses tool use as the structured-output mechanism (not prompt-only JSON
     wrapping). The model is forced to call `record_support_tickets`, and
     stop_reason='tool_use' is the signal that extraction is complete.

The Day 3 prompt-only extractor still has its place: it's cheaper and lower
latency when you know the email is single-issue. Day 5 extractor is what the
routing layer should call when the email's shape is unknown.
"""

from __future__ import annotations

import os

import anthropic
from pydantic import BaseModel, ValidationError

from meterflow.extractors.ticket_extractor import SupportTicket

MODEL = "claude-haiku-4-5-20251001"
TOOL_NAME = "record_support_tickets"


def tool_schema_from_pydantic(model: type[BaseModel]) -> dict:
    """Convert a Pydantic model to a JSON Schema dict suitable for an
    Anthropic tool's input_schema. Strips the `title` keys Pydantic adds
    automatically — tool schemas read cleaner without them, and the model
    doesn't need title hints when field names are already descriptive."""
    schema = model.model_json_schema()
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
    return schema


# Single source of truth for the per-ticket shape: Pydantic model →
# JSON Schema → tool input_schema. Editing SupportTicket auto-propagates.
TOOL_SCHEMA: dict = {
    "name": TOOL_NAME,
    "description": (
        "Record one or more independent support tickets extracted from a "
        "single customer email. Emit one ticket per distinct problem the "
        "customer reports. If the email contains zero actionable issues, "
        "return an empty tickets array."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tickets": {
                "type": "array",
                "description": "One entry per independent problem in the email.",
                "items": tool_schema_from_pydantic(SupportTicket),
            }
        },
        "required": ["tickets"],
    },
}


SYSTEM = """You are MeterFlow's support triage extractor. Read one customer
email and call the `record_support_tickets` tool exactly once. Split the
email into INDEPENDENT problems — a billing dispute and an auth failure in
the same email are two tickets, not one. Use 'unknown' for customer_id if
no account id is present.

Severity rubric: production-down or revenue-impacting = high or critical;
single-user friction = low or medium. When in doubt, pick the lower one."""


def extract_tickets_with_usage(
    raw_email: str,
    client: anthropic.Anthropic | None = None,
) -> tuple[list[SupportTicket], dict]:
    """Same as extract_tickets but also returns {"input_tokens", "output_tokens"}
    so pipeline callers can aggregate cost across the full request lifecycle."""
    client = client or anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        temperature=0,
        system=SYSTEM,
        tools=[TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": f"<email>\n{raw_email}\n</email>"}],
    )

    if response.stop_reason != "tool_use":
        raise ValueError(
            f"Expected stop_reason='tool_use', got {response.stop_reason!r}. "
            f"Content blocks: {[type(b).__name__ for b in response.content]}"
        )

    tool_block = next(
        (b for b in response.content if getattr(b, "type", None) == "tool_use"),
        None,
    )
    if tool_block is None or tool_block.name != TOOL_NAME:
        raise ValueError(f"No {TOOL_NAME} tool_use block in response.")

    raw_tickets = tool_block.input.get("tickets", [])
    if not isinstance(raw_tickets, list):
        raise ValueError(f"Tool 'tickets' was not a list: {raw_tickets!r}")

    validated: list[SupportTicket] = []
    for i, raw in enumerate(raw_tickets):
        try:
            validated.append(SupportTicket.model_validate(raw))
        except ValidationError as e:
            raise ValueError(f"Ticket {i} failed validation.\nRaw: {raw}\nError: {e}") from e

    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return validated, usage


def extract_tickets(
    raw_email: str,
    client: anthropic.Anthropic | None = None,
) -> list[SupportTicket]:
    """Extract zero or more validated SupportTickets from one raw email.

    Day 5 contract — unchanged. Now a thin wrapper around
    extract_tickets_with_usage so callers that don't care about token
    counts keep the simple return shape.
    """
    tickets, _ = extract_tickets_with_usage(raw_email, client=client)
    return tickets
