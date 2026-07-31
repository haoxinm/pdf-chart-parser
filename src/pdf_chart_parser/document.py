"""Generic multi-page PDF text + image extraction.

Generalizes the single-chart extraction in this server into a reusable document
reader: per-page Markdown text (via pymupdf4llm) plus optional rendered page
PNGs (via pymupdf). Any skill that needs to read a document can call this and 
get a deterministic, model-agnostic representation that works for vision and 
non-vision models alike.
"""

from __future__ import annotations

import base64
import re

import fitz  # pymupdf
import pymupdf4llm
from pydantic import BaseModel, Field

from pdf_chart_parser.io_utils import load_pdf_bytes
from pdf_chart_parser.ocr_layer import add_text_layer, doc_needs_ocr

# ─── Guardrails ───────────────────────────────────────────────────────────────
# Caps keep a single call bounded in time, memory, and response size so a large
# document can never hang the agent turn or blow the MCP response budget.
MAX_PAGES_PROCESSED = 60
MAX_IMAGES_RENDERED = 30
MAX_TOTAL_IMAGE_BYTES = 18 * 1024 * 1024  # ~18 MB of base64-decoded PNG
MAX_IMAGE_DPI = 200
MIN_IMAGE_DPI = 36
# A page whose extracted text is shorter than this is treated as image-only
# (scanned) and gets a rendered PNG even when render_page_images is False, so a
# vision model can still read it.
_IMAGE_ONLY_TEXT_THRESHOLD = 16

# pymupdf4llm emits a placeholder like "**==> picture [252 x 252] intentionally
# omitted <==**" for pages whose only content is a raster image. That marker is
# itself the strongest signal a page is scanned/image-only, so strip it before
# measuring text length — otherwise the placeholder's own length masks the page
# as if it had real text and the scanned-page PNG fallback never fires.
_PICTURE_OMITTED_RE = re.compile(
    r"\*{0,2}==>\s*(?:picture|image)\b.*?omitted\s*<==\*{0,2}", re.IGNORECASE | re.DOTALL
)


def _meaningful_len(text: str) -> int:
    """Length of page text ignoring pymupdf4llm's image-omitted placeholders."""
    return len(_PICTURE_OMITTED_RE.sub("", text).strip())


class PdfPage(BaseModel):
    page: int = Field(description="1-based page number.")
    text: str = Field(description="Page content as Markdown (pymupdf4llm).")
    image_png_base64: str | None = Field(
        default=None,
        description="Base64-encoded PNG render of the page, when requested or for scanned pages.",
    )


class PdfDocument(BaseModel):
    total_pages: int = Field(description="Total page count of the source PDF.")
    pages: list[PdfPage]
    truncated: bool = Field(
        default=False,
        description="True if processing/image caps dropped pages or images from the result.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable notes about any capping or scanned-page handling.",
    )


def _normalize_pages(pages: list[int] | None, total: int) -> tuple[list[int], bool]:
    """Map a 1-based page selection to 0-based indices within [0, total).

    Returns (zero_based_indices, truncated). Out-of-range pages are dropped.
    Default (None) selects all pages, capped at MAX_PAGES_PROCESSED.
    """
    if pages is None:
        selected = list(range(total))
    else:
        seen: set[int] = set()
        selected = []
        for p in pages:
            idx = p - 1
            if 0 <= idx < total and idx not in seen:
                seen.add(idx)
                selected.append(idx)
    truncated = False
    if len(selected) > MAX_PAGES_PROCESSED:
        selected = selected[:MAX_PAGES_PROCESSED]
        truncated = True
    return selected, truncated


