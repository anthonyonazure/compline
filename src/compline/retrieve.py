"""FTS5 retrieval over the chunks corpus.

Ranking blends BM25 (FTS5 native) with the per-chunk ``weight`` column,
which is updated by the OODA tune step (boost cited chunks, decay
never-cited ones — the SRS-adapted layer).
"""

from __future__ import annotations

import re
import sqlite3

DEFAULT_LIMIT = 6


def _fts_query(question: str) -> str:
    """Strip punctuation, OR the remaining keyword tokens.

    Conservative tokenization for v0.1 — FTS5 handles stemming.
    Words shorter than 3 chars are dropped to avoid common-word noise.
    """
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']+", question)
    keywords = [t.lower() for t in tokens if len(t) >= 3]
    if not keywords:
        return question
    # Quote each token to disable FTS5 syntax interpretation, then OR.
    return " OR ".join(f'"{k}"' for k in keywords)


def retrieve(
    conn: sqlite3.Connection,
    question: str,
    *,
    corpus: str,
    author_filter: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict]:
    fts_q = _fts_query(question)
    sql = """
        SELECT
            c.id           AS chunk_id,
            c.title        AS title,
            c.author       AS author,
            c.text         AS text,
            c.weight       AS weight,
            bm25(chunks_fts) AS bm25
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        WHERE chunks_fts MATCH ?
          AND c.corpus = ?
    """
    params: list = [fts_q, corpus]
    if author_filter:
        sql += " AND c.author = ?"
        params.append(author_filter)
    # bm25 is lower-is-better; multiply by 1/weight so heavier chunks rank higher.
    sql += " ORDER BY (bm25(chunks_fts) / c.weight) ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
