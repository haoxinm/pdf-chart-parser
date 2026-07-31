"""Tests for the generic extract_pdf_document tool."""

from __future__ import annotations

import base64
import shutil
from io import BytesIO

import fitz  # pymupdf
import pytest
from PIL import Image, ImageDraw

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


def test_to_markdown_called_with_use_ocr_false(
    monkeypatch: pytest.MonkeyPatch, multipage_pdf_bytes: bytes
) -> None:
    """Regression guard for the auto-OCR corruption bug: to_markdown must be
    called with use_ocr=False so pymupdf4llm's own image-heuristic never
    silently discards a page's real, correctly-extracted native text."""
    calls: list[dict] = []
    real_to_markdown = doc_mod.pymupdf4llm.to_markdown

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real_to_markdown(*args, **kwargs)

    monkeypatch.setattr(doc_mod.pymupdf4llm, "to_markdown", spy)

    b64 = base64.b64encode(multipage_pdf_bytes).decode("ascii")
    extract_pdf_document(pdf_base64=b64)

    assert len(calls) == 1
    assert calls[0]["use_ocr"] is False


def test_scanned_pdf_still_yields_real_text_with_use_ocr_false(
    synthetic_bar_raster_pdf,
) -> None:
    """Confirms use_ocr=False on the main to_markdown call does not regress
    genuinely scanned/image-only documents: doc_needs_ocr/add_text_layer burns
    a real OCR text layer in *before* to_markdown runs, so to_markdown reads
    that embedded text layer like any other native text — it is not starved
    of the OCR it needs just because the top-level call disables its own
    auto-OCR heuristic."""
    pytest.importorskip(
        "ocrmypdf",
        reason="ocrmypdf not installed; install pdf-chart-parser[ocr] to enable",
    )
    pdf_bytes = synthetic_bar_raster_pdf.read_bytes()
    out = extract_pdf_document(pdf_path=None, pdf_base64=base64.b64encode(pdf_bytes).decode("ascii"))

    if not any("OCR" in n or "ocrmypdf" in n.lower() for n in out["notes"]):
        pytest.skip("OCRmyPDF could not run in this environment")

    text = out["pages"][0]["text"] or ""
    assert len(text.strip()) >= doc_mod._IMAGE_ONLY_TEXT_THRESHOLD


def test_page_cap_enforced(monkeypatch: pytest.MonkeyPatch, multipage_pdf_bytes: bytes) -> None:
    # Lower the cap to 2 and confirm truncation kicks in on a 3-page doc.
    monkeypatch.setattr(doc_mod, "MAX_PAGES_PROCESSED", 2)
    b64 = base64.b64encode(multipage_pdf_bytes).decode("ascii")
    out = extract_pdf_document(pdf_base64=b64)
    assert len(out["pages"]) == 2
    assert out["truncated"] is True


def test_no_rasterization_after_byte_cap_trips(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once the total-image-bytes cap trips, later pages must not even be
    rasterized — get_pixmap must not be called for them at all. Asserting
    only on the returned page list (which already correctly excludes them)
    would miss the actual bug: wasted rasterization work for pages that are
    thrown away."""
    doc = fitz.open()
    for i in range(5):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1}")
    data = doc.tobytes()
    doc.close()

    real_get_pixmap = fitz.Page.get_pixmap
    call_count = 0

    def counting_get_pixmap(self, *args, **kwargs):
        nonlocal call_count
        # pymupdf4llm's own to_markdown call also rasterizes internally (with
        # no "dpi" kwarg) for its layout analysis, independent of this
        # function's own page-rendering loop below. document.py's rendering
        # loop always calls get_pixmap(dpi=dpi) explicitly, so filter on that
        # to isolate the calls this test actually cares about.
        if "dpi" in kwargs:
            call_count += 1
        return real_get_pixmap(self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_pixmap", counting_get_pixmap)

    # First page's PNG alone exceeds this cap, so the cap trips on page 1 and
    # every later page should skip rasterization entirely.
    monkeypatch.setattr(doc_mod, "MAX_TOTAL_IMAGE_BYTES", 100)

    b64 = base64.b64encode(data).decode("ascii")
    out = extract_pdf_document(pdf_base64=b64, render_page_images=True)

    assert call_count == 1
    assert out["truncated"] is True
    assert all(p["image_png_base64"] is None for p in out["pages"][1:])


def test_requires_exactly_one_source() -> None:
    with pytest.raises(ValueError):
        extract_pdf_document()


def test_image_input_is_converted_to_pdf() -> None:
    """A single image (e.g. a photo of a bill) is accepted directly and
    comes back as a one-page document — no separate PDF conversion step
    required by the caller."""
    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "USAGE 950 kWh", fill="black")
    buf = BytesIO()
    img.save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    out = extract_pdf_document(pdf_base64=b64)

    assert out["total_pages"] == 1
    assert len(out["pages"]) == 1
    assert out["pages"][0]["page"] == 1

    if shutil.which("tesseract") is not None:
        text = out["pages"][0]["text"] or ""
        image_b64 = out["pages"][0]["image_png_base64"]
        # Either the OCR text layer picked up the string, or a page image
        # came back so a vision model could read it — either is acceptable
        # structural success without pinning exact OCR output.
        assert "950" in text or image_b64 is not None
