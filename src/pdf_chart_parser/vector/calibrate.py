"""Calibrate chart axes from text tick labels."""

from __future__ import annotations

import re
from typing import NamedTuple

import fitz
import numpy as np

from pdf_chart_parser.models import Axes, AxisCalibration, AxisCalibrationPoint, AxisInfo
from pdf_chart_parser.vector.text import TextSpan

_MONTH_NAMES = {
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
    "january",
    "february",
    "march",
    "april",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}
_NUMBER_RE = re.compile(r"^[+\-]?\$?\s*(\d[\d,\.]*)\s*(k|kwh|kw|mwh|therm)?$", re.I)
_UNIT_RE = re.compile(r"kwh|kw|mwh|therm|\$", re.I)


class _FitResult(NamedTuple):
    a: float  # scale (value per pixel)
    b: float  # intercept
    r_squared: float
    points: list[AxisCalibrationPoint]


def calibrate_axes(
    spans: list[TextSpan],
    chart_rect: fitz.Rect,
    value_unit_hint: str = "auto",
    plot_rect: fitz.Rect | None = None,
) -> tuple[Axes, list[str]]:
    """Fit y-axis (primary + optional secondary) and x-axis from text spans.

    plot_rect is the tight bars/lines bbox; chart_rect includes label expansion.
    Uses plot_rect for determining which side labels belong to when provided.

    Returns (Axes, warnings).
    """
    warnings: list[str] = []
    # Use plot_rect for axis-side determination; fall back to chart_rect
    bounds = plot_rect if plot_rect is not None else chart_rect

    y_primary, y_unit, y_warnings = _calibrate_y_axis(
        spans, chart_rect, bounds, side="left", value_unit_hint=value_unit_hint
    )
    warnings.extend(y_warnings)
    if y_primary is None:
        warnings.append(
            "y-axis calibration failed: fewer than 2 numeric tick labels found; "
            "values are uncalibrated"
        )

    y_secondary = None
    y_sec_unit = None
    right_fit, r_unit, r_warnings = _calibrate_y_axis(
        spans, chart_rect, bounds, side="right", value_unit_hint="auto"
    )
    # Require >= 3 points: a 2-point fit is always exact (r² == 1.0), so two
    # stray right-side numbers would otherwise spawn a phantom secondary axis.
    if right_fit is not None and right_fit.r_squared > 0.95 and len(right_fit.points) >= 3:
        y_secondary = right_fit
        y_sec_unit = r_unit
        warnings.append("secondary y-axis detected")

    x_axis, x_labels = _calibrate_x_axis(spans, chart_rect, bounds)

    scale_pp = abs(y_primary.a) if y_primary else 0.0
    r2 = y_primary.r_squared if y_primary else 0.0

    if r2 < 0.999 and y_primary and len(y_primary.points) >= 2:
        warnings.append(f"y-axis R² = {r2:.4f} (< 0.999)")

    resolved_unit = _resolve_unit(y_unit, value_unit_hint)

    y_prim_model = AxisCalibration(
        unit=resolved_unit,
        points=y_primary.points if y_primary else [],
        scale_per_point=float(y_primary.a) if y_primary else 0.0,
        intercept=float(y_primary.b) if y_primary else 0.0,
        scale_per_pixel=float(scale_pp),
        r_squared=float(r2),
    )

    y_sec_model = None
    if y_secondary is not None:
        y_sec_model = AxisCalibration(
            unit=_resolve_unit(y_sec_unit, "auto"),
            points=y_secondary.points,
            scale_per_point=float(y_secondary.a),
            intercept=float(y_secondary.b),
            scale_per_pixel=float(abs(y_secondary.a)),
            r_squared=float(y_secondary.r_squared),
        )

    axes = Axes(
        x=x_axis,
        y_primary=y_prim_model,
        y_secondary=y_sec_model,
    )
    return axes, warnings


def _parse_number(text: str) -> float | None:
    t = text.strip().replace(",", "")
    m = _NUMBER_RE.match(t)
    if not m:
        return None
    val = float(m.group(1))
    suffix = (m.group(2) or "").lower()
    if suffix == "k":
        val *= 1000
    return val


def _collect_unit(text: str) -> str | None:
    m = _UNIT_RE.search(text)
    if not m:
        return None
    raw = m.group(0).lower()
    if raw == "$":
        return "dollars"
    if raw in ("kwh", "kw", "mwh", "therm"):
        return "kwh"
    return None


