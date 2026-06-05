# CCA-F Progress Log

One row per study day. Skips Sundays.

| Day | Date       | Topic                                          | Domain             | Score | Notes |
|-----|------------|------------------------------------------------|--------------------|-------|-------|
| 3   | 2026-06-04 | Structured extraction (XML-guided JSON schema) | Prompt Engineering | ⭐⭐⭐⭐⭐ | Schema-validated extractor live under `meterflow/extractors/`; 4 fixtures (clean, rambling, terse, missing-id fallback) extracted cleanly. |
| 4   | 2026-06-05 | Stateful support-agent conversation loop       | Agentic Architecture | ⭐⭐⭐⭐⭐ | `meterflow/agents/support_agent.py` is now the Scenario 1 spine. Happy path resolves in 3 turns, escalation correctly does not resolve in 5. Caught and corrected wrong claim about server-side role-alternation enforcement; rewrote the anti-pattern around the real silent-merge failure mode. |
