"""Persona definition + margin.md auto-load.

A persona is defined by a markdown file with YAML-ish frontmatter:

    ---
    name: Hamilton
    corpus: federalist
    author_filter: HAMILTON
    ---

    You are Alexander Hamilton...

The persona's accumulated identity lives in a sibling `<name>.margin.md`
file that the OODA loop appends to nightly. Both files are loaded into
the system prompt at session start.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class PersonaSpec:
    name: str
    corpus: str
    author_filter: str | None
    body: str
    spec_path: Path
    margin_path: Path


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse a small subset of YAML frontmatter (key: value pairs only)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    header = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in header.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body


def load_spec(spec_path: Path) -> PersonaSpec:
    text = spec_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    name = meta.get("name") or spec_path.stem.split(".")[0]
    corpus = meta.get("corpus", "")
    if not corpus:
        raise ValueError(f"persona spec {spec_path} missing 'corpus' frontmatter")
    margin_path = spec_path.with_name(f"{name}.margin.md")
    return PersonaSpec(
        name=name,
        corpus=corpus,
        author_filter=meta.get("author_filter") or None,
        body=body.strip(),
        spec_path=spec_path,
        margin_path=margin_path,
    )


def load_margin(margin_path: Path) -> str:
    """Return margin.md contents, or an empty stub if the file does not yet exist."""
    if not margin_path.exists():
        return ""
    return margin_path.read_text(encoding="utf-8").strip()


def append_margin(margin_path: Path, entry: str) -> None:
    """Append a dated margin entry. Creates the file with a header on first write."""
    entry = entry.strip()
    if not entry:
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = f"\n## {today}\n\n{entry}\n"
    if not margin_path.exists():
        header = (
            f"# {margin_path.stem.replace('.margin', '')} — margin notes\n\n"
            "_Appended nightly by the OODA tune step. The persona reads this file "
            "as part of its system prompt._\n"
        )
        margin_path.write_text(header + block, encoding="utf-8")
        return
    with margin_path.open("a", encoding="utf-8") as f:
        f.write(block)


def build_system_prompt(spec: PersonaSpec, margin: str) -> str:
    """Combine the persona spec body with margin notes into a single system prompt."""
    parts = [spec.body]
    if margin:
        parts.append("# Lessons accumulated from prior sessions\n\n" + margin)
    parts.append(
        "When you answer, ground every factual claim in a retrieved source chunk and "
        "return your response in the structured JSON format requested by the user "
        "message. If you cannot ground a claim, say so plainly rather than guessing."
    )
    return "\n\n---\n\n".join(parts)
