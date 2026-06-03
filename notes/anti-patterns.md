# CCA-F Anti-Patterns

Add one entry every day. These are your highest-leverage exam revision asset.

Each entry has the same shape so you can scan fast:

> **The mistake** — what you actually did
> **Why it fails** — the mechanism, not the symptom
> **Fix** — the minimal correct version (often with a code snippet)
> **Exam tip** — the distractor answer to *not* pick

Domain percentages reflect CCA-F exam weighting.

---

## 🧠 Prompt Engineering — 20%

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
The persona drifts across turns, can't be prompt-cached, and the `messages` list now mixes "what the customer said" with "what the agent is." Multi-turn conversations become unreadable and every turn re-pays the token cost of the rules.

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
Watch for distractors that say "include the role in the first user message for clarity." That's wrong — `system` exists exactly so you don't have to.

---

### W1D2 — Free-form output when you need to parse it

**The mistake**
Asking the model to "categorize this ticket and tell me the priority" and then trying to grep the answer.

**Why it fails**
Model output varies — sometimes "Priority: high", sometimes "I'd say this is high priority", sometimes a paragraph. Your parser breaks on the first variant it didn't see.

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

## 🔧 Tool Design & MCP — 18%

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

## 📊 Context Management & Reliability — 15%

*(none yet — Week 2+)*

---

## 💻 Claude Code — 20%

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
