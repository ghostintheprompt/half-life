# half-life

A content-decay auditor. It reads a folder of writing and tells you what's rotted.

Content rots the moment it's published. The 2019 tutorial with the dead `npm install`. The SEO fossil nobody updated. The doc describing a folder that no longer exists. The model ID that shipped last quarter and now dates the whole piece. Human content decays silently and pretends it hasn't — the static page frozen in amber, the broken link that's been broken since a redesign two years back. Lasting forever isn't the goal; it's the dishonest cosplay of the monument.

`half-life` is the honest version: point it at your archive and it ranks every piece by how far it's decayed.

## Two passes

**Deterministic** (no API key, runs anywhere):
- **Dead internal links** — `[…](/articles/slug)` where the target doesn't exist.
- **Age** — how long since the frontmatter date.
- **Zombie references** — superseded model IDs (`claude-3`, `gpt-4o`, aging `claude-4.x`), retired product names, future-tense framing that's already resolved.

**LLM judgment** (`--llm`, needs a key) — reads each piece and names what expired: predictions that already landed, version-specific claims that moved on, dead features. Scored, with the rotted lines quoted.

```bash
python half_life.py ./articles --today 2026-07-30            # deterministic, ranked report
python half_life.py ./articles --llm --json decay.json       # + LLM pass, full JSON
pip install -r requirements.txt                              # only needed for --llm
```

## The self-aware part

The model `half-life` uses to hunt stale model IDs is read from the environment, never hardcoded:

```python
MODEL = os.environ["HALFLIFE_MODEL"] if os.environ.get("HALFLIFE_MODEL") else "claude-opus-5"
```

A tool about rot that rots on its own is the joke that writes itself. Swap the model without touching the code:

```bash
HALFLIFE_MODEL=claude-haiku-4-5 python half_life.py ./articles --llm
```

## What it found on its own author's site

Run against a ~120-article red-team catalog (`report.example.md`), the deterministic pass alone surfaced a dead `/articles/…` link, three superseded `claude-3` IDs in one piece, `gpt-4o` scattered across another, and a `claude-sonnet-4-5-*` string baked into example code — none of which any human had flagged. 113 of 122 read clean; the other nine were quietly decaying.

The bots didn't kill the internet. They just stopped pretending it was ever alive-forever. Nothing is solid — so build things that know it.

---
*Defensive tooling for your own archives. Reads files, calls a model you configure, writes a report. Nothing leaves your machine except the article text you send to the LLM in `--llm` mode.*
