# CCA-F Progress Log

One row per study day. Skips Sundays.

| Day | Date       | Topic                                          | Domain             | Score | Notes |
|-----|------------|------------------------------------------------|--------------------|-------|-------|
| 3   | 2026-06-04 | Structured extraction (XML-guided JSON schema) | Prompt Engineering | ⭐⭐⭐⭐⭐ | Schema-validated extractor live under `meterflow/extractors/`; 4 fixtures (clean, rambling, terse, missing-id fallback) extracted cleanly. |
| 4   | 2026-06-05 | Stateful support-agent conversation loop       | Agentic Architecture | ⭐⭐⭐⭐⭐ | `meterflow/agents/support_agent.py` is now the Scenario 1 spine. Happy path resolves in 3 turns, escalation correctly does not resolve in 5. Caught and corrected wrong claim about server-side role-alternation enforcement; rewrote the anti-pattern around the real silent-merge failure mode. |
| 5   | 2026-06-08 | Multi-ticket extraction via forced tool use    | Tool Design & MCP    | ⭐⭐⭐⭐⭐ | `meterflow/extractors/multi_ticket_extractor.py` introduces tool use as structured output, with tool_schema derived from the Pydantic model. `triple_issue` extracts as 3 tickets (vs. Day 3 collapsing to 1); empty body returns []. Side-by-side comparison: tool use ~2× the cost of prompt-only for 2× the tickets recovered. Also shipped `notes/journey.md` as a scannable Day 1→5 revision asset. |
