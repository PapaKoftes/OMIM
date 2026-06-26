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
    # Holes near each panel edge (left/right/top/bottom) — the edge-joinery signal
    # the assembly solver uses to deduce how panels mate.
    edge_hole_counts: dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Assembly / project models
# ---------------------------------------------------------------------------


class PanelRef(BaseModel):
    """A panel's identity within an assembly (its part id + identified type)."""

    panel_id: str
    part_type: str = "UNKNOWN_PART"
    part_confidence: float = 0.0
    width_mm: float | None = None
    height_mm: float | None = None
    thickness_mm: float | None = None
    source_file: str = ""
    # Count of holes within a small band of each panel edge, keyed by edge
    # ("left"/"right"/"top"/"bottom"). Edge joinery (dowel/confirmat rows) on a
    # panel edge is what mates it to a neighbouring panel — the geometric signal
    # that lets the assembly solver DEDUCE structure instead of guessing.
    edge_hole_counts: dict[str, int] = Field(default_factory=dict)


class JoinHypothesis(BaseModel):
    """A hypothesised join between two panels in an assembly."""

    panel_a: str
    panel_b: str
    join_type: str  # e.g. "DOWEL", "CONFIRMAT", "EDGE_BUTT"
    confidence: float = 0.0
    reason: str = ""


class AssemblyIdentification(BaseModel):
    """A group of panels inferred to form one 3D construction."""

    assembly_id: str
    panels: list[PanelRef] = Field(default_factory=list)
    panel_count: int = 0
    confidence: float = 0.0
    assembly_type: str = "CARCASS"  # CARCASS | DRAWER | FRAME | UNKNOWN_ASSEMBLY
    joins: list[JoinHypothesis] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    provenance: dict | None = None


class ProjectStructure(BaseModel):
    """The full project tree: project -> assemblies -> panels -> (features)."""

    project_id: str
    name: str = ""
    assemblies: list[AssemblyIdentification] = Field(default_factory=list)
    assembly_count: int = 0
    panel_count: int = 0
    ungrouped_panels: list[PanelRef] = Field(default_factory=list)
    provenance: dict | None = None
