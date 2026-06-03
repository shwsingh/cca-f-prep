#!/usr/bin/env python3
"""
CCA-F Daily Reminder Agent
A real Claude agent that decides what to send and to whom.
Uses the raw Anthropic SDK loop — same pattern as the exam.

Run manually:  python reminder_agent.py
Auto via cron: set up with install.sh

Tools:
  get_study_day()        → calculates today's day number from start date
  get_day_plan(day)      → returns the full plan for that day
  send_email(subject, html) → sends to all three recipients
"""

import os, json, smtplib, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import anthropic

load_dotenv()
client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"   # fast + cheap for a simple task agent

START_DATE = datetime.date.fromisoformat(
    os.getenv("STUDY_START_DATE", "2025-06-02")
)
TO_EMAIL  = "shwetasiliconvalley@gmail.com"
CC_EMAILS = ["aaryanvanshi@gmail.com", "shefali.cse@gmail.com", "ajasingh@outlook.com"]

# ── PLAN DATA ────────────────────────────────────────────────────────────────
PLAN = {
    1:  {"week":1, "topic":"Setup & first API call",
         "domain":"Prompt Engineering 20%",
         "file":"week1/w1d1_setup.py", "run":"python week1/w1d1_setup.py",
         "objective":"Confirm your environment works end to end.",
         "steps":["Create .env with ANTHROPIC_API_KEY",
                  "Run pip install -r requirements.txt",
                  "Run the script — confirm ✅ API connection OK",
                  "Inspect stop_reason, usage, model in the response",
                  "Change max_tokens to 10 — observe truncation",
                  "Submit exam access request at anthropic.skilljar.com"],
         "commit":"W1D1: setup — first API call working"},

    2:  {"week":1, "topic":"Prompt engineering & tone variants",
         "domain":"Prompt Engineering 20%",
         "file":"week1/w1d2_prompt_engineering.py", "run":"python week1/w1d2_prompt_engineering.py",
         "objective":"Control Claude output style through system prompt design.",
         "steps":["Run — read all 3 tone outputs side by side",
                  "Edit TERSE prompt to add a max-word constraint",
                  "Add a contradictory instruction — observe degradation",
                  "Pick your house style and document why",
                  "Add rationale to README log"],
         "commit":"W1D2: prompt engineering — tone variants, house style chosen"},

    3:  {"week":1, "topic":"Structured extraction — JSON mode + Pydantic (Scenario 6)",
         "domain":"Prompt Engineering 20%",
         "file":"week1/w1d3_structured_extraction.py", "run":"python week1/w1d3_structured_extraction.py",
         "objective":"Extract validated ticket records from messy emails.",
         "steps":["Run — observe which emails validate vs trigger fallback",
                  "Remove 'No markdown' from system prompt — watch json.loads crash",
                  "Delete account_id from email 1 — watch re-prompt path",
                  "Add a 6th email with your own edge case",
                  "Add urgency-5 email — confirm flagged_for_human=True"],
         "commit":"W1D3: structured extraction — JSON mode, Pydantic, re-prompt fallback"},

    4:  {"week":1, "topic":"⭐ Bare-metal agent loop — MOST IMPORTANT DAY",
         "domain":"Agentic Architecture 27%",
         "file":"week1/w1d4_agent_loop.py", "run":"python week1/w1d4_agent_loop.py",
         "objective":"Implement the Anthropic agent loop from scratch.",
         "steps":["Read every line in run_agent() BEFORE running",
                  "Run — trace each turn in the printout",
                  "Comment out the assistant message append — watch the API error",
                  "Change tool_use_id to wrong value — watch the mismatch",
                  "Test account C-5500 (suspended) — does Claude change advice?",
                  "Add a second tool get_refund_policy() and wire it in"],
         "commit":"W1D4: bare-metal agent loop — stop_reason, tool_use_id, multi-turn"},

    5:  {"week":1, "topic":"Multi-tool selection & description quality",
         "domain":"Tool Design & MCP 18%",
         "file":"week1/w1d5_multi_tool.py", "run":"python week1/w1d5_multi_tool.py",
         "objective":"Prove tool description quality controls selection accuracy.",
         "steps":["Run USE_BAD_TOOLS=True — note wrong selections",
                  "Flip to False — compare accuracy",
                  "Identify the exact phrase causing each failure",
                  "Add a 4th tool with good and bad descriptions",
                  "Write 'Minimum description rules' in anti-patterns.md"],
         "commit":"W1D5: tool description quality — bad vs good compared"},

    6:  {"week":1, "topic":"Prompt caching + Batch API",
         "domain":"Context Management 15%",
         "file":"week1/w1d6_caching_batch.py", "run":"python week1/w1d6_caching_batch.py",
         "objective":"Reduce token cost 90%+ with cache_control.",
         "steps":["Run Part A — compare tokens with/without cache",
                  "Note cache_creation vs cache_read tokens",
                  "Shorten POLICY_DOC under 1024 tokens — observe cache stops",
                  "Run Part B — submit batch, note async pattern",
                  "Record token savings % in README"],
         "commit":"W1D6: prompt caching + batch — token savings measured"},

    7:  {"week":2, "topic":"MCP primitives — tools, resources, prompts",
         "domain":"Tool Design & MCP 18%",
         "file":"week2/w2d1_mcp_primitives.py", "run":"python week2/w2d1_mcp_primitives.py",
         "objective":"Distinguish MCP tools, resources, and prompts by observation.",
         "steps":["Install: npm install -g @modelcontextprotocol/server-filesystem",
                  "Run — observe tools, resources, prompts listed",
                  "Fill NOTES dict at bottom of file",
                  "Open Claude Code, point at meterflow/data, ask it to list files",
                  "Write one-sentence definition of each primitive"],
         "commit":"W2D1: MCP primitives — tools vs resources vs prompts"},

    8:  {"week":2, "topic":"Build MCP server over SQLite billing DB",
         "domain":"Tool Design & MCP 18%",
         "file":"week2/w2d2_mcp_server.py",
         "run":"Terminal 1: python week2/w2d2_mcp_server.py server\nTerminal 2: python week2/w2d2_mcp_server.py client",
         "objective":"Author a working MCP server exposing real DB data.",
         "steps":["Terminal 1: run server — confirm 'running (stdio)...'",
                  "Terminal 2: run client — confirm real DB data returned",
                  "Register server in Claude Code config",
                  "In Claude Code ask: What is status of account A-1042?",
                  "Add account F-9999 to DB — test not-found error"],
         "commit":"W2D2: MCP billing server — SQLite, tool exposed, wired into Claude Code"},

    9:  {"week":2, "topic":"MCP resources + structured errors",
         "domain":"Tool Design & MCP 18%",
         "file":"week2/w2d3_mcp_advanced.py",
         "run":"Terminal 1: server | Terminal 2: client",
         "objective":"Add resources and harden all error paths.",
         "steps":["Run client — verify resource URIs list correctly",
                  "Call tool with empty account_id — confirm validation_error",
                  "Call with unknown account — confirm account_not_found",
                  "Add second resource: billing://accounts/{id}/invoices",
                  "Verify agent receives error as dict, not exception"],
         "commit":"W2D3: MCP resources + structured errors"},

    10: {"week":2, "topic":"Tool design refactor — bad vs good",
         "domain":"Tool Design & MCP 18%",
         "file":"week2/w2d4_tool_design.py", "run":"python week2/w2d4_tool_design.py",
         "objective":"Internalize the one-tool-one-action rule.",
         "steps":["Run USE_BAD_TOOLS=True — note misroutes",
                  "Flip to False — verify 100% correct",
                  "Write fixed version of each bad description",
                  "Design send_receipt tool — both bad and good",
                  "Add 5 tool design principles to anti-patterns.md"],
         "commit":"W2D4: tool design refactor — granularity, naming principles"},

    11: {"week":2, "topic":"Retry, backoff, graceful degradation",
         "domain":"Reliability 15%",
         "file":"week2/w2d5_retry_fallback.py", "run":"python week2/w2d5_retry_fallback.py",
         "objective":"Keep the agent working when external APIs fail.",
         "steps":["Run FAILURE_RATE=0.0 — baseline",
                  "Set 0.5 — watch retry; note which attempt succeeds",
                  "Set 1.0 — watch full fallback: agent creates ticket",
                  "Change MAX_RETRIES to 1 — faster fallback?",
                  "Add exponential backoff (1s, 2s, 4s)"],
         "commit":"W2D5: retry + fallback — backoff, graceful degradation"},

    12: {"week":2, "topic":"Week 2 review + Scenario 6 decision page",
         "domain":"All Tool/MCP topics",
         "file":"notes/scenario-decisions.md", "run":"edit the file",
         "objective":"Consolidate tool + MCP knowledge.",
         "steps":["Complete all Scenario 6 checkboxes",
                  "Write 3 practice questions on tool design",
                  "Work through 1 distractor from a practice bank",
                  "Review Week 2 files — add new anti-patterns"],
         "commit":"W2D6: review — Scenario 6 complete"},

    13: {"week":3, "topic":"Bare-metal rebuild — what frameworks hide",
         "domain":"Agentic Architecture 27%",
         "file":"week3/w3d1_raw_loop.py", "run":"python week3/w3d1_raw_loop.py",
         "objective":"Expose every assumption LangGraph makes.",
         "steps":["Read LANGRAPH_EQUIVALENT comment first",
                  "Run — trace the raw loop turn by turn",
                  "Fill in every field in WHAT_FRAMEWORK_DOES",
                  "Add third tool with conditional logic",
                  "Write 'What frameworks hide' in README"],
         "commit":"W3D1: raw loop rebuild — framework vs raw SDK"},

    14: {"week":3, "topic":"First subagent — context isolation",
         "domain":"Agentic Architecture 27%",
         "file":"week3/w3d2d3_multiagent_research.py", "run":"python week3/w3d2d3_multiagent_research.py",
         "objective":"Implement coordinator-worker context isolation.",
         "steps":["Set competitors to just ['Stripe Billing']",
                  "Run — confirm worker messages list is isolated",
                  "Print len(worker_messages) to verify",
                  "Pass coordinator history into worker — observe bloat",
                  "Write context isolation rule in anti-patterns.md"],
         "commit":"W3D2: subagent — context isolation verified"},

    15: {"week":3, "topic":"Multi-Agent Research System (Scenario 3)",
         "domain":"Agentic Architecture 27%",
         "file":"week3/w3d2d3_multiagent_research.py", "run":"python week3/w3d2d3_multiagent_research.py",
         "objective":"Build parallel fan-out and handle a failing worker.",
         "steps":["Set PARALLEL=True, INJECT_FAILURE=True — run",
                  "Note which worker fails and how coordinator handles it",
                  "Set INJECT_FAILURE=False — measure wall-clock speedup",
                  "Change coordinator to Haiku — observe quality difference",
                  "Fill Scenario 3 in scenario-decisions.md"],
         "commit":"W3D3: multi-agent research — parallel fan-out, failure handling"},

    16: {"week":3, "topic":"Dedup + state passing across agents",
         "domain":"Agentic Architecture 27%",
         "file":"week3/w3d4d5_dedup_langfuse.py", "run":"python week3/w3d4d5_dedup_langfuse.py",
         "objective":"Aggregate and deduplicate results across workers.",
         "steps":["Run — observe raw vs deduped finding count",
                  "Print removed duplicates",
                  "Make two workers return identical findings — verify dedup",
                  "Add confidence field (1-5) to worker results",
                  "Filter out workers with confidence < 3"],
         "commit":"W3D4: dedup + aggregation — cross-worker dedup"},

    17: {"week":3, "topic":"Single vs multi-agent tradeoff analysis",
         "domain":"Agentic Architecture 27%",
         "file":"week3/w3d4d5_dedup_langfuse.py", "run":"python week3/w3d4d5_dedup_langfuse.py",
         "objective":"Justify multi-agent architecture with measured data.",
         "steps":["Run single-agent version — record time and tokens",
                  "Run multi-agent version — compare both metrics",
                  "Write tradeoff analysis in scenario-decisions.md",
                  "Identify when multi-agent is WORSE than single",
                  "Add speedup ratio to README log"],
         "commit":"W3D5: single vs multi-agent tradeoff measured"},

    18: {"week":3, "topic":"Week 3 review + Scenario 3 complete",
         "domain":"Agentic Architecture 27%",
         "file":"notes/scenario-decisions.md", "run":"review + complete",
         "objective":"Consolidate orchestration knowledge.",
         "steps":["Complete all Scenario 3 checkboxes",
                  "Draw hub-and-spoke diagram (ASCII)",
                  "Write 3 practice questions with distractor analysis",
                  "Review Week 3 anti-patterns"],
         "commit":"W3D6: review — Scenario 3 complete"},

    19: {"week":4, "topic":"Agent memory across sessions",
         "domain":"Reliability 15%",
         "file":"week4/w4d1d2_memory_context.py", "run":"python week4/w4d1d2_memory_context.py memory",
         "objective":"Give the agent persistent memory without passing full history.",
         "steps":["Run — note Session 2 references Session 1",
                  "Delete customer_memory.json — confirm Session 2 loses reference",
                  "Add preferred_contact field to memory schema",
                  "Save sentiment trend across sessions",
                  "Test with account C-5500 — what gets saved?"],
         "commit":"W4D1: agent memory — persistent store, cross-session recall"},

    20: {"week":4, "topic":"Context compaction over long conversations",
         "domain":"Reliability 15%",
         "file":"week4/w4d1d2_memory_context.py", "run":"python week4/w4d1d2_memory_context.py compaction",
         "objective":"Keep token count bounded over a 20-turn conversation.",
         "steps":["Run — observe token count per turn",
                  "Note which turn triggers compaction",
                  "Lower COMPACTION_THRESHOLD to 500",
                  "Inspect running_summary after compaction",
                  "Try truncate-only vs summarize — compare quality"],
         "commit":"W4D2: context compaction — threshold, summarization, token bounding"},

    21: {"week":4, "topic":"RAG over MeterFlow policy docs",
         "domain":"Reliability 15%",
         "file":"week4/w4d3d4d5_rag_eval.py", "run":"python week4/w4d3d4d5_rag_eval.py rag",
         "objective":"Build grounded Q&A so agents answer from retrieved context.",
         "steps":["Run — confirm answers cite source docs",
                  "Ask question NOT in any doc — confirm graceful response",
                  "Add a 4th policy doc — reindex and query",
                  "Ask question spanning two docs — observe merge",
                  "Add grounded check: does answer quote retrieved context?"],
         "commit":"W4D3: RAG — ChromaDB, retrieval, grounded answers"},

    22: {"week":4, "topic":"Resolve-vs-escalate agent (Scenario 1)",
         "domain":"Agentic Architecture 27%",
         "file":"week4/w4d3d4d5_rag_eval.py", "run":"python week4/w4d3d4d5_rag_eval.py resolve",
         "objective":"Build core support routing with confidence scoring.",
         "steps":["Run — observe 3 test cases route correctly",
                  "Add 4th case: $49 duplicate on SUSPENDED account — escalate",
                  "Add 5th case: $201 duplicate over auto-approve limit — escalate",
                  "Tune system prompt until both edge cases route correctly",
                  "Fill Scenario 1 checkboxes in scenario-decisions.md"],
         "commit":"W4D4: resolve-vs-escalate — confidence scoring, Scenario 1 complete"},

    23: {"week":4, "topic":"Evaluation harness",
         "domain":"Reliability 15%",
         "file":"week4/w4d3d4d5_rag_eval.py", "run":"python week4/w4d3d4d5_rag_eval.py eval",
         "objective":"Score the agent against 15 ground-truth cases.",
         "steps":["Run — note overall accuracy and per-category breakdown",
                  "For each wrong answer: prompt fault or model fault?",
                  "Fix system prompt for at least 1 failure — rerun",
                  "Add an LLM-judge score for response quality",
                  "Record weakest category in README"],
         "commit":"W4D5: eval harness — 15-case set, accuracy by category"},

    24: {"week":4, "topic":"Week 4 review + Scenario 1 complete",
         "domain":"All reliability topics",
         "file":"notes/scenario-decisions.md", "run":"review + complete",
         "objective":"Consolidate reliability knowledge.",
         "steps":["Verify all Scenario 1 checkboxes filled",
                  "Write 3 reliability questions with distractor analysis",
                  "Review all Week 4 anti-patterns",
                  "Identify your top 2 weakest domains"],
         "commit":"W4D6: review — Scenario 1 complete, reliability consolidated"},

    25: {"week":5, "topic":"Claude Code configuration — CLAUDE.md",
         "domain":"Claude Code 20%",
         "file":"CLAUDE.md", "run":"edit in Claude Code",
         "objective":"Make Claude Code productive via a complete CLAUDE.md.",
         "steps":["Open Claude Code — run a task BEFORE editing CLAUDE.md",
                  "Add: never modify week1/ files, always run pytest before committing",
                  "Re-run same task — observe changed behavior",
                  "Add 'forbidden patterns' section with your top 3 anti-patterns",
                  "Ask Claude Code to write a tool — confirm naming convention followed"],
         "commit":"W5D1: CLAUDE.md — conventions, forbidden patterns"},

    26: {"week":5, "topic":"Agent Skill — /triage slash command",
         "domain":"Claude Code 20%",
         "file":".claude/skills/triage/SKILL.md", "run":"open Claude Code, type /triage",
         "objective":"Build a reusable /triage skill for classifying emails.",
         "steps":["Open Claude Code — type /triage",
                  "Paste Test 1 (A-1042 duplicate charge) — confirm JSON output",
                  "Paste Test 2 (P0 locked out) — confirm urgency=5, on-call",
                  "Paste Test 3 (no account id) — confirm flagged=True",
                  "Edit skill to return a recommended response template"],
         "commit":"W5D2: /triage skill — slash command, 3 test cases"},

    27: {"week":5, "topic":"Claude Code + MCP server (Scenarios 2 & 4)",
         "domain":"Claude Code 20%",
         "file":"week2/w2d2_mcp_server.py", "run":"use inside Claude Code",
         "objective":"Wire billing MCP server into Claude Code.",
         "steps":["Confirm w2d2 server registered in Claude Code config",
                  "In Claude Code: What is balance for account C-5500?",
                  "Ask Claude Code to write a function using account status",
                  "Ask: Generate refund email for account A-1042",
                  "Fill Scenarios 2 and 4 in scenario-decisions.md"],
         "commit":"W5D3: Claude Code + MCP — billing server wired"},

    28: {"week":5, "topic":"GitHub PR workflow",
         "domain":"Claude Code 20%",
         "file":"(Claude Code generates)", "run":"use inside Claude Code",
         "objective":"Have Claude Code implement a feature and open a PR.",
         "steps":["Ask: Add get_invoice_history(account_id, months) to MCP server",
                  "Review diff — check error handling, validation, docstring",
                  "Request 2 specific changes — apply them",
                  "Have Claude Code open a PR — add link to README",
                  "Merge PR — confirm CI passes"],
         "commit":"W5D4: GitHub PR — Claude Code feature branch, review, merge"},

    29: {"week":5, "topic":"Claude Code in CI — GitHub Actions (Scenario 5)",
         "domain":"Claude Code 20%",
         "file":".github/workflows/ci.yml", "run":"push to GitHub, open a PR",
         "objective":"CI catches bugs and API key leaks on every PR.",
         "steps":["Push ci.yml to GitHub",
                  "Open PR with deliberate syntax error",
                  "Confirm CI catches it in Syntax check step",
                  "Add hardcoded API key — confirm Lint catches it",
                  "Fix both — CI goes green — fill Scenario 5"],
         "commit":"W5D5: Claude Code CI — GitHub Action, Scenario 5 complete"},

    30: {"week":5, "topic":"Week 5 review + Scenarios 2, 4, 5 complete",
         "domain":"All Claude Code topics",
         "file":"notes/scenario-decisions.md", "run":"review + complete",
         "objective":"Consolidate Claude Code knowledge.",
         "steps":["Complete Scenarios 2, 4, 5 in scenario-decisions.md",
                  "Write 3 Claude Code questions and answer them",
                  "Review all 5 weeks of anti-patterns",
                  "Identify top 3 weakest areas for Week 6"],
         "commit":"W5D6: review — Scenarios 2/4/5 complete"},

    31: {"week":6, "topic":"Capstone Day 1 — wire all 5 stages",
         "domain":"All 5 domains",
         "file":"week6/w6_capstone.py", "run":"python week6/w6_capstone.py",
         "objective":"Run all test cases through the full pipeline.",
         "steps":["Run all 3 test cases — each stage passes data to next",
                  "Add 4th case triggering no-account_id error path",
                  "Add print timer to each stage",
                  "Identify slowest stage",
                  "Map each stage to its exam domain"],
         "commit":"W6D1: capstone v1 — 5 stages wired, all cases passing"},

    32: {"week":6, "topic":"Capstone Day 2 — RAG + eval + trace",
         "domain":"All 5 domains",
         "file":"week6/w6_capstone.py", "run":"python week6/w6_capstone.py",
         "objective":"Add RAG path, run eval set, get full trace.",
         "steps":["Add RAG for billing_query issues",
                  "Route billing_query through RAG before routing agent",
                  "Run 15-case eval set against full pipeline",
                  "Document which domain each stage covers",
                  "Note what is missing for production"],
         "commit":"W6D2: capstone v2 — RAG path, eval set run"},

    33: {"week":6, "topic":"Full practice exam #1",
         "domain":"All 5 domains",
         "file":"practice/exam-1-log.md", "run":"timed 60-question session",
         "objective":"Take timed practice exam; identify weakest domain.",
         "steps":["Take timed 60-question set (anthropic.skilljar.com or udemy)",
                  "Log every miss: question, your answer, correct answer, WHY",
                  "Identify weakest domain",
                  "Add new anti-patterns from misses",
                  "Note score and target for exam 2"],
         "commit":"W6D3: practice exam 1 — score X/60, weak domain noted"},

    34: {"week":6, "topic":"Targeted review of weakest domain",
         "domain":"Your gap domain",
         "file":"re-run relevant exercise", "run":"depends on weak domain",
         "objective":"Close the gap before practice exam 2.",
         "steps":["Re-study only the weakest domain from Day 33",
                  "Re-read relevant Skilljar module + docs",
                  "Re-run the most relevant exercise file",
                  "Write 5 questions in that domain with distractor analysis",
                  "Re-check scenario-decisions.md for that domain"],
         "commit":"W6D4: targeted review — [domain] reinforced"},

    35: {"week":6, "topic":"Full practice exam #2",
         "domain":"All 5 domains",
         "file":"practice/exam-2-log.md", "run":"timed 60-question session",
         "objective":"Confirm you are clearing 720-equivalent.",
         "steps":["Take second timed set — different bank if possible",
                  "Log misses — confirm improvement from exam 1",
                  "If score >= 720-equivalent: you are ready",
                  "If not: repeat Day 34 pattern for remaining gaps",
                  "Confirm exam access is active in Skilljar"],
         "commit":"W6D5: practice exam 2 — score X/60, ready: yes/no"},

    36: {"week":6, "topic":"Light review + exam logistics",
         "domain":"All",
         "file":"notes/ (final skim)", "run":"review only",
         "objective":"Final check before exam day.",
         "steps":["Skim all 6 scenario-decisions.md pages — 10 min max",
                  "Skim anti-patterns.md — highlight top 5 exam traps",
                  "Confirm exam access is active in Skilljar",
                  "Run the proctoring system check",
                  "Rest — you have built a full production system. You know this."],
         "commit":"W6D6: ready — all scenarios reviewed, exam access confirmed"},
}

