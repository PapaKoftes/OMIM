"""Graph node, edge, and metadata models — exact spec from 02_SCHEMA/MGG_Schema.md."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from omim.provenance.models import ProvenanceRecord

# ---------------------------------------------------------------------------
# Edge types (from MGG Schema relationship table)
# ---------------------------------------------------------------------------


class EdgeType(str, Enum):  # noqa: UP042 — StrEnum changes str()/format output
    """Relationship types between graph nodes."""

    CONTAINS = "CONTAINS"  # panel contour → geometry (Shapely containment)
    COMPOSES = "COMPOSES"  # geometry → feature
    PRODUCES = "PRODUCES"  # operation → feature
    DEPENDS_ON = "DEPENDS_ON"  # operation → operation (ordering)
    CONFLICTS_WITH = "CONFLICTS_WITH"  # feature ↔ feature (spatial conflict)
    ADJACENT_TO = "ADJACENT_TO"  # geometry ↔ geometry (proximity threshold)
    REQUIRES_TOOLING = "REQUIRES_TOOLING"  # feature → operation
    SAME_GROUP = "SAME_GROUP"  # feature ↔ feature (logical grouping)
    SAME_ROW = "SAME_ROW"  # feature ↔ feature (collinear horizontal)
    SAME_COLUMN = "SAME_COLUMN"  # feature ↔ feature (collinear vertical)
    APPLIES_TO = "APPLIES_TO"  # constraint → geometry
    ENABLES = "ENABLES"  # feature → operation
    PRODUCED_BY = "PRODUCED_BY"  # feature → operation (reverse of PRODUCES)


# ---------------------------------------------------------------------------
# Supporting types
# ---------------------------------------------------------------------------


class FeatureHypothesis(BaseModel):
    """A candidate feature classification."""

    feature_class: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------


class GeometryNode(BaseModel):
    """Raw geometry extracted from DXF — immutable after creation.

    Spec: 02_SCHEMA/MGG_Schema.md -> GeometryNode
    """

    node_id: str
    node_type: Literal["geometry"] = "geometry"

    geometry_type: str  # "circle" | "polyline" | "arc" | "line" | "contour" | "spline"
    layer: str
    inferred_layer_type: str  # "cut" | "drill" | "pocket" | "engrave" | "border" | "unknown"

    # Coordinates (type-dependent)
    coordinates: list[Any]  # circle: [cx,cy,r]; polyline: [[x,y],...]; arc: [cx,cy,r,start,end]
    is_closed: bool = False

    # Derived geometry (computed by Shapely)
    bounding_box: list[float] | None = None  # [xmin, ymin, xmax, ymax]
    area_mm2: float | None = None
    perimeter_mm: float | None = None
    centroid: list[float] | None = None  # [cx, cy]

    # Circle-specific
    diameter_mm: float | None = None
    radius_mm: float | None = None

    # Depth / 2.5D. depth_mm is None for pure-2D features with no recoverable
    # depth. depth_source records provenance: "z_elevation" (measured from 2.5D
    # geometry), "layer_name" (inferred from a layer convention), or None.
    depth_mm: float | None = None
    depth_source: str | None = None
    elevation_z: float | None = None

    # True when a curved entity (SPLINE/ELLIPSE/bulged polyline) was flattened to
    # a many-vertex polyline at parse time. Consumers that analyse vertices (e.g.
    # corner-angle checks) skip these to avoid chord-induced false positives.
    is_approximated: bool = False

    # Panel boundary
    is_outer_boundary: bool | None = None
    contains_node_ids: list[str] = Field(default_factory=list)

    # Source
    source_entity_id: str  # ezdxf handle
    source_file: str = ""
    source_file_hash: str = ""  # SHA256
    creation_method: Literal["parsed"] = "parsed"

    # Provenance — REQUIRED per spec
    provenance: ProvenanceRecord | None = None


class FeatureNode(BaseModel):
    """Inferred manufacturing feature — attached to GeometryNodes.

    Spec: 02_SCHEMA/MGG_Schema.md -> FeatureNode
    """

    node_id: str
    node_type: Literal["feature"] = "feature"

    feature_class: str  # From ontology: SHELF_PIN_HOLE, HINGE_CUP_HOLE, CONFIRMAT_HOLE, etc.
    feature_label: str = ""  # Human-readable label
    feature_category: str = ""  # "HOLE_FEATURES" | "MILLED_FEATURES" | "PROFILE_FEATURES"
    confidence: float = 0.0  # [0.0, 1.0]
    inference_method: str = "unclassified"  # deterministic | heuristic | ml_gnn

    # Physical parameters
    diameter_mm: float | None = None
    depth_mm: float | None = None
    width_mm: float | None = None
    length_mm: float | None = None
    position_mm: list[float] | None = None  # [x, y]

    # Alternative hypotheses
    hypotheses: list[FeatureHypothesis] = Field(default_factory=list)

    # Evidence
    evidence: list[dict] = Field(default_factory=list)

    # Links
    geometry_node_ids: list[str] = Field(default_factory=list)
    group_id: str | None = None

    # Provenance — REQUIRED per spec
    provenance: ProvenanceRecord | None = None


class OperationNode(BaseModel):
    """Inferred CNC operation — linked to FeatureNodes.

    Spec: 02_SCHEMA/MGG_Schema.md -> OperationNode
    """

    node_id: str
    node_type: Literal["operation"] = "operation"

    operation_type: str  # "DRILLING" | "CNC_ROUTING" | "PROFILE_CUTTING" | "NESTING"
    confidence: float = 1.0
    tool_diameter_mm: float | None = None
    depth_mm: float | None = None
    tool_type: str | None = None
    feature_node_ids: list[str] = Field(default_factory=list)

    # Provenance
    provenance: ProvenanceRecord | None = None


class ConstraintNode(BaseModel):
    """A manufacturing constraint (violation or check).

    Spec: 02_SCHEMA/MGG_Schema.md -> ConstraintNode
    """

    node_id: str
    node_type: Literal["constraint"] = "constraint"

    constraint_type: str  # rule_id e.g. "MFG-001"
    constraint_value: float = 0.0
    constraint_unit: str = "mm"  # "mm" | "ratio" | "degrees"
    is_violated: bool = False
    violation_severity: str | None = None  # "ERROR" | "WARNING"
    applies_to_node_ids: list[str] = Field(default_factory=list)
    rule_id: str = ""
    message: str = ""

    # Provenance
    provenance: ProvenanceRecord | None = None


class RelationshipEdge(BaseModel):
    """A typed, provenance-tracked edge in the MGG.

    Spec: 02_SCHEMA/MGG_Schema.md -> RelationshipEdge
    """

    edge_id: str
    source_id: str
    target_id: str
    relationship_type: str  # EdgeType value
    confidence: float = 1.0
    weight: float | None = None
    metadata: dict = Field(default_factory=dict)

    # Provenance
    provenance: ProvenanceRecord | None = None


# ---------------------------------------------------------------------------
# Graph metadata
# ---------------------------------------------------------------------------


class GraphMetadata(BaseModel):
    """Metadata for an MGG instance."""

    graph_id: str
    spec_version: str = "v0.1.0"
    ontology_version: str = "v0.1.0"

    source_file: str = ""
    source_file_hash: str = ""

    panel_bbox: list[float] | None = None  # [xmin, ymin, xmax, ymax]
    panel_width_mm: float | None = None
    panel_height_mm: float | None = None

    geometry_node_count: int = 0
    feature_node_count: int = 0
    operation_node_count: int = 0
    constraint_node_count: int = 0
    edge_count: int = 0

    creation_timestamp: str = ""
    parser_version: str = "omim-v0.1.0"
