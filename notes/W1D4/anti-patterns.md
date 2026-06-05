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
