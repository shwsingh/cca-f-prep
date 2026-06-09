"""
W1D5 — Multi-ticket extraction via forced tool use (Scenario 6, second pass)

Day 3 was prompt-only structured output: schema in <schema>, output in
<ticket_json>, parse with regex, validate with Pydantic. Single ticket per
email. The rambling fixture exposed the failure mode — three problems got
collapsed into one ticket because the contract said "one ticket".

Day 5 fixes that with tool use as the structured-output mechanism. The tool's
input_schema enforces both the per-ticket fields AND the "list of tickets"
wrapper. stop_reason='tool_use' is the completion signal, not a regex.
"""

import os
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meterflow.extractors import (  # noqa: E402
    TOOL_SCHEMA,
    SupportTicket,
    extract_ticket,
    extract_tickets,
)
from meterflow.extractors.multi_ticket_extractor import SYSTEM as TOOL_SYSTEM  # noqa: E402
from meterflow.extractors.multi_ticket_extractor import TOOL_NAME  # noqa: E402
from meterflow.extractors.ticket_extractor import SYSTEM as PROMPT_SYSTEM  # noqa: E402
from scripts.anti_patterns import rebuild_master, write_day  # noqa: E402

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

COST_IN_PER_MTOK = 1.0
COST_OUT_PER_MTOK = 5.0
MODEL = "claude-haiku-4-5-20251001"


def cost(in_tok: int, out_tok: int) -> float:
    return in_tok / 1_000_000 * COST_IN_PER_MTOK + out_tok / 1_000_000 * COST_OUT_PER_MTOK


# ============================================================
# Fixtures — 4 from Day 3 + 1 new triple-issue + 1 empty body
# ============================================================
RAW_TICKETS: list[tuple[str, str]] = [
    (
        "clean_billing",
        """From: priya.kapoor@acme.io
Subject: Double charge on May invoice
Account A-1042 here. We were charged $49 twice on May 14 for the May
billing period. Could you refund one of the charges?
""",
    ),
    (
        "rambling_multi_issue",
        """Fwd: ugh
hey so first off our login is broken half the time (SSO via okta) which is
making my team crazy. also unrelated but we hit the 10M event quota
yesterday and the dashboard didn't warn us at all?? account is N-7781,
if this doesn't get fixed by friday we're escalating.
""",
    ),
    (
        "terse_api_error",
        """Subject: 500 on /v1/events
Account: C-3310
POST /v1/events returns 500 since 09:14 UTC. Need RCA.
""",
    ),
    (
        "missing_customer_id",
        """Subject: question
How do I rotate my API key? The docs link in the dashboard 404s.
""",
    ),
    (
        # NEW: explicit three-problem fixture. Each problem is independent —
        # billing dispute, login lockout, hitting the event quota. The tool-use
        # extractor should produce exactly 3 tickets; the Day 3 extractor will
        # collapse to 1.
        "triple_issue",
        """From: ops@helios-data.io
Subject: multiple problems on account H-7700

Three things, sorry to bundle but they're all hitting us today:
  1. Invoice for May shows $480 but our usage report says $312. Discrepancy
     of $168 we'd like reviewed.
  2. Two of our engineers (jasmine@, ravi@) cannot log in via SAML SSO as of
     this morning — 'auth_provider_unreachable' error.
  3. We crossed our 50M event quota an hour ago and the dashboard banner is
     orange. Wanted to flag before you cap us.

We're a paying customer, please prioritize.
""",
    ),
    (
        # Step 6 failure case. Empty body forces the model to decide: refuse
        # via empty array, or invent a default 'other' ticket?
        "empty_body",
        "Subject: (no body)\n\n",
    ),
]


# ============================================================
# TEST 1 — run extract_tickets across all 6 fixtures
# ============================================================
print("=" * 60)
print("TEST 1 — tool-use extraction across 6 fixtures")
print("=" * 60)

for label, email in RAW_TICKETS:
    print(f"\n[{label}]")
    try:
        tickets = extract_tickets(email, client=client)
        print(f"  → {len(tickets)} ticket(s)")
        for i, t in enumerate(tickets, 1):
            print(f"     {i}. {t.customer_id:10s} {t.severity:8s} {t.issue_type:10s} {t.summary}")
    except ValueError as e:
        print(f"  ❌ {e}")


