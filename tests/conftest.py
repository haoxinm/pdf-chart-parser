"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PDFS_DIR = FIXTURES_DIR / "pdfs"
EXPECTED_DIR = FIXTURES_DIR / "expected"


@pytest.fixture(scope="session", autouse=True)
def ensure_synthetic_fixtures():
    """Generate synthetic test fixtures if they don't exist."""
    bar_pdf = PDFS_DIR / "synthetic_bar.pdf"
    if not bar_pdf.exists():
        import subprocess
        import sys

        subprocess.run(
            [sys.executable, str(FIXTURES_DIR / "generate_synthetic.py")],
            check=True,
        )


@pytest.fixture
def synthetic_bar_pdf() -> Path:
    return PDFS_DIR / "synthetic_bar.pdf"


@pytest.fixture
def synthetic_line_pdf() -> Path:
    return PDFS_DIR / "synthetic_line.pdf"


@pytest.fixture
def synthetic_hybrid_pdf() -> Path:
    return PDFS_DIR / "synthetic_hybrid.pdf"


@pytest.fixture
def synthetic_bar_raster_pdf() -> Path:
    return PDFS_DIR / "synthetic_bar_raster.pdf"


@pytest.fixture
def synthetic_bar_expected() -> dict:
    return json.loads((EXPECTED_DIR / "synthetic_bar.json").read_text())


@pytest.fixture
def synthetic_line_expected() -> dict:
    return json.loads((EXPECTED_DIR / "synthetic_line.json").read_text())


@pytest.fixture
def synthetic_hybrid_expected() -> dict:
    return json.loads((EXPECTED_DIR / "synthetic_hybrid.json").read_text())
