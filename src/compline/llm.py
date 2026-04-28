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
ASK_MAX_TOKENS = 1024
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


def _parse_cited(raw: str) -> CitedAnswer:
    text = raw.strip()
    # Tolerate code fences.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Salvage attempt — find outermost JSON object.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return CitedAnswer(answer=text, citations=[], raw=raw)
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return CitedAnswer(answer=text, citations=[], raw=raw)
    answer = (data.get("answer") or "").strip()
    citations = data.get("citations") or []
    cleaned = [
        {"chunk_id": int(c["chunk_id"]), "quote": str(c["quote"])}
        for c in citations
        if isinstance(c, dict) and "chunk_id" in c and "quote" in c
    ]
    return CitedAnswer(answer=answer, citations=cleaned, raw=raw)


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
