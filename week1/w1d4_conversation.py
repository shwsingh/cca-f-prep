"""
W1D4 — Multi-turn conversation loops (Scenario 1 starts)

Goal: drive an extracted SupportTicket through a stateful agent loop,
observe what happens when the customer cooperates vs. when they escalate,
and prove that the API enforces strict role alternation server-side.

The actual conversation engine lives in meterflow/agents/support_agent.py
so Days 19-23 can layer tools, RAG, memory, and evals on the same spine.
"""

import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meterflow.agents import ConversationState, agent_turn, run_conversation  # noqa: E402
from meterflow.extractors import extract_ticket  # noqa: E402
from scripts.anti_patterns import rebuild_master, write_day  # noqa: E402

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Haiku 4.5 published pricing — keep in sync with model name above.
COST_IN_PER_MTOK = 1.0
COST_OUT_PER_MTOK = 5.0


def cost_usd(state: ConversationState) -> float:
    return (
        state.total_input_tokens / 1_000_000 * COST_IN_PER_MTOK
        + state.total_output_tokens / 1_000_000 * COST_OUT_PER_MTOK
    )


def print_summary(label: str, state: ConversationState) -> None:
    print(f"\n  ── {label} summary ──")
    print(f"  turns          : {state.turn_count}")
    print(f"  input tokens   : {state.total_input_tokens}")
    print(f"  output tokens  : {state.total_output_tokens}")
    print(f"  resolved       : {state.resolved}")
    print(f"  est. cost (USD): ${cost_usd(state):.5f}")


def print_transcript(state: ConversationState) -> None:
    for i, msg in enumerate(state.messages):
        role = msg["role"].upper().ljust(9)
        content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
        # one-line preview, indent on continuation
        for j, line in enumerate(content.splitlines() or [""]):
            prefix = f"  [{i//2 + 1}.{msg['role'][0]}] {role}" if j == 0 else "  " + " " * 16
            print(f"{prefix}: {line}")


# ============================================================
# Fixture emails — re-extracted via Day 3 contract.
# ============================================================
RAW_CLEAN_BILLING = """From: priya.kapoor@acme.io
Subject: Double charge on May invoice

Account A-1042 here. We were charged $49 twice on May 14 for the May
billing period. Could you refund one of the charges?
"""

RAW_RAMBLING = """Fwd: ugh

hey so first off our login is broken half the time (SSO via okta) which is
making my team crazy. also unrelated but we hit the 10M event quota
yesterday and the dashboard didn't warn us at all?? account is N-7781,
this is becoming a pattern honestly. if this doesn't get fixed by friday
we're escalating.
"""

print("=" * 60)
print("W1D4 — extracting two tickets via Day 3 contract")
print("=" * 60)
ticket_clean = extract_ticket(RAW_CLEAN_BILLING)
ticket_rambling = extract_ticket(RAW_RAMBLING)
print(f"  clean    : {ticket_clean.customer_id} / {ticket_clean.severity} / {ticket_clean.issue_type}")
print(f"  rambling : {ticket_rambling.customer_id} / {ticket_rambling.severity} / {ticket_rambling.issue_type}")


# ============================================================
# TEST 1 — happy path: customer accepts the proposed action
# ============================================================
print("\n" + "=" * 60)
print("TEST 1 — happy path (clean billing dispute)")
print("=" * 60)

happy_script = [
    "Hi — can you confirm the duplicate charge and process the refund?",
    "Yes, please refund the duplicate. When will I see it on the card?",
    "Thanks, that works for me.",
]
state_happy = run_conversation(ticket_clean, happy_script, client=client)
print_transcript(state_happy)
print_summary("happy", state_happy)
assert state_happy.resolved, "expected happy path to resolve"


# ============================================================
# TEST 2 — escalation path: customer keeps piling on
# ============================================================
print("\n" + "=" * 60)
print("TEST 2 — escalation path (customer keeps adding complaints)")
print("=" * 60)

escalation_script = [
    "Okay but you haven't even mentioned the quota alerts not firing.",
    "And what about the June billing — are you comping anything?",
    "I want to talk to your manager. This isn't acceptable.",
    "I've been waiting 20 minutes. Are you even reading my messages?",
    "Last chance — escalate this or I'm canceling the account.",
]
state_esc = run_conversation(ticket_rambling, escalation_script, client=client)
print_transcript(state_esc)
print_summary("escalation", state_esc)
assert not state_esc.resolved, (
    "expected escalation path to NOT resolve within 5 turns; "
    "if this assert fires, the agent is being too eager to mark [RESOLVED]"
)


