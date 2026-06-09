"""MCP server smoke tests — invokes tool function directly without live transport."""

from __future__ import annotations


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
