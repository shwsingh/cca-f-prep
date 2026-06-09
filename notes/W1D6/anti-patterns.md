<!-- domain: Agentic Architecture -->
### W1D6 — Fanning out per-ticket without per-ticket error isolation

**The mistake**
```python
# ❌ wrong — one bad conversation kills the batch
try:
    for ticket in tickets:
        run_conversation(ticket, script)
except anthropic.APIError as e:
    return BatchResult(extraction_failed=True)  # or just re-raise
```

**Why it fails**
If the loop's try/except wraps the whole iteration, the first API hiccup on any one ticket aborts every subsequent ticket — the customer with five problems gets help on zero. Worse, the error looks like 'pipeline broken' when really it was 'one transient 5xx from one model call'. Partial success is the right contract for batch processing; the loop has to be the unit of isolation.

**Fix**
Wrap each iteration body in its own try/except. Count errors, log per-ticket context, keep going. The result type exposes both successes and failures so callers can decide what to do.

```python
# ✅ right — per-ticket isolation
for ticket in tickets:
    try:
        state = run_conversation(ticket, script)
        result.conversations.append(state)
    except anthropic.APIError as e:
        result.errored_count += 1
        log(f'ticket {ticket.customer_id} errored: {e}')
```

**Exam tip**
When the exam frames a question as 'batch processing of N items, one item triggers a 5xx', the wrong answers are 'retry the whole batch' or 'abort'. The right answer is 'isolate per-item, surface partial success'. This is the same pattern as JS Promise.allSettled vs Promise.all.

---

<!-- domain: Agentic Architecture -->
### W1D6 — Processing tickets in extraction order instead of severity order

**The mistake**
Iterating `tickets` in the order the extractor returned them. For the H-7700 triple-issue email that meant resolving the medium-severity billing discrepancy *before* the high-severity SSO lockout and quota breach. Customer sat with login broken while the agent talked refunds.

**Why it fails**
Tool-use extraction returns tickets in the order they appeared in the email — usually chronological or whatever the customer typed first. That's an artifact of the input format, not a priority signal. Resolution order should be driven by what's most expensive to leave broken, which is what the `severity` field already encodes.

**Fix**
Sort by a `severity_rank` function before fanning out. Critical → high → medium → low. Keep the ordering logic in the pipeline, not in the extractor or the agent — it's a policy decision the system makes, not something the model should decide on its own.

```python
_SEVERITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}

def severity_rank(ticket: SupportTicket) -> int:
    return _SEVERITY_ORDER.get(ticket.severity, 99)

result.tickets = sorted(tickets, key=severity_rank)
```

**Exam tip**
Distractor: 'let the LLM decide resolution order'. Resolution order is a deterministic policy that benefits from being out of the model — same prompt should always produce the same priority. Reserve the model for decisions that genuinely require judgment.

---

<!-- domain: Context Management & Reliability -->
### W1D6 — Hand-summing usage across conversations at every call site

**The mistake**
```python
# ❌ wrong — every caller computes cost from scratch
result = process_email(...)
input_tok = result.extraction_input_tokens + sum(c.total_input_tokens for c in result.conversations)
cost = input_tok / 1_000_000 * 1.0 + ...   # somebody will get this wrong
```

**Why it fails**
If aggregation lives at the call site, every dashboard, report, and downstream pipeline reinvents the same arithmetic. The first time you add a new cost source (cached prompt tokens, tool execution overhead, a second model in a tiered strategy), every consumer is out of date and you can't tell which one to trust.

**Fix**
Encode the aggregation as a property on the result type. Callers depend on a stable shape (`result.cost_usd`, `result.total_input_tokens`) and the pipeline owns the math. Future cost sources extend the property; consumers don't change.

```python
@dataclass
class BatchResult:
    extraction_input_tokens: int = 0
    extraction_output_tokens: int = 0
    conversations: list[ConversationState] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return self.extraction_input_tokens + sum(
            c.total_input_tokens for c in self.conversations
        )

    @property
    def cost_usd(self) -> float:
        return (self.total_input_tokens / 1_000_000 * IN_RATE
                + self.total_output_tokens / 1_000_000 * OUT_RATE)
```

**Exam tip**
When the exam describes a system where 'three teams report different LLM costs for the same workload', the diagnosis isn't 'one team is lying' — it's 'aggregation is happening in three places instead of one'. Push the math down into the result type.
