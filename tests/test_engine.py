"""Engine-level tests with the LLM stubbed.

Verifies the wiring: ask flow logs turns + citations and validates them
deterministically; tune flow aggregates and writes a margin entry.
"""

from __future__ import annotations

from compline import engine
from compline.db import connect, init_schema
from compline.ingest import ingest_directory
from compline.llm import CitedAnswer


def _seed_corpus(tmp_path):
    f = tmp_path / "f-no-70.md"
    f.write_text(
        "---\nauthor: HAMILTON\n---\n\n# Federalist No. 70\n\n"
        + "Energy in the executive is a leading character in the definition of good government. "
        + "It is essential to the protection of the community against foreign attacks. "
        * 4
        + "\n\n"
        + "A feeble executive implies a feeble execution of the government. "
        + "A feeble execution is but another phrase for a bad execution. "
        * 4,
        encoding="utf-8",
    )
    p = tmp_path / "Hamilton.persona.md"
    p.write_text(
        "---\nname: Hamilton\ncorpus: federalist\nauthor_filter: HAMILTON\n---\n\n"
        "You are Alexander Hamilton.",
        encoding="utf-8",
    )
    conn = connect(tmp_path / "c.db")
    init_schema(conn)
    ingest_directory(conn, tmp_path, "federalist")
    return conn, p


def test_validate_citation_substring():
    chunk = "Energy in the executive is a leading character in the definition of good government."
    assert engine._validate_citation("energy in the executive", chunk) is True
    assert engine._validate_citation("totally fabricated quote", chunk) is False
    assert engine._validate_citation("", chunk) is False


def test_ask_validates_citations_and_logs_turn(tmp_path, monkeypatch):
    conn, persona_path = _seed_corpus(tmp_path)

    def fake_ask(system_prompt, question, retrieved):
        # Return one valid citation (substring of seeded chunk) and one invalid one.
        chunk_id = retrieved[0]["chunk_id"]
        return CitedAnswer(
            answer="Energy is essential to good government.",
            citations=[
                {"chunk_id": chunk_id, "quote": "Energy in the executive"},
                {"chunk_id": chunk_id, "quote": "this phrase is not in the source"},
            ],
            raw="(stub)",
        )

    monkeypatch.setattr(engine, "ask_with_citations", fake_ask)

    result = engine.ask(conn, persona_path, "What did you say about executive energy?")
    assert result.cite_total == 2
    assert result.cite_valid == 1

    rows = conn.execute("SELECT * FROM turns").fetchall()
    assert len(rows) == 1
    cites = conn.execute("SELECT * FROM citations").fetchall()
    assert len(cites) == 2
    assert sum(c["valid"] for c in cites) == 1


def test_tune_writes_margin_and_marks_turns(tmp_path, monkeypatch):
    conn, persona_path = _seed_corpus(tmp_path)

    def fake_ask(system_prompt, question, retrieved):
        return CitedAnswer(
            answer="Stub answer.",
            citations=[{"chunk_id": retrieved[0]["chunk_id"], "quote": "Energy in the executive"}],
            raw="(stub)",
        )

    monkeypatch.setattr(engine, "ask_with_citations", fake_ask)

    captured: dict = {}

    def fake_margin(*, persona_name, persona_body, recent_summary, metrics, model="x"):
        captured["metrics"] = metrics
        return "Tonight Hamilton noted: cite Federalist 70 first when asked about executive energy."

    monkeypatch.setattr(engine, "generate_margin_entry", fake_margin)

    engine.ask(conn, persona_path, "What about executive energy?")
    engine.ask(conn, persona_path, "And feeble executives?")
    result = engine.tune(conn, persona_path)
    assert result["turns_processed"] == 2
    assert "Federalist 70" in result["margin_entry"]
    assert captured["metrics"]["calibration_score"] == 1.0

    margin_path = persona_path.with_name("Hamilton.margin.md")
    assert margin_path.exists()
    assert "Federalist 70" in margin_path.read_text(encoding="utf-8")

    untuned = conn.execute(
        "SELECT COUNT(*) AS n FROM turns WHERE tuned_in_run IS NULL"
    ).fetchone()["n"]
    assert untuned == 0


def test_tune_skips_when_no_untuned_turns(tmp_path, monkeypatch):
    conn, persona_path = _seed_corpus(tmp_path)
    result = engine.tune(conn, persona_path)
    assert result.get("skipped") is True
