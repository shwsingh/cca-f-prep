# CCA-F Anti-Patterns

Add one entry every day. These are your highest-leverage exam revision asset.

Each entry has the same shape so you can scan fast:

> **The mistake** — what you actually did
> **Why it fails** — the mechanism, not the symptom
> **Fix** — the minimal correct version (often with a code snippet)
> **Exam tip** — the distractor answer to *not* pick

Domain percentages reflect CCA-F exam weighting.
This file is regenerated from `notes/W*D*/anti-patterns.md` — edit those, not this.

---

## 🧠 Prompt Engineering — 20%

<!-- domain: Prompt Engineering -->
### W1D2 — Stuffing role + rules into every user message

**The mistake**
```python
# ❌ wrong
messages = [{
    "role": "user",
    "content": "You are a MeterFlow agent. Reply in one sentence. "
               "Customer asks: when does my invoice generate?"
}]
```

**Why it fails**
The persona drifts across turns, can't be prompt-cached, and the `messages` list now mixes 'what the customer said' with 'what the agent is.' Multi-turn conversations become unreadable and every turn re-pays the token cost of the rules.

**Fix**
Put persona and rules in `system`; keep `messages` as pure user/assistant turns.

```python
# ✅ right
client.messages.create(
    model=MODEL,
    system="You are a MeterFlow agent. Reply in one sentence.",
    messages=[{"role": "user", "content": "When does my invoice generate?"}],
)
```

**Exam tip**
Watch for distractors that say 'include the role in the first user message for clarity.' That's wrong — `system` exists exactly so you don't have to.

---

<!-- domain: Prompt Engineering -->
### W1D2 — Free-form output when you need to parse it

**The mistake**
Asking the model to 'categorize this ticket and tell me the priority' and then trying to grep the answer.

**Why it fails**
Model output varies — sometimes `Priority: high`, sometimes `I'd say this is high priority`, sometimes a paragraph. Your parser breaks on the first variant it didn't see.

**Fix**
Demand XML tags in the system prompt and extract with regex. Reject responses missing required tags.

```python
system = """Respond ONLY in this format. No text outside the tags:
<category>billing | technical | account | other</category>
<priority>low | medium | high | urgent</priority>"""

import re
def extract(tag, text):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return m.group(1).strip() if m else None
```

**Exam tip**
JSON mode is the other right answer for structured output. XML tags are the right answer when you also want to *mix* prose and structure in one response (e.g. `<thinking>...</thinking><answer>...</answer>`).

---

<!-- domain: Prompt Engineering -->
### W1D3 — Trusting model JSON without schema validation

**The mistake**
```python
# ❌ wrong
text = response.content[0].text
ticket = json.loads(text)
route_to(ticket['severity'])   # KeyError or wrong enum at runtime
```

**Why it fails**
Even at temperature=0, models occasionally emit extra keys, drop fields, or pick an out-of-enum value ('urgent' instead of 'critical'). Downstream code that assumes the shape will crash in production on the email that triggers it.

**Fix**
Define the contract once as a Pydantic model and validate the JSON before anyone touches it. Schema violations become explicit, not silent.

```python
# ✅ right
class SupportTicket(BaseModel):
    severity: Literal['low','medium','high','critical']
    ...

ticket = SupportTicket.model_validate_json(payload)  # raises on mismatch
```

**Exam tip**
The wrong answer says 'parse with json.loads and trust the keys.' The right answer pairs the prompt's schema with code-side validation — same schema, two enforcement points.

---

<!-- domain: Prompt Engineering -->
### W1D3 — Describing the schema in prose instead of <schema> tags

**The mistake**
Writing 'Return a JSON object with customer_id (string), severity (low/med/high/critical), etc.' as a paragraph in the system prompt.

**Why it fails**
Prose schemas are ambiguous — Claude has to guess where one field's description ends and the next begins. XML-tagged schemas give the model a visible structure that mirrors what you want back, and they're easy to update without rewriting the surrounding instructions.

