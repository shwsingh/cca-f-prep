# CCA-F Anti-Patterns
Add one entry every day. These are your highest-leverage exam revision asset.

---

## Prompt Engineering 20%

## Tool Design & MCP 18%

## Agentic Architecture 27%

## W1D1 — Missing stop_reason check
❌ Process response content without checking `stop_reason`
   Why it fails: `max_tokens` truncation is silent — you act on a half-finished answer
   Fix: branch on `response.stop_reason` before reading `.content` (`end_turn`, `max_tokens`, `tool_use`, `stop_sequence`)
   Exam tip: distractor answers print/use `response.content[0].text` directly with no stop_reason guard

## W1D2 — Forgot to append assistant turn before tool_result
❌ Send `tool_result` back to the API without first appending the assistant's `tool_use` turn to `messages`
   Why it fails: the API rejects the sequence — a `tool_result` block must follow an assistant turn that contains the matching `tool_use` block with the same `tool_use_id`
   Fix: after `stop_reason == "tool_use"`, append `{role: "assistant", content: response.content}` THEN append `{role: "user", content: [{type: "tool_result", tool_use_id: ..., content: ...}]}`
   Exam tip: the wrong answer skips the assistant turn and jumps straight from prior user message → new user message with `tool_result` — looks tidy, fails validation

## Context Management & Reliability 15%

## Claude Code 20%

## W1D1 — Hardcoded API key
❌ Put the API key as a string literal in source code
   Why it fails: key leaks the moment the file is committed, shared, or pasted into a screenshot
   Fix: load from `.env` via `python-dotenv` (`load_dotenv()` → `os.environ["ANTHROPIC_API_KEY"]`), and add `.env` to `.gitignore` BEFORE the first `git add`
   Exam tip: "rotate the key after committing" is a distractor — the right answer is "never let it reach the commit in the first place"

## W1D1 — Committed .env before adding it to .gitignore
❌ Run `git add` / `git commit` on a tree where `.env` exists but `.gitignore` does not yet list it
   Why it fails: the secret enters git history — deleting `.env` in a later commit leaves it readable via `git log -p`, `git show <old-sha>`, and the remote's history forever
   Fix: create `.gitignore` with `.env` on its own line BEFORE the first `git add`; if it already leaked, rotate the key immediately, then `git rm --cached .env` + `git filter-repo` (or BFG) to scrub history, then force-push
   Exam tip: "I deleted the .env file in a follow-up commit" is the canonical wrong answer — the secret is still in the earlier commit's blob and must be treated as compromised

## W1D2 — System Prompts & Structure
❌ Stuffing role + rules into every user message
   Fix: put persona and rules in `system`; user messages stay clean turns

❌ Free-form output when you need to parse it
   Fix: ask for XML tags + regex-extract; reject responses missing required tags
