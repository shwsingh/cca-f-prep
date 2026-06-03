"""
W1D2 — System prompts + XML-structured output

Goal: see how the *system* parameter changes Claude's behavior, and use XML tags
to get parseable structure out of free-form text.
"""
 
import os
import re
import anthropic
from dotenv import load_dotenv

load_dotenv()
os.makedirs("notes", exist_ok=True)

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

# ---------- anti-pattern log ----------
week_day = "W1D2"  # change this each day
os.makedirs(f"notes/{week_day}", exist_ok=True)

with open(f"notes/{week_day}/anti-patterns.md", "a") as f:
    f.write("\n## W1D2 — System Prompts & Structure\n")
    f.write("❌ Stuffing role + rules into every user message\n")
    f.write("   Fix: put persona and rules in `system`; user messages stay clean turns\n\n")
    f.write("❌ Free-form output when you need to parse it\n")
    f.write("   Fix: ask for XML tags + regex-extract; reject responses missing required tags\n")

# ---------- regenerate master summary ----------
def build_summary():
    import glob
    summary = "# Anti-Patterns Log\n\nCumulative findings across all days:\n"
    
    # find all W1D*/anti-patterns.md files, sorted by week/day
    day_files = sorted(glob.glob("notes/W1D*/anti-patterns.md"))
    
    for filepath in day_files:
        with open(filepath, "r") as f:
            summary += f.read()
    
    # write the master summary
    with open("notes/ANTI_PATTERNS_SUMMARY.md", "w") as f:
        f.write(summary)
    
    print("\n✅ notes/ANTI_PATTERNS_SUMMARY.md regenerated")
    print("\nCURRENT SUMMARY:")
    print(summary)

build_summary()