# ── TOOL IMPLEMENTATIONS ─────────────────────────────────────────────────────

def get_study_day() -> dict:
    """Calculate today's study day number based on start date, skipping Sundays."""
    today = datetime.date.today()
    if today < START_DATE:
        return {"day": 1, "date": str(today), "note": "Study hasn't started yet — sending Day 1"}
    study_day = 0
    current = START_DATE
    while current <= today:
        if current.weekday() != 6:   # skip Sundays
            study_day += 1
        if current == today:
            break
        current += datetime.timedelta(days=1)
    day = max(1, min(study_day, 36))
    return {"day": day, "date": str(today), "total": 36}

def get_day_plan(day: int) -> dict:
    """Return the full study plan for a given day number."""
    day = max(1, min(int(day), 36))
    if day not in PLAN:
        return {"error": f"No plan for day {day}"}
    p = PLAN[day]
    return {
        "day": day,
        "week": p["week"],
        "topic": p["topic"],
        "domain": p["domain"],
        "objective": p["objective"],
        "file": p["file"],
        "run_command": p["run"],
        "steps": p["steps"],
        "commit_message": p["commit"],
        "total_days": 36,
        "progress_pct": round((day / 36) * 100),
    }

def send_email(subject: str, body_html: str) -> dict:
    """Send the reminder email to all recipients."""
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASS")

    if not gmail_user or not gmail_pass:
        return {"error": "GMAIL_USER or GMAIL_APP_PASS not set in .env"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = TO_EMAIL
    msg["Cc"]      = ", ".join(CC_EMAILS)
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [TO_EMAIL] + CC_EMAILS, msg.as_string())
        return {
            "sent": True,
            "to": TO_EMAIL,
            "cc": CC_EMAILS,
            "subject": subject
        }
    except Exception as e:
        return {"error": str(e), "sent": False}

