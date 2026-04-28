"""Chunking + ingest tests. No API key needed."""

from __future__ import annotations

from compline.db import connect, init_schema
from compline.ingest import chunk_file, ingest_directory, merge_to_target, split_paragraphs


def test_split_paragraphs():
    text = "First para.\n\nSecond para.\n\n\n  Third para.  "
    paras = split_paragraphs(text)
    assert paras == ["First para.", "Second para.", "Third para."]


def test_merge_respects_minimum():
    short = ["one two three"] * 5  # each is too short
    merged = merge_to_target(short)
    assert len(merged) == 1, "short paragraphs should merge"


def test_chunk_file_extracts_title_and_author(tmp_path):
    f = tmp_path / "f-no-1.md"
    f.write_text(
        "---\nauthor: HAMILTON\n---\n\n"
        "# Federalist No. 1\n\n"
        + ("After an unequivocal experience of the inefficacy of the subsisting federal government, "
           "you are called upon to deliberate on a new constitution for the United States of America. "
           * 5)
        + "\n\n"
        + ("The subject speaks its own importance, comprehending in its consequences nothing less "
           "than the existence of the union, the safety and welfare of the parts of which it is "
           "composed. " * 5),
        encoding="utf-8",
    )
    chunks = chunk_file(f, corpus="federalist")
    assert len(chunks) >= 1
    assert chunks[0].title == "Federalist No. 1"
    assert chunks[0].author == "HAMILTON"
    assert chunks[0].corpus == "federalist"


def test_ingest_skips_metadata_files(tmp_path):
    (tmp_path / "Hamilton.persona.md").write_text(
        "---\ncorpus: federalist\n---\n\nYou are Hamilton.", encoding="utf-8",
    )
    (tmp_path / "Hamilton.margin.md").write_text("# margin\n\nlesson", encoding="utf-8")
    (tmp_path / "README.md").write_text("# README\n\ndocs", encoding="utf-8")
    (tmp_path / "f-no-1.md").write_text(
        "---\nauthor: HAMILTON\n---\n\n# F1\n\n"
        + ("Real corpus content here, long enough to be a chunk. " * 20),
        encoding="utf-8",
    )
    conn = connect(tmp_path / "c.db")
    init_schema(conn)
    n = ingest_directory(conn, tmp_path, "federalist")
    assert n >= 1
    sources = {r["source"] for r in conn.execute("SELECT DISTINCT source FROM chunks").fetchall()}
    assert sources == {"f-no-1.md"}, f"unexpected sources ingested: {sources}"


def test_ingest_directory_populates_fts(tmp_path):
    f = tmp_path / "x.md"
    f.write_text(
        "---\nauthor: HAMILTON\n---\n\n# Test\n\n"
        + ("Energy in the executive is a leading character in the definition of good government. "
           * 10),
        encoding="utf-8",
    )
    conn = connect(tmp_path / "c.db")
    init_schema(conn)
    n = ingest_directory(conn, tmp_path, "federalist")
    assert n >= 1
    rows = conn.execute(
        "SELECT c.text FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid "
        "WHERE chunks_fts MATCH 'energy executive'"
    ).fetchall()
    assert len(rows) >= 1
