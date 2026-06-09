"""
W1D6 — Email-to-resolution pipeline (Week 1 capstone integration)

First day the Week 1 modules connect end-to-end:
  Day 5 extract_tickets_with_usage  →  Day 6 severity ordering  →
  Day 4 run_conversation × N        →  BatchResult roll-up.

Three emails exercise the integration:
  • triple_issue   — 3 tickets, mixed severity (the marquee case)
  • clean_billing  — 1 ticket   (graceful length-1 behavior)
  • empty body     — 0 tickets  (no-op, not an error)
"""

import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meterflow.pipelines import BatchResult, process_email  # noqa: E402
from scripts.anti_patterns import rebuild_master, write_day  # noqa: E402

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ============================================================
# Fixtures
# ============================================================
TRIPLE_ISSUE_EMAIL = """From: ops@helios-data.io
Subject: multiple problems on account H-7700

Three things, sorry to bundle but they're all hitting us today:
  1. Invoice for May shows $480 but our usage report says $312. Discrepancy
     of $168 we'd like reviewed.
  2. Two of our engineers (jasmine@, ravi@) cannot log in via SAML SSO as of
     this morning — 'auth_provider_unreachable' error.
  3. We crossed our 50M event quota an hour ago and the dashboard banner is
     orange. Wanted to flag before you cap us.

We're a paying customer, please prioritize.
"""

CLEAN_BILLING_EMAIL = """From: priya.kapoor@acme.io
Subject: Double charge on May invoice
Account A-1042 here. We were charged $49 twice on May 14 for the May
billing period. Could you refund one of the charges?
"""

EMAILS: list[tuple[str, str]] = [
    ("triple_issue",  TRIPLE_ISSUE_EMAIL),
    ("clean_billing", CLEAN_BILLING_EMAIL),
    ("empty_body",    ""),
]


# ============================================================
# Run
# ============================================================
print("=" * 70)
print("W1D6 — running 3 inbound emails end-to-end through the pipeline")
print("=" * 70)

results: list[BatchResult] = []
for email_id, raw in EMAILS:
    print(f"\n[{email_id}]")
    r = process_email(raw, email_id=email_id, client=client)
    results.append(r)
    if r.extraction_failed:
        print(f"  ❌ extraction failed; skipping fan-out")
        continue
    print(
        f"  extracted: {len(r.tickets)} ticket(s), severity order: "
        f"{[t.severity for t in r.tickets]}"
    )
    print(f"  resolved : {r.resolved_count}/{len(r.tickets)}, errored: {r.errored_count}")
    print(f"  tokens   : in={r.total_input_tokens}, out={r.total_output_tokens}")
    print(f"  cost     : ${r.cost_usd:.5f}")


# ============================================================
# Batch report
# ============================================================
print("\n" + "=" * 70)
print("BATCH REPORT")
print("=" * 70)
print(
    f"  {'email_id':<16}{'tickets':>9}{'resolved':>10}{'errored':>9}"
    f"{'total_tok':>12}{'cost_usd':>12}"
)
print(f"  {'-' * 68}")
for r in results:
    total_tok = r.total_input_tokens + r.total_output_tokens
    print(
        f"  {r.email_id:<16}{len(r.tickets):>9}{r.resolved_count:>10}"
        f"{r.errored_count:>9}{total_tok:>12}"
        f"{'$' + format(r.cost_usd, '.5f'):>12}"
    )
print(f"  {'-' * 68}")
total_tickets = sum(len(r.tickets) for r in results)
total_resolved = sum(r.resolved_count for r in results)
total_errored = sum(r.errored_count for r in results)
grand_tok = sum(r.total_input_tokens + r.total_output_tokens for r in results)
grand_cost = sum(r.cost_usd for r in results)
print(
    f"  {'TOTAL':<16}{total_tickets:>9}{total_resolved:>10}{total_errored:>9}"
    f"{grand_tok:>12}{'$' + format(grand_cost, '.5f'):>12}"
)


# ============================================================
# anti-pattern log
# ============================================================
WEEK_DAY = "W1D6"

