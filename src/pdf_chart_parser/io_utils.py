"""PDF input handling: path, base64, or URL → bytes."""

from __future__ import annotations

import base64
from pathlib import Path

_PDF_MAGIC = b"%PDF"
_MAX_URL_BYTES = 50 * 1024 * 1024  # 50 MB


def _validate_magic(data: bytes, source: str) -> None:
    if not data.startswith(_PDF_MAGIC):
        raise ValueError(f"{source} does not appear to be a PDF (missing %PDF magic bytes)")


def _looks_like_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _load_from_url(url: str) -> bytes:
    import httpx

    try:
        with httpx.stream("GET", url, timeout=30, follow_redirects=True) as resp:
            resp.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes(chunk_size=65536):
                total += len(chunk)
                if total > _MAX_URL_BYTES:
                    raise ValueError(
                        f"PDF at URL exceeds {_MAX_URL_BYTES // (1024 * 1024)} MB size limit"
                    )
                chunks.append(chunk)
            data = b"".join(chunks)
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"HTTP error fetching PDF: {exc}") from exc
    except httpx.RequestError as exc:
        raise ValueError(f"Network error fetching PDF: {exc}") from exc

    _validate_magic(data, f"URL '{url}'")
    return data


def load_pdf_bytes(
    pdf_path: str | None = None,
    pdf_base64: str | None = None,
    pdf_url: str | None = None,
) -> bytes:
    """Return raw PDF bytes from exactly one of the three input sources.

    A caller-supplied `pdf_path` that is actually an http(s) URL (e.g. a
    presigned download URL forwarded under the wrong argument name) is
    fetched the same way as `pdf_url` rather than being treated as a local
    filesystem path — a URL string can never `Path.exists()`, so without
    this it fails instantly with a misleading "PDF not found" error instead
    of ever attempting the download.
    """
    provided = [x for x in (pdf_path, pdf_base64, pdf_url) if x is not None]
    if len(provided) == 0:
        raise ValueError("Exactly one of pdf_path, pdf_base64, or pdf_url must be provided")
    if len(provided) > 1:
        raise ValueError("Provide exactly one of pdf_path, pdf_base64, or pdf_url — got multiple")

    if pdf_path is not None:
        if _looks_like_url(pdf_path):
            return _load_from_url(pdf_path)
        p = Path(pdf_path)
        if not p.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        data = p.read_bytes()
        _validate_magic(data, f"file '{pdf_path}'")
        return data

    if pdf_base64 is not None:
        try:
            data = base64.b64decode(pdf_base64)
        except Exception as exc:
            raise ValueError(f"Invalid base64 data: {exc}") from exc
        _validate_magic(data, "base64 input")
        return data

    # pdf_url
    assert pdf_url is not None
    return _load_from_url(pdf_url)
