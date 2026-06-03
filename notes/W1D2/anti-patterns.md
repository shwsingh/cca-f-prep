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
