# CCA-F Journey · Day 1 → Day 5

A scannable visual of what's been learned, how lessons stack, and what's
ahead. Regenerate as you finish more days — this is a revision asset, not
a static map.

Last updated: end of Day 5 (W1D5 done — `triple_issue` → 3 tickets, `empty_body` → []).

## 1. Timeline (what you learned each day)

```
   Day 1            Day 2            Day 3            Day 4            Day 5
   ─────            ─────            ─────            ─────            ─────
   W1D1             W1D2             W1D3             W1D4             W1D5
   06-02            06-03            06-04            06-05            06-08
   ⭐ ⭐ ⭐ ⭐ ⭐    ⭐ ⭐ ⭐ ⭐ ⭐    ⭐ ⭐ ⭐ ⭐ ⭐    ⭐ ⭐ ⭐ ⭐ ⭐    ⭐ ⭐ ⭐ ⭐ ⭐
     │                │                │                │                │
     ▼                ▼                ▼                ▼                ▼
  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
  │ FIRST   │    │ SHAPE   │    │ EXTRACT │    │ TALK    │    │ ENFORCE │
  │ API     │    │ THE     │    │ ONE     │    │ BACK    │    │ THE     │
  │ CALL    │    │ OUTPUT  │    │ FROM    │    │ AND     │    │ SHAPE   │
  │         │    │         │    │ MESS    │    │ FORTH   │    │ AT API  │
  └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
                                                                  ▲
                                                               TODAY
                                                          (1→N tickets;
                                                          empty→[]; 2× cost,
                                                          2× correctness)
```

## 2. Concept dependency (how lessons stack)

```
                  ┌──────────────────────────────────────────────┐
                  │   stop_reason matters on EVERY response      │
                  │   (learned D1, reused D4 max_tokens guard,   │
                  │    reused D5 tool_use completion signal)     │
                  └──────────────────┬───────────────────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            │                        │                        │
            ▼                        ▼                        ▼
   ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
   │  D2: persona │         │ D3: extract  │         │ D4: stateful │
   │  in `system` │ ──────► │ ONE ticket   │ ──────► │ conversation │
   │  + XML tags  │         │ (XML+regex)  │         │ loop, role   │
   │  for parsing │         │ + Pydantic   │         │ alternation  │
   └──────┬───────┘         └──────┬───────┘         └──────┬───────┘
          │                        │                        │
          │                        ▼                        │
          │                ┌──────────────┐                 │
          └───────────────►│ D5: extract  │                 │
                           │ MANY tickets │◄────────────────┘
                           │ via tool use │
                           │ (typed shape)│
                           └──────┬───────┘
                                  │
                  ┌───────────────┴──────────────────┐
                  │                                  │
                  ▼                                  ▼
            (Wk 2 routing)                   (Wk 4 reliability)
            fan out per-ticket               retry / escalate on
            to Resolution Agent              non-end_turn states
```

## 3. Capstone architecture growth (`meterflow/`)

```
After D1+D2:      After D3:                     After D5:
─────────────     ──────────────────────        ──────────────────────────────
(no meterflow/    meterflow/                    meterflow/
 yet — just       ├── __init__.py               ├── __init__.py
 day scripts)     └── extractors/               ├── extractors/
                      ├── __init__.py           │   ├── __init__.py
                      └── ticket_extractor.py   │   ├── ticket_extractor.py
                          • SupportTicket       │   │   • SupportTicket
                          • extract_ticket()    │   │   • extract_ticket()
                                                │   └── multi_ticket_extractor.py
                                                │       • extract_tickets()
                                                │       • TOOL_SCHEMA
                                                │       • tool_schema_from_pydantic()
                                                └── agents/         ◄─ added D4
                                                    ├── __init__.py
                                                    └── support_agent.py
                                                        • ConversationState
                                                        • build_system_prompt()
                                                        • agent_turn()
                                                        • run_conversation()
```

## 4. CCA-F exam domain coverage (5 days in)

```
Domain                              Weight   Touched     Anti-patterns logged
─────────────────────────────────── ──────   ─────────   ────────────────────
🧠 Prompt Engineering                 20%    ████████░   4   (D2, D3)
🔧 Tool Design & MCP                  18%    ███████░░   4   (D2, D5)
🏗 Agentic Architecture               27%    ██████░░░   3   (D4)
📊 Context Mgmt & Reliability         15%    ████░░░░░   2   (D3, D4)
💻 Claude Code                        20%    ░░░░░░░░░   0   (not yet — Wk 4)

                                                         ───
                                                         16 entries
```

## 5. The five rules you've absorbed so far

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  1. Persona goes in `system`, never in user messages.             [D2]  │
│                                                                         │
│  2. Anything you parse → demand structure (XML tags, JSON schema, │     │
│     or a tool call). Free-text parsing is technical debt.        [D3]  │
│                                                                         │
│  3. Set `temperature=0` for any task whose output you'll compare       │
│     or route on. Sampling variance is for generation, not          [D3] │
│     classification.                                                     │
│                                                                         │
│  4. Multi-turn loops are a client-side contract — the API will         │
│     silently accept broken conversation shape. `ConversationState` [D4] │
│     (or equivalent) makes the bug unrepresentable.                      │
│                                                                         │
│  5. Tool use is structured output's other right answer. When            │
│     the shape is a list, or the contract has to be enforced at    [D5] │
│     the API surface, reach for tools. Derive the schema from           │
│     Pydantic — one source of truth.                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 6. What's next (the road ahead)

```
   Week 1              Week 2              Week 3+
   ─────────           ─────────           ──────────
   ✅ D1 setup         D7-12: MCP +        D13-18: multi-agent
   ✅ D2 system        prompt caching      research (Scenario 3)
   ✅ D3 extract       + agent loops
   ✅ D4 conversation                      D19-23: support-agent
   ✅ D5 tool use                          reliability (Scenario 1
                                           full build-out)
   ⏳ D6: Week 1
        capstone        D24-29: Claude
        integration     Code + CI/CD
                        (Scenarios 2, 4, 5)

                                           D30-36: evals, polish,
                                           full system exam-shaped
```
