"""Tests for the generic extract_pdf_document tool."""

from __future__ import annotations

import base64

import fitz  # pymupdf
import pytest

from pdf_chart_parser import document as doc_mod
from pdf_chart_parser.document import extract_pdf_document


@pytest.fixture
def multipage_pdf_bytes() -> bytes:
    """A small 3-page text PDF for extraction tests."""
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} heading\nSome body text on page {i + 1}.")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def scanned_pdf_bytes() -> bytes:
    """A 1-page PDF with no text layer (simulates a scanned page)."""
    doc = fitz.open()
    page = doc.new_page()
    # Draw a filled rectangle so the page renders to a non-trivial image but
    # carries no extractable text.
    page.draw_rect(fitz.Rect(50, 50, 300, 300), fill=(0.2, 0.4, 0.6))
    data = doc.tobytes()
    doc.close()
    return data


def test_extracts_all_pages_text(multipage_pdf_bytes: bytes) -> None:
    b64 = base64.b64encode(multipage_pdf_bytes).decode("ascii")
    out = extract_pdf_document(pdf_base64=b64)
    assert out["total_pages"] == 3
    assert len(out["pages"]) == 3
    assert out["pages"][0]["page"] == 1
    assert "Page 1" in out["pages"][0]["text"]
    # No images requested and pages are text → no image rendered.
    assert out["pages"][0]["image_png_base64"] is None
    assert out["truncated"] is False


def test_page_selection_is_one_based(multipage_pdf_bytes: bytes) -> None:
    b64 = base64.b64encode(multipage_pdf_bytes).decode("ascii")
    out = extract_pdf_document(pdf_base64=b64, pages=[2])
    assert [p["page"] for p in out["pages"]] == [2]
    assert "Page 2" in out["pages"][0]["text"]


def test_render_page_images_returns_png(multipage_pdf_bytes: bytes) -> None:
    b64 = base64.b64encode(multipage_pdf_bytes).decode("ascii")
    out = extract_pdf_document(pdf_base64=b64, render_page_images=True, pages=[1])
    png_b64 = out["pages"][0]["image_png_base64"]
    assert png_b64 is not None
    # Decodes to a real PNG (magic bytes).
    assert base64.b64decode(png_b64).startswith(b"\x89PNG\r\n\x1a\n")


def test_scanned_page_gets_image_even_without_flag(scanned_pdf_bytes: bytes) -> None:
    b64 = base64.b64encode(scanned_pdf_bytes).decode("ascii")
    out = extract_pdf_document(pdf_base64=b64, render_page_images=False)
    # Image-only page → PNG returned anyway so a vision model can read it.
    assert out["pages"][0]["image_png_base64"] is not None
    assert any("scanned" in n or "image-only" in n for n in out["notes"])


def test_page_cap_enforced(monkeypatch: pytest.MonkeyPatch, multipage_pdf_bytes: bytes) -> None:
    # Lower the cap to 2 and confirm truncation kicks in on a 3-page doc.
    monkeypatch.setattr(doc_mod, "MAX_PAGES_PROCESSED", 2)
    b64 = base64.b64encode(multipage_pdf_bytes).decode("ascii")
    out = extract_pdf_document(pdf_base64=b64)
    assert len(out["pages"]) == 2
    assert out["truncated"] is True


def test_requires_exactly_one_source() -> None:
    with pytest.raises(ValueError):
        extract_pdf_document()
