# Federalist Papers — Compline demo corpus

The 85 essays of *The Federalist Papers* (1787-1788), public domain, are the canonical demo corpus for Compline.

## Why this corpus
- **Public domain.** No licensing friction.
- **Three named authors** (Alexander Hamilton, James Madison, John Jay) → three personas with real, citable disagreements.
- **Small enough to bundle** (~85 essays) but large enough to make retrieval non-trivial.
- **Constitutional-law nerds amplify it for free** when the demo lands on social media.

## What ships in v0.1
- `Hamilton.persona.md` — the Hamilton persona spec (this directory)
- `questions.md` — 18 curated questions across the major thematic clusters of Hamilton's writings, used to seed calibration data
- After tune runs, a `Hamilton.margin.md` will appear here automatically

## Running a batch of questions

For seeding W2 calibration data without hand-typing each question:

    python scripts/run_questions.py \
        --persona examples/federalist/Hamilton.persona.md \
        --questions examples/federalist/questions.md

By default the runner skips questions that have already been asked. Pass `--force` to re-ask everything, or `--limit N` to cap the batch. Use `--dry-run` to see which questions would be asked without calling the LLM.

## What's deferred to v0.2
- `Madison.persona.md`, `Jay.persona.md` — for multi-persona debate
- A pre-indexed SQLite database bundled in the wheel

## Bringing your own corpus copy

The Federalist Papers are public domain. The simplest free source is Project Gutenberg:

    https://www.gutenberg.org/ebooks/1404

For Compline ingestion, split the essays into one `.md` file per essay with frontmatter:

    ---
    author: HAMILTON   # or MADISON, or JAY
    ---

    # Federalist No. N: <Title>

    <body>

Then:

    compline init
    compline ingest path/to/federalist --corpus federalist
    compline ask examples/federalist/Hamilton.persona.md "What did you mean by 'energy in the executive'?"
    compline tune examples/federalist/Hamilton.persona.md
