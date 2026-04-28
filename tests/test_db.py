"""Schema + FTS5 sanity tests. No API key needed."""

from __future__ import annotations

from compline.db import connect, init_schema


def test_schema_initializes_idempotently(tmp_path):
    db = tmp_path / "c.db"
    conn = connect(db)
    init_schema(conn)
    init_schema(conn)
    tables = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        ).fetchall()
    }
    for required in {"chunks", "chunks_fts", "personas", "turns", "citations", "tune_runs"}:
        assert required in tables, f"missing {required} in {tables}"


def test_fts5_round_trip(tmp_path):
    conn = connect(tmp_path / "c.db")
    init_schema(conn)
    conn.execute(
        "INSERT INTO chunks (corpus, source, ordinal, title, author, text) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "federalist",
            "f-no-1.md",
            0,
            "Federalist No. 1",
            "HAMILTON",
            "Energy in the executive is a leading character in the definition of good government.",
        ),
    )
    conn.commit()
    rows = conn.execute(
        "SELECT c.id, c.text FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid "
        "WHERE chunks_fts MATCH ?",
        ("energy executive",),
    ).fetchall()
    assert len(rows) == 1
    assert "Energy in the executive" in rows[0]["text"]


def test_foreign_keys_enforced(tmp_path):
    import sqlite3

    conn = connect(tmp_path / "c.db")
    init_schema(conn)
    try:
        conn.execute(
            "INSERT INTO turns (persona_id, question, answer) VALUES (?, ?, ?)",
            (999, "q", "a"),
        )
        conn.commit()
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised, "expected FK constraint to reject persona_id=999"
