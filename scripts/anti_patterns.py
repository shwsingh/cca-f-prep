"""
Shared helpers for the CCA-F anti-pattern log.

Each day's exercise script defines a list of ENTRIES (dicts with `domain`,
`title`, `mistake`, `why`, `fix`, `exam_tip`) and calls:

    from scripts.anti_patterns import write_day, rebuild_master
    write_day("W1D2", ENTRIES)
    rebuild_master()

`write_day` writes `notes/{week_day}/anti-patterns.md` (idempotent).
`rebuild_master` scans every per-day file, groups by exam domain, and
overwrites `notes/anti-patterns.md`. Hand-edits to the master are lost on
the next rebuild — edit the per-day file instead.

All paths are resolved relative to the repo root (the parent of this file's
directory), so callers don't need to worry about CWD.
"""

from __future__ import annotations

import glob
import re
from pathlib import Path
from typing import TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTES_DIR = REPO_ROOT / "notes"
MASTER_PATH = NOTES_DIR / "anti-patterns.md"


class Entry(TypedDict):
    domain: str
    title: str
    mistake: str
    why: str
    fix: str
    exam_tip: str


# (name, exam %, emoji) — order here drives section order in the master file.
DOMAINS: list[tuple[str, int, str]] = [
    ("Prompt Engineering",              20, "🧠"),
    ("Tool Design & MCP",               18, "🔧"),
    ("Agentic Architecture",            27, "🏗"),
    ("Context Management & Reliability", 15, "📊"),
    ("Claude Code",                     20, "💻"),
]

PREAMBLE = """# CCA-F Anti-Patterns

Add one entry every day. These are your highest-leverage exam revision asset.

Each entry has the same shape so you can scan fast:

> **The mistake** — what you actually did
> **Why it fails** — the mechanism, not the symptom
> **Fix** — the minimal correct version (often with a code snippet)
> **Exam tip** — the distractor answer to *not* pick

Domain percentages reflect CCA-F exam weighting.
This file is regenerated from `notes/W*D*/anti-patterns.md` — edit those, not this.

---

"""


def render_entry(entry: Entry, week_day: str) -> str:
    return (
        f"<!-- domain: {entry['domain']} -->\n"
        f"### {week_day} — {entry['title']}\n\n"
        f"**The mistake**\n{entry['mistake']}\n\n"
        f"**Why it fails**\n{entry['why']}\n\n"
        f"**Fix**\n{entry['fix']}\n\n"
        f"**Exam tip**\n{entry['exam_tip']}\n"
    )


def write_day(week_day: str, entries: list[Entry]) -> Path:
    """Write notes/{week_day}/anti-patterns.md from `entries`. Overwrites."""
    valid = {d for d, _, _ in DOMAINS}
    for e in entries:
        if e["domain"] not in valid:
            raise ValueError(
                f"unknown domain {e['domain']!r}; must be one of {sorted(valid)}"
            )

    day_dir = NOTES_DIR / week_day
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / "anti-patterns.md"

    blocks = [render_entry(e, week_day) for e in entries]
    path.write_text("\n---\n\n".join(blocks))
    print(f"✅ {path.relative_to(REPO_ROOT)} written ({len(entries)} entries)")
    return path


def rebuild_master() -> Path:
    """Regenerate notes/anti-patterns.md from every notes/W*D*/anti-patterns.md."""
    by_domain: dict[str, list[str]] = {d: [] for d, _, _ in DOMAINS}

    pattern = str(NOTES_DIR / "W*D*" / "anti-patterns.md")
    for filepath in sorted(glob.glob(pattern)):
        text = Path(filepath).read_text()
        for block in re.split(r"\n---\n", text):
            block = block.strip()
            if not block:
                continue
            m = re.search(r"<!-- domain: (.+?) -->", block)
            if not m:
                continue
            domain = m.group(1).strip()
            if domain in by_domain:
                by_domain[domain].append(block)

    parts: list[str] = [PREAMBLE]
    for domain, pct, emoji in DOMAINS:
        parts.append(f"## {emoji} {domain} — {pct}%\n\n")
        entries = by_domain[domain]
        if not entries:
            parts.append("*(none yet)*\n\n")
            continue
        for i, block in enumerate(entries):
            parts.append(block + "\n\n")
            if i < len(entries) - 1:
                parts.append("---\n\n")
        parts.append("---\n\n")

    MASTER_PATH.write_text("".join(parts).rstrip() + "\n")
    print(f"✅ {MASTER_PATH.relative_to(REPO_ROOT)} regenerated from per-day files")
    return MASTER_PATH
