# Contributing to Compline

Compline is small, opinionated, and keeps a tight scope on purpose. Before you open an issue or a PR, please read this — it explains both the discipline behind v0.1 and the kinds of contributions that are most useful right now.

## What v0.1 is and isn't

v0.1 is intentionally minimal:

- **One persona** (Hamilton from the Federalist Papers).
- **FTS5 only** — no embeddings.
- **CLI only** — no MCP server, no web UI.
- **One LLM dependency** (`anthropic`).
- **One generative LLM call per night** plus deterministic SQL for everything else.

This is not a prototype that grows into something larger by accident. The minimalism IS the design. Several things you might think "should be there" are deliberately deferred:

- Multi-persona debate → v0.2
- MCP server → v0.2
- Embeddings → v0.3 (as an optional `[embeddings]` extra)
- Obsidian importer → v0.3
- Evaluation harness → v0.3

If you want one of those sooner, please open an issue describing the use case before sending a PR. It's cheaper for both of us than rejecting code that's already written.

## Contributions that are highly welcome

- **Bug reports against real corpora.** Compline is most likely to break on inputs different from the bundled Federalist Papers — different chunk sizes, different citation styles, different languages. Please include a minimal repro.
- **Test cases for parser failure modes.** The LLM JSON parser already salvages truncated and prose-wrapped output, but there are surely failure shapes we haven't seen. A failing test is a wonderful contribution.
- **Documentation improvements.** Especially around the OODA loop and the `margin.md` pattern, which are the parts most likely to be misunderstood.
- **Persona spec examples.** If you write a persona for a public-domain corpus (Plato, Marcus Aurelius, the Linux kernel mailing list, etc.) and it produces good results, please open a PR adding it under `examples/`.

## Contributions that need discussion first

Anything that touches:

- The OODA loop's mechanism (deterministic checks, the single-LLM-call-per-night discipline)
- The `margin.md` file format
- The default model selection
- New top-level dependencies
- The CLI's command surface

These aren't off-limits — they're just load-bearing enough that we want to talk about it before code lands.

## Local development

```bash
git clone https://github.com/<you>/compline.git
cd compline
python3.12 -m venv .venv  # or 3.13
source .venv/bin/activate
pip install -e ".[dev]"

# Run the test suite (no API key required — engine tests stub the LLM)
pytest -q

# Run the linter and the formatter
ruff check src tests
ruff format src tests

# Try the full pipeline against the bundled demo
export ANTHROPIC_API_KEY=...
compline init
compline ingest examples/federalist/papers --corpus federalist
compline ask examples/federalist/Hamilton.persona.md "your question"
compline tune examples/federalist/Hamilton.persona.md
compline chart Hamilton --output chart.svg
```

The full test suite should run in under a second on any modern machine. If it gets slower than that, something is probably wrong.

## Discipline checklist for PRs

Before opening a PR, please confirm:

- [ ] `pytest -q` passes locally
- [ ] `ruff check src tests` passes
- [ ] `ruff format --check src tests` passes
- [ ] No new top-level dependencies (or you've discussed it in an issue first)
- [ ] No new generative LLM calls in the OODA loop (one per night, total)
- [ ] No use of "self-improving", "agent", or "RAG" in user-facing copy without discussion (see `CLAUDE.md` for the locked positioning)

## Reporting security issues

Please do not open a public issue for security-sensitive bugs. Email the maintainer directly.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
