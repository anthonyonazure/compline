"""Persona spec parsing + margin.md plumbing. No API key needed."""

from __future__ import annotations

from compline.persona import (
    append_margin,
    build_system_prompt,
    load_margin,
    load_spec,
    parse_frontmatter,
)


def test_parse_frontmatter():
    text = "---\nname: Hamilton\ncorpus: federalist\n---\n\nYou are Hamilton."
    meta, body = parse_frontmatter(text)
    assert meta == {"name": "Hamilton", "corpus": "federalist"}
    assert body == "You are Hamilton."


def test_load_spec_uses_filename_when_name_missing(tmp_path):
    p = tmp_path / "Hamilton.persona.md"
    p.write_text("---\ncorpus: federalist\n---\n\nbody", encoding="utf-8")
    spec = load_spec(p)
    assert spec.name == "Hamilton"
    assert spec.corpus == "federalist"
    assert spec.margin_path == tmp_path / "Hamilton.margin.md"


def test_append_margin_creates_file_with_header(tmp_path):
    margin = tmp_path / "Hamilton.margin.md"
    assert not margin.exists()
    append_margin(margin, "First lesson learned.")
    assert margin.exists()
    text = margin.read_text(encoding="utf-8")
    assert "Hamilton — margin notes" in text
    assert "First lesson learned." in text


def test_append_margin_appends_to_existing(tmp_path):
    margin = tmp_path / "Hamilton.margin.md"
    append_margin(margin, "First.")
    append_margin(margin, "Second.")
    text = margin.read_text(encoding="utf-8")
    assert text.count("##") >= 2
    assert "First." in text and "Second." in text


def test_build_system_prompt_includes_margin_when_present(tmp_path):
    p = tmp_path / "Hamilton.persona.md"
    p.write_text("---\ncorpus: federalist\n---\n\nYou are Hamilton.", encoding="utf-8")
    spec = load_spec(p)
    append_margin(spec.margin_path, "Be precise about executive war powers.")
    prompt = build_system_prompt(spec, load_margin(spec.margin_path))
    assert "You are Hamilton." in prompt
    assert "Lessons accumulated" in prompt
    assert "executive war powers" in prompt


def test_build_system_prompt_omits_margin_section_when_empty(tmp_path):
    p = tmp_path / "Hamilton.persona.md"
    p.write_text("---\ncorpus: federalist\n---\n\nbody", encoding="utf-8")
    spec = load_spec(p)
    prompt = build_system_prompt(spec, load_margin(spec.margin_path))
    assert "Lessons accumulated" not in prompt
