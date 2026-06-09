"""FastMCP server exposing the extract_usage_chart tool."""

from __future__ import annotations

import os
from typing import Literal

from mcp.server.fastmcp import FastMCP, Image

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


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
