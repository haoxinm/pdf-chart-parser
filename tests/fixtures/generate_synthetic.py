"""Generate synthetic born-digital PDFs for testing.

Run: uv run python tests/fixtures/generate_synthetic.py
Produces: tests/fixtures/pdfs/*.pdf and tests/fixtures/expected/*.json
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent
PDFS_DIR = FIXTURES_DIR / "pdfs"
EXPECTED_DIR = FIXTURES_DIR / "expected"

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# Known values for reproducibility
BAR_VALUES = [120.0, 135.5, 98.0, 145.2, 160.8, 175.0, 188.5, 172.3, 150.0, 130.7, 115.0, 140.0]
LINE_VALUES = [55.1, 62.3, 78.9, 85.0, 90.2, 95.5, 88.7, 82.1, 75.3, 68.0, 60.4, 58.8]
HYBRID_BAR_VALUES = [
    210.0,
    225.0,
    190.0,
    240.0,
    260.0,
    280.0,
    295.0,
    275.0,
    250.0,
    230.0,
    205.0,
    220.0,
]
HYBRID_LINE_VALUES = [
    520.0,
    580.0,
    650.0,
    700.0,
    720.0,
    750.0,
    730.0,
    690.0,
    640.0,
    600.0,
    555.0,
    510.0,
]


def _make_bar_pdf(path: Path) -> None:
    """Create a simple bar chart PDF with known dollar values."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    chart_left = 80.0
    chart_right = 540.0
    chart_top = 150.0
    chart_bottom = 550.0
    chart_w = chart_right - chart_left
    chart_h = chart_bottom - chart_top

    max_val = max(BAR_VALUES)
    n = len(BAR_VALUES)
    bar_width = chart_w / (n * 1.5)
    bar_spacing = chart_w / n

    # Y-axis tick marks and labels (left side)
    y_ticks = [0, 50, 100, 150, 200]
    for tick in y_ticks:
        y_px = chart_bottom - (tick / max_val) * chart_h
        # Tick mark
        page.draw_line(fitz.Point(chart_left - 5, y_px), fitz.Point(chart_left, y_px))
        # Label
        page.insert_text(
            fitz.Point(chart_left - 40, y_px + 4),
            f"${tick}",
            fontsize=9,
            color=(0, 0, 0),
        )
        # Gridline
        page.draw_line(
            fitz.Point(chart_left, y_px),
            fitz.Point(chart_right, y_px),
            color=(0.8, 0.8, 0.8),
            width=0.5,
        )

    # Axis lines
    page.draw_line(
        fitz.Point(chart_left, chart_top), fitz.Point(chart_left, chart_bottom), width=1.5
    )
    page.draw_line(
        fitz.Point(chart_left, chart_bottom), fitz.Point(chart_right, chart_bottom), width=1.5
    )

    # Bars
    bar_fill = (0.22, 0.47, 0.72)
    for i, val in enumerate(BAR_VALUES):
        bar_top = chart_bottom - (val / max_val) * chart_h
        bar_x0 = chart_left + i * bar_spacing + (bar_spacing - bar_width) / 2
        bar_x1 = bar_x0 + bar_width
        page.draw_rect(
            fitz.Rect(bar_x0, bar_top, bar_x1, chart_bottom),
            fill=bar_fill,
            color=None,
        )
        # X label
        page.insert_text(
            fitz.Point(bar_x0 + bar_width / 2 - 8, chart_bottom + 12),
            MONTHS[i],
            fontsize=8,
            color=(0, 0, 0),
        )

    # Title
    page.insert_text(fitz.Point(200, 130), "Monthly Utility Charges ($)", fontsize=12)

    doc.save(str(path))
    doc.close()