# ============================================================
# TEST 2 — side-by-side: prompt-only vs. tool use on rambling
# Same email, same model, instrumented inline so we can read response.usage.
# ============================================================
print("\n" + "=" * 60)
print("TEST 2 — prompt-only vs. tool use on the same rambling email")
print("=" * 60)

rambling_email = dict(RAW_TICKETS)["rambling_multi_issue"]

# Prompt-only run (Day 3 SYSTEM, parse <ticket_json>, single ticket)
r_prompt = client.messages.create(
    model=MODEL,
    max_tokens=1024,
    temperature=0,
    system=PROMPT_SYSTEM,
    messages=[{"role": "user", "content": f"<email>\n{rambling_email}\n</email>"}],
)
m = re.search(r"<ticket_json>(.*?)</ticket_json>", r_prompt.content[0].text, re.DOTALL)
prompt_count = 1 if m else 0
prompt_in, prompt_out = r_prompt.usage.input_tokens, r_prompt.usage.output_tokens

# Tool-use run (Day 5 SYSTEM, forced tool_choice, list of tickets)
r_tool = client.messages.create(
    model=MODEL,
    max_tokens=2048,
    temperature=0,
    system=TOOL_SYSTEM,
    tools=[TOOL_SCHEMA],
    tool_choice={"type": "tool", "name": TOOL_NAME},
    messages=[{"role": "user", "content": f"<email>\n{rambling_email}\n</email>"}],
)
tool_block = next(b for b in r_tool.content if getattr(b, "type", None) == "tool_use")
tool_count = len(tool_block.input.get("tickets", []))
tool_in, tool_out = r_tool.usage.input_tokens, r_tool.usage.output_tokens

print(f"  {'approach':<18}{'tickets':>10}{'in_tok':>10}{'out_tok':>10}{'cost_usd':>14}")
print(f"  {'-' * 62}")
print(f"  {'prompt-only (D3)':<18}{prompt_count:>10}{prompt_in:>10}{prompt_out:>10}{'$' + format(cost(prompt_in, prompt_out), '.5f'):>14}")
print(f"  {'tool use (D5)':<18}{tool_count:>10}{tool_in:>10}{tool_out:>10}{'$' + format(cost(tool_in, tool_out), '.5f'):>14}")

print()
print("  Ship decision: tool use for the inbound routing layer. Higher input")
print("  cost (the schema lives in input tokens every call) and slightly higher")
print("  output cost — but it correctly enumerates independent issues, and the")
print("  contract is a typed tool_use block instead of a regex over free text.")
print("  Prompt-only is still the right pick for single-issue followups where")
print("  cost beats expressiveness.")


# ============================================================
# TEST 3 — empty-body fixture: which behavior did the model pick?
# Findings get printed inline so the day's report is honest.
# ============================================================
print("\n" + "=" * 60)
print("TEST 3 — what does the tool do with an empty email body?")
print("=" * 60)
empty_tickets = extract_tickets("Subject: (no body)\n\n", client=client)
if not empty_tickets:
    print(f"  → empty array returned. Tool description 'return empty if no actionable issues' held.")
else:
    print(f"  → {len(empty_tickets)} ticket(s) invented:")
    for t in empty_tickets:
        print(f"     {t.customer_id} / {t.severity} / {t.issue_type} / {t.summary!r}")
    print("  The model chose to fabricate rather than emit []. Flag for the prompt-tuning pass.")


# ============================================================
# anti-pattern log
# ============================================================
WEEK_DAY = "W1D5"