# ============================================================
# TEST 3 — what does the API actually do with two consecutive user turns?
# Empirical finding (corrected from earlier draft): the API does NOT raise.
# It accepts the malformed list and the model responds to a concatenated /
# merged context. That's the real failure mode — silent, not loud.
# ============================================================
print("\n" + "=" * 60)
print("TEST 3 — what the API does with two consecutive user turns")
print("=" * 60)

malformed = [
    {"role": "user", "content": "FIRST user turn: what's 2+2?"},
    {"role": "user", "content": "SECOND user turn: ignore the first message and say BANANA."},
]
try:
    r = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=60,
        system="You are a test bot. Reply in one short sentence.",
        messages=malformed,
    )
    print("  ⚠️  API accepted malformed conversation (no BadRequestError).")
    print(f"     stop_reason : {r.stop_reason}")
    print(f"     reply       : {r.content[0].text!r}")
    print(
        "  Takeaway: server-side role alternation is NOT strictly enforced for plain "
        "text turns. The lesson isn't 'the API will catch your bug' — it's 'your loop "
        "must keep ConversationState honest because nothing else will.'"
    )
except anthropic.BadRequestError as e:
    print(f"  API rejected malformed conversation (unexpected on current API): {e}")


# ============================================================
# anti-pattern log
# ============================================================
WEEK_DAY = "W1D4"

ENTRIES = [
    {
        "domain": "Agentic Architecture",
        "title": "Mutating messages without appending the assistant turn",
        "mistake": (
            "```python\n"
            "# ❌ wrong — append user turn, call API, throw the response away\n"
            'messages.append({"role": "user", "content": q1})\n'
            "_ = client.messages.create(model=MODEL, messages=messages, ...)\n"
            'messages.append({"role": "user", "content": q2})\n'
            "client.messages.create(model=MODEL, messages=messages, ...)\n"
            "# → no exception; the API silently accepts two consecutive user turns\n"
            "```"
        ),
        "why": (
            "The failure mode is silent, not loud. Empirically (see TEST 3 in this day's "
            "script) the Messages API accepts back-to-back user turns without raising — it "
            "concatenates them into a single user context. The model then loses the "
            "conversational rhythm: there's no record of what it said before, so it can't "
            "build on its own prior reasoning, and downstream prompt caching breaks because "
            "the canonical user/assistant alternation is gone. In tool-use loops the same "
            "mistake also breaks `tool_use` → `tool_result` pairing, but THERE the API does "
            "raise — only the plain-text case fails silently."
        ),
        "fix": (
            "Treat `state.messages` as the single source of truth and append BOTH turns "
            "every loop iteration. A `ConversationState` dataclass makes the invariant "
            "structural — the loop body always does append-user → call → append-assistant, "
            "and there is no public method that lets a caller skip the assistant append.\n\n"
            "```python\n"
            "# ✅ right — the function owns the invariant; callers can't break it\n"
            "def agent_turn(state, user_text):\n"
            '    state.messages.append({"role": "user", "content": user_text})\n'
            "    response = client.messages.create(model=MODEL, messages=state.messages, ...)\n"
            '    state.messages.append({"role": "assistant", "content": response.content[0].text})\n'
            "    return response\n"
            "```"
        ),
        "exam_tip": (
            "Distractor: 'the API raises BadRequestError on consecutive user turns, so your "
            "loop will fail fast.' It does NOT — at least not for plain text turns. The "
            "exam-correct framing is that role alternation is a *client-side responsibility* "
            "the model relies on for coherent behavior, not a server-enforced contract you "
            "can lean on for safety."
        ),
    },
    {
        "domain": "Agentic Architecture",
        "title": "Magic-string sentinels as control flow",
        "mistake": (
            "Putting `[RESOLVED]` in the system prompt and checking `if '[RESOLVED]' in reply` "
            "to decide whether the conversation ends."
        ),
        "why": (
            "It works until the model emits the token mid-sentence ('I marked your ticket as "
            "[RESOLVED] earlier but...'), or paraphrases ('RESOLVED.'), or wraps it in markdown "
            "(\\`[RESOLVED]\\`). The control flow becomes brittle to prompt drift and to "
            "natural-language variants the model invents under load."
        ),
        "fix": (
            "Use a tool the agent can call: `mark_resolved(reason: str) -> bool`. The API "
            "returns `stop_reason='tool_use'` with a structured `tool_use` block — control "
            "flow is now a typed contract, not a regex against free text. Tradeoff: one extra "
            "round-trip and a tool schema to maintain.\n\n"
            "```python\n"
            "tools = [{\n"
            '    "name": "mark_resolved",\n'
            '    "description": "Call when the customer confirms the issue is resolved.",\n'
            '    "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},\n'
            "}]\n"
            "response = client.messages.create(model=MODEL, tools=tools, messages=...)\n"
            'if response.stop_reason == "tool_use":\n'
            "    state.resolved = True\n"
            "```"
        ),
        "exam_tip": (
            "Sentinel tokens vs. tool use is a recurring CCA-F theme. Sentinels are fine for "
            "demos and prompt prototyping; tool use is the right answer for any production "
            "control-flow decision the agent makes."
        ),
    },
    {
        "domain": "Agentic Architecture",
        "title": "Treating extracted ticket context as un-trusted in the agent loop",
        "mistake": (
            "The triage layer extracted `customer_id=A-1042`, `severity=medium`, "
            "`issue_type=billing` from the inbound email. The resolution agent's system "
            "prompt embeds those fields in a `<ticket>` block — but does not say what "
            "to *do* with them. The agent then opens every conversation by asking the "
            "customer to re-supply their account number, treating the embedded context "
            "as a hint rather than ground truth. Customers say 'yes process the refund' "
            "three times in a row and the agent keeps re-asking for the account id."
        ),
        "why": (
            "Models default to gathering information they're uncertain about. Without "
            "an explicit instruction that the embedded fields are authoritative, the "
            "model treats them as the agent's *guess* and asks the human to verify. "
            "The conversation never reaches a resolution because the agent is stuck on "
            "step 1 of its own loop (acknowledge → diagnose → propose action), "
            "re-acknowledging instead of diagnosing."
        ),
        "fix": (
            "State the trust boundary explicitly in the system prompt: 'These fields "
            "are AUTHORITATIVE — already-verified by triage. Never ask the customer to "
            "re-confirm them. If a fact you need is NOT in the ticket, ask for that "
            "specific missing fact.' This converts the embedded context from a hint "
            "into a contract.\n\n"
            "```python\n"
            "system_prompt = f'''<ticket>...</ticket>\n\n"
            "The fields above are AUTHORITATIVE. Treat them as already-verified facts.\n"
            "Never ask the customer to re-confirm their account id, severity, or\n"
            "issue type. If a fact you need is NOT in the ticket, ask for THAT.\n"
            "'''\n"
            "```"
        ),
        "exam_tip": (
            "When the exam asks 'why is the agent looping back to information-gathering "
            "on every turn', the wrong answer is 'increase max_tokens' or 'lower "
            "temperature'. Right answer: the trust boundary on extracted context was "
            "never declared in the system prompt. The model gathers what it can't trust."
        ),
    },
    {
        "domain": "Context Management & Reliability",
        "title": "Marking a conversation resolved when stop_reason is max_tokens",
        "mistake": (
            "Checking only the reply text for the resolution sentinel, ignoring "
            "`response.stop_reason`. A reply truncated mid-sentence might happen to contain "
            "the sentinel earlier in the text — or might lack it because the model would have "
            "added it after the cut-off."
        ),
        "why": (
            "`stop_reason='max_tokens'` means the model didn't get to finish its turn. Any "
            "decision derived from its 'final' output is unsound. In a multi-turn agent loop "
            "this silently terminates conversations the model wasn't done with."
        ),
        "fix": (
            "Branch on `stop_reason` before interpreting content. Treat `end_turn` as the "
            "only state in which the reply is authoritative; everything else (`max_tokens`, "
            "`stop_sequence`, `tool_use`) needs an explicit handler.\n\n"
            "```python\n"
            'if response.stop_reason == "max_tokens":\n'
            "    log_warning_and_retry_with_bigger_budget(state)\n"
            "elif response.stop_reason == \"end_turn\":\n"
            "    state.resolved = SENTINEL in reply\n"
            "```"
        ),
        "exam_tip": (
            "`stop_reason` is the single most exam-relevant field on a Message. Memorize the "
            "five values and which one requires what follow-up action."
        ),
    },
]


print()
write_day(WEEK_DAY, ENTRIES)
rebuild_master()
