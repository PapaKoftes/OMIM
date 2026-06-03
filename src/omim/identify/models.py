"""Shared models for the identification layer (parts, assemblies, projects).

The identification layer is pure, read-only inference over a built MGG (plus its
feature annotations). Every identification carries a confidence in [0,1],
ranked alternatives, human-readable evidence, and a provenance dict — mirroring
the feature classifier's contract so the auto-labeler can treat all layers
uniformly.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Part-type taxonomy (furniture-panel domain). Kept here as the single source
# of truth so rules, tests, and the dataset schema agree.
# ---------------------------------------------------------------------------

PART_TYPES: tuple[str, ...] = (
    "SIDE_PANEL",
    "TOP_PANEL",
    "BOTTOM_PANEL",
    "SHELF",
    "DOOR",
    "DRAWER_FRONT",
    "DRAWER_SIDE",
    "DRAWER_BACK",
    "DRAWER_BOTTOM",
    "BACK_PANEL",
    "DIVIDER",
    "RAIL",
    "UNKNOWN_PART",
)


class PartIdentification(BaseModel):
    """Identification of a single panel as a furniture part type."""

    panel_id: str  # MGG graph_id (or panel node id within a nest)
    part_type: str  # one of PART_TYPES
    confidence: float = 0.0
    evidence: list[dict] = Field(default_factory=list)
    alternatives: list[dict] = Field(default_factory=list)  # [{part_type, confidence, reason}]
    provenance: dict | None = None

    # Useful derived attributes (so consumers needn't re-open the MGG).
    width_mm: float | None = None
    height_mm: float | None = None
    thickness_mm: float | None = None
    feature_summary: dict[str, int] = Field(default_factory=dict)  # feature_class -> count
