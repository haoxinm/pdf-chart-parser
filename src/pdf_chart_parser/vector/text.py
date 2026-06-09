"""Extract text spans with bounding boxes from a PDF page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import fitz


@dataclass
class TextSpan:
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    font_size: float = 0.0
    color: int = 0

    @property
    def x_center(self) -> float:
        return (self.bbox[0] + self.bbox[2]) / 2

    @property
    def y_center(self) -> float:
        return (self.bbox[1] + self.bbox[3]) / 2


def nearest_x_label(x: float, labels: list[str], x_domain: fitz.Rect) -> str:
    """Map an x coordinate to the nearest categorical label by position.

    Labels are assumed evenly distributed across the plot's x domain. Used by
    both bar and line extraction so they assign labels the same way.
    """
    if not labels:
        return ""
    plot_width = x_domain.x1 - x_domain.x0
    if plot_width <= 0:
        return labels[0]
    n = len(labels)
    rel = (x - x_domain.x0) / plot_width
    idx = int(round(rel * (n - 1)))
    idx = max(0, min(idx, n - 1))
    return labels[idx]


def collect_text_spans(page: fitz.Page) -> list[TextSpan]:
    """Return all non-empty text spans from the page with their bboxes."""
    spans: list[TextSpan] = []
    d: dict[str, Any] = page.get_text("dict")
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue
                bbox = span.get("bbox", (0, 0, 0, 0))
                spans.append(
                    TextSpan(
                        text=text,
                        bbox=tuple(bbox),
                        font_size=span.get("size", 0.0),
                        color=span.get("color", 0),
                    )
                )
    return spans
