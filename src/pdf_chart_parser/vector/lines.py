"""Extract line series data points from stroked polylines."""

from __future__ import annotations

import fitz

from pdf_chart_parser.models import Axes, DataPoint, Series
from pdf_chart_parser.vector.calibrate import y_to_value
from pdf_chart_parser.vector.drawings import StrokedPath
from pdf_chart_parser.vector.text import TextSpan

_MARKER_SIZE_THRESHOLD = 8.0  # max bbox dimension to be a marker shape


def extract_lines(
    line_paths: list[StrokedPath],
    axes: Axes,
    spans: list[TextSpan],
    chart_rect: fitz.Rect,
    plot_rect: fitz.Rect | None = None,
) -> tuple[list[Series], list[str]]:
    """Convert polyline paths to Series data points.

    plot_rect is the tight bars/lines bbox (no label expansion); used for x-mapping.
    Returns ([Series], warnings).
    """
    warnings: list[str] = []
    if not line_paths:
        return [], warnings

    # Use plot_rect for x-label position mapping; fall back to chart_rect
    x_domain = plot_rect if plot_rect is not None else chart_rect

    # Group paths by color
    color_groups: dict[tuple, list[StrokedPath]] = {}
    for path in line_paths:
        key = _quantize_color(path.stroke)
        color_groups.setdefault(key, []).append(path)

    # Build legend: small colored text-adjacent swatches → label
    legend = _build_legend(line_paths, spans, chart_rect)

    x_labels = axes.x.labels

    all_series: list[Series] = []
    series_idx = 0

    for color_key, paths in color_groups.items():
        # Merge all points from paths of the same color, sort by x
        all_pts: list[fitz.Point] = []
        for path in paths:
            all_pts.extend(path.points)

        if not all_pts:
            continue

        all_pts.sort(key=lambda p: p.x)

        # Determine which y-axis to use
        axis_id = "y_primary"
        calibration = axes.y_primary
        if axes.y_secondary is not None:
            # Use secondary if the secondary axis R² is better or unit matches
            sec_r2 = axes.y_secondary.r_squared if axes.y_secondary else 0
            prim_r2 = axes.y_primary.r_squared
            if sec_r2 >= prim_r2 * 0.98 and axes.y_secondary.unit != axes.y_primary.unit:
                axis_id = "y_secondary"
                calibration = axes.y_secondary

        points: list[DataPoint] = []
        for pt in all_pts:
            value = y_to_value(pt.y, calibration)
            x_label = _nearest_x_label(pt.x, x_labels, x_domain)
            points.append(
                DataPoint(
                    x_label=x_label,
                    x=round(pt.x, 2),
                    value=round(value, 4),
                    y=round(pt.y, 2),
                    confidence=0.9,
                )
            )

        # Deduplicate points at same x_label, keeping highest confidence
        points = _deduplicate_points(points)

        color_list = list(color_key) if color_key else []
        label = legend.get(color_key, "")
        series = Series(
            id=f"s{series_idx}",
            type="line",
            label=label,
            unit=calibration.unit if calibration else "auto",
            axis=axis_id,
            color=color_list,
            confidence=0.9,
            points=points,
        )
        all_series.append(series)
        series_idx += 1

    if not all_series:
        warnings.append("no line series extracted from paths")

    return all_series, warnings


def _build_legend(
    paths: list[StrokedPath],
    spans: list[TextSpan],
    chart_rect: fitz.Rect,
) -> dict[tuple, str]:
    """Match small colored swatches near text to build a color→label map."""
    legend: dict[tuple, str] = {}
    # Look for small path segments (swatches) near text spans outside the chart plot area
    for path in paths:
        if len(path.points) < 2:
            continue
        bbox = path.bbox
        # Small horizontal segment outside or at the edge of chart — likely a legend swatch
        width = bbox.x1 - bbox.x0
        height = bbox.y1 - bbox.y0
        if width > 30 or height > 10:
            continue
        # Find adjacent text
        for span in spans:
            if abs(span.y_center - (bbox.y0 + bbox.y1) / 2) < 8 and span.bbox[0] > bbox.x1:
                color_key = _quantize_color(path.stroke)
                if color_key not in legend:
                    legend[color_key] = span.text.strip()
                    break
    return legend


def _nearest_x_label(x: float, labels: list[str], x_domain: fitz.Rect) -> str:
    if not labels:
        return ""
    plot_width = x_domain.x1 - x_domain.x0
    if plot_width <= 0:
        return labels[0]
    n = len(labels)
    # Map x to label index using the inner plot domain boundaries
    rel = (x - x_domain.x0) / plot_width
    idx = int(round(rel * (n - 1)))
    idx = max(0, min(idx, n - 1))
    return labels[idx]


def _quantize_color(c: tuple | None, buckets: int = 10) -> tuple:
    if c is None:
        return (0,)
    return tuple(round(v * buckets) / buckets for v in c[:3])


def _deduplicate_points(points: list[DataPoint]) -> list[DataPoint]:
    """Keep one point per x_label (the one with highest confidence)."""
    seen: dict[str, DataPoint] = {}
    for pt in points:
        key = pt.x_label or str(round(pt.x, 1))
        if key not in seen or pt.confidence > seen[key].confidence:
            seen[key] = pt
    return list(seen.values())
