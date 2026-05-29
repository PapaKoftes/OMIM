"""Parser data models."""

from pydantic import BaseModel, Field


class RawEntity(BaseModel):
    """A single geometric entity extracted from a DXF file."""

    entity_id: str  # ezdxf entity handle
    entity_type: str  # CIRCLE | LWPOLYLINE | LINE | ARC
    layer: str
    inferred_layer_type: str = "unknown"  # cut | drill | pocket | engrave | border | unknown

    # Coordinates (entity-type dependent)
    center: tuple[float, float] | None = None  # circles/arcs
    radius_mm: float | None = None  # circles/arcs
    points: list[tuple[float, float]] | None = None  # polylines/lines
    is_closed: bool = False

    # Bounding box (computed)
    bbox: tuple[float, float, float, float] | None = None  # xmin, ymin, xmax, ymax


class ParseWarning(BaseModel):
    """A non-fatal issue encountered during parsing."""

    warning_code: str
    message: str
    entity_id: str | None = None


class RawGeometry(BaseModel):
    """All geometry extracted from a single DXF file."""

    source_file: str
    source_file_hash: str  # SHA-256
    dxf_version: str
    units: str = "mm"
    units_normalized_from: str | None = None  # e.g., "inches" if converted

    entities: list[RawEntity] = Field(default_factory=list)
    warnings: list[ParseWarning] = Field(default_factory=list)

    panel_boundary_detected: bool = False
    panel_boundary_entity_id: str | None = None


class ParseError(BaseModel):
    """A fatal parsing error."""

    error_code: str  # DXF_CORRUPT | DXF_TOO_LARGE | DXF_VERSION_UNSUPPORTED
    message: str


class ParseResult(BaseModel):
    """Result of parsing a DXF file."""

    success: bool
    geometry: RawGeometry | None = None
    errors: list[ParseError] = Field(default_factory=list)
