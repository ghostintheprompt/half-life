#!/usr/bin/env python3
"""
half-life — a content-decay auditor.

Content rots the moment it's published. The dead `npm install`, the SEO fossil,
the doc describing a folder that no longer exists, the model ID that shipped
three months ago. This walks a folder of markdown and tells you what's decaying:
a deterministic pass (dead links, age, zombie references) that needs no API key,
and an optional LLM judgment pass that reads each piece and says what expired.

Usage:
    python half_life.py <articles_dir> [--today YYYY-MM-DD] [--llm] [--json out.json]

The LLM's model is read from the environment (HALFLIFE_MODEL), never hardcoded.
A tool that hunts stale model IDs must not rot on its own — that's the joke that
writes itself. Default is claude-opus-5; swap it without a code change.
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

# ── deterministic detectors (no LLM, no key) ─────────────────────────────────

# Zombie references: names/versions that date a piece the moment they're read.
ZOMBIE = [
    (re.compile(r"\bclaude-(?:3|2)[\w.-]*\b", re.I), "superseded Claude model id"),
    (re.compile(r"\bclaude-(?:sonnet|opus|haiku)-4[\w.-]*\b", re.I), "aging Claude 4.x model id"),
    (re.compile(r"\bgpt-(?:3\.5|4o?|4-turbo)\b", re.I), "superseded GPT model id"),
    (re.compile(r"\bClaude Design\b"), "retired product name (Claude Design)"),
    (re.compile(r"\b(?:coming|arriving|due|expected)\s+(?:in\s+)?(?:late\s+|early\s+)?20\d\d\b", re.I), "future-tense that may have resolved"),
    (re.compile(r"\bby\s+(?:the\s+)?end\s+of\s+20\d\d\b", re.I), "deadline framing that may have passed"),
]

FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
FM_FIELD = re.compile(r'^(\w+):\s*"?(.*?)"?\s*$', re.M)
# internal article links: [text](/articles/slug) or [text](slug)
INTERNAL_LINK = re.compile(r"\]\((?:/articles/)?([a-z0-9][a-z0-9-]*)\)")
DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")


def frontmatter(text: str) -> dict:
    m = FRONTMATTER.match(text)
    return dict(FM_FIELD.findall(m.group(1))) if m else {}


def article_date(fm: dict) -> datetime.date | None:
    d = DATE.search(fm.get("date", ""))
    if not d:
        return None
    try:
        return datetime.date(int(d[1]), int(d[2]), int(d[3]))
    except ValueError:
        return None


def deterministic_scan(path: Path, slugs: set[str], today: datetime.date) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = frontmatter(text)
    body = FRONTMATTER.sub("", text)
    flags: list[dict] = []

    # age
    d = article_date(fm)
    age_days = (today - d).days if d else None
    if age_days is not None and age_days > 365:
        flags.append({"kind": "age", "detail": f"{age_days // 30} months old", "line": None})

    # dead internal links (skip the piece's own slug and external http links)
    self_slug = path.stem
    for m in INTERNAL_LINK.finditer(text):
        target = m.group(1)
        if target in ("http", "https") or target == self_slug:
            continue
        if target not in slugs and "-" in target:  # slug-shaped but missing
            line = text[: m.start()].count("\n") + 1
            flags.append({"kind": "dead-link", "detail": f"/articles/{target}", "line": line})

    # zombie references
    for rx, why in ZOMBIE:
        for m in rx.finditer(body):
            line = body[: m.start()].count("\n") + 1
            flags.append({"kind": "zombie", "detail": f"{why}: '{m.group(0)}'", "line": line})

    # deterministic score: dead links bite hardest, then zombies, then age
    score = 0
    score += 25 * sum(f["kind"] == "dead-link" for f in flags)
    score += 8 * sum(f["kind"] == "zombie" for f in flags)
    if age_days and age_days > 365:  # age only counts once it's actually flagged
        score += min(20, age_days // 60)
    return {
        "slug": self_slug,
        "title": fm.get("title", self_slug),
        "date": d.isoformat() if d else None,
        "age_days": age_days,
        "det_score": min(100, score),
        "flags": flags,
    }


# ── optional LLM judgment pass ───────────────────────────────────────────────

MODEL = os.environ.get("HALFLIFE_MODEL", "claude-opus-5")  # swappable; never hardcoded rot

SYSTEM = (
    "You are a content-decay auditor for a red-team / AI-security editorial site. "
    "Given today's date and one article, find what has EXPIRED or now reads as dated: "
    "superseded model versions, dead product or feature names, predictions that already "
    "resolved, future-tense framing that is now in the past, and version-specific claims "
    "that have moved on. Ignore timeless argument, voice, and intentionally-historical "
    "references. Be specific: quote the rotted line and say why."
)

DECAY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "score": {"type": "integer", "description": "0 = fresh, 100 = fully rotted"},
        "verdict": {"type": "string", "description": "one blunt sentence"},
        "rot": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "quote": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["quote", "why"],
            },
        },
    },
    "required": ["score", "verdict", "rot"],
}


def llm_scan(body: str, today: datetime.date):
    from anthropic import Anthropic  # imported lazily so --no-llm needs no dep

    client = Anthropic()  # resolves ANTHROPIC_API_KEY or an `ant auth login` profile
    prompt = f"Today is {today.isoformat()}.\n\nArticle:\n\n{body[:16000]}"
    resp = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": DECAY_SCHEMA}},
    )
    # Auditing your own prose shouldn't trip safety classifiers, but Opus 5 can
    # decline — handle it rather than index content[0] blind.
    if resp.stop_reason == "refusal":
        return {"score": None, "verdict": "model declined (unexpected here)", "rot": []}
    return json.loads(resp.content[0].text)


# ── report ───────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="content-decay auditor")
    ap.add_argument("dir", help="folder of markdown articles")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    ap.add_argument("--llm", action="store_true", help="add the LLM judgment pass (needs a key)")
    ap.add_argument("--json", metavar="FILE", help="also write the full report as JSON")
    args = ap.parse_args()

    today = (
        datetime.date.fromisoformat(args.today)
        if args.today
        else datetime.datetime.now(datetime.timezone.utc).date()
    )
    root = Path(args.dir)
    files = sorted(root.glob("*.md"))
    if not files:
        print(f"no .md files in {root}", file=sys.stderr)
        return 1
    slugs = {f.stem for f in files}

    rows = []
    for f in files:
        row = deterministic_scan(f, slugs, today)
        if args.llm:
            body = FRONTMATTER.sub("", f.read_text(encoding="utf-8", errors="replace"))
            j = llm_scan(body, today)
            row["llm"] = j
            row["score"] = (j.get("score") or 0) if j else row["det_score"]
        else:
            row["score"] = row["det_score"]
        rows.append(row)

    rows.sort(key=lambda r: r["score"], reverse=True)

    print(f"# Decay report — {len(rows)} articles, as of {today}\n")
    for r in rows:
        if r["score"] == 0 and not r["flags"]:
            continue
        print(f"## [{r['score']:>3}] {r['title']}  ·  `{r['slug']}`")
        if r.get("llm") and r["llm"].get("verdict"):
            print(f"    → {r['llm']['verdict']}")
        for fl in r["flags"]:
            loc = f"L{fl['line']}" if fl["line"] else "—"
            print(f"    · [{fl['kind']:<9} {loc:>5}] {fl['detail']}")
        for rot in (r.get("llm") or {}).get("rot", []):
            print(f"    · [rotted   ] {rot['quote'][:80]!r} — {rot['why']}")
        print()

    clean = sum(r["score"] == 0 and not r["flags"] for r in rows)
    print(f"---\n{clean}/{len(rows)} read clean. The rest are decaying at the rate above.")

    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"full report → {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