def _make_line_pdf(path: Path) -> None:
    """Create a line chart PDF with known kWh usage values."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    chart_left = 80.0
    chart_right = 540.0
    chart_top = 150.0
    chart_bottom = 550.0
    chart_w = chart_right - chart_left
    chart_h = chart_bottom - chart_top

    max_val = 120.0
    n = len(LINE_VALUES)
    x_spacing = chart_w / (n - 1)

    # Y-axis
    y_ticks = [0, 25, 50, 75, 100, 120]
    for tick in y_ticks:
        y_px = chart_bottom - (tick / max_val) * chart_h
        page.draw_line(fitz.Point(chart_left - 5, y_px), fitz.Point(chart_left, y_px))
        page.insert_text(
            fitz.Point(chart_left - 40, y_px + 4),
            f"{tick} kWh",
            fontsize=9,
            color=(0, 0, 0),
        )
        page.draw_line(
            fitz.Point(chart_left, y_px),
            fitz.Point(chart_right, y_px),
            color=(0.8, 0.8, 0.8),
            width=0.5,
        )

    # Axes
    page.draw_line(
        fitz.Point(chart_left, chart_top), fitz.Point(chart_left, chart_bottom), width=1.5
    )
    page.draw_line(
        fitz.Point(chart_left, chart_bottom), fitz.Point(chart_right, chart_bottom), width=1.5
    )

    # Line series
    line_color = (0.85, 0.33, 0.10)
    pts = []
    for i, val in enumerate(LINE_VALUES):
        x = chart_left + i * x_spacing
        y = chart_bottom - (val / max_val) * chart_h
        pts.append(fitz.Point(x, y))
        page.insert_text(
            fitz.Point(x - 8, chart_bottom + 12),
            MONTHS[i],
            fontsize=8,
            color=(0, 0, 0),
        )

    for i in range(len(pts) - 1):
        page.draw_line(pts[i], pts[i + 1], color=line_color, width=2.0)

    # Marker dots
    for pt in pts:
        page.draw_circle(pt, 3, color=line_color, fill=line_color)

    page.insert_text(fitz.Point(200, 130), "Monthly Energy Usage (kWh)", fontsize=12)
    doc.save(str(path))
    doc.close()


def _make_hybrid_pdf(path: Path) -> None:
    """Create a hybrid bar+line chart with dual y-axis."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    chart_left = 80.0
    chart_right = 540.0
    chart_top = 150.0
    chart_bottom = 550.0
    chart_w = chart_right - chart_left
    chart_h = chart_bottom - chart_top

    max_bar = 320.0
    max_line = 800.0
    n = len(HYBRID_BAR_VALUES)
    bar_width = chart_w / (n * 1.5)
    bar_spacing = chart_w / n

    # Left Y-axis (dollars)
    for tick in [0, 100, 200, 300]:
        y_px = chart_bottom - (tick / max_bar) * chart_h
        page.draw_line(fitz.Point(chart_left - 5, y_px), fitz.Point(chart_left, y_px))
        page.insert_text(
            fitz.Point(chart_left - 45, y_px + 4),
            f"${tick}",
            fontsize=9,
            color=(0, 0, 0),
        )
        page.draw_line(
            fitz.Point(chart_left, y_px),
            fitz.Point(chart_right, y_px),
            color=(0.85, 0.85, 0.85),
            width=0.5,
        )

    # Right Y-axis (kWh)
    for tick in [0, 200, 400, 600, 800]:
        y_px = chart_bottom - (tick / max_line) * chart_h
        page.draw_line(fitz.Point(chart_right, y_px), fitz.Point(chart_right + 5, y_px))
        page.insert_text(
            fitz.Point(chart_right + 8, y_px + 4),
            f"{tick} kWh",
            fontsize=9,
            color=(0, 0, 0),
        )

    # Axis lines
    page.draw_line(
        fitz.Point(chart_left, chart_top), fitz.Point(chart_left, chart_bottom), width=1.5
    )
    page.draw_line(
        fitz.Point(chart_left, chart_bottom), fitz.Point(chart_right, chart_bottom), width=1.5
    )
    page.draw_line(
        fitz.Point(chart_right, chart_top), fitz.Point(chart_right, chart_bottom), width=1.5
    )

    # Bars (charges)
    bar_fill = (0.22, 0.47, 0.72)
    for i, val in enumerate(HYBRID_BAR_VALUES):
        bar_top = chart_bottom - (val / max_bar) * chart_h
        bar_x0 = chart_left + i * bar_spacing + (bar_spacing - bar_width) / 2
        bar_x1 = bar_x0 + bar_width
        page.draw_rect(
            fitz.Rect(bar_x0, bar_top, bar_x1, chart_bottom),
            fill=bar_fill,
            color=None,
        )
        page.insert_text(
            fitz.Point(bar_x0 + bar_width / 2 - 8, chart_bottom + 12),
            MONTHS[i],
            fontsize=8,
            color=(0, 0, 0),
        )

    # Line series (kWh on secondary axis)
    line_color = (0.84, 0.19, 0.15)
    pts = []
    x_spacing = chart_w / (n - 1)
    for i, val in enumerate(HYBRID_LINE_VALUES):
        x = chart_left + i * x_spacing
        y = chart_bottom - (val / max_line) * chart_h
        pts.append(fitz.Point(x, y))

    for i in range(len(pts) - 1):
        page.draw_line(pts[i], pts[i + 1], color=line_color, width=2.0)

    for pt in pts:
        page.draw_circle(pt, 3, color=line_color, fill=line_color)

    page.insert_text(fitz.Point(180, 130), "Monthly Charges ($) and Usage (kWh)", fontsize=12)
    doc.save(str(path))
    doc.close()


