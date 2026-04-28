"""Ingest a directory of markdown files into the corpus.

Chunking strategy for v0.1: split on blank lines (paragraphs), then merge
short adjacent paragraphs up to a target token count. No embeddings.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

# Cheap token estimate — words * 1.3. Good enough for batching.
TARGET_TOKENS = 350
MIN_TOKENS = 60


@dataclass(frozen=True)
class Chunk:
    corpus: str
    source: str
    ordinal: int
    title: str | None
    author: str | None
    text: str


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def split_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def merge_to_target(paragraphs: list[str]) -> list[str]:
    """Merge adjacent paragraphs until each is at least MIN_TOKENS, capped at TARGET_TOKENS."""
    out: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    for p in paragraphs:
        ptok = estimate_tokens(p)
        if buf and buf_tokens + ptok > TARGET_TOKENS and buf_tokens >= MIN_TOKENS:
            out.append("\n\n".join(buf))
            buf, buf_tokens = [p], ptok
        else:
            buf.append(p)
            buf_tokens += ptok
    if buf:
        out.append("\n\n".join(buf))
    return out


def parse_markdown_header(text: str) -> tuple[str | None, str]:
    """If the file starts with a `# Title` line, peel it off and return as title."""
    m = re.match(r"#\s+(.+?)\n", text)
    if not m:
        return None, text
    return m.group(1).strip(), text[m.end() :]


def parse_frontmatter_meta(text: str) -> tuple[dict[str, str], str]:
    """Same minimal frontmatter parser as persona.py — duplicated to avoid coupling."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    header = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    meta = {}
    for line in header.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, body


def chunk_file(path: Path, corpus: str) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter_meta(raw)
    title, body = parse_markdown_header(body)
    title = meta.get("title") or title
    author = meta.get("author")
    paragraphs = split_paragraphs(body)
    chunked = merge_to_target(paragraphs)
    return [
        Chunk(
            corpus=corpus,
            source=path.name,
            ordinal=i,
            title=title,
            author=author,
            text=text,
        )
        for i, text in enumerate(chunked)
    ]


SKIP_FILENAMES = {"README.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE.md"}


def _is_corpus_file(path: Path) -> bool:
    """Filter out metadata files: persona specs, margin notes, READMEs, etc."""
    name = path.name
    if name in SKIP_FILENAMES:
        return False
    return not (name.endswith(".persona.md") or name.endswith(".margin.md"))


def ingest_directory(conn: sqlite3.Connection, directory: Path, corpus: str) -> int:
    """Ingest every corpus `.md` file in the directory. Returns count of inserted chunks."""
    files = sorted(p for p in directory.glob("*.md") if _is_corpus_file(p))
    inserted = 0
    for path in files:
        chunks = chunk_file(path, corpus)
        for c in chunks:
            conn.execute(
                "INSERT INTO chunks (corpus, source, ordinal, title, author, text) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (c.corpus, c.source, c.ordinal, c.title, c.author, c.text),
            )
            inserted += 1
    conn.commit()
    return inserted
