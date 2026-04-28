"""SVG chart renderer tests. Stdlib only — no headless rendering needed."""

from __future__ import annotations

import re

from compline.chart import render_calibration_svg


def _is_well_formed_svg(svg: str) -> bool:
    return svg.startswith("<svg") and svg.endswith("</svg>") and "viewBox" in svg


def test_empty_history_produces_placeholder():
    svg = render_calibration_svg([])
    assert _is_well_formed_svg(svg)
    assert "no tune runs yet" in svg


def test_single_run_renders_a_point_no_line():
    history = [{"ran_at": "2026-04-28 11:00:00", "turns_processed": 5, "calibration_score": 0.74}]
    svg = render_calibration_svg(history)
    assert _is_well_formed_svg(svg)
    assert svg.count("<circle") == 1
    # No <path> for a line with only 1 point.
    assert "<path " not in svg
    assert "0.74" in svg
    assert "04-28" in svg


def test_multiple_runs_draw_line_and_markers():
    history = [
        {"ran_at": "2026-04-28 11:41:48", "turns_processed": 5, "calibration_score": 0.742},
        {"ran_at": "2026-04-28 11:44:05", "turns_processed": 2, "calibration_score": 0.375},
        {"ran_at": "2026-04-28 11:53:56", "turns_processed": 2, "calibration_score": 1.000},
    ]
    svg = render_calibration_svg(history)
    assert _is_well_formed_svg(svg)
    assert svg.count("<circle") == 3
    assert svg.count("<path ") == 1
    # Each score label present in output.
    assert "0.74" in svg
    assert "0.38" in svg or "0.37" in svg
    assert "1.00" in svg


def test_score_clamping_is_applied():
    """A pathological score outside [0,1] should not break the renderer."""
    history = [
        {"ran_at": "2026-04-28 11:00:00", "turns_processed": 1, "calibration_score": 1.5},
        {"ran_at": "2026-04-28 11:00:00", "turns_processed": 1, "calibration_score": -0.2},
    ]
    svg = render_calibration_svg(history)
    assert _is_well_formed_svg(svg)
    # All <circle cy="..."> values should fall within plot area (40 .. 360 roughly)
    cy_values = [float(m.group(1)) for m in re.finditer(r'<circle cx="[^"]+" cy="([\d.]+)"', svg)]
    assert all(40 <= cy <= 360 for cy in cy_values), f"cy out of range: {cy_values}"


def test_title_is_escaped():
    history = [{"ran_at": "2026-04-28 11:00:00", "turns_processed": 1, "calibration_score": 0.5}]
    svg = render_calibration_svg(history, title="<script>alert(1)</script>")
    # Raw script tag must not appear; HTML-escaped form must.
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg
