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
