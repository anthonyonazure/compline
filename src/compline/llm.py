"""Thin Anthropic SDK wrapper.

Two call patterns:
- ``ask_with_citations(...)`` for the QA path: structured JSON response.
- ``generate_margin_entry(...)`` for the nightly tune: short prose.

Model defaults are conservative and cheap. Override with COMPLINE_MODEL env var.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

DEFAULT_MODEL = os.environ.get("COMPLINE_MODEL", "claude-haiku-4-5-20251001")
# Rich answers + several long citations easily exceed 1024 tokens.
# 4096 leaves headroom while still capping cost predictably.
ASK_MAX_TOKENS = 4096
TUNE_MAX_TOKENS = 400


@dataclass(frozen=True)
class CitedAnswer:
    answer: str
    citations: list[dict]  # [{"chunk_id": int, "quote": str}, ...]
    raw: str


def _client():
    # Imported lazily so tests that don't hit the API don't need anthropic installed.
    import anthropic

    return anthropic.Anthropic()


def ask_with_citations(
    system_prompt: str,
    question: str,
    retrieved: list[dict],
    *,
    model: str = DEFAULT_MODEL,
) -> CitedAnswer:
    """Ask the LLM and require structured citations.

    ``retrieved`` is a list of {"chunk_id": int, "title": str, "text": str}.
    """
    sources_block = "\n\n".join(
        f"[{c['chunk_id']}] {c.get('title') or ''}\n{c['text']}" for c in retrieved
    )
    user = (
        "Sources retrieved for this question:\n\n"
        f"{sources_block}\n\n"
        f"Question: {question}\n\n"
        "Respond with a JSON object on a single line. Schema:\n"
        '  {"answer": "<your answer in plain prose>",\n'
        '   "citations": [{"chunk_id": <int>, "quote": "<verbatim substring '
        'from the cited source supporting your claim>"}]}\n\n'
        "Rules:\n"
        "- Every factual claim must be supported by a citation.\n"
        "- Each ``quote`` MUST appear verbatim in the text of the cited chunk.\n"
        "- If you cannot ground a claim, omit it rather than guessing.\n"
        "- Output ONLY the JSON object. No preamble."
    )
    client = _client()
    msg = client.messages.create(
        model=model,
        max_tokens=ASK_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text
    return _parse_cited(raw)


# Matches a complete {"chunk_id": N, "quote": "..."} object even inside a
# truncated JSON array. Tolerates either field-order, escaped quotes in the
# quote string, and arbitrary whitespace.
_CITATION_RE = re.compile(
    r"\{\s*"
    r"(?:"
    r'"chunk_id"\s*:\s*(?P<id1>\d+)\s*,\s*"quote"\s*:\s*"(?P<q1>(?:[^"\\]|\\.)*)"'
    r"|"
    r'"quote"\s*:\s*"(?P<q2>(?:[^"\\]|\\.)*)"\s*,\s*"chunk_id"\s*:\s*(?P<id2>\d+)'
    r")"
    r"\s*\}",
    re.DOTALL,
)
_ANSWER_RE = re.compile(
    r'"answer"\s*:\s*"(?P<a>(?:[^"\\]|\\.)*)"',
    re.DOTALL,
)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text


def _coerce_citations(items) -> list[dict]:
    cleaned = []
    for c in items or []:
        if not isinstance(c, dict) or "chunk_id" not in c or "quote" not in c:
            continue
        try:
            cleaned.append({"chunk_id": int(c["chunk_id"]), "quote": str(c["quote"])})
        except (TypeError, ValueError):
            continue
    return cleaned


def _salvage(text: str, raw: str) -> CitedAnswer:
    """Recover answer + complete citation objects from malformed/truncated JSON.

    Used when the LLM hits max_tokens mid-citation, emits stray prose around
    the JSON, or otherwise produces output json.loads cannot accept whole.
    """
    answer = ""
    m = _ANSWER_RE.search(text)
    if m:
        try:
            answer = json.loads('"' + m.group("a") + '"')
        except json.JSONDecodeError:
            answer = m.group("a")

    citations: list[dict] = []
    for cm in _CITATION_RE.finditer(text):
        try:
            chunk_id = int(cm.group("id1") or cm.group("id2"))
            quote_raw = cm.group("q1") or cm.group("q2") or ""
            try:
                quote = json.loads('"' + quote_raw + '"')
            except json.JSONDecodeError:
                quote = quote_raw
            citations.append({"chunk_id": chunk_id, "quote": quote})
        except (ValueError, TypeError):
            continue

    if not answer and not citations:
        # Total parse failure — surface the raw text so the user sees something.
        return CitedAnswer(answer=text, citations=[], raw=raw)
    return CitedAnswer(answer=answer or text, citations=citations, raw=raw)


def _parse_cited(raw: str) -> CitedAnswer:
    text = _strip_fences(raw)

    # Fast path: clean parse.
    try:
        data = json.loads(text)
        return CitedAnswer(
            answer=(data.get("answer") or "").strip(),
            citations=_coerce_citations(data.get("citations")),
            raw=raw,
        )
    except json.JSONDecodeError:
        pass

    # Second try: outermost balanced object.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return CitedAnswer(
                answer=(data.get("answer") or "").strip(),
                citations=_coerce_citations(data.get("citations")),
                raw=raw,
            )
        except json.JSONDecodeError:
            pass

    # Last resort: regex salvager. Handles truncated and malformed output.
    return _salvage(text, raw)


def generate_margin_entry(
    *,
    persona_name: str,
    persona_body: str,
    recent_summary: str,
    metrics: dict,
    model: str = DEFAULT_MODEL,
) -> str:
    """Single LLM call per night. Produces ONE margin entry.

    The OODA discipline: never a sweeping rewrite. One short note per night.
    """
    metrics_block = "\n".join(f"- {k}: {v}" for k, v in metrics.items())
    system = (
        "You are the OODA tune step for the Compline framework. "
        "You are NOT the persona; you are an editor that writes a single "
        "short margin note that the persona will read tomorrow."
    )
    user = (
        f"Persona: {persona_name}\n"
        f"Persona definition:\n{persona_body}\n\n"
        f"Recent activity:\n{recent_summary}\n\n"
        f"Metrics:\n{metrics_block}\n\n"
        "Write ONE margin note (2-4 sentences max). Pick the SINGLE most "
        "important thing for the persona to remember tomorrow — a recurring "
        "blind spot, a weak citation pattern, a vague phrasing tic, or a "
        "topic to lead with next time. Be concrete. Cite specific chunks "
        "or phrases when useful. No preamble. No headers. Just the note."
    )
    client = _client()
    msg = client.messages.create(
        model=model,
        max_tokens=TUNE_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()
