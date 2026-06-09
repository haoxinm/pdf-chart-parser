"""Extract bar chart data points from detected bar rectangles."""

from __future__ import annotations

import fitz

from pdf_chart_parser.models import Axes, DataPoint, Series
from pdf_chart_parser.vector.calibrate import y_to_value
from pdf_chart_parser.vector.drawings import RectItem


def extract_bars(
    bar_rects: list[RectItem],
    axes: Axes,
    chart_rect: fitz.Rect,
) -> tuple[list[Series], list[str]]:
    """Convert bar rectangles to Series data points.

    Returns ([Series], warnings).
    """
    warnings: list[str] = []
    if not bar_rects:
        return [], warnings

    # Sort bars left-to-right
    sorted_bars = sorted(bar_rects, key=lambda r: r.rect.x0)

    # Establish baseline (shared bottom y of bars)
    bottoms = [r.rect.y1 for r in sorted_bars]
    median_bottom = sorted(bottoms)[len(bottoms) // 2]
    baseline_value = y_to_value(median_bottom, axes.y_primary)

    if abs(baseline_value) > 5:
        warnings.append(f"non-zero baseline detected: baseline_value={baseline_value:.2f}")

    # Get x labels
    x_labels = axes.x.labels
    n_labels = len(x_labels)

    # Group bars by color (each color = one series)
    color_groups: dict[tuple, list[RectItem]] = {}
    for bar in sorted_bars:
        key = _quantize_color(bar.fill)
        color_groups.setdefault(key, []).append(bar)

    # If multiple colors, each is a separate series; otherwise one series
    all_series = []
    series_idx = 0
    for color_key, group_bars in color_groups.items():
        group_bars.sort(key=lambda r: r.rect.x0)
        points: list[DataPoint] = []
        for i, bar in enumerate(group_bars):
            x_center = (bar.rect.x0 + bar.rect.x1) / 2
            value = y_to_value(bar.rect.y0, axes.y_primary) - baseline_value
            if value < -1:
                warnings.append(f"negative bar value {value:.2f} at index {i}; clipping to 0")
                value = 0.0

            # Match x label by position
            x_label = ""
            if n_labels > 0:
                # Find closest label by x_center position
                if i < n_labels:
                    x_label = x_labels[i]
            bar_conf = _bar_confidence(bar, group_bars, axes, median_bottom)
            points.append(
                DataPoint(
                    x_label=x_label,
                    x=round(x_center, 2),
                    value=round(value, 4),
                    y=round(bar.rect.y0, 2),
                    baseline_y=round(median_bottom, 2),
                    confidence=bar_conf,
                )
            )

        color_list = list(color_key) if color_key else []
        series = Series(
            id=f"s{series_idx}",
            type="bar",
            label="",
            unit=axes.y_primary.unit,
            axis="y_primary",
            color=color_list,
            confidence=_series_confidence(points),
            points=points,
        )
        all_series.append(series)
        series_idx += 1

    return all_series, warnings


def _quantize_color(c: tuple | None, buckets: int = 10) -> tuple:
    if c is None:
        return (0,)
    return tuple(round(v * buckets) / buckets for v in c[:3])


def _bar_confidence(
    bar: RectItem,
    group: list[RectItem],
    axes: Axes,
    baseline_y: float,
) -> float:
    widths = [r.rect.width for r in group]
    median_w = sorted(widths)[len(widths) // 2]
    width_dev = abs(bar.rect.width - median_w) / max(median_w, 1)
    conf = 1.0 - min(width_dev, 0.5)
    if abs(bar.rect.y1 - baseline_y) > 3:
        conf *= 0.9
    return round(conf, 3)


def _series_confidence(points: list[DataPoint]) -> float:
    if not points:
        return 0.0
    return round(sum(p.confidence for p in points) / len(points), 3)