# ── TOOL SCHEMAS (what Claude sees) ──────────────────────────────────────────
TOOLS = [
    {
        "name": "get_study_day",
        "description": (
            "Calculate which study day it is today based on the start date. "
            "Call this first to know which day plan to fetch."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_day_plan",
        "description": (
            "Get the full study plan for a specific day number. "
            "Returns topic, objective, steps, file to run, and commit message. "
            "Call this after get_study_day to fetch today's plan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "day": {"type": "integer", "description": "Day number between 1 and 36"}
            },
            "required": ["day"],
        },
    },
    {
        "name": "send_email",
        "description": (
            "Send the formatted study reminder email to all recipients. "
            "Call this last, after you have the day plan and have composed the HTML. "
            "Always include all steps and the commit message in the email body."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject":   {"type": "string", "description": "Email subject line"},
                "body_html": {"type": "string", "description": "Full HTML email body"},
            },
            "required": ["subject", "body_html"],
        },
    },
]

# ── TOOL EXECUTOR ─────────────────────────────────────────────────────────────
def run_tool(name: str, inp: dict) -> str:
    if name == "get_study_day":
        return json.dumps(get_study_day())
    if name == "get_day_plan":
        return json.dumps(get_day_plan(inp["day"]))
    if name == "send_email":
        return json.dumps(send_email(inp["subject"], inp["body_html"]))
    return json.dumps({"error": f"Unknown tool: {name}"})

