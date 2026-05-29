"""Graph node and edge models."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class EdgeType(str, Enum):
    """Relationship types between graph nodes."""

    CONTAINS = "CONTAINS"  # panel → feature
    ADJACENT_TO = "ADJACENT_TO"  # feature ↔ feature (spatial proximity)
    SAME_GROUP = "SAME_GROUP"  # feature ↔ feature (logical grouping)
    SAME_ROW = "SAME_ROW"  # hole ↔ hole (collinear horizontal)
    SAME_COLUMN = "SAME_COLUMN"  # hole ↔ hole (collinear vertical)
    COMPOSES = "COMPOSES"  # geometry → feature
    PRODUCED_BY = "PRODUCED_BY"  # feature → operation
    VIOLATES = "VIOLATES"  # feature → constraint
    CONFLICTS_WITH = "CONFLICTS_WITH"  # feature ↔ feature (spatial conflict)


class GeometryNode(BaseModel):
    """Raw geometry extracted from DXF — immutable after creation."""

    node_id: str
    node_type: Literal["geometry"] = "geometry"

    geometry_type: str  # circle | polyline | arc | line
    layer: str
    inferred_layer_type: str  # cut | drill | pocket | engrave | border | unknown

    # Coordinates
    coordinates: list[Any]  # circle: [cx,cy,r]; polyline: [[x,y],...]; etc.
    is_closed: bool = False

    # Derived geometry (computed by Shapely)
    bbox: tuple[float, float, float, float] | None = None  # xmin, ymin, xmax, ymax
    area_mm2: float | None = None
    perimeter_mm: float | None = None
    centroid: tuple[float, float] | None = None

    # Circle-specific
    diameter_mm: float | None = None
    radius_mm: float | None = None

    # Panel boundary
    is_outer_boundary: bool = False

    # Source
    source_entity_id: str  # ezdxf handle
    source_file: str = ""
    source_file_hash: str = ""


class FeatureNode(BaseModel):
    """Inferred manufacturing feature — attached to GeometryNodes."""

    node_id: str
    node_type: Literal["feature"] = "feature"

    feature_class: str  # from ontology: SHELF_PIN_HOLE, HINGE_CUP_HOLE, etc.
    confidence: float = 0.0  # [0.0, 1.0]
    inference_method: str = "unclassified"  # deterministic | heuristic | ml_gnn

    # Physical parameters
    diameter_mm: float | None = None
    depth_mm: float | None = None
    position_mm: tuple[float, float] | None = None

    # Alternative hypotheses
    hypotheses: list[dict] = Field(default_factory=list)

    # Links
    geometry_node_ids: list[str] = Field(default_factory=list)
    group_id: str | None = None


class ConstraintNode(BaseModel):
    """A manufacturing constraint violation."""

    node_id: str
    node_type: Literal["constraint"] = "constraint"

    constraint_type: str
    rule_id: str
    severity: str  # ERROR | WARNING
    message: str

    measured_value: float | None = None
    threshold_value: float | None = None

    applies_to_node_ids: list[str] = Field(default_factory=list)


class GraphMetadata(BaseModel):
    """Metadata for an MGG instance."""

    graph_id: str
    spec_version: str = "v0.1.0"
    ontology_version: str = "v0.1.0"

    source_file: str = ""
    source_file_hash: str = ""

    panel_bbox: tuple[float, float, float, float] | None = None
    panel_width_mm: float | None = None
    panel_height_mm: float | None = None

    geometry_node_count: int = 0
    feature_node_count: int = 0
    constraint_node_count: int = 0
    edge_count: int = 0

    creation_timestamp: str = ""
