<!-- domain: Tool Design & MCP -->
### W1D5 — Reaching for prompt-only JSON when tool use is the right answer

**The mistake**
Building structured extraction by stuffing a schema into the system prompt and parsing the model's free-text reply with a regex, even when the API has a typed tool_use mechanism that does exactly this job.

**Why it fails**
Prompt-only structured output couples your contract to a string-match: the model has to remember to wrap output in `<ticket_json>` AND emit JSON that happens to parse AND match your Pydantic schema. Each of those is a place the model can drift. Tool use moves the contract into the API: the model is told 'call this function with this signature', and the response comes back as a typed `ToolUseBlock` with `input: dict[str, Any]` you can validate directly. The contract is enforced by the API surface, not by your prompt's politeness.

**Fix**
```python
# ✅ tool use as structured output
tool = {
    "name": "record_support_tickets",
    "description": "Record one or more tickets from a customer email.",
    "input_schema": {"type": "object", "properties": {...}, "required": [...]},
}
r = client.messages.create(
    model=MODEL, tools=[tool],
    tool_choice={"type": "tool", "name": "record_support_tickets"},
    messages=[...],
)
assert r.stop_reason == "tool_use"
tickets = next(b for b in r.content if b.type == "tool_use").input["tickets"]
```

**Exam tip**
When the exam describes a task as 'extract a list of X', tool use is almost always the right answer. Prompt-only JSON is the right answer only when the model also needs to emit prose (e.g. chain-of-thought + final answer) in the same turn — tool use makes that awkward.

---

<!-- domain: Tool Design & MCP -->
### W1D5 — Reading the tool_use block before checking stop_reason

**The mistake**
```python
# ❌ wrong — assume the model called the tool
tool_block = next(b for b in r.content if b.type == 'tool_use')
tickets = tool_block.input['tickets']  # StopIteration if model declined
```

**Why it fails**
Without `tool_choice={'type': 'tool', 'name': ...}`, the model is FREE to reply with prose ('I don't have enough info to extract tickets from this') instead of calling the tool. Then `response.content` has only TextBlocks, the `next()` raises `StopIteration`, and the routing layer crashes on a perfectly valid model response. Even WITH forced tool use, a future model update could change defaults — branching on stop_reason is the durable check.

**Fix**
Branch on `stop_reason` first. Treat anything other than 'tool_use' as a model refusal and surface it explicitly.

```python
# ✅ right
if r.stop_reason != 'tool_use':
    raise ValueError(f'model refused tool; reason={r.stop_reason!r}')
tool_block = next(b for b in r.content if b.type == 'tool_use')
tickets = tool_block.input['tickets']
```

**Exam tip**
Five `stop_reason` values: `end_turn`, `max_tokens`, `stop_sequence`, `tool_use`, `pause_turn`. Each demands a different follow-up. Memorize the branching matrix — the exam loves this.

---

<!-- domain: Tool Design & MCP -->
### W1D5 — Hand-typing the tool input_schema instead of generating it

**The mistake**
Maintaining a Pydantic model AND a hand-written JSON Schema dict for the tool's input_schema. The two drift the first time you add a field — model validation passes, the tool's schema is missing the new key, the model leaves it out, the routing layer breaks.

**Why it fails**
Two sources of truth always become two definitions of truth. The Pydantic model is already the canonical definition of `SupportTicket`; the tool input_schema has to agree with it on every field, type, and enum. The only way to keep them aligned is to derive one from the other.

**Fix**
Generate the tool input_schema from the Pydantic model. Pydantic 2 emits a JSON Schema dict natively; strip the `title` keys Pydantic adds and you have a tool-ready schema.

```python
def tool_schema_from_pydantic(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    schema.pop('title', None)
    for prop in schema.get('properties', {}).values():
        prop.pop('title', None)
    return schema

TOOL_SCHEMA = {
    'name': 'record_support_tickets',
    'input_schema': {
        'type': 'object',
        'properties': {'tickets': {'type': 'array',
                                    'items': tool_schema_from_pydantic(SupportTicket)}},
        'required': ['tickets'],
    },
}
```

**Exam tip**
Distractor: 'tool input_schemas should be hand-tuned for the model's reading.' They shouldn't — they're a contract, not a prompt. Derive from your domain model and trust the schema to do its job.