def _make_raster_pdf(path: Path, source_pdf: Path) -> None:
    """Rasterize the bar chart PDF to create a scanned-image PDF."""
    import fitz

    src_doc = fitz.open(str(source_pdf))
    src_page = src_doc[0]
    w = src_page.rect.width
    h = src_page.rect.height
    pix = src_page.get_pixmap(dpi=150)
    src_doc.close()

    doc = fitz.open()
    page = doc.new_page(width=w, height=h)
    page.insert_image(page.rect, pixmap=pix)
    doc.save(str(path))
    doc.close()


def generate_expected(
    name: str, chart_type: str, series_data: list[dict], tolerance_pct: float = 2.0
) -> None:
    expected = {
        "_note": "Values are synthetically generated with known ground truth. Human verification recommended before use with real bills.",
        "chart_type": chart_type,
        "tolerance_pct": tolerance_pct,
        "series": series_data,
    }
    out_path = EXPECTED_DIR / f"{name}.json"
    out_path.write_text(json.dumps(expected, indent=2))
    print(f"  Written: {out_path}")


def main() -> None:
    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating synthetic bar chart PDF...")
    _make_bar_pdf(PDFS_DIR / "synthetic_bar.pdf")
    generate_expected(
        "synthetic_bar",
        "bar",
        [
            {
                "type": "bar",
                "unit": "dollars",
                "points": [{"x_label": m, "value": v} for m, v in zip(MONTHS, BAR_VALUES)],
            }
        ],
    )

    print("Generating synthetic line chart PDF...")
    _make_line_pdf(PDFS_DIR / "synthetic_line.pdf")
    generate_expected(
        "synthetic_line",
        "line",
        [
            {
                "type": "line",
                "unit": "kwh",
                "points": [{"x_label": m, "value": v} for m, v in zip(MONTHS, LINE_VALUES)],
            }
        ],
    )

    print("Generating synthetic hybrid chart PDF...")
    _make_hybrid_pdf(PDFS_DIR / "synthetic_hybrid.pdf")
    generate_expected(
        "synthetic_hybrid",
        "hybrid",
        [
            {
                "type": "bar",
                "unit": "dollars",
                "points": [{"x_label": m, "value": v} for m, v in zip(MONTHS, HYBRID_BAR_VALUES)],
            },
            {
                "type": "line",
                "unit": "kwh",
                "points": [{"x_label": m, "value": v} for m, v in zip(MONTHS, HYBRID_LINE_VALUES)],
            },
        ],
    )

    print("Generating rasterized (scanned) bar chart PDF...")
    _make_raster_pdf(PDFS_DIR / "synthetic_bar_raster.pdf", PDFS_DIR / "synthetic_bar.pdf")
    # No expected for raster — pixel-space values are not calibrated without OCR
    print("Done. Synthetic fixtures written to tests/fixtures/pdfs/ and tests/fixtures/expected/")


if __name__ == "__main__":
    main()
