"""Orchestrator: load PDF, detect chart type, run extraction, assemble result."""

from __future__ import annotations

from typing import Any, Literal

from pdf_chart_parser.io_utils import load_pdf_bytes


def extract_usage_chart(
    pdf_path: str | None = None,
    pdf_base64: str | None = None,
    pdf_url: str | None = None,
    page: int | None = None,
    chart_type: Literal["auto", "bar", "line", "hybrid"] = "auto",
    value_unit: Literal["auto", "dollars", "kwh"] = "auto",
    return_annotated_image: bool = True,
    render_dpi: int = 200,
) -> dict[str, Any]:
    """End-to-end extraction: returns a dict matching the ExtractionResult schema.

    Also includes an 'annotated_png' key (bytes | None) when return_annotated_image=True.
    """
    import fitz  # PyMuPDF

    pdf_bytes = load_pdf_bytes(pdf_path=pdf_path, pdf_base64=pdf_base64, pdf_url=pdf_url)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Extract full-page markdown text via pymupdf4llm
    page_markdown = _extract_page_markdown(doc, page)

    # Determine target page
    target_page = _select_page(doc, page)

    # Try vector extraction
    result = _try_vector(
        doc, target_page, chart_type, value_unit, render_dpi, return_annotated_image
    )
    result["page_markdown"] = page_markdown
    result["page"] = target_page

    doc.close()
    return result


def _extract_page_markdown(doc: Any, page_hint: int | None) -> str:
    """Return LLM-friendly markdown for the target page (or whole doc if page unknown)."""
    try:
        import pymupdf4llm

        if page_hint is not None:
            return pymupdf4llm.to_markdown(doc, pages=[page_hint])
        return pymupdf4llm.to_markdown(doc)
    except Exception:
        return ""


def _select_page(doc: Any, page_hint: int | None) -> int:
    """Return the 0-based page index most likely to contain a usage chart."""
    if page_hint is not None:
        return max(0, min(page_hint, len(doc) - 1))

    best_page = 0
    best_score = -1
    for i in range(len(doc)):
        pg = doc[i]
        text = pg.get_text("text").lower()
        score = sum(
            kw in text
            for kw in ("kwh", "usage", "kw", "$", "electric", "gas", "billing", "charges")
        )
        drawings = pg.get_drawings()
        rects = sum(1 for d in drawings if any(it[0] == "re" for it in d.get("items", [])))
        score += min(rects // 5, 5)
        if score > best_score:
            best_score = score
            best_page = i

    return best_page


def _try_vector(
    doc: Any,
    page_index: int,
    chart_type_hint: str,
    value_unit_hint: str,
    render_dpi: int,
    return_annotated_image: bool,
) -> dict[str, Any]:
    """Attempt vector extraction; fall back to raster on failure."""
    from pdf_chart_parser.annotate import annotate_chart
    from pdf_chart_parser.vector.bars import extract_bars
    from pdf_chart_parser.vector.calibrate import calibrate_axes
    from pdf_chart_parser.vector.drawings import collect_drawings
    from pdf_chart_parser.vector.lines import extract_lines
    from pdf_chart_parser.vector.locate import locate_chart
    from pdf_chart_parser.vector.text import collect_text_spans

    warnings: list[str] = []
    page = doc[page_index]

    # Gate: check if scanned/raster page
    raw_text = page.get_text("text").strip()
    if not raw_text:
        warnings.append("page appears scanned or raster; text layer empty")
        return _try_raster(
            doc,
            page_index,
            chart_type_hint,
            value_unit_hint,
            render_dpi,
            return_annotated_image,
            warnings,
        )

    try:
        drawings = collect_drawings(page)
        spans = collect_text_spans(page)
        location = locate_chart(drawings, spans, chart_type_hint)

        if location is None:
            warnings.append("no qualifying chart region found via vector; falling back to raster")
            return _try_raster(
                doc,
                page_index,
                chart_type_hint,
                value_unit_hint,
                render_dpi,
                return_annotated_image,
                warnings,
            )

        chart_rect, detected_type, bar_rects, line_paths, plot_rect = location
        axes, calibration_warnings = calibrate_axes(
            spans, chart_rect, value_unit_hint, plot_rect=plot_rect
        )
        warnings.extend(calibration_warnings)

        series = []
        if bar_rects:
            bar_series, bar_warnings = extract_bars(bar_rects, axes, chart_rect)
            warnings.extend(bar_warnings)
            series.extend(bar_series)

        if line_paths:
            line_series, line_warnings = extract_lines(
                line_paths, axes, spans, chart_rect, plot_rect=plot_rect
            )
            warnings.extend(line_warnings)
            series.extend(line_series)

        annotated_png = None
        if return_annotated_image:
            try:
                annotated_png = annotate_chart(
                    page, chart_rect, series, axes, render_dpi, detected_type
                )
            except Exception as exc:
                warnings.append(f"annotation failed: {exc}")

        confidence = _compute_confidence(axes, series, warnings)

        result: dict = {
            "chart_found": True,
            "method": "vector",
            "chart_type": detected_type,
            "axes": axes.model_dump(exclude_none=True),
            "series": [s.model_dump() for s in series],
            "warnings": warnings,
            "confidence": confidence,
            "annotated_png": annotated_png,
        }
        return result

    except Exception as exc:
        warnings.append(f"vector extraction failed: {exc}")
        return _try_raster(
            doc,
            page_index,
            chart_type_hint,
            value_unit_hint,
            render_dpi,
            return_annotated_image,
            warnings,
        )


def _try_raster(
    doc: Any,
    page_index: int,
    chart_type_hint: str,
    value_unit_hint: str,
    render_dpi: int,
    return_annotated_image: bool,
    warnings: list[str],
) -> dict[str, Any]:
    """Attempt raster CV/OCR extraction. Returns failed result if unavailable."""
    try:
        from pdf_chart_parser.raster.cv_pipeline import extract_raster
    except ImportError:
        warnings.append("raster extra not installed; install pdf-chart-parser[raster] for fallback")
        return _failed_result(warnings)

    try:
        return extract_raster(
            doc,
            page_index,
            chart_type_hint,
            value_unit_hint,
            render_dpi,
            return_annotated_image,
            warnings,
        )
    except Exception as exc:
        warnings.append(f"raster extraction failed: {exc}")
        return _failed_result(warnings)


def _failed_result(warnings: list[str]) -> dict[str, Any]:
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


def _compute_confidence(axes: Any, series: list, warnings: list[str]) -> float:
    """Heuristic overall confidence score."""
    base = 1.0
    r2 = getattr(axes.y_primary, "r_squared", 0.0)
    if r2 < 0.999:
        base -= 0.1
    if any("secondary" in w for w in warnings):
        base -= 0.02
    if not series:
        base = 0.0
    series_confidences = [s.confidence for s in series]
    if series_confidences:
        avg_series = sum(series_confidences) / len(series_confidences)
        base = (base + avg_series) / 2
    return round(max(0.0, min(1.0, base)), 4)
