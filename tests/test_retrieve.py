"""Retrieval tests with focus on stopword behavior."""

from __future__ import annotations

from compline.db import connect, init_schema
from compline.ingest import ingest_directory
from compline.retrieve import _fts_query, retrieve


def test_fts_query_strips_stopwords():
    q = _fts_query("What did you mean by energy in the executive?")
    assert "the" not in q
    assert "did" not in q
    assert "you" not in q
    assert "what" not in q
    assert '"energy"' in q
    assert '"executive"' in q


def test_fts_query_falls_back_when_only_stopwords():
    q = _fts_query("What did you?")
    # Should not be empty — must always return something queryable.
    assert q
    assert "OR" in q or '"' in q


def test_retrieve_prefers_content_match_over_stopword_noise(tmp_path):
    # Two chunks: A is the correct answer, B is filler that matches stopwords.
    a = tmp_path / "a.md"
    a.write_text(
        "---\nauthor: HAMILTON\n---\n\n# A\n\n"
        + ("Energy in the executive is a leading character in the definition of good "
           "government. Decision, activity, secrecy, and despatch will generally "
           "characterize the proceedings of one man. " * 3),
        encoding="utf-8",
    )
    b = tmp_path / "b.md"
    b.write_text(
        "---\nauthor: HAMILTON\n---\n\n# B\n\n"
        + ("This is a generic essay about other matters. The text references "
           "many common words that you would expect in any document. "
           "Did this concern the writer at the time? It did not. " * 3),
        encoding="utf-8",
    )
    conn = connect(tmp_path / "c.db")
    init_schema(conn)
    ingest_directory(conn, tmp_path, "federalist")

    hits = retrieve(
        conn,
        "What did you mean by energy in the executive?",
        corpus="federalist",
        author_filter="HAMILTON",
    )
    assert hits, "expected at least one hit"
    top_source = next(
        (
            r["source"]
            for r in conn.execute(
                "SELECT source FROM chunks WHERE id = ?", (hits[0]["chunk_id"],)
            ).fetchall()
        ),
        None,
    )
    assert top_source == "a.md", f"top hit should be the content match, got {top_source}"