def extract_pdf_document(
    pdf_path: str | None = None,
    pdf_base64: str | None = None,
    pdf_url: str | None = None,
    pages: list[int] | None = None,
    render_page_images: bool = False,
    image_dpi: int = 100,
) -> dict:
    """Extract page text + optional page images from a PDF. Pure/deterministic.

    image_dpi defaults to 100: model image-token cost plateaus at roughly
    2,500 tokens/image above ~100 DPI (the vision patch cap), so a higher
    default buys the model nothing while costing bytes and latency, and makes
    it more likely a multi-page request trips MAX_TOTAL_IMAGE_BYTES before all
    pages are rendered.
    """
    data = load_pdf_bytes(pdf_path=pdf_path, pdf_base64=pdf_base64, pdf_url=pdf_url)
    dpi = max(MIN_IMAGE_DPI, min(MAX_IMAGE_DPI, image_dpi))

    notes: list[str] = []
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        total = doc.page_count
        selected, truncated = _normalize_pages(pages, total)
        if truncated:
            notes.append(
                f"page selection capped at {MAX_PAGES_PROCESSED} pages (document has {total})"
            )

        # If any selected page is scanned/image-only, embed a searchable text
        # layer so its content comes back as real Markdown instead of nothing.
        if doc_needs_ocr(doc, selected):
            ocr_bytes, applied, ocr_note = add_text_layer(data)
            if ocr_note:
                notes.append(ocr_note)
            if applied:
                doc.close()
                doc = fitz.open(stream=ocr_bytes, filetype="pdf")

        # pymupdf4llm wants 0-based page numbers; request exactly the selected set.
        # use_ocr=False: pymupdf4llm's own page-analysis heuristic (image
        # variance / edge energy / vector-glyph-count) will otherwise decide a
        # page "needs OCR" and silently discard its real, correctly-extracted
        # native text layer in favor of a Tesseract read of a flattened raster
        # — a false positive on any page with an embedded photo, vicinity map,
        # or manufacturer screenshot, which is common on plan-set cover and
        # cutsheet pages. This is complementary to, not a regression of, the
        # doc_needs_ocr/add_text_layer step above: a genuinely scanned page has
        # already had a real OCR text layer burned in by that step by the time
        # to_markdown runs, so use_ocr=False here just stops pymupdf4llm from
        # redundantly (and sometimes incorrectly) re-deciding to OCR on its own.
        md_chunks = pymupdf4llm.to_markdown(doc, pages=selected, page_chunks=True, use_ocr=False)
        # to_markdown returns one chunk per requested page, in request order.
        text_by_index = {
            idx: (chunk.get("text") or "") for idx, chunk in zip(selected, md_chunks)
        }

        rendered_images = 0
        total_image_bytes = 0
        # Sticky flag: once the total-bytes cap trips on some page, stop even
        # attempting to rasterize later pages — rendering a PNG just to throw
        # it away (because the cap check used to happen *after* rendering) was
        # pure wasted work. Per-page text extraction above is unaffected: it
        # already ran for every page in `selected` before this loop starts.
        image_byte_cap_tripped = False
        out_pages: list[PdfPage] = []
        for idx in selected:
            text = text_by_index.get(idx, "")
            image_b64: str | None = None

            is_image_only = _meaningful_len(text) < _IMAGE_ONLY_TEXT_THRESHOLD
            want_image = render_page_images or is_image_only

            if want_image:
                if rendered_images >= MAX_IMAGES_RENDERED:
                    truncated = True
                    notes.append(
                        f"image rendering capped at {MAX_IMAGES_RENDERED} images"
                    )
                elif image_byte_cap_tripped:
                    # Already know any further page would blow the byte cap —
                    # don't rasterize it just to discard the result.
                    truncated = True
                else:
                    png = doc.load_page(idx).get_pixmap(dpi=dpi).tobytes("png")
                    if total_image_bytes + len(png) > MAX_TOTAL_IMAGE_BYTES:
                        truncated = True
                        image_byte_cap_tripped = True
                        notes.append("image rendering stopped at the total-bytes cap")
                    else:
                        total_image_bytes += len(png)
                        rendered_images += 1
                        image_b64 = base64.b64encode(png).decode("ascii")
                        if is_image_only and not render_page_images:
                            notes.append(
                                f"page {idx + 1} appears scanned/image-only — returning a rendered PNG"
                            )

            out_pages.append(PdfPage(page=idx + 1, text=text, image_png_base64=image_b64))

        return PdfDocument(
            total_pages=total,
            pages=out_pages,
            truncated=truncated,
            notes=notes,
        ).model_dump()
    finally:
        doc.close()
