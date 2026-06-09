"""Locate the chart region on the page and classify bar/line/hybrid."""

from __future__ import annotations

import fitz

from pdf_chart_parser.vector.color import (
    COLOR_DIST_THRESHOLD,
    color_distance,
    color_lightness,
    color_saturation,
    quantize_color,
)
from pdf_chart_parser.vector.drawings import RectItem, StrokedPath
from pdf_chart_parser.vector.text import TextSpan

# Minimum bars to consider a valid bar group
MIN_BARS = 4
# Minimum points for a line series to span the plot
MIN_LINE_POINTS = 4


def locate_chart(
    drawings: dict[str, list],
    spans: list[TextSpan],
    chart_type_hint: str = "auto",
) -> tuple[fitz.Rect, str, list[RectItem], list[StrokedPath], fitz.Rect] | None:
    """Find the chart region, classify its type, and return component geometry.

    Returns (chart_rect, chart_type, bar_rects, line_paths, plot_rect) or None.
    plot_rect is the tight bbox of bars/lines only (no label expansion).
    chart_rect is expanded to include nearby axis labels for rendering.
    """
    rects: list[RectItem] = drawings["rects"]
    paths: list[StrokedPath] = drawings["paths"]

    bar_groups = _find_bar_groups(rects)
    line_series = _find_line_series(paths, spans)

    # Apply hint filtering
    if chart_type_hint == "bar":
        line_series = []
    elif chart_type_hint == "line":
        bar_groups = []

    if not bar_groups and not line_series:
        return None

    # Pick best candidate
    best_bars = _best_bar_group(bar_groups, spans)
    best_lines = _best_line_series(line_series, best_bars)

    if best_bars is None and not best_lines:
        return None

    # Classify
    if best_bars is not None and best_lines:
        detected_type = "hybrid"
    elif best_bars is not None:
        detected_type = "bar"
    else:
        detected_type = "line"

    # Compute tight plot_rect (bars/lines only) and expanded chart_rect (with labels)
    plot_rect = _plot_rect(best_bars or [], best_lines)
    chart_rect = _compute_chart_rect(best_bars or [], best_lines, spans)
    return chart_rect, detected_type, best_bars or [], best_lines, plot_rect


