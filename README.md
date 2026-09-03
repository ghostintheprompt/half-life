<div align="center">
  <img src="half_life.png" width="500" alt="half-life">
  <h1>half-life</h1>
</div>

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

## A second kind of rot

Stale prose isn't the only way content decays. A repo can be fully fixed
locally and still be running a months-old build in production — silently,
with no crash and no error page, because nothing about a working homepage
tells you the backend routes behind it stopped resolving.

**Deploy-drift check** (`--deploy-check`, no manifest, no LLM):

```bash
python half_life.py --deploy-check /path/to/netlify-repo https://example.com
```

It reads the repo's own `netlify.toml` to learn which routes are supposed to
be real — serverless functions, pretty-path redirects — then asks the live
site whether each one actually resolves, or whether it's quietly falling
through to the same SPA-fallback page as a made-up path. A route that returns
the exact same bytes as a path that cannot possibly exist isn't live; it's
being swallowed.

This isn't hypothetical. It's how a four-month-old production outage on a
live Polygon contract got found — every route silently serving the same
stale `index.html`, including the one that issues signed jackpot payouts.

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

Run against the ~134-article red-team catalog (`report.example.md`), the deterministic pass caught `GPT-4o` and `GPT-4` scattered across three separate pieces, a `claude-sonnet-4-5-*` string baked into example code, and — best case for the thesis — its own stale model IDs in the article about itself, `half-life-came-for-me-first`. 127 of 134 read clean; the other seven were quietly decaying.

The bots didn't kill the internet. They just stopped pretending it was ever alive-forever. Nothing is solid — so build things that know it.

---
*Defensive tooling for your own archives. Reads files, calls a model you configure, writes a report. Nothing leaves your machine except the article text you send to the LLM in `--llm` mode.*
