"""
W1D3 — Structured extraction (XML-guided JSON schema)

Goal: extract reliable, schema-validated fields from messy customer support
emails. The right pattern is: schema in `<schema>`, an example in `<example>`,
output wrapped in `<ticket_json>`, then Pydantic-validate before trusting it.

The actual extractor lives in meterflow/extractors/ticket_extractor.py so
future routing/triage layers can import the same contract.
"""

import json
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from meterflow.extractors import extract_ticket  # noqa: E402
from scripts.anti_patterns import write_day, rebuild_master  # noqa: E402

load_dotenv()


# ---------- Fixtures: realistic noise (signatures, forwards, typos) ----------
RAW_TICKETS: list[tuple[str, str]] = [
    (
        "clean_billing",
        """From: priya.kapoor@acme.io
Subject: Double charge on May invoice

Hi MeterFlow team,

Account A-1042 here. We were charged $49 twice on May 14 for the May
billing period. Could you refund one of the charges? No rush, but please
confirm.

Thanks,
Priya
--
Priya Kapoor · Platform Eng · Acme
""",
    ),
    (
        "rambling_multi_issue",
        """Fwd: ugh

---------- Forwarded message ---------
From: dev@northwind.test
Subject: a few things

hey so first off our login is broken half the time (SSO via okta) which is
making my team crazy. also unrelated but we hit the 10M event quota
yesterday and the dashboard didn't warn us at all?? account is N-7781,
this is becoming a pattern honestly. if this doesn't get fixed by friday
we're escalating. billing for june is gonna be a mess too I bet.

—jamie
sent from my phone, excuse typos
""",
    ),
    (
        "terse_api_error",
        """Subject: 500 on /v1/events
Account: C-3310

POST /v1/events returns 500 since 09:14 UTC. Webhook retries piling up.
Need RCA.
""",
    ),
    (
        # Deliberate failure case (step 8). Prompt tells the model to fall
        # back to customer_id="unknown" rather than refuse, so this should
        # extract cleanly with that sentinel — not raise.
        "missing_customer_id",
        """Subject: question

How do I rotate my API key? The docs link in the dashboard 404s.
""",
    ),
]


# ---------- Run ----------
print("=" * 60)
print("W1D3 — extracting structured tickets from 4 raw emails")
print("=" * 60)

results = []
for label, email in RAW_TICKETS:
    print(f"\n[{label}]")
    try:
        ticket = extract_ticket(email)
        results.append(ticket)
        print(json.dumps(ticket.model_dump(), indent=2))
    except ValueError as e:
        print(f"  ❌ extraction failed: {e}")

print("\n" + "-" * 60)
print("Severity buckets:")
for sev, n in Counter(t.severity for t in results).most_common():
    print(f"  {sev:8s}: {n}")


# ============================================================
# anti-pattern log
# ============================================================
WEEK_DAY = "W1D3"

ENTRIES = [
    {
        "domain": "Prompt Engineering",
        "title": "Trusting model JSON without schema validation",
        "mistake": (
            "```python\n"
            "# ❌ wrong\n"
            "text = response.content[0].text\n"
            "ticket = json.loads(text)\n"
            "route_to(ticket['severity'])   # KeyError or wrong enum at runtime\n"
            "```"
        ),
        "why": (
            "Even at temperature=0, models occasionally emit extra keys, drop fields, or "
            "pick an out-of-enum value ('urgent' instead of 'critical'). Downstream code "
            "that assumes the shape will crash in production on the email that triggers it."
        ),
        "fix": (
            "Define the contract once as a Pydantic model and validate the JSON before "
            "anyone touches it. Schema violations become explicit, not silent.\n\n"
            "```python\n"
            "# ✅ right\n"
            "class SupportTicket(BaseModel):\n"
            "    severity: Literal['low','medium','high','critical']\n"
            "    ...\n\n"
            "ticket = SupportTicket.model_validate_json(payload)  # raises on mismatch\n"
            "```"
        ),
        "exam_tip": (
            "The wrong answer says 'parse with json.loads and trust the keys.' The right "
            "answer pairs the prompt's schema with code-side validation — same schema, "
            "two enforcement points."
        ),
    },
    {
        "domain": "Prompt Engineering",
        "title": "Describing the schema in prose instead of <schema> tags",
        "mistake": (
            "Writing 'Return a JSON object with customer_id (string), severity (low/med/"
            "high/critical), etc.' as a paragraph in the system prompt."
        ),
        "why": (
            "Prose schemas are ambiguous — Claude has to guess where one field's description "
            "ends and the next begins. XML-tagged schemas give the model a visible structure "
            "that mirrors what you want back, and they're easy to update without rewriting "
            "the surrounding instructions."
        ),
        "fix": (
            "Wrap the schema in `<schema>...</schema>` and the example in `<example>...`. "
            "Wrap the model's output in a dedicated tag (`<ticket_json>`) so a regex can "
            "isolate it even if the model adds a stray newline.\n\n"
            "```python\n"
            'SYSTEM = """...\n'
            "<schema>\n"
            '  { "customer_id": "string", "severity": "low|medium|high|critical", ... }\n'
            "</schema>\n"
            "<example>\n"
            "  <email>...</email>\n"
            "  <ticket_json>{...}</ticket_json>\n"
            '</example>"""\n'
            "```"
        ),
        "exam_tip": (
            "When the exam asks 'how should you instruct Claude to return structured data,' "
            "the wrong answers usually say 'in plain English' or 'with code comments.' "
            "Right answer: XML-delimited schema + a worked example."
        ),
    },
    {
        "domain": "Context Management & Reliability",
        "title": "Non-zero temperature for extraction",
        "mistake": (
            "Leaving `temperature` unset (defaults to 1.0) on a structured-extraction call. "
            "Different runs against the same email return different severities or summaries."
        ),
        "why": (
            "Extraction is deterministic by nature — there is one right answer for "
            "'what's the customer_id in this email'. Sampling variance just adds flakiness "
            "to your eval suite and your routing decisions."
        ),
        "fix": (
            "Set `temperature=0` for any task whose output you intend to parse or compare. "
            "Reserve higher temperature for generation tasks (drafting replies, brainstorming).\n\n"
            "```python\n"
            "client.messages.create(\n"
            "    model=MODEL,\n"
            "    max_tokens=1024,\n"
            "    temperature=0,           # ← extraction\n"
            "    system=SYSTEM,\n"
            "    messages=[...],\n"
            ")\n"
            "```"
        ),
        "exam_tip": (
            "Distractor pattern: 'use temperature=0.7 for creative routing'. Routing is not "
            "creative. The exam expects temperature=0 for classification, extraction, and "
            "any deterministic decision."
        ),
    },
]


print()
write_day(WEEK_DAY, ENTRIES)
rebuild_master()