# ── THE AGENT LOOP ────────────────────────────────────────────────────────────
def run_agent() -> None:
    print(f"\n{'='*50}")
    print(f"  CCA-F Reminder Agent — {datetime.date.today()}")
    print(f"{'='*50}")

    messages = [{
        "role": "user",
        "content": (
            "You are the CCA-F study reminder agent. "
            "Your job every morning:\n"
            "1. Call get_study_day to find out which day it is today\n"
            "2. Call get_day_plan with that day number\n"
            "3. Compose a clean, motivating HTML email with:\n"
            "   - Day number and topic as a bold header\n"
            "   - Today's objective\n"
            "   - The file to run and the run command in a code block\n"
            "   - All steps as a numbered list\n"
            "   - The exact commit message at the bottom\n"
            "   - A one-line motivational note\n"
            "4. Call send_email with subject 'CCA-F Day X/36 — [topic]' and your HTML\n"
            "Do this now."
        )
    }]

    turn = 0
    while True:
        turn += 1
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            tools=TOOLS,
            messages=messages,
        )

        print(f"\nTurn {turn} — stop_reason: {response.stop_reason}")

        # ── Done ──────────────────────────────────────────────────────────
        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if b.type == "text"), "")
            print(f"Agent: {text}")
            break

        # ── Tool use ──────────────────────────────────────────────────────
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                print(f"  → tool: {block.name}  input: {json.dumps(block.input)[:80]}")
                result = run_tool(block.name, block.input)
                result_data = json.loads(result)
                # Print meaningful summary per tool
                if block.name == "get_study_day":
                    print(f"  ← day: {result_data.get('day')}, date: {result_data.get('date')}")
                elif block.name == "get_day_plan":
                    print(f"  ← topic: {result_data.get('topic')}")
                elif block.name == "send_email":
                    if result_data.get("sent"):
                        print(f"  ← ✅ Email sent to {result_data.get('to')} + CC")
                    else:
                        print(f"  ← ❌ Email failed: {result_data.get('error')}")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
            messages.append({"role": "user", "content": results})

if __name__ == "__main__":
    run_agent()
