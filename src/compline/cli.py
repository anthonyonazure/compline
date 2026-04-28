"""Compline CLI entry point.

Subcommands:
  init    Initialize the SQLite database and FTS5 schema.
  ingest  Ingest a directory of .md files into a named corpus.
  ask     Ask a persona a question.
  tune    Run one OODA cycle for a persona (the nightly tune step).
  history Print tune-run history as JSON (feeds the chart command later).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from compline import __version__
from compline.chart import render_calibration_svg
from compline.db import connect, init_schema
from compline.engine import ask, history, history_json, tune
from compline.ingest import ingest_directory


def _db_path(args) -> Path:
    return Path(args.db).expanduser()


def cmd_init(args) -> int:
    db = _db_path(args)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db)
    init_schema(conn)
    conn.close()
    print(f"initialized {db}")
    return 0


def cmd_ingest(args) -> int:
    conn = connect(_db_path(args))
    init_schema(conn)
    n = ingest_directory(conn, Path(args.directory).expanduser(), args.corpus)
    conn.close()
    print(f"ingested {n} chunks into corpus '{args.corpus}'")
    return 0


def cmd_ask(args) -> int:
    conn = connect(_db_path(args))
    init_schema(conn)
    result = ask(conn, Path(args.persona).expanduser(), args.question)
    conn.close()
    print(result.answer)
    print()
    print(f"-- citations: {result.cite_valid}/{result.cite_total} valid")
    for c in result.citations:
        mark = "✓" if c["valid"] else "✗"
        title = c.get("title") or "(untitled)"
        print(f"  {mark} [{c['chunk_id']}] {title}: {c['quote'][:80]!r}")
    return 0


def cmd_tune(args) -> int:
    conn = connect(_db_path(args))
    init_schema(conn)
    result = tune(conn, Path(args.persona).expanduser())
    conn.close()
    if result.get("skipped"):
        print(f"no untuned turns for {result['persona']}")
        return 0
    print(f"tune run #{result['tune_run_id']} for {result['persona']}")
    print(f"  turns processed:   {result['turns_processed']}")
    print(f"  calibration score: {result['calibration_score']}")
    print()
    print("--- margin entry ---")
    print(result["margin_entry"])
    return 0


def cmd_history(args) -> int:
    conn = connect(_db_path(args))
    init_schema(conn)
    print(history_json(conn, args.persona))
    conn.close()
    return 0


def cmd_chart(args) -> int:
    conn = connect(_db_path(args))
    init_schema(conn)
    rows = history(conn, args.persona)
    conn.close()
    title = args.title or f"{args.persona} — calibration over nights"
    svg = render_calibration_svg(rows, title=title)
    out = Path(args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} ({len(rows)} run{'s' if len(rows) != 1 else ''})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compline",
        description="AI that gets sharper while you sleep.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    default_db = os.environ.get("COMPLINE_DB", str(Path.home() / ".compline" / "compline.db"))
    parser.add_argument("--db", default=default_db, help=f"SQLite path (default: {default_db})")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="initialize database")
    p_init.set_defaults(func=cmd_init)

    p_ingest = sub.add_parser("ingest", help="ingest a directory of .md files")
    p_ingest.add_argument("directory", help="path to directory of .md files")
    p_ingest.add_argument("--corpus", required=True, help="corpus name")
    p_ingest.set_defaults(func=cmd_ingest)

    p_ask = sub.add_parser("ask", help="ask a persona a question")
    p_ask.add_argument("persona", help="path to .persona.md spec")
    p_ask.add_argument("question", help="the question to ask")
    p_ask.set_defaults(func=cmd_ask)

    p_tune = sub.add_parser("tune", help="run one OODA cycle for a persona")
    p_tune.add_argument("persona", help="path to .persona.md spec")
    p_tune.set_defaults(func=cmd_tune)

    p_hist = sub.add_parser("history", help="print tune-run history as JSON")
    p_hist.add_argument("persona", help="persona name")
    p_hist.set_defaults(func=cmd_history)

    p_chart = sub.add_parser(
        "chart",
        help="render calibration chart as SVG (the W2 launch hero artifact)",
    )
    p_chart.add_argument("persona", help="persona name")
    p_chart.add_argument(
        "--output",
        "-o",
        default="chart.svg",
        help="output path (default: chart.svg in current dir)",
    )
    p_chart.add_argument(
        "--title",
        default=None,
        help="chart title (default: '<persona> — calibration over nights')",
    )
    p_chart.set_defaults(func=cmd_chart)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))