def _calibrate_y_axis(
    spans: list[TextSpan],
    chart_rect: fitz.Rect,
    bounds: fitz.Rect,
    side: str,
    value_unit_hint: str,
) -> tuple[_FitResult | None, str | None, list[str]]:
    warnings: list[str] = []
    # Use bounds (plot rect) for side determination, chart_rect for vertical extent
    bx0, by0, bx1, by1 = bounds
    _, cy0, _, cy1 = chart_rect

    if side == "left":
        # Left-side labels: their right edge is at or left of the plot left edge
        label_spans = [
            s for s in spans if s.bbox[2] <= bx0 + 5 and cy0 - 20 <= s.y_center <= cy1 + 20
        ]
    else:
        # Right-side labels: their left edge is at or right of the plot right edge
        label_spans = [
            s for s in spans if s.bbox[0] >= bx1 - 5 and cy0 - 20 <= s.y_center <= cy1 + 20
        ]

    pairs: list[tuple[float, float]] = []
    unit: str | None = None
    for s in label_spans:
        val = _parse_number(s.text)
        if val is not None:
            pairs.append((val, s.y_center))
        u = _collect_unit(s.text)
        if u:
            unit = u

    # Remove calendar-year-like values (1900–2200) when other scale values exist.
    # Year labels on the x-axis can bleed into the left-side search area and corrupt
    # the linear fit with a wildly out-of-range point.
    pairs_no_years = [(v, y) for v, y in pairs if not (1900 <= v <= 2200)]
    if len(pairs_no_years) >= 2:
        pairs = pairs_no_years

    if len(pairs) < 2:
        return None, unit, warnings

    values = np.array([p[0] for p in pairs])
    ys = np.array([p[1] for p in pairs])

    fit = np.polyfit(ys, values, 1)
    a, b = float(fit[0]), float(fit[1])
    predicted = a * ys + b
    ss_res = float(np.sum((values - predicted) ** 2))
    ss_tot = float(np.sum((values - values.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-9 else 1.0

    calib_points = [AxisCalibrationPoint(value=v, y=y) for v, y in pairs]
    result = _FitResult(a=a, b=b, r_squared=r2, points=calib_points)
    return result, unit, warnings


def y_to_value(y: float, calibration: AxisCalibration) -> float:
    """Convert a y pixel coordinate to a calibrated value.

    Reuses the slope/intercept computed during calibration rather than
    re-fitting on every call.
    """
    if not calibration.points or len(calibration.points) < 2:
        return 0.0
    return calibration.scale_per_point * y + calibration.intercept


def _calibrate_x_axis(
    spans: list[TextSpan],
    chart_rect: fitz.Rect,
    bounds: fitz.Rect | None = None,
) -> tuple[AxisInfo, list[str]]:
    bx0 = bounds.x0 if bounds else chart_rect.x0
    bx1 = bounds.x1 if bounds else chart_rect.x1
    by1 = bounds.y1 if bounds else chart_rect.y1
    plot_w = max(bx1 - bx0, 1.0)

    # Candidate spans: at or below the plot baseline and within the chart rect.
    # The horizontal bound is the (label-expanded) chart rect rather than the
    # tight plot bounds, because outermost x-labels often overhang the data and,
    # for line charts, the label row can be wider than the polyline's bbox.
    cands = [
        s
        for s in spans
        if s.bbox[1] >= by1 - 5
        and s.y_center <= chart_rect.y1 + 10
        and chart_rect.x0 - 5 <= s.x_center <= chart_rect.x1 + 5
        and s.text.strip()
    ]
    if not cands:
        return AxisInfo(kind="categorical", labels=[]), []

    labels = _build_x_labels(cands, plot_w)
    if not labels:
        return AxisInfo(kind="categorical", labels=[]), []

    # Determine categorical vs numeric
    numeric_count = sum(1 for lbl in labels if _parse_number(lbl) is not None)
    if numeric_count > len(labels) * 0.7:
        return AxisInfo(kind="numeric", labels=labels), []

    return AxisInfo(kind="categorical", labels=labels), []


def _group_rows(spans: list[TextSpan], y_tol: float = 5.0) -> list[list[TextSpan]]:
    """Cluster spans into horizontal rows by y-center proximity."""
    rows: list[list[TextSpan]] = []
    for s in sorted(spans, key=lambda s: s.y_center):
        if rows and s.y_center - rows[-1][-1].y_center <= y_tol:
            rows[-1].append(s)
        else:
            rows.append([s])
    return rows


def _build_x_labels(cands: list[TextSpan], plot_w: float) -> list[str]:
    """Derive ordered x-axis labels from candidate spans below the baseline.

    The label row is the one nearest below the plot baseline that spreads across
    the plot with several entries; its spans define one column each (left to
    right).  Genuine two-line labels (a month row above a year row, or the two
    lines of a "dal …"/"al …" date range) are kept by absorbing a directly
    adjacent lower row only when it has about the same number of entries — one
    per column.  Stray content (temperature readouts, "<"/"=" markers, billing
    tables) differs in count or sits below a larger vertical gap, so it is
    dropped instead of polluting the label list.
    """
    rows = _group_rows(cands)

    def coverage(row: list[TextSpan]) -> float:
        xs = [s.x_center for s in row]
        return (max(xs) - min(xs)) / plot_w

    def qualifies(row: list[TextSpan]) -> bool:
        return len(row) >= 2 and coverage(row) >= 0.3

    primary_idx = next((i for i, r in enumerate(rows) if qualifies(r)), None)
    if primary_idx is None:
        primary_idx = max(range(len(rows)), key=lambda i: coverage(rows[i]))

    primary = sorted(rows[primary_idx], key=lambda s: s.x_center)

    # Each primary-row span is a column; lower rows attach to their nearest column.
    columns: list[list[TextSpan]] = [[s] for s in primary]
    column_x = [s.x_center for s in primary]

    for i in range(primary_idx + 1, len(rows)):
        prev_y = max(s.y_center for s in rows[i - 1])
        curr_y = min(s.y_center for s in rows[i])
        if curr_y - prev_y > 12:
            break
        # A true second label line has roughly one entry per column.
        if not (len(primary) * 0.7 <= len(rows[i]) <= len(primary) * 1.3):
            break
        for s in rows[i]:
            nearest = min(range(len(column_x)), key=lambda c: abs(column_x[c] - s.x_center))
            columns[nearest].append(s)

    labels: list[str] = []
    for col in columns:
        col.sort(key=lambda s: (s.y_center, s.x_center))
        text = " ".join(s.text.strip() for s in col if s.text.strip())
        if text:
            labels.append(text)
    return labels


def _resolve_unit(detected: str | None, hint: str) -> str:
    if hint != "auto":
        return hint
    return detected or "auto"
