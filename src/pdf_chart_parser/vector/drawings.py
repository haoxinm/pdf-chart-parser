"""Parse page.get_drawings() into normalized rects and stroked paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import fitz


@dataclass
class RectItem:
    rect: fitz.Rect
    fill: tuple[float, ...] | None
    stroke: tuple[float, ...] | None
    width: float
    seqno: int


@dataclass
class StrokedPath:
    points: list[fitz.Point]
    stroke: tuple[float, ...] | None
    width: float
    dashed: bool
    close_path: bool
    seqno: int
    fill: tuple[float, ...] | None = None
    bbox: fitz.Rect = field(default_factory=fitz.Rect)

    def __post_init__(self) -> None:
        if self.points:
            xs = [p.x for p in self.points]
            ys = [p.y for p in self.points]
            self.bbox = fitz.Rect(min(xs), min(ys), max(xs), max(ys))


def collect_drawings(page: fitz.Page) -> dict[str, list]:
    """Return {'rects': [...RectItem], 'paths': [...StrokedPath]}."""
    rects: list[RectItem] = []
    paths: list[StrokedPath] = []

    for seqno, path in enumerate(page.get_drawings()):
        fill = _to_tuple(path.get("fill"))
        stroke = _to_tuple(path.get("color"))
        width = path.get("width") or 0.0
        dashed = bool(path.get("dashes"))
        close_path = bool(path.get("closePath"))
        items: list[Any] = path.get("items", [])

        pts: list[fitz.Point] = []
        has_rect = False

        for item in items:
            kind = item[0]
            if kind == "re":
                r = item[1]
                rects.append(RectItem(rect=r, fill=fill, stroke=stroke, width=width, seqno=seqno))
                has_rect = True
            elif kind == "l":
                pts += [fitz.Point(item[1]), fitz.Point(item[2])]
            elif kind == "c":
                # Bezier: take on-curve anchors (item[1] = start, item[4] = end)
                pts += [fitz.Point(item[1]), fitz.Point(item[4])]
            elif kind == "m":
                pts.append(fitz.Point(item[1]))

        if pts and not has_rect:
            # Deduplicate consecutive identical points
            deduped = [pts[0]]
            for p in pts[1:]:
                if abs(p.x - deduped[-1].x) > 0.01 or abs(p.y - deduped[-1].y) > 0.01:
                    deduped.append(p)
            paths.append(
                StrokedPath(
                    points=deduped,
                    stroke=stroke,
                    width=width,
                    dashed=dashed,
                    close_path=close_path,
                    seqno=seqno,
                    fill=fill,
                )
            )

    return {"rects": rects, "paths": paths}


def _to_tuple(color: Any) -> tuple[float, ...] | None:
    if color is None:
        return None
    return tuple(float(c) for c in color)
