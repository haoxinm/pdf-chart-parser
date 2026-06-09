"""Raster CV/OCR fallback for scanned PDFs or failed vector extraction."""

from __future__ import annotations

from typing import Any


def extract_raster(
    doc: Any,
    page_index: int,
    chart_type_hint: str,
    value_unit_hint: str,
    render_dpi: int,
    return_annotated_image: bool,
    warnings: list[str],
) -> dict[str, Any]:
    """Run OpenCV-based chart extraction as a fallback.

    Requires the [raster] extra: opencv-python-headless + pytesseract.
    """
    import cv2
    import fitz
    import numpy as np

    from pdf_chart_parser.raster.ocr import ocr_axis_labels

    page = doc[page_index]
    zoom = render_dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img_bytes = pix.tobytes("png")

    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        warnings.append("cv2 failed to decode rendered page image")
        return _failed(warnings)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Detect bars via contours
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bar_candidates = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if h > w * 0.8 and h > 20 and w > 5:
            bar_candidates.append((x, y, w, h))

    if not bar_candidates:
        warnings.append("raster: no bar candidates found")
        return _failed(warnings)

    # Sort by x
    bar_candidates.sort(key=lambda b: b[0])

    # OCR axis labels
    h_img, w_img = img.shape[:2]
    bottom_strip = img[h_img * 7 // 8 :, :]
    bottom_labels = ocr_axis_labels(bottom_strip)

    warnings.append("raster fallback used; accuracy may be lower than vector path")

    from pdf_chart_parser.models import Axes, AxisCalibration, AxisInfo, DataPoint, Series

    baseline_y = max(b[1] + b[3] for b in bar_candidates)
    series_points = []
    for i, (x, y, w, h) in enumerate(bar_candidates):
        bar_top_y = y
        pixel_height = baseline_y - bar_top_y
        x_label = bottom_labels[i] if i < len(bottom_labels) else str(i)
        series_points.append(
            DataPoint(
                x_label=x_label,
                x=float(x + w // 2),
                value=float(pixel_height),
                y=float(bar_top_y),
                baseline_y=float(baseline_y),
                confidence=0.7,
            )
        )

    bar_series = Series(
        id="s0",
        type="bar",
        label="",
        unit=value_unit_hint if value_unit_hint != "auto" else "auto",
        axis="y_primary",
        color=[0.3, 0.5, 0.8],
        confidence=0.7,
        points=series_points,
    )

    axes = Axes(
        x=AxisInfo(kind="categorical", labels=bottom_labels),
        y_primary=AxisCalibration(
            unit=value_unit_hint if value_unit_hint != "auto" else "auto",
            points=[],
            scale_per_point=1.0,
            scale_per_pixel=1.0 / zoom,
            r_squared=0.0,
        ),
    )

    return {
        "chart_found": True,
        "method": "raster_cv",
        "chart_type": "bar",
        "axes": axes.model_dump(exclude_none=True),
        "series": [bar_series.model_dump()],
        "warnings": warnings,
        "confidence": 0.6,
        "annotated_png": None,
    }


def _failed(warnings: list[str]) -> dict[str, Any]:
    return {
        "chart_found": False,
        "method": "failed",
        "chart_type": None,
        "axes": {},
        "series": [],
        "warnings": warnings,
        "confidence": 0.0,
        "annotated_png": None,
    }
