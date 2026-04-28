"""LLM JSON-output parser tests.

Covers the failure modes observed in real runs against the Federalist
corpus on Day 2: clean JSON, code-fenced JSON, prose-wrapped JSON, and
the painful one — JSON truncated mid-citation when the LLM hit
max_tokens.
"""

from __future__ import annotations

from compline.llm import _parse_cited


def test_clean_json():
    raw = '{"answer": "Hello.", "citations": [{"chunk_id": 5, "quote": "x"}]}'
    p = _parse_cited(raw)
    assert p.answer == "Hello."
    assert p.citations == [{"chunk_id": 5, "quote": "x"}]


def test_code_fenced_json():
    raw = '```json\n{"answer": "fenced", "citations": []}\n```'
    p = _parse_cited(raw)
    assert p.answer == "fenced"
    assert p.citations == []


def test_prose_around_json():
    """Sometimes the model adds a preamble or trailing commentary."""
    raw = (
        "Here is the response:\n\n"
        '{"answer": "wrapped", "citations": [{"chunk_id": 1, "quote": "y"}]}\n'
        "Hope that helps!"
    )
    p = _parse_cited(raw)
    assert p.answer == "wrapped"
    assert p.citations == [{"chunk_id": 1, "quote": "y"}]


def test_truncated_mid_citation():
    """The exact failure mode from Day 2 Q6: LLM hit max_tokens while emitting
    a citation quote. Outer braces never close, last quote is unterminated.
    Expected: salvage the answer + every COMPLETE citation entry."""
    raw = (
        "{\n"
        '  "answer": "The taxing power must be unqualified because requisitions failed.",\n'
        '  "citations": [\n'
        '    {"chunk_id": 191, "quote": "A government ought to contain in itself"},\n'
        '    {"chunk_id": 193, "quote": "The wealth of nations depends upon"},\n'
        '    {"chunk_id": 193, "quote": "The consequence clearly is that there can'
        # truncated mid-string here, no closing quote, no closing brace
    )
    p = _parse_cited(raw)
    assert "taxing power" in p.answer
    # Two complete citations should be salvaged; the third (truncated) is dropped.
    assert len(p.citations) == 2
    assert p.citations[0] == {"chunk_id": 191, "quote": "A government ought to contain in itself"}
    assert p.citations[1] == {"chunk_id": 193, "quote": "The wealth of nations depends upon"}


def test_truncated_in_answer_is_still_recovered():
    """If the answer string itself is truncated, surface what we have."""
    raw = '{"answer": "I was about to say som'  # totally truncated
    p = _parse_cited(raw)
    # The answer regex requires a closing quote so this won't match — fall
    # through gracefully without crashing.
    assert p.answer  # something non-empty
    assert p.citations == []


def test_field_order_swapped_in_citation():
    raw = '{"answer": "ok", "citations": [{"quote": "z", "chunk_id": 9}]}'
    p = _parse_cited(raw)
    assert p.citations == [{"chunk_id": 9, "quote": "z"}]


def test_escaped_quotes_in_quote_string():
    raw = (
        '{"answer": "ok",'
        ' "citations": [{"chunk_id": 5,'
        ' "quote": "He said \\"energy in the executive\\" was essential"}]}'
    )
    p = _parse_cited(raw)
    assert len(p.citations) == 1
    assert "energy in the executive" in p.citations[0]["quote"]


def test_completely_unparseable_returns_raw_as_answer():
    raw = "this is just prose with no JSON at all"
    p = _parse_cited(raw)
    assert p.answer == raw
    assert p.citations == []


def test_non_int_chunk_id_is_dropped():
    raw = '{"answer": "ok", "citations": [{"chunk_id": "not_an_int", "quote": "z"}]}'
    p = _parse_cited(raw)
    assert p.citations == []


def test_calibration_excludes_no_citation_turns():
    """Sanity: calibration formula should ignore turns with cite_total=0."""
    from compline import engine

    class FakeRow(dict):
        def __getitem__(self, key):
            return super().__getitem__(key)

    rows = [
        FakeRow(cite_valid=4, cite_total=4),  # 1.0
        FakeRow(cite_valid=0, cite_total=0),  # excluded
        FakeRow(cite_valid=2, cite_total=4),  # 0.5
    ]
    score = engine._calibration_score(rows)
    assert score == 0.75  # mean of 1.0 and 0.5

    no_cite = engine._no_citation_rate(rows)
    assert no_cite == round(1 / 3, 3) or abs(no_cite - 1 / 3) < 0.01
