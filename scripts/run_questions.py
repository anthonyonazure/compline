#!/usr/bin/env python3
"""Batch-ask runner for a curated questions file.

Reads a markdown file where every line starting with ``?`` is treated as a
question, and runs ``compline.engine.ask`` against the given persona for each.
Used during W2 stealth iteration to seed calibration data without hand-typing
each question.

Usage:
    python scripts/run_questions.py \\
        --persona examples/federalist/Hamilton.persona.md \\
        --questions examples/federalist/questions.md \\
        --db ~/.compline/dev.db

Skips questions that have already been asked (matched by exact text) by
default. Pass --force to re-ask everything.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Allow running from repo root without installing.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from compline.db import connect, init_schema  # noqa: E402
from compline.engine import ask  # noqa: E402
from compline.persona import load_spec  # noqa: E402

_QUESTION_RE = re.compile(r"^\?\s*(.+)$")


def parse_questions(path: Path) -> list[str]:
    """Pull every line that starts with `?` out of the markdown file."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _QUESTION_RE.match(line)
        if m:
            q = m.group(1).strip()
            if q:
                out.append(q)
    return out


def already_asked(conn, persona_id: int, question: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM turns WHERE persona_id = ? AND question = ? LIMIT 1",
        (persona_id, question),
    ).fetchone()
    return row is not None


def persona_id_for(conn, persona_path: Path) -> int | None:
    """Look up an existing persona row by NAME parsed from the spec.

    Looking up by spec_path is brittle because the path may have been stored
    as relative on first ask (running ``compline ask examples/...``) and is
    resolved to absolute when the script runs. Name is the stable identifier
    that ``engine._ensure_persona_row`` also uses.
    """
    spec = load_spec(persona_path)
    row = conn.execute("SELECT id FROM personas WHERE name = ?", (spec.name,)).fetchone()
    return row["id"] if row else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--persona", required=True, type=Path, help="path to .persona.md")
    ap.add_argument("--questions", required=True, type=Path, help="path to questions.md")
    ap.add_argument(
        "--db",
        default=os.environ.get("COMPLINE_DB", str(Path.home() / ".compline" / "compline.db")),
        help="SQLite path",
    )
    ap.add_argument("--force", action="store_true", help="re-ask questions already in the log")
    ap.add_argument("--limit", type=int, default=None, help="cap number of questions asked")
    ap.add_argument(
        "--dry-run", action="store_true", help="parse + print questions, don't call the LLM"
    )
    args = ap.parse_args()

    persona_path = args.persona.expanduser().resolve()
    questions_path = args.questions.expanduser().resolve()

    if not persona_path.exists():
        print(f"persona spec not found: {persona_path}", file=sys.stderr)
        return 2
    if not questions_path.exists():
        print(f"questions file not found: {questions_path}", file=sys.stderr)
        return 2

    questions = parse_questions(questions_path)
    if not questions:
        print(
            f"no questions found in {questions_path} (lines must start with '?')", file=sys.stderr
        )
        return 2
    print(f"parsed {len(questions)} questions from {questions_path.name}", file=sys.stderr)

    if args.dry_run:
        for i, q in enumerate(questions, 1):
            print(f"  [{i}] {q}")
        return 0

    db_path = Path(args.db).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    init_schema(conn)

    pid = persona_id_for(conn, persona_path)
    skipped = 0
    asked_count = 0
    failures = 0

    for i, q in enumerate(questions, 1):
        if args.limit and asked_count >= args.limit:
            print(f"reached --limit {args.limit}, stopping", file=sys.stderr)
            break
        if not args.force and pid and already_asked(conn, pid, q):
            skipped += 1
            print(f"  [{i}/{len(questions)}] SKIP (already asked): {q[:80]}", file=sys.stderr)
            continue
        print(f"  [{i}/{len(questions)}] ASK: {q[:80]}", file=sys.stderr)
        try:
            result = ask(conn, persona_path, q)
        except Exception as e:
            failures += 1
            print(f"      FAIL: {e}", file=sys.stderr)
            continue
        # If this is the first question for an unseen persona, capture id now.
        if pid is None:
            pid = persona_id_for(conn, persona_path)
        asked_count += 1
        print(
            f"      cite_valid={result.cite_valid}/{result.cite_total}",
            file=sys.stderr,
        )

    conn.close()
    print(
        f"\ndone: {asked_count} asked, {skipped} skipped, {failures} failed",
        file=sys.stderr,
    )
    return 1 if failures and not asked_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
