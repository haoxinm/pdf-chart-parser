"""Shared pytest fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SYNTHETIC_PDFS_DIR = FIXTURES_DIR / "pdfs" / "synthetic"
SYNTHETIC_EXPECTED_DIR = FIXTURES_DIR / "expected" / "synthetic"


@pytest.fixture(scope="session", autouse=True)
def ensure_synthetic_fixtures():
    """Generate synthetic test fixtures if they don't exist."""
    if not (SYNTHETIC_PDFS_DIR / "bar.pdf").exists():
        subprocess.run(
            [sys.executable, str(FIXTURES_DIR / "generate_synthetic.py")],
            check=True,
        )


@pytest.fixture
def synthetic_bar_pdf() -> Path:
    return SYNTHETIC_PDFS_DIR / "bar.pdf"


@pytest.fixture
def synthetic_line_pdf() -> Path:
    return SYNTHETIC_PDFS_DIR / "line.pdf"


@pytest.fixture
def synthetic_hybrid_pdf() -> Path:
    return SYNTHETIC_PDFS_DIR / "hybrid.pdf"


@pytest.fixture
def synthetic_bar_raster_pdf() -> Path:
    return SYNTHETIC_PDFS_DIR / "bar_raster.pdf"


@pytest.fixture
def synthetic_bar_expected() -> dict:
    return json.loads((SYNTHETIC_EXPECTED_DIR / "bar.json").read_text())


@pytest.fixture
def synthetic_line_expected() -> dict:
    return json.loads((SYNTHETIC_EXPECTED_DIR / "line.json").read_text())


@pytest.fixture
def synthetic_hybrid_expected() -> dict:
    return json.loads((SYNTHETIC_EXPECTED_DIR / "hybrid.json").read_text())
