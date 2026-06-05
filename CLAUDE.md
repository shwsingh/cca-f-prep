# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

36-day prep for the **Anthropic CCA-F (Certified Architect Foundations)** exam, structured as a daily build of one application: **MeterFlow SupportOps**, a multi-agent billing-support system. Every study day adds one runnable component, and by Day 36 the `meterflow/` package is a complete system covering all 5 exam domains.

Start date: **2026-06-02**. Day numbering skips Sundays. README progress table tracks completion.

## Two-layer architecture (important)

This repo has a deliberate separation. Future-you must respect it.

- **`weekN/wNdN_*.py`** — day exercise scripts. Demo scripts that *run* one concept end to end, print diagnostics, and write that day's anti-patterns. They are entry points, not libraries. They import from `meterflow/`.
- **`meterflow/`** — the capstone package. Production-shaped modules (`meterflow/extractors/`, `meterflow/agents/`, …) that day scripts import. The same contract is reused by every later day. **When a day exercise produces something importable, move it into `meterflow/` and re-export from the day script** — don't duplicate Pydantic models or prompts across days.

Pattern: day script = how you learned it. `meterflow/` module = what the system actually uses.

## Anti-pattern logging pipeline

This is the highest-value exam-prep artifact and has a specific shape — don't fight it.

- Each day script defines `ENTRIES: list[dict]` with keys `domain`, `title`, `mistake`, `why`, `fix`, `exam_tip`.
- It then calls `write_day("W1D3", ENTRIES)` + `rebuild_master()` from `scripts.anti_patterns`.
- Per-day file `notes/W*D*/anti-patterns.md` is the **source of truth** — edit there.
- Master `notes/anti-patterns.md` is **regenerated** from per-day files, grouped by exam domain. **Hand edits to the master are lost on the next rebuild.**
- Domain string MUST be one of the values in `DOMAINS` in `scripts/anti_patterns.py:42` (e.g. `"Prompt Engineering"`, `"Tool Design & MCP"`, `"Agentic Architecture"`, `"Context Management & Reliability"`, `"Claude Code"`). `write_day` raises on unknown domains.

## Slash commands

Project-local commands live in `.claude/commands/`. Don't bypass them.

- `/study [day N | today | week N | scenario N]` — show plan for a day/week/exam scenario.
- `/start` — show today's plan, scaffold the day's exercise file.
- `/checkin` — score today's session 0–5 stars, append a row to `notes/progress.md`.
- `/antipattern` — log one anti-pattern (free-form; the `ENTRIES` pattern above is the preferred path).

Scenario → day mapping is documented in `.claude/commands/study.md`.

## Running things

```bash
# from repo root
source .venv/bin/activate
python week1/wNdN_xxx.py
```

The venv lives at `.venv/` in repo root. `.env` holds `ANTHROPIC_API_KEY` and (for the reminder agent) `STUDY_START_DATE` + SMTP creds.

**Default model** for day scripts is `claude-haiku-4-5-20251001` — cheap, fast, deterministic at `temperature=0`. Reach for `claude-opus-4-7` only when a day's objective explicitly needs reasoning beyond haiku's capability.

## Conventions baked into the exam-prep style

- **`temperature=0` for any task whose output is parsed** (extraction, classification, routing). Higher temperature is reserved for generation (drafting replies).
- **Structured output uses XML-delimited schemas** (`<schema>`, `<example>`, custom output tag like `<ticket_json>`) plus Pydantic validation on the code side. Two enforcement points, same schema.
- **Check `response.stop_reason` on every API call.** `max_tokens` truncation is silent — agents must not treat truncated output as final.
- **Persona/rules go in `system`, never in user messages.** Multi-turn loops must keep `messages` as pure user/assistant turns.
- Per CLAUDE.md repo policy: prefer haiku for any extraction or classification step, document the *why* in code only when non-obvious.

## Reminder agent

`scripts/reminder_agent.py` is a real Claude agent (Anthropic SDK tool-use loop) that sends a daily study reminder email. It's wired to cron locally — logs go to `logs/reminder.log` and `logs/reminder_error.log`. Run manually with `python scripts/reminder_agent.py`. Recipient list and `STUDY_START_DATE` come from env vars; CC list is in-code.