ENTRIES = [
    {
        "domain": "Tool Design & MCP",
        "title": "Reaching for prompt-only JSON when tool use is the right answer",
        "mistake": (
            "Building structured extraction by stuffing a schema into the system prompt "
            "and parsing the model's free-text reply with a regex, even when the API has "
            "a typed tool_use mechanism that does exactly this job."
        ),
        "why": (
            "Prompt-only structured output couples your contract to a string-match: "
            "the model has to remember to wrap output in `<ticket_json>` AND emit JSON "
            "that happens to parse AND match your Pydantic schema. Each of those is a "
            "place the model can drift. Tool use moves the contract into the API: the "
            "model is told 'call this function with this signature', and the response "
            "comes back as a typed `ToolUseBlock` with `input: dict[str, Any]` you can "
            "validate directly. The contract is enforced by the API surface, not by your "
            "prompt's politeness."
        ),
        "fix": (
            "```python\n"
            "# ✅ tool use as structured output\n"
            "tool = {\n"
            '    "name": "record_support_tickets",\n'
            '    "description": "Record one or more tickets from a customer email.",\n'
            '    "input_schema": {"type": "object", "properties": {...}, "required": [...]},\n'
            "}\n"
            "r = client.messages.create(\n"
            "    model=MODEL, tools=[tool],\n"
            '    tool_choice={"type": "tool", "name": "record_support_tickets"},\n'
            "    messages=[...],\n"
            ")\n"
            'assert r.stop_reason == "tool_use"\n'
            "tickets = next(b for b in r.content if b.type == \"tool_use\").input[\"tickets\"]\n"
            "```"
        ),
        "exam_tip": (
            "When the exam describes a task as 'extract a list of X', tool use is almost "
            "always the right answer. Prompt-only JSON is the right answer only when the "
            "model also needs to emit prose (e.g. chain-of-thought + final answer) in the "
            "same turn — tool use makes that awkward."
        ),
    },
    {
        "domain": "Tool Design & MCP",
        "title": "Reading the tool_use block before checking stop_reason",
        "mistake": (
            "```python\n"
            "# ❌ wrong — assume the model called the tool\n"
            "tool_block = next(b for b in r.content if b.type == 'tool_use')\n"
            "tickets = tool_block.input['tickets']  # StopIteration if model declined\n"
            "```"
        ),
        "why": (
            "Without `tool_choice={'type': 'tool', 'name': ...}`, the model is FREE to "
            "reply with prose ('I don't have enough info to extract tickets from this') "
            "instead of calling the tool. Then `response.content` has only TextBlocks, "
            "the `next()` raises `StopIteration`, and the routing layer crashes on a "
            "perfectly valid model response. Even WITH forced tool use, a future model "
            "update could change defaults — branching on stop_reason is the durable check."
        ),
        "fix": (
            "Branch on `stop_reason` first. Treat anything other than 'tool_use' as a "
            "model refusal and surface it explicitly.\n\n"
            "```python\n"
            "# ✅ right\n"
            "if r.stop_reason != 'tool_use':\n"
            "    raise ValueError(f'model refused tool; reason={r.stop_reason!r}')\n"
            "tool_block = next(b for b in r.content if b.type == 'tool_use')\n"
            "tickets = tool_block.input['tickets']\n"
            "```"
        ),
        "exam_tip": (
            "Five `stop_reason` values: `end_turn`, `max_tokens`, `stop_sequence`, "
            "`tool_use`, `pause_turn`. Each demands a different follow-up. Memorize the "
            "branching matrix — the exam loves this."
        ),
    },
    {
        "domain": "Tool Design & MCP",
        "title": "Hand-typing the tool input_schema instead of generating it",
        "mistake": (
            "Maintaining a Pydantic model AND a hand-written JSON Schema dict for the "
            "tool's input_schema. The two drift the first time you add a field — model "
            "validation passes, the tool's schema is missing the new key, the model "
            "leaves it out, the routing layer breaks."
        ),
        "why": (
            "Two sources of truth always become two definitions of truth. The Pydantic "
            "model is already the canonical definition of `SupportTicket`; the tool "
            "input_schema has to agree with it on every field, type, and enum. The only "
            "way to keep them aligned is to derive one from the other."
        ),
        "fix": (
            "Generate the tool input_schema from the Pydantic model. Pydantic 2 emits a "
            "JSON Schema dict natively; strip the `title` keys Pydantic adds and you have "
            "a tool-ready schema.\n\n"
            "```python\n"
            "def tool_schema_from_pydantic(model: type[BaseModel]) -> dict:\n"
            "    schema = model.model_json_schema()\n"
            "    schema.pop('title', None)\n"
            "    for prop in schema.get('properties', {}).values():\n"
            "        prop.pop('title', None)\n"
            "    return schema\n\n"
            "TOOL_SCHEMA = {\n"
            "    'name': 'record_support_tickets',\n"
            "    'input_schema': {\n"
            "        'type': 'object',\n"
            "        'properties': {'tickets': {'type': 'array',\n"
            "                                    'items': tool_schema_from_pydantic(SupportTicket)}},\n"
            "        'required': ['tickets'],\n"
            "    },\n"
            "}\n"
            "```"
        ),
        "exam_tip": (
            "Distractor: 'tool input_schemas should be hand-tuned for the model's reading.' "
            "They shouldn't — they're a contract, not a prompt. Derive from your domain "
            "model and trust the schema to do its job."
        ),
    },
]


print()
write_day(WEEK_DAY, ENTRIES)
rebuild_master()
