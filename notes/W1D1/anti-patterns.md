<!-- domain: Agentic Architecture -->
### W1D1 — Missing stop_reason check

**The mistake**
Read `response.content[0].text` and act on it without first checking `response.stop_reason`.

**Why it fails**
`max_tokens` truncation is **silent** at the content level — you get a half-finished sentence that looks fine until it doesn't. Same for `tool_use`: there's no final text to consume; you must dispatch the tool call instead.

**Fix**
```python
# ✅ right — branch on stop_reason every time
match response.stop_reason:
    case "end_turn":
        return response.content[0].text
    case "max_tokens":
        raise TruncatedError("response was cut off")
    case "tool_use":
        return handle_tool_use(response)
    case "stop_sequence":
        ...
```

The four values you must memorize: `end_turn`, `max_tokens`, `tool_use`, `stop_sequence`.

**Exam tip**
Distractor answers print/use `response.content[0].text` directly with no stop_reason guard. Any answer that bypasses `stop_reason` is wrong in an agent loop.

---

<!-- domain: Claude Code -->
### W1D1 — Hardcoded API key

**The mistake**
```python
# ❌ wrong
client = anthropic.Anthropic(api_key="sk-ant-api03-xxxxxxxxxxxx")
```

**Why it fails**
The key leaks the moment the file is committed, shared in a PR, or pasted into a screenshot. GitHub's secret scanner will find it within minutes; bots clone the key and start spending against your account.

**Fix**
```python
# ✅ right
import os
from dotenv import load_dotenv
load_dotenv()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
```

Plus add `.env` to `.gitignore` **before** the first `git add`.

**Exam tip**
"Rotate the key after committing" is a distractor — the right answer is "never let it reach the commit in the first place." If it *did* leak: rotate first, then scrub history.

---

<!-- domain: Claude Code -->
### W1D1 — Committed .env before adding it to .gitignore

**The mistake**
Ran `git add` / `git commit` on a tree where `.env` exists but `.gitignore` does not yet list it.

**Why it fails**
The secret is now in git history. Deleting `.env` in a follow-up commit does **not** remove it — anyone with the repo can still read it via:
```bash
git log -p .env
git show <old-sha>:.env
```
And the remote's history keeps it forever.

**Fix (prevention)**
```bash
# do this BEFORE the first git add
echo ".env" >> .gitignore
git add .gitignore
```

**Fix (recovery, if it already leaked)**
```bash
# 1. rotate the key in the Anthropic console IMMEDIATELY
# 2. remove it from the index but keep the local file
git rm --cached .env
# 3. scrub from history
git filter-repo --path .env --invert-paths   # or BFG Repo-Cleaner
# 4. force-push
git push --force-with-lease
```

**Exam tip**
"I deleted the .env file in a follow-up commit" is the canonical wrong answer — the secret still lives in the earlier commit's blob and must be treated as compromised.
