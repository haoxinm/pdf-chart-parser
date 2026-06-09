"""Pydantic output models for the chart extraction result."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AxisCalibrationPoint(BaseModel):
    value: float
    y: float


class AxisInfo(BaseModel):
    kind: Literal["categorical", "numeric"] = "categorical"
    labels: list[str] = Field(default_factory=list)


class AxisCalibration(BaseModel):
    unit: str = "auto"
    points: list[AxisCalibrationPoint] = Field(default_factory=list)
    scale_per_point: float = 0.0
    scale_per_pixel: float = 0.0
    r_squared: float = 0.0


class Axes(BaseModel):
    x: AxisInfo = Field(default_factory=AxisInfo)
    y_primary: AxisCalibration = Field(default_factory=AxisCalibration)
    y_secondary: AxisCalibration | None = None


class DataPoint(BaseModel):
    x_label: str = ""
    x: float = 0.0
    value: float
    y: float = 0.0
    baseline_y: float | None = None
    confidence: float = 1.0


class Series(BaseModel):
    id: str
    type: Literal["bar", "line"]
    label: str = ""
    unit: str = "auto"
    axis: Literal["y_primary", "y_secondary"] = "y_primary"
    color: list[float] = Field(default_factory=list)
    confidence: float = 1.0
    points: list[DataPoint] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    chart_found: bool = False
    method: Literal["vector", "raster_cv", "failed"] = "failed"
    chart_type: Literal["bar", "line", "hybrid"] | None = None
    page: int = 0
    axes: Axes = Field(default_factory=Axes)
    series: list[Series] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    page_markdown: str = ""
