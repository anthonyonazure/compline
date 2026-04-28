"""SQLite + FTS5 database layer."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY,
    corpus      TEXT NOT NULL,
    source      TEXT NOT NULL,
    ordinal     INTEGER NOT NULL,
    title       TEXT,
    author      TEXT,
    text        TEXT NOT NULL,
    weight      REAL NOT NULL DEFAULT 1.0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chunks_corpus_author ON chunks(corpus, author);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content='chunks',
    content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TABLE IF NOT EXISTS personas (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    spec_path   TEXT NOT NULL,
    margin_path TEXT NOT NULL,
    corpus      TEXT NOT NULL,
    author_filter TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS turns (
    id           INTEGER PRIMARY KEY,
    persona_id   INTEGER NOT NULL REFERENCES personas(id),
    question     TEXT NOT NULL,
    answer       TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    cite_valid   INTEGER,
    cite_total   INTEGER,
    tuned_in_run INTEGER REFERENCES tune_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_turns_persona_created ON turns(persona_id, created_at);
CREATE INDEX IF NOT EXISTS idx_turns_untuned ON turns(persona_id) WHERE tuned_in_run IS NULL;

CREATE TABLE IF NOT EXISTS citations (
    id        INTEGER PRIMARY KEY,
    turn_id   INTEGER NOT NULL REFERENCES turns(id),
    chunk_id  INTEGER NOT NULL REFERENCES chunks(id),
    quote     TEXT NOT NULL,
    valid     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_citations_turn ON citations(turn_id);
CREATE INDEX IF NOT EXISTS idx_citations_chunk ON citations(chunk_id);

CREATE TABLE IF NOT EXISTS tune_runs (
    id                 INTEGER PRIMARY KEY,
    persona_id         INTEGER NOT NULL REFERENCES personas(id),
    ran_at             TEXT NOT NULL DEFAULT (datetime('now')),
    turns_processed    INTEGER NOT NULL,
    calibration_score  REAL NOT NULL,
    margin_entry       TEXT
);

CREATE INDEX IF NOT EXISTS idx_tune_runs_persona_ran ON tune_runs(persona_id, ran_at);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
