# Compline — Project Instructions

## What this is
OSS framework for **knowledge-grounded personas that self-improve**. A persona is bound to a corpus (FTS5 index over Markdown/PDF/audio transcripts). After each QA session, a nightly OODA loop appends notes to the persona's `margin.md`, which is auto-loaded into the system prompt. The persona's accumulated identity lives in that one file.

## Locked positioning
**Hook:** AI that gets sharper while you sleep.

**Subhead:** Bind a persona to your library — books, podcasts, courses, papers. It cites the page. It argues with the other personas. Every night it scores its own answers, finds where it was vague or wrong, and tunes itself. Month two is measurably better than month one. Show me another framework that ships that chart.

## Pillar priority (do not reorder in marketing copy)
1. Self-evolving (rare claim, leads everything)
2. Knowledge-grounded with citations (table stakes; earns trust)
3. Multi-persona / debate (one verb only — "argues")
4. Measurable improvement chart (credibility wedge)

## v0.1 scope (LOCKED — resist scope creep)
- ONE persona (Hamilton from the Federalist Papers)
- FTS5 only — no embeddings
- CLI only — no MCP, no web UI
- pip-installable in <8 seconds, no GPU, no model download
- Federalist Papers pre-indexed in the wheel

## Deferred
- v0.2: multi-persona (Madison + Jay), TS MCP wrapper, one outside corpus example
- v0.3: pick ONE of {Obsidian importer, optional embeddings, evaluation harness}
- v0.4: citation auditor as standalone CLI, web UI, hosted demo

## The killer concept: margin.md
Every persona owns a markdown file. The OODA loop appends one note per night. Auto-loaded into system prompt → IS the persona's identity. `git diff` on the file is the demo. Inspectable, diff-able, screenshotable.

## OODA mechanism (LOCKED)
The whole loop is mostly deterministic:
- **Citation validity** = literal substring/keyword match between answer claims and cited chunks. SQL.
- **Coverage map** = which chunks were cited this week / never. SQL.
- **Follow-up classifier** = was the user's next message a clarifier or a confirmation? **One LLM call per turn**, hard binary label.
- **Nightly tune** = **one LLM call per night** generates a diff: one prompt edit + one corpus reweight + one margin entry.

Total LLM cost per night must stay <$0.50 on a small corpus, or adopters won't run it.

## Tune-one-thing-per-night discipline
Resist the urge to make the nightly diff a sweeping rewrite. ONE prompt edit, ONE corpus reweight, ONE margin entry. This:
- Makes the overnight-diff readable as a screenshot
- Prevents persona thrash
- Maps to the "compline" metaphor (the slow nightly hour)
- Gives users a narrative ("tonight Hamilton learned X")

## Demo corpus
Federalist Papers, public domain, ~85 essays. Three named authors → three personas (v0.2). v0.1 ships only Hamilton. Constitutional-law nerds amplify on launch for free.

## Killer demo (forced by hook)
1. **Hero**: 30-night calibration chart on Federalist Papers, real data from owner's runs. Annotated.
2. **Secondary**: `git log` of `Hamilton.margin.md` showing 30 nights of accumulated lessons.
3. Both shipped as artifacts in `examples/`.

## Release posture
**Stealth-then-bang.** Public repo from day one (or close to it), unannounced for 4 weeks. Polish, close own issues, run real nightly tunes for chart data. Then planned launch:

| Step | Time |
|---|---|
| HN "Show HN" post | 08:00 PT launch day |
| r/LocalLLaMA + r/MachineLearning | 08:30 PT |
| Twitter thread (chart as hero) | 09:00 PT |
| Personal blog post | 09:30 PT |
| Reply to every comment | next 48h |

**Target launch**: Tue 2026-06-02 (conservative) or Tue 2026-05-19 (aggressive).

## Hard gates (do not skip)
- **G1 (end W1)**: real QA session produces sensible margin.md entry → else debug mechanism
- **G2 (end W2) ⛔ KILL SWITCH**: 14-night chart shows monotonic improvement → else shelve, do not paper over
- **G3 (end W3)**: README passes "would a stranger star this cold?" test → else rewrite before launch
- **G4 (end W4)**: 30+ nights data + outsider installed end-to-end → else push launch +1 week
- **G5 (T+7)**: ≥1500 stars = HIT, 500-1500 = WARM, <500 = COLD; branch v0.2 strategy on result

## Things to NEVER do
- Lead marketing with corpus-grounding (RAG-fatigue collision)
- Use the word "self-improving" in copy (AutoGPT-burned)
- Add features pre-launch (stealth = polish only)
- Ship a flat or noisy chart (G2 is non-negotiable)
- Argue with name conflicts post-launch — fall back without debate
- Multi-persona debate in v0.1 (Madison + Jay = v0.2)
- Embeddings in v0.1 (= v0.3)

## Tribe
**Acquisition**: AI-engineering Python devs (~250K, install OSS routinely, drive star velocity)
**Retention**: researchers, indie hackers, domain experts running on personal corpora long-term

## Language choice
Python core (matches tribe lingua franca). TS MCP wrapper at v0.2 only.

## Reference
Brainstorming session that produced this plan: `/Users/anthony/_bmad-output/analysis/brainstorming-session-2026-04-27.md`
