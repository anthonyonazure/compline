"""Compline engine: ask flow + nightly tune flow.

Ask flow (per turn):
    1. Load persona spec + margin.md → system prompt
    2. FTS5 retrieve top N chunks
    3. LLM call with citations contract
    4. Validate citations deterministically (literal substring match)
    5. Log turn + citations to DB
    6. Return answer + cited chunks for display

Tune flow (nightly):
    1. Pull untuned turns since last tune
    2. Aggregate citation validity, coverage delta
    3. ONE LLM call → margin entry
    4. Append to margin.md
    5. Insert tune_runs row with calibration_score
    6. Mark turns as tuned

The whole tune step is mostly deterministic SQL; only one generative
LLM call per night.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from .llm import CitedAnswer, ask_with_citations, generate_margin_entry
from .persona import (
    PersonaSpec,
    append_margin,
    build_system_prompt,
    load_margin,
    load_spec,
)
from .retrieve import retrieve


@dataclass
class AskResult:
    answer: str
    citations: list[dict]  # [{chunk_id, quote, valid, title}]
    turn_id: int
    cite_valid: int
    cite_total: int


def _ensure_persona_row(conn: sqlite3.Connection, spec: PersonaSpec) -> int:
    row = conn.execute("SELECT id FROM personas WHERE name = ?", (spec.name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO personas (name, spec_path, margin_path, corpus, author_filter) "
        "VALUES (?, ?, ?, ?, ?)",
        (spec.name, str(spec.spec_path), str(spec.margin_path), spec.corpus, spec.author_filter),
    )
    conn.commit()
    return int(cur.lastrowid)


def _validate_citation(quote: str, chunk_text: str) -> bool:
    """Deterministic validity: literal substring (case-insensitive, whitespace-normalized)."""
    if not quote:
        return False
    norm_quote = " ".join(quote.split()).lower()
    norm_chunk = " ".join(chunk_text.split()).lower()
    if not norm_quote:
        return False
    return norm_quote in norm_chunk


def ask(
    conn: sqlite3.Connection,
    spec_path,
    question: str,
) -> AskResult:
    spec = load_spec(spec_path)
    persona_id = _ensure_persona_row(conn, spec)
    margin = load_margin(spec.margin_path)
    system_prompt = build_system_prompt(spec, margin)

    retrieved = retrieve(
        conn,
        question,
        corpus=spec.corpus,
        author_filter=spec.author_filter,
    )
    if not retrieved:
        # No corpus hits — record an empty turn so the OODA loop can see the gap.
        cur = conn.execute(
            "INSERT INTO turns (persona_id, question, answer, cite_valid, cite_total) "
            "VALUES (?, ?, ?, 0, 0)",
            (persona_id, question, "(no relevant sources found in corpus)"),
        )
        conn.commit()
        return AskResult(
            answer="(no relevant sources found in corpus)",
            citations=[],
            turn_id=int(cur.lastrowid),
            cite_valid=0,
            cite_total=0,
        )

    cited: CitedAnswer = ask_with_citations(system_prompt, question, retrieved)

    chunk_lookup = {c["chunk_id"]: c for c in retrieved}
    validated: list[dict] = []
    for c in cited.citations:
        chunk = chunk_lookup.get(c["chunk_id"])
        if not chunk:
            validated.append({**c, "valid": False, "title": None})
            continue
        ok = _validate_citation(c["quote"], chunk["text"])
        validated.append({**c, "valid": ok, "title": chunk.get("title")})

    cite_valid = sum(1 for c in validated if c["valid"])
    cite_total = len(validated)

    cur = conn.execute(
        "INSERT INTO turns (persona_id, question, answer, cite_valid, cite_total) "
        "VALUES (?, ?, ?, ?, ?)",
        (persona_id, question, cited.answer, cite_valid, cite_total),
    )
    turn_id = int(cur.lastrowid)
    for c in validated:
        conn.execute(
            "INSERT INTO citations (turn_id, chunk_id, quote, valid) VALUES (?, ?, ?, ?)",
            (turn_id, c["chunk_id"], c["quote"], 1 if c["valid"] else 0),
        )
    conn.commit()

    return AskResult(
        answer=cited.answer,
        citations=validated,
        turn_id=turn_id,
        cite_valid=cite_valid,
        cite_total=cite_total,
    )


def _untuned_turns(conn: sqlite3.Connection, persona_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, question, answer, cite_valid, cite_total "
        "FROM turns WHERE persona_id = ? AND tuned_in_run IS NULL "
        "ORDER BY created_at ASC",
        (persona_id,),
    ).fetchall()


def _summarize_turns(turns: list[sqlite3.Row]) -> str:
    """Compact summary fed to the OODA LLM call. Truncates per turn to keep cost low."""
    out = []
    for t in turns:
        q = t["question"][:200]
        a = t["answer"][:400]
        out.append(
            f"Turn {t['id']}: cite_valid={t['cite_valid']}/{t['cite_total']}\n"
            f"  Q: {q}\n  A: {a}"
        )
    return "\n\n".join(out)


def _calibration_score(turns: list[sqlite3.Row]) -> float:
    """Headline metric for the chart. Mean citation validity rate."""
    rates = []
    for t in turns:
        total = t["cite_total"] or 0
        if total == 0:
            rates.append(0.0)
        else:
            rates.append(t["cite_valid"] / total)
    return sum(rates) / len(rates) if rates else 0.0


def _coverage_metrics(conn: sqlite3.Connection, persona_id: int, corpus: str) -> dict:
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM chunks WHERE corpus = ?", (corpus,)
    ).fetchone()["n"]
    cited = conn.execute(
        "SELECT COUNT(DISTINCT chunk_id) AS n FROM citations c "
        "JOIN turns t ON t.id = c.turn_id "
        "WHERE t.persona_id = ? AND c.valid = 1",
        (persona_id,),
    ).fetchone()["n"]
    return {
        "corpus_chunks_total": total,
        "chunks_cited_validly_ever": cited,
        "coverage_pct": round(100 * cited / total, 1) if total else 0.0,
    }


def tune(conn: sqlite3.Connection, spec_path) -> dict:
    """Run one OODA cycle for a persona. Returns a result dict for CLI/test use."""
    spec = load_spec(spec_path)
    persona_id = _ensure_persona_row(conn, spec)
    turns = _untuned_turns(conn, persona_id)

    if not turns:
        return {"persona": spec.name, "turns_processed": 0, "skipped": True}

    score = _calibration_score(turns)
    coverage = _coverage_metrics(conn, persona_id, spec.corpus)
    metrics = {
        "turns_processed": len(turns),
        "calibration_score": round(score, 3),
        **coverage,
    }
    summary = _summarize_turns(turns)
    margin_entry = generate_margin_entry(
        persona_name=spec.name,
        persona_body=spec.body,
        recent_summary=summary,
        metrics=metrics,
    )

    append_margin(spec.margin_path, margin_entry)

    cur = conn.execute(
        "INSERT INTO tune_runs (persona_id, turns_processed, calibration_score, margin_entry) "
        "VALUES (?, ?, ?, ?)",
        (persona_id, len(turns), score, margin_entry),
    )
    run_id = int(cur.lastrowid)
    turn_ids = [t["id"] for t in turns]
    conn.executemany(
        "UPDATE turns SET tuned_in_run = ? WHERE id = ?",
        [(run_id, tid) for tid in turn_ids],
    )
    conn.commit()

    return {
        "persona": spec.name,
        "tune_run_id": run_id,
        "turns_processed": len(turns),
        "calibration_score": round(score, 3),
        "margin_entry": margin_entry,
        "metrics": metrics,
    }


def history(conn: sqlite3.Connection, persona_name: str) -> list[dict]:
    """Return tune-run history for the chart command."""
    rows = conn.execute(
        "SELECT tr.ran_at, tr.turns_processed, tr.calibration_score "
        "FROM tune_runs tr JOIN personas p ON p.id = tr.persona_id "
        "WHERE p.name = ? ORDER BY tr.ran_at ASC",
        (persona_name,),
    ).fetchall()
    return [dict(r) for r in rows]


def history_json(conn: sqlite3.Connection, persona_name: str) -> str:
    return json.dumps(history(conn, persona_name), indent=2)