ENTRIES = [
    {
        "domain": "Agentic Architecture",
        "title": "Fanning out per-ticket without per-ticket error isolation",
        "mistake": (
            "```python\n"
            "# ❌ wrong — one bad conversation kills the batch\n"
            "try:\n"
            "    for ticket in tickets:\n"
            "        run_conversation(ticket, script)\n"
            "except anthropic.APIError as e:\n"
            "    return BatchResult(extraction_failed=True)  # or just re-raise\n"
            "```"
        ),
        "why": (
            "If the loop's try/except wraps the whole iteration, the first API "
            "hiccup on any one ticket aborts every subsequent ticket — the "
            "customer with five problems gets help on zero. Worse, the error "
            "looks like 'pipeline broken' when really it was 'one transient "
            "5xx from one model call'. Partial success is the right contract "
            "for batch processing; the loop has to be the unit of isolation."
        ),
        "fix": (
            "Wrap each iteration body in its own try/except. Count errors, "
            "log per-ticket context, keep going. The result type exposes both "
            "successes and failures so callers can decide what to do.\n\n"
            "```python\n"
            "# ✅ right — per-ticket isolation\n"
            "for ticket in tickets:\n"
            "    try:\n"
            "        state = run_conversation(ticket, script)\n"
            "        result.conversations.append(state)\n"
            "    except anthropic.APIError as e:\n"
            "        result.errored_count += 1\n"
            "        log(f'ticket {ticket.customer_id} errored: {e}')\n"
            "```"
        ),
        "exam_tip": (
            "When the exam frames a question as 'batch processing of N items, "
            "one item triggers a 5xx', the wrong answers are 'retry the whole "
            "batch' or 'abort'. The right answer is 'isolate per-item, surface "
            "partial success'. This is the same pattern as JS Promise.allSettled "
            "vs Promise.all."
        ),
    },
    {
        "domain": "Agentic Architecture",
        "title": "Processing tickets in extraction order instead of severity order",
        "mistake": (
            "Iterating `tickets` in the order the extractor returned them. "
            "For the H-7700 triple-issue email that meant resolving the medium-"
            "severity billing discrepancy *before* the high-severity SSO "
            "lockout and quota breach. Customer sat with login broken while "
            "the agent talked refunds."
        ),
        "why": (
            "Tool-use extraction returns tickets in the order they appeared in "
            "the email — usually chronological or whatever the customer typed "
            "first. That's an artifact of the input format, not a priority "
            "signal. Resolution order should be driven by what's most "
            "expensive to leave broken, which is what the `severity` field "
            "already encodes."
        ),
        "fix": (
            "Sort by a `severity_rank` function before fanning out. Critical "
            "→ high → medium → low. Keep the ordering logic in the pipeline, "
            "not in the extractor or the agent — it's a policy decision the "
            "system makes, not something the model should decide on its own.\n\n"
            "```python\n"
            "_SEVERITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}\n\n"
            "def severity_rank(ticket: SupportTicket) -> int:\n"
            "    return _SEVERITY_ORDER.get(ticket.severity, 99)\n\n"
            "result.tickets = sorted(tickets, key=severity_rank)\n"
            "```"
        ),
        "exam_tip": (
            "Distractor: 'let the LLM decide resolution order'. Resolution "
            "order is a deterministic policy that benefits from being out of "
            "the model — same prompt should always produce the same priority. "
            "Reserve the model for decisions that genuinely require judgment."
        ),
    },
    {
        "domain": "Context Management & Reliability",
        "title": "Hand-summing usage across conversations at every call site",
        "mistake": (
            "```python\n"
            "# ❌ wrong — every caller computes cost from scratch\n"
            "result = process_email(...)\n"
            "input_tok = result.extraction_input_tokens + sum(c.total_input_tokens for c in result.conversations)\n"
            "cost = input_tok / 1_000_000 * 1.0 + ...   # somebody will get this wrong\n"
            "```"
        ),
        "why": (
            "If aggregation lives at the call site, every dashboard, report, "
            "and downstream pipeline reinvents the same arithmetic. The first "
            "time you add a new cost source (cached prompt tokens, tool "
            "execution overhead, a second model in a tiered strategy), every "
            "consumer is out of date and you can't tell which one to trust."
        ),
        "fix": (
            "Encode the aggregation as a property on the result type. Callers "
            "depend on a stable shape (`result.cost_usd`, `result.total_input_tokens`) "
            "and the pipeline owns the math. Future cost sources extend the "
            "property; consumers don't change.\n\n"
            "```python\n"
            "@dataclass\n"
            "class BatchResult:\n"
            "    extraction_input_tokens: int = 0\n"
            "    extraction_output_tokens: int = 0\n"
            "    conversations: list[ConversationState] = field(default_factory=list)\n\n"
            "    @property\n"
            "    def total_input_tokens(self) -> int:\n"
            "        return self.extraction_input_tokens + sum(\n"
            "            c.total_input_tokens for c in self.conversations\n"
            "        )\n\n"
            "    @property\n"
            "    def cost_usd(self) -> float:\n"
            "        return (self.total_input_tokens / 1_000_000 * IN_RATE\n"
            "                + self.total_output_tokens / 1_000_000 * OUT_RATE)\n"
            "```"
        ),
        "exam_tip": (
            "When the exam describes a system where 'three teams report "
            "different LLM costs for the same workload', the diagnosis isn't "
            "'one team is lying' — it's 'aggregation is happening in three "
            "places instead of one'. Push the math down into the result type."
        ),
    },
]


print()
write_day(WEEK_DAY, ENTRIES)
rebuild_master()
