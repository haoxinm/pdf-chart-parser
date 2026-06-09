"""Tests for io_utils.load_pdf_bytes."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from pdf_chart_parser.io_utils import load_pdf_bytes

PDFS_DIR = Path(__file__).parent / "fixtures" / "pdfs"


def test_load_from_path(synthetic_bar_pdf):
    data = load_pdf_bytes(pdf_path=str(synthetic_bar_pdf))
    assert data.startswith(b"%PDF")


def test_load_from_base64(synthetic_bar_pdf):
    raw = synthetic_bar_pdf.read_bytes()
    encoded = base64.b64encode(raw).decode()
    data = load_pdf_bytes(pdf_base64=encoded)
    assert data == raw


def test_no_input_raises():
    with pytest.raises(ValueError, match="Exactly one"):
        load_pdf_bytes()


def test_multiple_inputs_raises(synthetic_bar_pdf):
    raw = synthetic_bar_pdf.read_bytes()
    encoded = base64.b64encode(raw).decode()
    with pytest.raises(ValueError, match="exactly one"):
        load_pdf_bytes(pdf_path=str(synthetic_bar_pdf), pdf_base64=encoded)


def test_nonexistent_path_raises():
    with pytest.raises(FileNotFoundError):
        load_pdf_bytes(pdf_path="/no/such/file.pdf")


def test_invalid_base64_raises():
    with pytest.raises(ValueError, match="base64"):
        load_pdf_bytes(pdf_base64="not-valid-base64!!!")


def test_non_pdf_bytes_raises(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a pdf")
    with pytest.raises(ValueError, match="magic bytes"):
        load_pdf_bytes(pdf_path=str(bad))


def test_non_pdf_base64_raises():
    encoded = base64.b64encode(b"not a pdf at all").decode()
    with pytest.raises(ValueError, match="magic bytes"):
        load_pdf_bytes(pdf_base64=encoded)
