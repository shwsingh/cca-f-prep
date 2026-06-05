"""
MeterFlow Support Resolution Agent.

Stateful conversation loop that takes an extracted SupportTicket and drives a
multi-turn dialogue toward resolution. Future Days 19-23 layer tool use, RAG,
memory, and evals on top of this same loop — do not re-invent the state
shape downstream; extend it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import anthropic

from meterflow.extractors import SupportTicket

MODEL = "claude-haiku-4-5-20251001"
RESOLVED_SENTINEL = "[RESOLVED]"


@dataclass
class ConversationState:
    ticket: SupportTicket
    messages: list[dict] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    turn_count: int = 0
    resolved: bool = False


def build_system_prompt(ticket: SupportTicket) -> str:
    return f"""You are the MeterFlow Resolution Agent — the human-facing voice
of MeterFlow support. You have already received the triaged ticket below.

<ticket>
  <customer_id>{ticket.customer_id}</customer_id>
  <severity>{ticket.severity}</severity>
  <issue_type>{ticket.issue_type}</issue_type>
  <summary>{ticket.summary}</summary>
</ticket>

The fields above are AUTHORITATIVE — treat them as already-verified facts
from your triage system. Never ask the customer to re-confirm or re-supply
their account id, the severity, the issue type, or what the summary says
they reported. If a fact you need to act is NOT in the ticket, ask the
customer for that specific missing fact.

Follow this resolution loop every turn:
  1. Acknowledge what the customer just said in one short sentence.
  2. Diagnose: state what you believe the underlying cause is, in plain language.
  3. Propose action: either a concrete fix you can perform, a clarifying
     question you need answered, or an escalation path. Pick exactly one.

Stay under 4 sentences per reply. No greetings after the first turn.

When — and only when — the customer confirms the issue is resolved or
indicates they have no further questions, end your reply with the literal
token {RESOLVED_SENTINEL} on its own line. Never use {RESOLVED_SENTINEL}
mid-conversation as a hedge."""


def agent_turn(
    state: ConversationState,
    user_text: str,
    client: anthropic.Anthropic | None = None,
) -> str:
    """Drive one customer→agent turn. Mutates state in place; returns the
    cleaned assistant reply (sentinel stripped)."""
    client = client or anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    state.messages.append({"role": "user", "content": user_text})
    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        temperature=0.3,
        system=build_system_prompt(state.ticket),
        messages=state.messages,
    )

    reply = response.content[0].text
    state.total_input_tokens += response.usage.input_tokens
    state.total_output_tokens += response.usage.output_tokens
    state.turn_count += 1

    if response.stop_reason == "max_tokens":
        # Truncated output is not a confident resolution — never mark resolved
        # on a stop_reason we didn't plan for. The agent loop downstream needs
        # to retry with a larger budget or escalate.
        print(f"  ⚠️  turn {state.turn_count}: stop_reason=max_tokens — reply truncated, not marking resolved")
    else:
        state.resolved = RESOLVED_SENTINEL in reply

    cleaned = reply.replace(RESOLVED_SENTINEL, "").strip()
    state.messages.append({"role": "assistant", "content": cleaned})
    return cleaned


def run_conversation(
    ticket: SupportTicket,
    customer_script: list[str],
    client: anthropic.Anthropic | None = None,
) -> ConversationState:
    """Run a scripted customer through the agent until [RESOLVED] or the
    script is exhausted. Returns the final state for inspection."""
    state = ConversationState(ticket=ticket)
    for user_text in customer_script:
        agent_turn(state, user_text, client=client)
        if state.resolved:
            break
    return state
