"""Data models for multi-panel nesting comprehension.

A real shop DXF is frequently a *nest*: one stock sheet carrying many panels laid
out for cutting, rather than a single panel. OMIM must understand the whole nest —
which closed contours are panels (vs features cut into them), which sheet they sit
on, how features distribute across panels, and whether the layout is physically
sane (panels inside the sheet, not overlapping).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NestedPanel(BaseModel):
    """One panel within a nest: its boundary plus the features that fall inside it."""

    panel_id: str  # geometry node id of the panel boundary contour
    bounding_box: list[float]  # [xmin, ymin, xmax, ymax] (mm)
    area_mm2: float
    width_mm: float
    height_mm: float
    feature_node_ids: list[str] = Field(default_factory=list)
    feature_count: int = 0


class NestingLayout(BaseModel):
    """The full nesting analysis of a DXF that may contain multiple panels."""

    is_nested: bool  # True when more than one panel was detected
    panel_count: int

    # Sheet (stock) boundary, when an explicit sheet/stock layer was found.
    sheet_boundary_id: str | None = None
    sheet_bounding_box: list[float] | None = None
    sheet_area_mm2: float | None = None
    sheet_source: str = "none"  # "sheet_layer" | "convex_hull" | "none"

    panels: list[NestedPanel] = Field(default_factory=list)

    # Quality / sanity metrics.
    total_panel_area_mm2: float = 0.0
    utilization: float | None = None  # total panel area / sheet area, [0,1]
    overlapping_panel_pairs: list[list[str]] = Field(default_factory=list)
    panels_outside_sheet: list[str] = Field(default_factory=list)

    # Optional packing analysis (only when rectpack is installed).
    packing_available: bool = False
    packing_note: str = ""

    warnings: list[str] = Field(default_factory=list)
