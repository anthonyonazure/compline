#!/usr/bin/env python3
"""Fetch The Federalist Papers from Project Gutenberg and split into per-essay markdown.

One-shot reproducibility script. Output goes to examples/federalist/papers/
as federalist-NN.md, one file per essay, with frontmatter:

    ---
    number: N
    author: HAMILTON | MADISON | JAY | HAMILTON_AND_MADISON | MADISON_WITH_HAMILTON
    ---

    # Federalist No. N: <Title>

    <body>

The script strips the Project Gutenberg legal header/footer. The text
itself is public domain (1787-1788). Re-run anytime to refresh from
upstream.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

PG_URL = "https://www.gutenberg.org/cache/epub/1404/pg1404.txt"
OUT_DIR = Path(__file__).resolve().parent.parent / "examples" / "federalist" / "papers"

PG_START = re.compile(r"\*\*\* START OF THE PROJECT GUTENBERG EBOOK[^*]+\*\*\*")
PG_END = re.compile(r"\*\*\* END OF THE PROJECT GUTENBERG EBOOK[^*]+\*\*\*")
ESSAY_HEAD = re.compile(r"^FEDERALIST No\.\s+(\d+)\s*$", re.MULTILINE)

AUTHOR_NORMALIZE = {
    "HAMILTON": "HAMILTON",
    "MADISON": "MADISON",
    "JAY": "JAY",
    "HAMILTON AND MADISON": "HAMILTON_AND_MADISON",
    "HAMILTON OR MADISON": "HAMILTON_OR_MADISON",
    "MADISON, WITH HAMILTON": "MADISON_WITH_HAMILTON",
    "HAMILTON, WITH MADISON": "HAMILTON_WITH_MADISON",
}


def fetch_text(url: str = PG_URL) -> str:
    with urllib.request.urlopen(url) as resp:
        raw = resp.read().decode("utf-8-sig")
    start = PG_START.search(raw)
    end = PG_END.search(raw)
    if not start or not end:
        raise RuntimeError("could not locate Project Gutenberg start/end markers")
    return raw[start.end() : end.start()].strip()


def parse_author_line(line: str) -> str | None:
    """Return normalized author key if the line looks like a Federalist attribution.

    Attribution lines appear shortly after the title. They are short and
    contain only Federalist authorship vocabulary (HAMILTON, MADISON, JAY,
    AND/OR/WITH). The collaborative form "MADISON, with HAMILTON" uses a
    lowercase "with" in the Project Gutenberg edition.
    """
    s = line.strip().rstrip(".:")
    if not s or len(s) > 60:
        return None
    upper = s.upper()
    if upper not in AUTHOR_NORMALIZE:
        return None
    # Guard against an upper-cased body line that happens to match. The
    # legitimate attribution lines contain only authorship words; reject
    # if the original line has any character outside [A-Z, comma, space,
    # lowercase 'with'].
    body_words = upper.replace(",", " ").split()
    allowed = {"HAMILTON", "MADISON", "JAY", "AND", "OR", "WITH"}
    if not all(w in allowed for w in body_words):
        return None
    return AUTHOR_NORMALIZE[upper]


def parse_essay(block: str, number: int) -> dict:
    """Split a single essay block into title, author, body."""
    lines = block.splitlines()
    # Drop leading blank lines.
    while lines and not lines[0].strip():
        lines.pop(0)

    title = lines.pop(0).strip() if lines else ""

    # Walk forward looking for the author line. It's a short all-caps line
    # within the first ~10 non-blank content lines. Anything before it is
    # publication metadata ("For the Independent Journal. ...").
    author: str | None = None
    body_start_idx = 0
    seen_nonblank = 0
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        seen_nonblank += 1
        a = parse_author_line(line)
        if a:
            author = a
            body_start_idx = i + 1
            break
        if seen_nonblank > 12:
            break

    if author is None:
        raise RuntimeError(f"could not find author for essay #{number}")

    body_lines = lines[body_start_idx:]
    body = "\n".join(body_lines).strip()
    # Collapse 3+ blank lines to a single blank line.
    body = re.sub(r"\n{3,}", "\n\n", body)
    return {"number": number, "title": title, "author": author, "body": body}


def split_essays(text: str) -> list[dict]:
    matches = list(ESSAY_HEAD.finditer(text))
    if not matches:
        raise RuntimeError("no essay headers matched")
    essays = []
    for i, m in enumerate(matches):
        number = int(m.group(1))
        block_start = m.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[block_start:block_end]
        essays.append(parse_essay(block, number))
    return essays


def write_essay(essay: dict, out_dir: Path) -> Path:
    out = out_dir / f"federalist-{essay['number']:02d}.md"
    front = (
        "---\n"
        f"number: {essay['number']}\n"
        f"author: {essay['author']}\n"
        "source: Project Gutenberg eBook #1404 (public domain)\n"
        "---\n\n"
    )
    title = f"# Federalist No. {essay['number']}: {essay['title']}\n\n"
    out.write_text(front + title + essay["body"] + "\n", encoding="utf-8")
    return out


def main() -> int:
    print(f"fetching {PG_URL}", file=sys.stderr)
    text = fetch_text()
    essays = split_essays(text)
    print(f"parsed {len(essays)} essays", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_author: dict[str, int] = {}
    for e in essays:
        write_essay(e, OUT_DIR)
        by_author[e["author"]] = by_author.get(e["author"], 0) + 1

    print(f"wrote {len(essays)} files to {OUT_DIR}", file=sys.stderr)
    for a, n in sorted(by_author.items(), key=lambda x: -x[1]):
        print(f"  {a:30s} {n:3d}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
