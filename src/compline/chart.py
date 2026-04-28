"""SVG calibration chart renderer.

Stdlib only — no matplotlib, no numpy. Output is a self-contained SVG that
renders inline in GitHub README markdown without any extra dependencies on
the reader's side. The chart is the W2 launch hero artifact, so it has to
work everywhere and look clean at any zoom.

Public API:
    render_calibration_svg(history: list[dict]) -> str

``history`` is the same list ``engine.history()`` returns:
    [{"ran_at": "2026-04-28 11:41:48",
      "turns_processed": 5,
      "calibration_score": 0.741}, ...]
"""

from __future__ import annotations

from html import escape

# Layout constants. Picked to look balanced on a typical README at ~720px wide
# but the SVG scales fluidly thanks to viewBox.
_WIDTH = 720
_HEIGHT = 400
_PAD_L = 56
_PAD_R = 24
_PAD_T = 56
_PAD_B = 56

_FONT = "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif"
_AXIS_COLOR = "#cbd5e1"  # slate-300
_GRID_COLOR = "#e2e8f0"  # slate-200
_TEXT_COLOR = "#0f172a"  # slate-900
_MUTED_COLOR = "#64748b"  # slate-500
_LINE_COLOR = "#0f766e"  # teal-700
_POINT_FILL = "#ffffff"
_POINT_STROKE = "#0f766e"
_BG_COLOR = "#ffffff"


def _plot_area() -> tuple[float, float, float, float]:
    """Return (x0, y0, x1, y1) of the inner plot rectangle."""
    return _PAD_L, _PAD_T, _WIDTH - _PAD_R, _HEIGHT - _PAD_B


def _x_for_index(i: int, n: int) -> float:
    x0, _, x1, _ = _plot_area()
    if n <= 1:
        return (x0 + x1) / 2
    return x0 + (x1 - x0) * (i / (n - 1))


def _y_for_score(score: float) -> float:
    _, y0, _, y1 = _plot_area()
    score = max(0.0, min(1.0, score))
    # Y is inverted in SVG — score=1.0 maps to top.
    return y1 - (y1 - y0) * score


def _format_date(ran_at: str) -> str:
    """Pull MM-DD out of a 'YYYY-MM-DD HH:MM:SS' timestamp."""
    if not ran_at or len(ran_at) < 10:
        return ""
    return ran_at[5:10]  # MM-DD


def render_calibration_svg(history: list[dict], title: str = "Calibration over nights") -> str:
    """Render the night-by-night calibration line chart as a self-contained SVG."""
    n = len(history)
    x0, y0, x1, y1 = _plot_area()

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {_HEIGHT}" '
        f'width="{_WIDTH}" height="{_HEIGHT}" font-family="{_FONT}">'
    )
    parts.append(f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="{_BG_COLOR}"/>')

    # Title
    parts.append(
        f'<text x="{_PAD_L}" y="28" font-size="18" font-weight="600" '
        f'fill="{_TEXT_COLOR}">{escape(title)}</text>'
    )
    parts.append(
        f'<text x="{_PAD_L}" y="46" font-size="11" fill="{_MUTED_COLOR}">'
        f'compline · mean citation validity per tune run · {n} run{"s" if n != 1 else ""}'
        f'</text>'
    )

    # Y-axis grid + labels (0.0, 0.25, 0.5, 0.75, 1.0)
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        ty = _y_for_score(tick)
        parts.append(
            f'<line x1="{x0}" y1="{ty:.1f}" x2="{x1}" y2="{ty:.1f}" '
            f'stroke="{_GRID_COLOR}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x0 - 8}" y="{ty + 4:.1f}" font-size="11" '
            f'fill="{_MUTED_COLOR}" text-anchor="end">{tick:.2f}</text>'
        )

    # Axes
    parts.append(
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{_AXIS_COLOR}" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{_AXIS_COLOR}" stroke-width="1.5"/>'
    )

    # Y-axis label
    parts.append(
        f'<text transform="translate(16 {(y0 + y1) / 2:.1f}) rotate(-90)" '
        f'font-size="11" fill="{_MUTED_COLOR}" text-anchor="middle">'
        f'calibration score</text>'
    )

    if n == 0:
        parts.append(
            f'<text x="{(x0 + x1) / 2:.1f}" y="{(y0 + y1) / 2:.1f}" font-size="13" '
            f'fill="{_MUTED_COLOR}" text-anchor="middle">no tune runs yet</text>'
        )
        parts.append("</svg>")
        return "".join(parts)

    # Data line
    points = [(_x_for_index(i, n), _y_for_score(h["calibration_score"])) for i, h in enumerate(history)]
    if n >= 2:
        path = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in points)
        parts.append(
            f'<path d="{path}" fill="none" stroke="{_LINE_COLOR}" '
            f'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    # Points + value labels
    for (px, py), h in zip(points, history):
        parts.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" '
            f'fill="{_POINT_FILL}" stroke="{_POINT_STROKE}" stroke-width="2"/>'
        )
        # Label: score above point
        label_y = py - 12 if py > y0 + 16 else py + 22
        parts.append(
            f'<text x="{px:.1f}" y="{label_y:.1f}" font-size="11" '
            f'font-weight="600" fill="{_TEXT_COLOR}" text-anchor="middle">'
            f'{h["calibration_score"]:.2f}</text>'
        )

    # X-axis tick labels (date for each run; if too dense, every other)
    step = 1 if n <= 10 else max(1, n // 8)
    for i, h in enumerate(history):
        if i % step != 0 and i != n - 1:
            continue
        px = _x_for_index(i, n)
        parts.append(
            f'<text x="{px:.1f}" y="{y1 + 18:.1f}" font-size="10" '
            f'fill="{_MUTED_COLOR}" text-anchor="middle">'
            f'{escape(_format_date(h["ran_at"]))}</text>'
        )
        parts.append(
            f'<text x="{px:.1f}" y="{y1 + 32:.1f}" font-size="9" '
            f'fill="{_MUTED_COLOR}" text-anchor="middle">'
            f'{h["turns_processed"]} turn{"s" if h["turns_processed"] != 1 else ""}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)
