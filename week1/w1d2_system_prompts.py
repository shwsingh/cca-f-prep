"""
W1D2 — System prompts + XML-structured output

Goal: see how the *system* parameter changes Claude's behavior, and use XML tags
to get parseable structure out of free-form text.
"""

import os
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.anti_patterns import write_day, rebuild_master  # noqa: E402

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5-20251001"


def ask(system: str, user: str, max_tokens: int = 300) -> str:
    r = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    print(f"  tokens — in: {r.usage.input_tokens}, out: {r.usage.output_tokens} (cap: {max_tokens})")
    return r.content[0].text


# ---------- 1. Same user prompt, two system prompts ----------
print("=" * 60)
print("TEST 1 — system prompt changes tone + scope")
print("=" * 60)

user_q = "Customer A-1042 says they were double-charged $49 in May. What do I do?"
terse_sys = "You are a MeterFlow billing agent. Reply in ONE sentence. No greetings."
verbose_sys = (
    "You are a friendly MeterFlow billing support agent. "
    "Always greet the customer, explain the steps you will take, and end with reassurance."
)
print("\n[terse system]")
print(ask(terse_sys, user_q, max_tokens=80))
print("\n[verbose system]")
print(ask(verbose_sys, user_q, max_tokens=250))


# ---------- 2. XML-tagged output for downstream parsing ----------
print("\n" + "=" * 60)
print("TEST 2 — XML tags give parseable structure")
print("=" * 60)

triage_sys = """You are a MeterFlow ticket triage agent.
For every ticket, respond ONLY in this exact format:

<category>billing | technical | account | other</category>
<priority>low | medium | high | urgent</priority>
<summary>one short sentence</summary>
<next_action>what the human agent should do next</next_action>

Do not include any text outside these tags."""

ticket = (
    "Hi — our prod ingestion has been failing for 2 hours, "
    "MeterFlow webhook returns 500. We're losing usage events. Account E-9981."
)

raw = ask(triage_sys, ticket, max_tokens=400)
print("\nRAW MODEL OUTPUT:")
print(raw)


def extract(tag: str, text: str) -> str | None:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return m.group(1).strip() if m else None


print("\nPARSED:")
for tag in ("category", "priority", "summary", "next_action"):
    print(f"  {tag:12s}: {extract(tag, raw)}")


# ---------- 3. Anti-pattern: instructions in user message vs system ----------
print("\n" + "=" * 60)
print("TEST 3 — why instructions belong in `system`, not `user`")
print("=" * 60)

mixed = ask(
    system="",
    user="You are a MeterFlow agent. Reply in one sentence. "
         "Customer asks: when does my invoice generate?",
    max_tokens=100,
)
clean = ask(
    system="You are a MeterFlow agent. Reply in one sentence.",
    user="When does my invoice generate?",
    max_tokens=100,
)
print(f"\n[instructions in user message]\n  {mixed}")
print(f"\n[instructions in system  ]\n  {clean}")
print(
    "\nNote: the second form is what every multi-turn conversation needs — "
    "stable persona in `system`, only the customer turn in `messages`."
)


# ============================================================
# anti-pattern log — data only; rendering lives in scripts/anti_patterns.py
# ============================================================
WEEK_DAY = "W1D2"

ENTRIES = [
    {
        "domain": "Prompt Engineering",
        "title": "Stuffing role + rules into every user message",
        "mistake": (
            "```python\n"
            "# ❌ wrong\n"
            "messages = [{\n"
            '    "role": "user",\n'
            '    "content": "You are a MeterFlow agent. Reply in one sentence. "\n'
            '               "Customer asks: when does my invoice generate?"\n'
            "}]\n"
            "```"
        ),
        "why": (
            "The persona drifts across turns, can't be prompt-cached, and the `messages` "
            "list now mixes 'what the customer said' with 'what the agent is.' Multi-turn "
            "conversations become unreadable and every turn re-pays the token cost of the rules."
        ),
        "fix": (
            "Put persona and rules in `system`; keep `messages` as pure user/assistant turns.\n\n"
            "```python\n"
            "# ✅ right\n"
            "client.messages.create(\n"
            "    model=MODEL,\n"
            '    system="You are a MeterFlow agent. Reply in one sentence.",\n'
            '    messages=[{"role": "user", "content": "When does my invoice generate?"}],\n'
            ")\n"
            "```"
        ),
        "exam_tip": (
            "Watch for distractors that say 'include the role in the first user message for "
            "clarity.' That's wrong — `system` exists exactly so you don't have to."
        ),
    },
    {
        "domain": "Prompt Engineering",
        "title": "Free-form output when you need to parse it",
        "mistake": (
            "Asking the model to 'categorize this ticket and tell me the priority' "
            "and then trying to grep the answer."
        ),
        "why": (
            "Model output varies — sometimes `Priority: high`, sometimes `I'd say this is high "
            "priority`, sometimes a paragraph. Your parser breaks on the first variant it "
            "didn't see."
        ),
        "fix": (
            "Demand XML tags in the system prompt and extract with regex. Reject responses "
            "missing required tags.\n\n"
            "```python\n"
            'system = """Respond ONLY in this format. No text outside the tags:\n'
            "<category>billing | technical | account | other</category>\n"
            '<priority>low | medium | high | urgent</priority>"""\n\n'
            "import re\n"
            "def extract(tag, text):\n"
            '    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)\n'
            "    return m.group(1).strip() if m else None\n"
            "```"
        ),
        "exam_tip": (
            "JSON mode is the other right answer for structured output. XML tags are the right "
            "answer when you also want to *mix* prose and structure in one response "
            "(e.g. `<thinking>...</thinking><answer>...</answer>`)."
        ),
    },
    {
        "domain": "Tool Design & MCP",
        "title": "Forgot to append assistant turn before tool_result",
        "mistake": (
            "After Claude returns `stop_reason == \"tool_use\"`, you run the tool and POST a new "
            "user message containing the `tool_result` — but you forgot to first append Claude's "
            "assistant turn (the one with the `tool_use` block) to `messages`.\n\n"
            "```python\n"
            "# ❌ wrong — skips the assistant turn\n"
            'messages.append({"role": "user", "content": "What\'s the weather in SF?"})\n'
            "response = client.messages.create(..., messages=messages)\n"
            "# response has tool_use block, you call the tool, then:\n"
            "messages.append({\n"
            '    "role": "user",\n'
            '    "content": [{"type": "tool_result", "tool_use_id": tu_id, "content": "72°F"}]\n'
            "})  # API rejects: tool_result has no matching tool_use turn above it\n"
            "```"
        ),
        "why": (
            "The API validates conversation shape: a `tool_result` block in a user turn MUST be "
            "preceded by an assistant turn containing a `tool_use` block with the matching "
            "`tool_use_id`. Skipping the assistant turn looks tidy in code but the conversation "
            "is malformed."
        ),
        "fix": (
            "```python\n"
            "# ✅ right — append BOTH turns\n"
            'messages.append({"role": "assistant", "content": response.content})\n'
            "messages.append({\n"
            '    "role": "user",\n'
            '    "content": [{"type": "tool_result", "tool_use_id": tu_id, "content": "72°F"}]\n'
            "})\n"
            "```"
        ),
        "exam_tip": (
            "The wrong answer on the exam looks like it goes `user → tool_result` directly. "
            "The correct shape is always "
            "`user → assistant(tool_use) → user(tool_result) → assistant(final answer)`."
        ),
    },
]


print()
write_day(WEEK_DAY, ENTRIES)
rebuild_master()