def _find_bar_groups(rects: list[RectItem]) -> list[list[RectItem]]:
    """Group fill rectangles into candidate bar groups."""
    # Only filled rects with significant height
    candidates = [
        r
        for r in rects
        if r.fill is not None
        and color_saturation(r.fill) > 0.05  # not white/near-white
        and r.rect.height > 5
        and r.rect.width > 2
        and r.rect.height > r.rect.width * 0.5  # taller than wide (bars are vertical)
    ]

    if not candidates:
        return []

    # Group by similar fill color and similar width
    groups: list[list[RectItem]] = []
    used = set()

    for i, r in enumerate(candidates):
        if i in used:
            continue
        group = [r]
        used.add(i)
        for j, r2 in enumerate(candidates):
            if j in used:
                continue
            if (
                color_distance(r.fill, r2.fill) < COLOR_DIST_THRESHOLD
                and abs(r.rect.width - r2.rect.width) < r.rect.width * 0.3
            ):
                group.append(r2)
                used.add(j)
        if len(group) >= MIN_BARS:
            groups.append(group)

    # Validate: group members must share a common baseline (y1 cluster)
    valid_groups = []
    for group in groups:
        bottoms = [r.rect.y1 for r in group]
        median_bottom = sorted(bottoms)[len(bottoms) // 2]
        aligned = [r for r in group if abs(r.rect.y1 - median_bottom) < 5]
        if len(aligned) >= MIN_BARS:
            valid_groups.append(aligned)

    return valid_groups


def _find_line_series(paths: list[StrokedPath], spans: list[TextSpan]) -> list[list[StrokedPath]]:
    """Identify non-axis, data line paths and group by color."""
    if not paths:
        return []

    # Separate out axis/gridline candidates
    data_paths = []
    for path in paths:
        if len(path.points) < MIN_LINE_POINTS:
            continue
        if _is_axis_or_gridline(path):
            continue
        if path.stroke is None:
            continue
        # Must have some saturation (not gray/black axes)
        if color_saturation(path.stroke) < 0.1 and color_lightness(path.stroke) < 0.7:
            continue
        data_paths.append(path)

    if not data_paths:
        return []

    # Group by stroke color
    color_groups: dict[tuple, list[StrokedPath]] = {}
    for path in data_paths:
        key = quantize_color(path.stroke) or (0,)
        color_groups.setdefault(key, []).append(path)

    return [group for group in color_groups.values() if len(group) >= 1]


def _is_axis_or_gridline(path: StrokedPath) -> bool:
    """Return True if the path looks like an axis or gridline (not data)."""
    if len(path.points) < 2:
        return True
    xs = [p.x for p in path.points]
    ys = [p.y for p in path.points]
    x_range = max(xs) - min(xs)
    y_range = max(ys) - min(ys)

    # Purely horizontal (gridline)
    if y_range < 1.5 and x_range > 20:
        return True
    # Purely vertical (axis line)
    if x_range < 1.5 and y_range > 20:
        return True
    # Very thin gray lines
    if path.stroke is not None:
        sat = color_saturation(path.stroke)
        light = color_lightness(path.stroke)
        if sat < 0.05 and light > 0.5:
            return True

    return False


def _best_bar_group(groups: list[list[RectItem]], spans: list[TextSpan]) -> list[RectItem] | None:
    if not groups:
        return None
    if len(groups) == 1:
        return groups[0]

    # Prefer group with more month-like x labels nearby
    best = groups[0]
    best_score = _score_bar_group(groups[0], spans)
    for group in groups[1:]:
        score = _score_bar_group(group, spans)
        if score > best_score:
            best_score = score
            best = group
    return best


def _score_bar_group(group: list[RectItem], spans: list[TextSpan]) -> float:
    bbox = _rects_bbox(group)
    below = [s for s in spans if s.bbox[1] > bbox.y1 and s.bbox[1] < bbox.y1 + 40]
    month_keywords = {
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    }
    month_score = sum(1 for s in below if s.text.strip().lower()[:3] in month_keywords)
    unit_keywords = {"kwh", "$", "dollar", "kw", "usage"}
    left = [
        s for s in spans if s.bbox[2] < bbox.x0 and abs(s.y_center - bbox.y_center) < bbox.height
    ]
    unit_score = sum(1 for s in left if any(u in s.text.lower() for u in unit_keywords))
    return month_score + unit_score * 2 + len(group) * 0.1


def _best_line_series(
    series: list[list[StrokedPath]], bar_group: list[RectItem] | None
) -> list[StrokedPath]:
    if not series:
        return []

    # Flatten: if bar group exists, filter lines that spatially overlap with it
    flat: list[StrokedPath] = []
    for group in series:
        for path in group:
            flat.append(path)

    if bar_group is not None:
        bar_bbox = _rects_bbox(bar_group)
        flat = [p for p in flat if _rects_overlap(p.bbox, bar_bbox)]

    return flat


def _rects_bbox(rects: list[RectItem]) -> fitz.Rect:
    x0 = min(r.rect.x0 for r in rects)
    y0 = min(r.rect.y0 for r in rects)
    x1 = max(r.rect.x1 for r in rects)
    y1 = max(r.rect.y1 for r in rects)
    return fitz.Rect(x0, y0, x1, y1)


def _rects_overlap(a: fitz.Rect, b: fitz.Rect, margin: float = 20.0) -> bool:
    return (
        a.x0 < b.x1 + margin
        and a.x1 > b.x0 - margin
        and a.y0 < b.y1 + margin
        and a.y1 > b.y0 - margin
    )


def _plot_rect(bar_rects: list[RectItem], line_paths: list[StrokedPath]) -> fitz.Rect:
    """Tight bbox of only bar/line geometry (no label expansion)."""
    points_x: list[float] = []
    points_y: list[float] = []
    for r in bar_rects:
        points_x += [r.rect.x0, r.rect.x1]
        points_y += [r.rect.y0, r.rect.y1]
    for p in line_paths:
        for pt in p.points:
            points_x.append(pt.x)
            points_y.append(pt.y)
    if not points_x:
        return fitz.Rect(0, 0, 100, 100)
    return fitz.Rect(min(points_x), min(points_y), max(points_x), max(points_y))


def _compute_chart_rect(
    bar_rects: list[RectItem],
    line_paths: list[StrokedPath],
    spans: list[TextSpan],
) -> fitz.Rect:
    """Union bbox of bars + lines, expanded to include nearby axis labels."""
    core = _plot_rect(bar_rects, line_paths)

    # Expand to include axis labels (text within 60px around the chart core)
    MARGIN = 60
    search = fitz.Rect(core.x0 - MARGIN, core.y0 - MARGIN, core.x1 + MARGIN, core.y1 + MARGIN)
    nearby_x: list[float] = []
    nearby_y: list[float] = []
    for s in spans:
        if search.x0 <= s.x_center <= search.x1 and search.y0 <= s.y_center <= search.y1:
            nearby_x += [s.bbox[0], s.bbox[2]]
            nearby_y += [s.bbox[1], s.bbox[3]]

    all_x = [core.x0, core.x1] + nearby_x
    all_y = [core.y0, core.y1] + nearby_y
    return fitz.Rect(min(all_x), min(all_y), max(all_x), max(all_y))