**Fix**
Wrap the schema in `<schema>...</schema>` and the example in `<example>...`. Wrap the model's output in a dedicated tag (`<ticket_json>`) so a regex can isolate it even if the model adds a stray newline.

```python
SYSTEM = """...
<schema>
  { "customer_id": "string", "severity": "low|medium|high|critical", ... }
</schema>
<example>
  <email>...</email>
  <ticket_json>{...}</ticket_json>
</example>"""
```

**Exam tip**
When the exam asks 'how should you instruct Claude to return structured data,' the wrong answers usually say 'in plain English' or 'with code comments.' Right answer: XML-delimited schema + a worked example.

---

## 🔧 Tool Design & MCP — 18%

<!-- domain: Tool Design & MCP -->
### W1D2 — Forgot to append assistant turn before tool_result

**The mistake**
After Claude returns `stop_reason == "tool_use"`, you run the tool and POST a new user message containing the `tool_result` — but you forgot to first append Claude's assistant turn (the one with the `tool_use` block) to `messages`.

```python
# ❌ wrong — skips the assistant turn
messages.append({"role": "user", "content": "What's the weather in SF?"})
response = client.messages.create(..., messages=messages)
# response has tool_use block, you call the tool, then:
messages.append({
    "role": "user",
    "content": [{"type": "tool_result", "tool_use_id": tu_id, "content": "72°F"}]
})  # API rejects: tool_result has no matching tool_use turn above it
```

**Why it fails**
The API validates conversation shape: a `tool_result` block in a user turn MUST be preceded by an assistant turn containing a `tool_use` block with the matching `tool_use_id`. Skipping the assistant turn looks tidy in code but the conversation is malformed.

**Fix**
```python
# ✅ right — append BOTH turns
messages.append({"role": "assistant", "content": response.content})
messages.append({
    "role": "user",
    "content": [{"type": "tool_result", "tool_use_id": tu_id, "content": "72°F"}]
})
```

**Exam tip**
The wrong answer on the exam looks like it goes `user → tool_result` directly. The correct shape is always `user → assistant(tool_use) → user(tool_result) → assistant(final answer)`.

---

## 🏗 Agentic Architecture — 27%

<!-- domain: Agentic Architecture -->
### W1D1 — Missing stop_reason check

**The mistake**
Read `response.content[0].text` and act on it without first checking `response.stop_reason`.

**Why it fails**
`max_tokens` truncation is **silent** at the content level — you get a half-finished sentence that looks fine until it doesn't. Same for `tool_use`: there's no final text to consume; you must dispatch the tool call instead.

**Fix**
```python
# ✅ right — branch on stop_reason every time
match response.stop_reason:
    case "end_turn":
        return response.content[0].text
    case "max_tokens":
        raise TruncatedError("response was cut off")
    case "tool_use":
        return handle_tool_use(response)
    case "stop_sequence":
        ...
```

The four values you must memorize: `end_turn`, `max_tokens`, `tool_use`, `stop_sequence`.

**Exam tip**
Distractor answers print/use `response.content[0].text` directly with no stop_reason guard. Any answer that bypasses `stop_reason` is wrong in an agent loop.

---

<!-- domain: Agentic Architecture -->
### W1D4 — Mutating messages without appending the assistant turn

**The mistake**
```python
# ❌ wrong — append user turn, call API, throw the response away
messages.append({"role": "user", "content": q1})
_ = client.messages.create(model=MODEL, messages=messages, ...)
messages.append({"role": "user", "content": q2})
client.messages.create(model=MODEL, messages=messages, ...)
# → no exception; the API silently accepts two consecutive user turns
```

**Why it fails**
The failure mode is silent, not loud. Empirically (see TEST 3 in this day's script) the Messages API accepts back-to-back user turns without raising — it concatenates them into a single user context. The model then loses the conversational rhythm: there's no record of what it said before, so it can't build on its own prior reasoning, and downstream prompt caching breaks because the canonical user/assistant alternation is gone. In tool-use loops the same mistake also breaks `tool_use` → `tool_result` pairing, but THERE the API does raise — only the plain-text case fails silently.

**Fix**
Treat `state.messages` as the single source of truth and append BOTH turns every loop iteration. A `ConversationState` dataclass makes the invariant structural — the loop body always does append-user → call → append-assistant, and there is no public method that lets a caller skip the assistant append.

```python
# ✅ right — the function owns the invariant; callers can't break it
def agent_turn(state, user_text):
    state.messages.append({"role": "user", "content": user_text})
    response = client.messages.create(model=MODEL, messages=state.messages, ...)
    state.messages.append({"role": "assistant", "content": response.content[0].text})
    return response
```

**Exam tip**
Distractor: 'the API raises BadRequestError on consecutive user turns, so your loop will fail fast.' It does NOT — at least not for plain text turns. The exam-correct framing is that role alternation is a *client-side responsibility* the model relies on for coherent behavior, not a server-enforced contract you can lean on for safety.

---

<!-- domain: Agentic Architecture -->
### W1D4 — Magic-string sentinels as control flow

**The mistake**
Putting `[RESOLVED]` in the system prompt and checking `if '[RESOLVED]' in reply` to decide whether the conversation ends.

**Why it fails**
It works until the model emits the token mid-sentence ('I marked your ticket as [RESOLVED] earlier but...'), or paraphrases ('RESOLVED.'), or wraps it in markdown (\`[RESOLVED]\`). The control flow becomes brittle to prompt drift and to natural-language variants the model invents under load.

**Fix**
Use a tool the agent can call: `mark_resolved(reason: str) -> bool`. The API returns `stop_reason='tool_use'` with a structured `tool_use` block — control flow is now a typed contract, not a regex against free text. Tradeoff: one extra round-trip and a tool schema to maintain.

```python
tools = [{
    "name": "mark_resolved",
    "description": "Call when the customer confirms the issue is resolved.",
    "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
}]
response = client.messages.create(model=MODEL, tools=tools, messages=...)
if response.stop_reason == "tool_use":
    state.resolved = True
```

**Exam tip**
Sentinel tokens vs. tool use is a recurring CCA-F theme. Sentinels are fine for demos and prompt prototyping; tool use is the right answer for any production control-flow decision the agent makes.

---

<!-- domain: Agentic Architecture -->
### W1D4 — Treating extracted ticket context as un-trusted in the agent loop

**The mistake**
The triage layer extracted `customer_id=A-1042`, `severity=medium`, `issue_type=billing` from the inbound email. The resolution agent's system prompt embeds those fields in a `<ticket>` block — but does not say what to *do* with them. The agent then opens every conversation by asking the customer to re-supply their account number, treating the embedded context as a hint rather than ground truth. Customers say 'yes process the refund' three times in a row and the agent keeps re-asking for the account id.

**Why it fails**
Models default to gathering information they're uncertain about. Without an explicit instruction that the embedded fields are authoritative, the model treats them as the agent's *guess* and asks the human to verify. The conversation never reaches a resolution because the agent is stuck on step 1 of its own loop (acknowledge → diagnose → propose action), re-acknowledging instead of diagnosing.

**Fix**
State the trust boundary explicitly in the system prompt: 'These fields are AUTHORITATIVE — already-verified by triage. Never ask the customer to re-confirm them. If a fact you need is NOT in the ticket, ask for that specific missing fact.' This converts the embedded context from a hint into a contract.

```python
system_prompt = f'''<ticket>...</ticket>

The fields above are AUTHORITATIVE. Treat them as already-verified facts.
Never ask the customer to re-confirm their account id, severity, or
issue type. If a fact you need is NOT in the ticket, ask for THAT.
'''
```

**Exam tip**
When the exam asks 'why is the agent looping back to information-gathering on every turn', the wrong answer is 'increase max_tokens' or 'lower temperature'. Right answer: the trust boundary on extracted context was never declared in the system prompt. The model gathers what it can't trust.

---

## 📊 Context Management & Reliability — 15%

<!-- domain: Context Management & Reliability -->
### W1D3 — Non-zero temperature for extraction

**The mistake**
Leaving `temperature` unset (defaults to 1.0) on a structured-extraction call. Different runs against the same email return different severities or summaries.

**Why it fails**
Extraction is deterministic by nature — there is one right answer for 'what's the customer_id in this email'. Sampling variance just adds flakiness to your eval suite and your routing decisions.

**Fix**
Set `temperature=0` for any task whose output you intend to parse or compare. Reserve higher temperature for generation tasks (drafting replies, brainstorming).

```python
client.messages.create(
    model=MODEL,
    max_tokens=1024,
    temperature=0,           # ← extraction
    system=SYSTEM,
    messages=[...],
)
```

**Exam tip**
Distractor pattern: 'use temperature=0.7 for creative routing'. Routing is not creative. The exam expects temperature=0 for classification, extraction, and any deterministic decision.

---

<!-- domain: Context Management & Reliability -->
### W1D4 — Marking a conversation resolved when stop_reason is max_tokens

**The mistake**
Checking only the reply text for the resolution sentinel, ignoring `response.stop_reason`. A reply truncated mid-sentence might happen to contain the sentinel earlier in the text — or might lack it because the model would have added it after the cut-off.

**Why it fails**
`stop_reason='max_tokens'` means the model didn't get to finish its turn. Any decision derived from its 'final' output is unsound. In a multi-turn agent loop this silently terminates conversations the model wasn't done with.

**Fix**
Branch on `stop_reason` before interpreting content. Treat `end_turn` as the only state in which the reply is authoritative; everything else (`max_tokens`, `stop_sequence`, `tool_use`) needs an explicit handler.

```python
if response.stop_reason == "max_tokens":
    log_warning_and_retry_with_bigger_budget(state)
elif response.stop_reason == "end_turn":
    state.resolved = SENTINEL in reply
```

**Exam tip**
`stop_reason` is the single most exam-relevant field on a Message. Memorize the five values and which one requires what follow-up action.

---

## 💻 Claude Code — 20%

<!-- domain: Claude Code -->
### W1D1 — Hardcoded API key

**The mistake**
```python
# ❌ wrong
client = anthropic.Anthropic(api_key="sk-ant-api03-xxxxxxxxxxxx")
```

**Why it fails**
The key leaks the moment the file is committed, shared in a PR, or pasted into a screenshot. GitHub's secret scanner will find it within minutes; bots clone the key and start spending against your account.

**Fix**
```python
# ✅ right
import os
from dotenv import load_dotenv
load_dotenv()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
```

Plus add `.env` to `.gitignore` **before** the first `git add`.

**Exam tip**
"Rotate the key after committing" is a distractor — the right answer is "never let it reach the commit in the first place." If it *did* leak: rotate first, then scrub history.

---

<!-- domain: Claude Code -->
### W1D1 — Committed .env before adding it to .gitignore

**The mistake**
Ran `git add` / `git commit` on a tree where `.env` exists but `.gitignore` does not yet list it.

**Why it fails**
The secret is now in git history. Deleting `.env` in a follow-up commit does **not** remove it — anyone with the repo can still read it via:
```bash
git log -p .env
git show <old-sha>:.env
```
And the remote's history keeps it forever.

**Fix (prevention)**
```bash
# do this BEFORE the first git add
echo ".env" >> .gitignore
git add .gitignore
```

**Fix (recovery, if it already leaked)**
```bash
# 1. rotate the key in the Anthropic console IMMEDIATELY
# 2. remove it from the index but keep the local file
git rm --cached .env
# 3. scrub from history
git filter-repo --path .env --invert-paths   # or BFG Repo-Cleaner
# 4. force-push
git push --force-with-lease
```

**Exam tip**
"I deleted the .env file in a follow-up commit" is the canonical wrong answer — the secret still lives in the earlier commit's blob and must be treated as compromised.

---
