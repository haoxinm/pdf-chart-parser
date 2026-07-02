"""FastMCP server exposing the extract_usage_chart tool."""

from __future__ import annotations

import os
from typing import Literal

from mcp.server.fastmcp import FastMCP, Image

from pdf_chart_parser.document import extract_pdf_document as _extract_pdf_document
from pdf_chart_parser.pipeline import extract_usage_chart as _run_pipeline

mcp = FastMCP(
    "usage-chart-extractor",
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "8000")),
    # Each tool call is independent — no session tracking or SSE streaming needed.
    # json_response=True also satisfies AI agent clients that only send Accept: application/json.
    json_response=True,
    stateless_http=True,
)


@mcp.tool()
def extract_usage_chart(
    pdf_path: str | None = None,
    pdf_base64: str | None = None,
    pdf_url: str | None = None,
    page: int | None = None,
    chart_type: Literal["auto", "bar", "line", "hybrid"] = "auto",
    value_unit: Literal["auto", "dollars", "kwh"] = "auto",
    return_annotated_image: bool = True,
    render_dpi: int = 200,
) -> list:
    """Extract energy-usage chart data from a utility-bill PDF.

    Returns the full page text as Markdown, structured chart data as JSON,
    and optionally an annotated PNG of the chart region.

    Provide exactly one of pdf_path, pdf_base64, or pdf_url.

    The result includes a 'series' list.  When the chart contains multiple
    utility types (e.g. electricity and gas on the same chart), each type is
    returned as a separate Series entry with its own 'id' ('s0', 's1', …) and
    'color'.  The caller is responsible for determining which series corresponds
    to which utility — use the bar colors, the series order, and the page
    Markdown context to make that determination.

    IMPORTANT — check `values_calibrated` before using any numbers:
    Some bills draw a chart whose bars/lines are visible but whose y-axis has
    no usable numeric scale (fewer than two readable tick labels, or a
    low-confidence fit). In that case this tool cannot compute real values, so
    every affected point's 'value' is returned as null rather than a fabricated
    number (0 or otherwise) — do not treat null as zero usage.

    - `values_calibrated` (bool): true only when every point's 'value' is a
      real, calibrated number. If false, DO NOT use 'series' as consumption or
      cost data — the bars/lines were detected but their values could not be
      measured.
    - `calibration_status` (string): "calibrated", "uncalibrated_axis" (no
      usable y-axis ticks were found), "low_confidence" (the axis or CV fit
      was too poor to trust), or "no_chart" (no chart was found at all).

    When `values_calibrated` is false, fall back to reading the document's
    full text instead — call the generic text-extraction tool in this same
    server (`extract_pdf_document`) on the same PDF and look for a printed
    monthly/13-month usage table, or a per-period daily-average value, in the
    page text. Only ask the caller/user for the numbers if neither the chart
    nor the text yields them.
    """
    result = _run_pipeline(
        pdf_path=pdf_path,
        pdf_base64=pdf_base64,
        pdf_url=pdf_url,
        page=page,
        chart_type=chart_type,
        value_unit=value_unit,
        return_annotated_image=return_annotated_image,
        render_dpi=render_dpi,
    )

    annotated_png: bytes | None = result.pop("annotated_png", None)

    out: list = [result]
    if return_annotated_image and annotated_png:
        out.append(Image(data=annotated_png, format="png"))
    return out


@mcp.tool()
def extract_pdf_document(
    pdf_path: str | None = None,
    pdf_base64: str | None = None,
    pdf_url: str | None = None,
    pages: list[int] | None = None,
    render_page_images: bool = False,
    image_dpi: int = 150,
) -> dict:
    """Extract per-page text and (optionally) page images from any PDF document.

    Generic, model-agnostic document reader for plan sets, permit packets, spec
    sheets, contracts, or any multi-page PDF — not just utility-bill charts. Use
    this whenever a skill needs the textual content of an uploaded PDF, or page
    images for visual review.

    Provide exactly one of pdf_path, pdf_base64, or pdf_url. `pages` is a 1-based
    list selecting specific pages (default: all). Set render_page_images=true to
    also get a base64 PNG of each page (e.g. for cover sheets, site plans, or
    single-line diagrams that need visual inspection). Scanned/image-only pages
    always come back with a rendered PNG so vision models can still read them.

    Returns { total_pages, pages: [{ page, text (Markdown), image_png_base64? }],
    truncated, notes }. Page/image counts and total bytes are capped so a large
    document can never hang the turn.
    """
    return _extract_pdf_document(
        pdf_path=pdf_path,
        pdf_base64=pdf_base64,
        pdf_url=pdf_url,
        pages=pages,
        render_page_images=render_page_images,
        image_dpi=image_dpi,
    )


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
