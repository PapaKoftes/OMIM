"""DXF Parser implementation using ezdxf."""

import hashlib
import logging
import math
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import ezdxf
from shapely.geometry import LinearRing, LineString, Point, Polygon

from omim.parser.models import (
    PanelBoundary,
    ParseError,
    ParseResult,
    ParseWarning,
    RawEntity,
    RawGeometry,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 50

# Layer name prefix → inferred operation type (case-insensitive prefix matching)
LAYER_CONVENTIONS = {
    "cut": ["CUT", "CUT_", "PROFILE", "OUTLINE", "OUTER", "CONTOUR"],
    "drill": ["DRILL", "HOLE", "BORE", "PUNCH"],
    "pocket": ["POCKET", "GROOVE", "SLOT", "DADO", "RABBET"],
    "border": ["BORDER", "SHEET", "STOCK", "MATERIAL"],
    "engrave": ["ENGRAVE", "ETCH", "SCORE"],
}

# Geometry entity types that indicate real geometry (not annotation-only)
GEOMETRY_ENTITY_TYPES = {"LINE", "CIRCLE", "ARC", "LWPOLYLINE", "POLYLINE", "SPLINE"}


def _infer_layer_type(layer_name: str) -> str:
    """Infer operation type from layer name (case-insensitive prefix match)."""
    upper = layer_name.upper().strip()
    for layer_type, prefixes in LAYER_CONVENTIONS.items():
        for prefix in prefixes:
            if upper.startswith(prefix):
                return layer_type
    return "unknown"


def _file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _scale(value: float, from_units: str | None) -> float:
    """Scale a value from original units to mm."""
    if from_units == "inches":
        return value * 25.4
    return value


def _scale_pt(x: float, y: float, from_units: str | None) -> tuple[float, float]:
    """Scale a 2D point from original units to mm."""
    if from_units == "inches":
        return x * 25.4, y * 25.4
    return x, y


def _compute_shapely_circle(cx: float, cy: float, r: float) -> dict:
    """Compute Shapely-derived properties for a circle."""
    shape = Point(cx, cy).buffer(r, quad_segs=64)
    return {
        "bounding_box": [cx - r, cy - r, cx + r, cy + r],
        "centroid": [cx, cy],
        "area_mm2": round(shape.area, 4),
        "perimeter_mm": round(shape.length, 4),
        "diameter_mm": round(r * 2, 4),
        "radius_mm": round(r, 4),
    }


def _compute_shapely_polyline(pts: list[list[float]], is_closed: bool) -> dict:
    """Compute Shapely-derived properties for a polyline/polygon."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    result: dict = {
        "bounding_box": [min(xs), min(ys), max(xs), max(ys)],
    }

    if is_closed and len(pts) >= 3:
        ring = LinearRing(pts)
        shape = Polygon(ring)
        c = shape.centroid
        result["centroid"] = [round(c.x, 4), round(c.y, 4)]
        result["area_mm2"] = round(shape.area, 4)
        result["perimeter_mm"] = round(ring.length, 4)
    elif len(pts) >= 2:
        line = LineString(pts)
        c = line.centroid
        result["centroid"] = [round(c.x, 4), round(c.y, 4)]
        result["perimeter_mm"] = round(line.length, 4)

    return result


def _compute_shapely_arc(cx: float, cy: float, r: float,
                         start_deg: float, end_deg: float) -> dict:
    """Compute Shapely-derived properties for an arc."""
    # Generate arc points for length calculation
    if end_deg < start_deg:
        end_deg += 360.0
    sweep = end_deg - start_deg
    n_pts = max(int(sweep / 5), 2)
    pts = []
    for i in range(n_pts + 1):
        angle = math.radians(start_deg + sweep * i / n_pts)
        pts.append([cx + r * math.cos(angle), cy + r * math.sin(angle)])

    line = LineString(pts)
    c = line.centroid
    return {
        "bounding_box": [cx - r, cy - r, cx + r, cy + r],
        "centroid": [round(c.x, 4), round(c.y, 4)],
        "perimeter_mm": round(line.length, 4),
        "radius_mm": round(r, 4),
        "diameter_mm": round(r * 2, 4),
    }


def _compute_shapely_line(pts: list[list[float]]) -> dict:
    """Compute Shapely-derived properties for a line segment."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    line = LineString(pts)
    c = line.centroid
    return {
        "bounding_box": [min(xs), min(ys), max(xs), max(ys)],
        "centroid": [round(c.x, 4), round(c.y, 4)],
        "perimeter_mm": round(line.length, 4),
    }


class DXFParser:
    """Parse a DXF file into RawGeometry."""

    def parse(self, filepath: str | Path) -> ParseResult:
        filepath = Path(filepath)

        # A-001: File not found
        if not filepath.exists():
            return ParseResult(
                success=False,
                errors=[ParseError(
                    error_code="DXF_NOT_FOUND",
                    message=str(filepath),
                    recoverable=False,
                )],
            )

        # A-004: File too large
        size_mb = filepath.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            return ParseResult(
                success=False,
                errors=[ParseError(
                    error_code="DXF_TOO_LARGE",
                    message=f"{size_mb:.1f}MB exceeds {MAX_FILE_SIZE_MB}MB limit",
                    recoverable=False,
                )],
            )

        # Parse with ezdxf
        try:
            doc = ezdxf.readfile(str(filepath))
        except ezdxf.DXFStructureError as e:
            return ParseResult(
                success=False,
                errors=[ParseError(
                    error_code="DXF_CORRUPT",
                    message=str(e),
                    recoverable=False,
                )],
            )
        except Exception as e:
            return ParseResult(
                success=False,
                errors=[ParseError(
                    error_code="DXF_CORRUPT",
                    message=str(e),
                    recoverable=False,
                )],
            )

        file_hash = _file_hash(filepath)
        dxf_version = doc.dxfversion

        # A-003: DXF version check — versions below AC1015 (AutoCAD 2000) are unsupported
        if dxf_version < "AC1015":
            return ParseResult(
                success=False,
                errors=[ParseError(
                    error_code="DXF_VERSION_UNSUPPORTED",
                    message=f"DXF version {dxf_version} is below AC1015 (AutoCAD 2000 minimum)",
                    recoverable=False,
                )],
            )

        # Check units
        warnings: list[ParseWarning] = []
        units_original = "mm"
        units_normalized_from: str | None = None
        insunits = doc.header.get("$INSUNITS", 0)
        if insunits == 1:  # inches
            units_original = "inches"
            units_normalized_from = "inches"
            warnings.append(
                ParseWarning(
                    warning_code="units_converted",
                    message="Inches -> mm conversion applied",
                )
            )

        # Extract entities from modelspace
        msp = doc.modelspace()
        entities: list[RawEntity] = []
        type_counter: Counter = Counter()

        # Track largest closed contour for panel boundary detection
        largest_closed_entity: RawEntity | None = None
        largest_closed_area: float = 0.0

        for entity in msp:
            etype = entity.dxftype()
            handle = entity.dxf.handle
            layer = entity.dxf.layer if hasattr(entity.dxf, "layer") else "0"
            layer_type = _infer_layer_type(layer)

            if etype == "CIRCLE":
                cx, cy, _ = entity.dxf.center
                r = entity.dxf.radius
                cx, cy = _scale_pt(cx, cy, units_normalized_from)
                r = _scale(r, units_normalized_from)
                if r <= 0:
                    warnings.append(
                        ParseWarning(
                            warning_code="degenerate_circle_skipped",
                            message=f"Circle radius={r}",
                            entity_id=handle,
                        )
                    )
                    continue

                coords = [cx, cy, r]
                shapely_props = _compute_shapely_circle(cx, cy, r)
                eid = str(uuid.uuid4())
                raw_ent = RawEntity(
                    entity_id=eid,
                    ezdxf_handle=handle,
                    entity_type="CIRCLE",
                    layer=layer,
                    inferred_layer_type=layer_type,
                    coordinates=coords,
                    is_closed=True,
                    **shapely_props,
                )
                entities.append(raw_ent)
                type_counter["CIRCLE"] += 1

            elif etype == "LWPOLYLINE":
                pts = [[p[0], p[1]] for p in entity.get_points(format="xy")]
                if units_normalized_from == "inches":
                    pts = [[x * 25.4, y * 25.4] for x, y in pts]
                is_closed = entity.closed
                if len(pts) < 2:
                    warnings.append(
                        ParseWarning(
                            warning_code="degenerate_polyline_skipped",
                            message=f"Polyline with {len(pts)} points",
                            entity_id=handle,
                        )
                    )
                    continue

                shapely_props = _compute_shapely_polyline(pts, is_closed)
                eid = str(uuid.uuid4())
                raw_ent = RawEntity(
                    entity_id=eid,
                    ezdxf_handle=handle,
                    entity_type="LWPOLYLINE",
                    layer=layer,
                    inferred_layer_type=layer_type,
                    coordinates=pts,
                    is_closed=is_closed,
                    **shapely_props,
                )
                entities.append(raw_ent)
                type_counter["LWPOLYLINE"] += 1

                # Track largest closed contour for panel boundary detection
                if is_closed and len(pts) >= 3:
                    area = shapely_props.get("area_mm2", 0.0) or 0.0
                    if area > largest_closed_area:
                        largest_closed_area = area
                        largest_closed_entity = raw_ent

            elif etype == "POLYLINE":
                # Legacy 2D polylines
                try:
                    pts = [[v.dxf.location.x, v.dxf.location.y] for v in entity.vertices]
                    if units_normalized_from == "inches":
                        pts = [[x * 25.4, y * 25.4] for x, y in pts]
                    is_closed = entity.is_closed
                    if len(pts) < 2:
                        warnings.append(
                            ParseWarning(
                                warning_code="degenerate_polyline_skipped",
                                message=f"Polyline with {len(pts)} points",
                                entity_id=handle,
                            )
                        )
                        continue

                    shapely_props = _compute_shapely_polyline(pts, is_closed)
                    eid = str(uuid.uuid4())
                    raw_ent = RawEntity(
                        entity_id=eid,
                        ezdxf_handle=handle,
                        entity_type="POLYLINE",
                        layer=layer,
                        inferred_layer_type=layer_type,
                        coordinates=pts,
                        is_closed=is_closed,
                        **shapely_props,
                    )
                    entities.append(raw_ent)
                    type_counter["POLYLINE"] += 1

                    # Track largest closed contour for panel boundary detection
                    if is_closed and len(pts) >= 3:
                        area = shapely_props.get("area_mm2", 0.0) or 0.0
                        if area > largest_closed_area:
                            largest_closed_area = area
                            largest_closed_entity = raw_ent
                except Exception as e:
                    warnings.append(
                        ParseWarning(
                            warning_code="polyline_read_error",
                            message=f"Failed to read POLYLINE vertices: {e}",
                            entity_id=handle,
                        )
                    )

            elif etype == "LINE":
                sx, sy, _ = entity.dxf.start
                ex, ey, _ = entity.dxf.end
                sx, sy = _scale_pt(sx, sy, units_normalized_from)
                ex, ey = _scale_pt(ex, ey, units_normalized_from)
                pts = [[sx, sy], [ex, ey]]
                shapely_props = _compute_shapely_line(pts)
                eid = str(uuid.uuid4())
                raw_ent = RawEntity(
                    entity_id=eid,
                    ezdxf_handle=handle,
                    entity_type="LINE",
                    layer=layer,
                    inferred_layer_type=layer_type,
                    coordinates=pts,
                    is_closed=False,
                    **shapely_props,
                )
                entities.append(raw_ent)
                type_counter["LINE"] += 1

            elif etype == "ARC":
                cx, cy, _ = entity.dxf.center
                r = entity.dxf.radius
                cx, cy = _scale_pt(cx, cy, units_normalized_from)
                r = _scale(r, units_normalized_from)
                start_angle = entity.dxf.start_angle
                end_angle = entity.dxf.end_angle
                coords = [cx, cy, r, start_angle, end_angle]
                shapely_props = _compute_shapely_arc(cx, cy, r, start_angle, end_angle)
                eid = str(uuid.uuid4())
                raw_ent = RawEntity(
                    entity_id=eid,
                    ezdxf_handle=handle,
                    entity_type="ARC",
                    layer=layer,
                    inferred_layer_type=layer_type,
                    coordinates=coords,
                    is_closed=False,
                    **shapely_props,
                )
                entities.append(raw_ent)
                type_counter["ARC"] += 1

            elif etype == "SPLINE":
                # Approximate SPLINE as polyline with 50 segments
                try:
                    # Use ezdxf's flattening to approximate the spline
                    pts = [[p.x, p.y] for p in entity.flattening(0.1)]
                    if units_normalized_from == "inches":
                        pts = [[x * 25.4, y * 25.4] for x, y in pts]

                    if len(pts) < 2:
                        # Fallback: generate from control points
                        ctrl_pts = entity.control_points
                        if len(ctrl_pts) >= 2:
                            pts = [[p.x, p.y] for p in ctrl_pts]
                            if units_normalized_from == "inches":
                                pts = [[x * 25.4, y * 25.4] for x, y in pts]

                    if len(pts) < 2:
                        warnings.append(
                            ParseWarning(
                                warning_code="degenerate_spline_skipped",
                                message="Spline with insufficient points",
                                entity_id=handle,
                            )
                        )
                        continue

                    is_closed = entity.closed
                    shapely_props = _compute_shapely_polyline(pts, is_closed)
                    eid = str(uuid.uuid4())
                    raw_ent = RawEntity(
                        entity_id=eid,
                        ezdxf_handle=handle,
                        entity_type="SPLINE",
                        layer=layer,
                        inferred_layer_type=layer_type,
                        coordinates=pts,
                        is_closed=is_closed,
                        is_approximated=True,
                        **shapely_props,
                    )
                    entities.append(raw_ent)
                    type_counter["SPLINE"] += 1
                except Exception as e:
                    warnings.append(
                        ParseWarning(
                            warning_code="spline_approximation_error",
                            message=f"Failed to approximate SPLINE: {e}",
                            entity_id=handle,
                        )
                    )

            else:
                warnings.append(
                    ParseWarning(
                        warning_code="entity_skipped",
                        message=f"Unsupported entity type: {etype}",
                        entity_id=handle,
                    )
                )

        # A-006: Annotation-only file detection
        has_geometry = any(e.entity_type in GEOMETRY_ENTITY_TYPES for e in entities)
        if len(entities) == 0 or not has_geometry:
            warnings.append(
                ParseWarning(
                    warning_code="annotation_only",
                    message="No geometric entities found (LINE/CIRCLE/ARC/POLYLINE). File may be annotation-only.",
                )
            )

        # Panel boundary detection
        panel_boundary: PanelBoundary | None = None
        panel_boundary_inferred = False

        if largest_closed_entity is not None:
            # Use the largest closed contour
            panel_boundary = PanelBoundary(
                entity_id=largest_closed_entity.entity_id,
                coordinates=largest_closed_entity.coordinates,
                bounding_box=largest_closed_entity.bounding_box or [],
                area_mm2=largest_closed_entity.area_mm2 or 0.0,
                inferred=False,
            )
        elif len(entities) > 0:
            # Infer from bounding box of all entities + 10mm margin
            all_bboxes = [e.bounding_box for e in entities if e.bounding_box]
            if all_bboxes:
                xmin = min(b[0] for b in all_bboxes) - 10.0
                ymin = min(b[1] for b in all_bboxes) - 10.0
                xmax = max(b[2] for b in all_bboxes) + 10.0
                ymax = max(b[3] for b in all_bboxes) + 10.0
                inferred_coords = [
                    [xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax],
                ]
                inferred_area = (xmax - xmin) * (ymax - ymin)
                panel_boundary = PanelBoundary(
                    entity_id=f"inferred-{uuid.uuid4().hex[:8]}",
                    coordinates=inferred_coords,
                    bounding_box=[xmin, ymin, xmax, ymax],
                    area_mm2=round(inferred_area, 4),
                    inferred=True,
                )
                panel_boundary_inferred = True

        parse_timestamp = datetime.now(timezone.utc).isoformat()

        geometry = RawGeometry(
            source_file=str(filepath),
            source_file_hash=file_hash,
            dxf_version=dxf_version,
            units_original=units_original,
            units_normalized_to="mm",
            entities=entities,
            panel_boundary=panel_boundary,
            panel_boundary_inferred=panel_boundary_inferred,
            entity_counts=dict(type_counter),
            warnings=warnings,
            parse_timestamp=parse_timestamp,
            parser_version="omim-v0.1.0",
        )

        return ParseResult(success=True, geometry=geometry, warnings=warnings)
