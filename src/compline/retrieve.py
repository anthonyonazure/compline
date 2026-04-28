"""FTS5 retrieval over the chunks corpus.

Ranking blends BM25 (FTS5 native) with the per-chunk ``weight`` column,
which is updated by the OODA tune step (boost cited chunks, decay
never-cited ones — the SRS-adapted layer).
"""

from __future__ import annotations

import re
import sqlite3

DEFAULT_LIMIT = 6

# Compact English stopword list. Tuned for the question→FTS5 path: focuses on
# high-frequency words that drown out content terms in BM25 scoring. NOT a
# linguistic stopword list — keeps words like "no" / "not" because negations
# can be load-bearing in retrieval.
STOPWORDS = frozenset(
    """
    the and you your yours yourself yourselves did does done has have having
    had was were been being are was were what when where why how who whom which
    that this those these them they their theirs there here from with into onto
    upon about above below over under again further then once also too very can
    will would could should may might must shall ought
    a an as at be by do for if in is it of on or so to up
    """.split()
)


def _fts_query(question: str) -> str:
    """Strip punctuation, drop stopwords, OR the remaining content tokens.

    FTS5 handles stemming via the porter tokenizer; we only need to keep the
    content words. Without stopword filtering, BM25 picks up generic noise
    (the/and/you/did) and outranks chunks that match the actual concept.
    """
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']+", question)
    keywords = [t.lower() for t in tokens if len(t) >= 3 and t.lower() not in STOPWORDS]
    if not keywords:
        # Fall back to all >=3-char tokens so we never produce an empty query.
        keywords = [t.lower() for t in tokens if len(t) >= 3]
    if not keywords:
        return question
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
