"""MCP server smoke tests — invokes tool function directly without live transport."""

from __future__ import annotations

import inspect


def test_extract_pdf_document_wrapper_dpi_default_matches_impl():
    """server.py's @mcp.tool() wrapper declares its own image_dpi default,
    duplicated from document.py's implementation rather than delegating to
    it — so the two can silently drift apart (as happened here: the
    implementation's default moved to 100 while this wrapper stayed at the
    old 150, meaning every real MCP caller that omits image_dpi would still
    have gotten 150). Guard against that drift recurring."""
    from pdf_chart_parser.document import extract_pdf_document as impl
    from pdf_chart_parser.server import extract_pdf_document as wrapped

    # FastMCP's @mcp.tool() decorator returns a FunctionTool wrapping the
    # original function; the original is preserved as .fn for inspection.
    tool_fn = getattr(wrapped, "fn", wrapped)
    wrapper_default = inspect.signature(tool_fn).parameters["image_dpi"].default
    impl_default = inspect.signature(impl).parameters["image_dpi"].default
    assert wrapper_default == impl_default == 100


def test_server_importable():
    from pdf_chart_parser.server import extract_usage_chart, mcp

    assert mcp is not None
    assert callable(extract_usage_chart)


def test_tool_returns_list(synthetic_bar_pdf):
    from pdf_chart_parser.server import extract_usage_chart as tool

    result = tool(pdf_path=str(synthetic_bar_pdf), return_annotated_image=True)
    assert isinstance(result, list)
    assert len(result) >= 1


def test_tool_first_element_is_dict(synthetic_bar_pdf):
    from pdf_chart_parser.server import extract_usage_chart as tool

    result = tool(pdf_path=str(synthetic_bar_pdf), return_annotated_image=False)
    assert isinstance(result[0], dict)
    assert "chart_found" in result[0]
    assert "series" in result[0]


def test_tool_includes_image_content(synthetic_bar_pdf):
    from mcp.server.fastmcp import Image

    from pdf_chart_parser.server import extract_usage_chart as tool

    result = tool(pdf_path=str(synthetic_bar_pdf), return_annotated_image=True)
    assert len(result) == 2
    assert isinstance(result[1], Image)


def test_tool_no_image_when_flag_false(synthetic_bar_pdf):
    from pdf_chart_parser.server import extract_usage_chart as tool

    result = tool(pdf_path=str(synthetic_bar_pdf), return_annotated_image=False)
    assert len(result) == 1


def test_tool_includes_page_markdown(synthetic_bar_pdf):
    from pdf_chart_parser.server import extract_usage_chart as tool

    result = tool(pdf_path=str(synthetic_bar_pdf), return_annotated_image=False)
    data = result[0]
    assert "page_markdown" in data
    assert isinstance(data["page_markdown"], str)
