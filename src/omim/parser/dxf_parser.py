"""DXF Parser implementation using ezdxf.

Hardened against real-world DXF mess: SPLINE/ELLIPSE approximation, legacy
POLYLINE, LWPOLYLINE with bulges (arc segments), INSERT (block reference)
explosion, non-zero Z / 3D coordinates flattened to XY, and graceful
skip-with-warning for annotations (TEXT/MTEXT/DIMENSION/HATCH/LEADER).

Determinism note (Phase 0): entity ids are derived from the ezdxf handle
(`ent-<handle>`), never from uuid/now, so artifacts are byte-reproducible.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import ezdxf
from ezdxf import path as ezdxf_path
from shapely.geometry import LinearRing, LineString, Point, Polygon

from omim.parser.models import (
    DEFAULT_LAYER_MAP,
    PanelBoundary,
    ParseError,
    ParserConfig,
    ParseResult,
    ParseWarning,
    RawEntity,
    RawGeometry,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 50

# Geometry entity types that indicate real geometry (not annotation-only).
GEOMETRY_ENTITY_TYPES = {
    "LINE", "CIRCLE", "ARC", "LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE",
}

# Annotation / fill entity types that are intentionally skipped (not geometry).
ANNOTATION_ENTITY_TYPES = {
    "TEXT", "MTEXT", "ATTDEF", "ATTRIB", "DIMENSION", "HATCH", "LEADER",
    "MULTILEADER", "MLEADER", "WIPEOUT", "IMAGE", "TOLERANCE",
}


def _infer_layer_type(
    layer_name: str, conventions: dict[str, list[str]] | None = None
) -> str:
    """Infer operation type from layer name (case-insensitive prefix match)."""
    conventions = conventions or DEFAULT_LAYER_MAP
    upper = layer_name.upper().strip()
    for layer_type, prefixes in conventions.items():
        for prefix in prefixes:
            if upper.startswith(prefix.upper()):
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


def _scale_pts(
    pts: list[list[float]], from_units: str | None
) -> list[list[float]]:
    """Scale a list of 2D points from original units to mm."""
    if from_units == "inches":
        return [[x * 25.4, y * 25.4] for x, y in pts]
    return pts


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


def _has_bulge(entity) -> bool:
    """True if an LWPOLYLINE carries any non-zero bulge (arc segments)."""
    try:
        return any(abs(p[4]) > 1e-9 for p in entity.get_points(format="xyseb"))
    except Exception:
        return False


def _flatten_path(entity, segments: int) -> list[list[float]]:
    """Flatten any path-convertible entity to XY points in WCS.

    Uses ezdxf's path machinery so bulges/curves are honoured. ``segments`` is
    a target resolution; we derive a flattening distance from the entity's
    extent so the segment count is roughly respected without being brittle.
    """
    p = ezdxf_path.make_path(entity)
    # Estimate a flattening tolerance from the bounding extent so that curves
    # get ~`segments` chords. Fall back to a small absolute distance.
    try:
        ctrl = list(p.control_vertices())
        if ctrl:
            xs = [v.x for v in ctrl]
            ys = [v.y for v in ctrl]
            extent = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
            distance = max(extent / max(segments, 1), 1e-4)
        else:
            distance = 0.1
    except Exception:
        distance = 0.1
    return [[v.x, v.y] for v in p.flattening(distance, segments=max(segments, 4))]


class DXFParser:
    """Parse a DXF file into RawGeometry."""

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        max_bytes = self.config.max_file_size_bytes
        size_bytes = filepath.stat().st_size
        if size_bytes > max_bytes:
            return ParseResult(
                success=False,
                errors=[ParseError(
                    error_code="DXF_TOO_LARGE",
                    message=(
                        f"{size_bytes / (1024 * 1024):.1f}MB exceeds "
                        f"{max_bytes / (1024 * 1024):.0f}MB limit"
                    ),
                    recoverable=False,
                )],
            )

        # Parse with ezdxf — A-002 corrupt/binary/unreadable
        try:
            doc = ezdxf.readfile(str(filepath))
        except ezdxf.DXFStructureError as e:
            logger.error("DXF corrupt: %s: %s", filepath, e)
            return self._corrupt(e)
        except Exception as e:  # noqa: BLE001 - any read failure is a corrupt file
            logger.error("DXF unreadable: %s: %s", filepath, e)
            return self._corrupt(e)

        file_hash = _file_hash(filepath)
        dxf_version = doc.dxfversion

        # A-003: DXF version check — versions below AC1015 are unsupported
        if dxf_version < "AC1015":
            return ParseResult(
                success=False,
                errors=[ParseError(
                    error_code="DXF_VERSION_UNSUPPORTED",
                    message=(
                        f"DXF version {dxf_version} is below AC1015 "
                        "(AutoCAD 2000 minimum)"
                    ),
                    recoverable=False,
                )],
            )

        warnings: list[ParseWarning] = []

        # B-007: Units. $INSUNITS == 1 -> inches.
        units_original = "mm"
        units_from: str | None = None
        insunits = doc.header.get("$INSUNITS", 0)
        if insunits == 1:
            units_original = "inches"
            units_from = "inches"
            warnings.append(ParseWarning(
                warning_code="units_converted",
                message="Inches -> mm conversion applied",
            ))

        # Extract entities from modelspace only (paperspace is documented as
        # out of scope; we never crash on paperspace content).
        msp = doc.modelspace()
        msp_entity_count = 0
        entities: list[RawEntity] = []
        type_counter: Counter = Counter()

        largest_closed_entity: RawEntity | None = None
        largest_closed_area: float = 0.0

        for entity in msp:
            msp_entity_count += 1
            produced = self._process_entity(entity, units_from, warnings, depth=0)
            for raw_ent in produced:
                entities.append(raw_ent)
                type_counter[raw_ent.entity_type] += 1
                if (
                    raw_ent.is_closed
                    and raw_ent.area_mm2
                    and isinstance(raw_ent.coordinates, list)
                    and raw_ent.coordinates
                    and isinstance(raw_ent.coordinates[0], list)
                    and len(raw_ent.coordinates) >= 3
                    and raw_ent.area_mm2 > largest_closed_area
                ):
                    largest_closed_area = raw_ent.area_mm2
                    largest_closed_entity = raw_ent

        # A-005 (empty modelspace) vs A-006 (annotation-only).
        has_geometry = any(
            e.entity_type in GEOMETRY_ENTITY_TYPES for e in entities
        )
        if msp_entity_count == 0:
            warnings.append(ParseWarning(
                warning_code="empty_file",
                message="Modelspace contains zero entities (A-005).",
            ))
        elif not has_geometry:
            warnings.append(ParseWarning(
                warning_code="annotation_only",
                message=(
                    "No cuttable geometry found "
                    "(LINE/CIRCLE/ARC/POLYLINE/SPLINE/ELLIPSE). "
                    "File may be annotation-only (A-006)."
                ),
            ))

        # Panel boundary detection.
        panel_boundary, panel_boundary_inferred = self._detect_panel_boundary(
            entities, largest_closed_entity, warnings
        )

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
            parse_timestamp=datetime.now(UTC).isoformat(),
            parser_version="omim-v0.1.0",
        )

        return ParseResult(success=True, geometry=geometry, warnings=warnings)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _corrupt(self, e: Exception) -> ParseResult:
        return ParseResult(
            success=False,
            errors=[ParseError(
                error_code="DXF_CORRUPT",
                message=str(e),
                recoverable=False,
            )],
        )

    def _process_entity(
        self,
        entity,
        units_from: str | None,
        warnings: list[ParseWarning],
        depth: int,
        id_suffix: str = "",
    ) -> list[RawEntity]:
        """Dispatch a single ezdxf entity to a RawEntity (or several).

        Returns a (possibly empty) list. INSERT entities explode to their
        primitives and recurse. Anything that cannot be handled becomes a
        ParseWarning — never a silent drop, never a crash.
        """
        etype = entity.dxftype()
        handle = getattr(entity.dxf, "handle", None) or "noh"
        eid = f"ent-{handle}{id_suffix}"
        layer = entity.dxf.layer if hasattr(entity.dxf, "layer") else "0"
        layer_type = _infer_layer_type(layer, self.config.layer_conventions)

        try:
            if etype == "CIRCLE":
                return self._circle(entity, eid, handle, layer, layer_type,
                                    units_from, warnings)
            if etype == "ARC":
                return self._arc(entity, eid, handle, layer, layer_type, units_from)
            if etype == "LINE":
                return self._line(entity, eid, handle, layer, layer_type, units_from)
            if etype == "LWPOLYLINE":
                return self._lwpolyline(entity, eid, handle, layer, layer_type,
                                        units_from, warnings)
            if etype == "POLYLINE":
                return self._legacy_polyline(entity, eid, handle, layer,
                                             layer_type, units_from, warnings)
            if etype == "SPLINE":
                return self._spline(entity, eid, handle, layer, layer_type,
                                    units_from, warnings)
            if etype == "ELLIPSE":
                return self._ellipse(entity, eid, handle, layer, layer_type,
                                     units_from, warnings)
            if etype == "INSERT":
                return self._insert(entity, handle, units_from, warnings, depth)

            # Annotation / unsupported -> skip with warning.
            code = (
                "annotation_skipped"
                if etype in ANNOTATION_ENTITY_TYPES
                else "entity_skipped"
            )
            warnings.append(ParseWarning(
                warning_code=code,
                message=f"Skipped entity type: {etype}",
                entity_id=handle,
            ))
            return []
        except Exception as e:  # noqa: BLE001 - one bad entity must not crash parse
            logger.warning("Failed to process %s %s: %s", etype, handle, e)
            warnings.append(ParseWarning(
                warning_code="entity_read_error",
                message=f"Failed to read {etype}: {e}",
                entity_id=handle,
            ))
            return []

    def _circle(self, entity, eid, handle, layer, layer_type, units_from,
                warnings) -> list[RawEntity]:
        cx, cy = entity.dxf.center.x, entity.dxf.center.y  # drop Z (flatten)
        r = entity.dxf.radius
        cx, cy = _scale_pt(cx, cy, units_from)
        r = _scale(r, units_from)
        if r <= 0:  # B-004 degenerate circle
            warnings.append(ParseWarning(
                warning_code="degenerate_circle_skipped",
                message=f"Circle radius={r}",
                entity_id=handle,
            ))
            return []
        props = _compute_shapely_circle(cx, cy, r)
        return [RawEntity(
            entity_id=eid, ezdxf_handle=handle, entity_type="CIRCLE",
            layer=layer, inferred_layer_type=layer_type,
            coordinates=[cx, cy, r], is_closed=True, **props,
        )]

    def _arc(self, entity, eid, handle, layer, layer_type, units_from
             ) -> list[RawEntity]:
        cx, cy = entity.dxf.center.x, entity.dxf.center.y
        r = entity.dxf.radius
        cx, cy = _scale_pt(cx, cy, units_from)
        r = _scale(r, units_from)
        start_angle = entity.dxf.start_angle
        end_angle = entity.dxf.end_angle
        props = _compute_shapely_arc(cx, cy, r, start_angle, end_angle)
        return [RawEntity(
            entity_id=eid, ezdxf_handle=handle, entity_type="ARC",
            layer=layer, inferred_layer_type=layer_type,
            coordinates=[cx, cy, r, start_angle, end_angle],
            is_closed=False, **props,
        )]

    def _line(self, entity, eid, handle, layer, layer_type, units_from
              ) -> list[RawEntity]:
        sx, sy = entity.dxf.start.x, entity.dxf.start.y  # drop Z
        ex, ey = entity.dxf.end.x, entity.dxf.end.y
        sx, sy = _scale_pt(sx, sy, units_from)
        ex, ey = _scale_pt(ex, ey, units_from)
        pts = [[sx, sy], [ex, ey]]
        props = _compute_shapely_line(pts)
        return [RawEntity(
            entity_id=eid, ezdxf_handle=handle, entity_type="LINE",
            layer=layer, inferred_layer_type=layer_type,
            coordinates=pts, is_closed=False, **props,
        )]

    def _lwpolyline(self, entity, eid, handle, layer, layer_type, units_from,
                    warnings) -> list[RawEntity]:
        is_closed = bool(entity.closed)
        approximated = False
        if _has_bulge(entity):
            # Bulges encode arc segments — flatten via ezdxf.path so we keep
            # the true curved geometry instead of chording across the arc.
            pts = _flatten_path(entity, self.config.spline_approximation_segments)
            approximated = True
        else:
            pts = [[p[0], p[1]] for p in entity.get_points(format="xy")]
        pts = _scale_pts(pts, units_from)
        if len(pts) < 2:
            warnings.append(ParseWarning(
                warning_code="degenerate_polyline_skipped",
                message=f"Polyline with {len(pts)} points",
                entity_id=handle,
            ))
            return []
        props = _compute_shapely_polyline(pts, is_closed)
        return [RawEntity(
            entity_id=eid, ezdxf_handle=handle, entity_type="LWPOLYLINE",
            layer=layer, inferred_layer_type=layer_type,
            coordinates=pts, is_closed=is_closed,
            is_approximated=approximated, **props,
        )]

    def _legacy_polyline(self, entity, eid, handle, layer, layer_type,
                         units_from, warnings) -> list[RawEntity]:
        # Old-style POLYLINE. Use vertices_in_wcs() when available (handles
        # bulges/3D), else fall back to vertex locations.
        approximated = False
        try:
            if any(
                abs(getattr(v.dxf, "bulge", 0.0)) > 1e-9 for v in entity.vertices
            ):
                pts = _flatten_path(
                    entity, self.config.spline_approximation_segments
                )
                approximated = True
            else:
                pts = [[v.x, v.y] for v in entity.points_in_wcs()]
        except Exception:
            pts = [
                [v.dxf.location.x, v.dxf.location.y] for v in entity.vertices
            ]
        pts = _scale_pts(pts, units_from)
        is_closed = bool(entity.is_closed)
        if len(pts) < 2:
            warnings.append(ParseWarning(
                warning_code="degenerate_polyline_skipped",
                message=f"Polyline with {len(pts)} points",
                entity_id=handle,
            ))
            return []
        props = _compute_shapely_polyline(pts, is_closed)
        return [RawEntity(
            entity_id=eid, ezdxf_handle=handle, entity_type="POLYLINE",
            layer=layer, inferred_layer_type=layer_type,
            coordinates=pts, is_closed=is_closed,
            is_approximated=approximated, **props,
        )]

    def _spline(self, entity, eid, handle, layer, layer_type, units_from,
                warnings) -> list[RawEntity]:
        # Approximate SPLINE as a polyline (P2; ~N segments per spec).
        n = self.config.spline_approximation_segments
        pts = [[v.x, v.y] for v in entity.flattening(0.01, segments=max(n, 4))]
        if len(pts) < 2:
            ctrl = list(entity.control_points)
            pts = [[p.x, p.y] for p in ctrl] if len(ctrl) >= 2 else pts
        pts = _scale_pts(pts, units_from)
        if len(pts) < 2:
            warnings.append(ParseWarning(
                warning_code="degenerate_spline_skipped",
                message="Spline with insufficient points",
                entity_id=handle,
            ))
            return []
        is_closed = bool(getattr(entity, "closed", False))
        props = _compute_shapely_polyline(pts, is_closed)
        return [RawEntity(
            entity_id=eid, ezdxf_handle=handle, entity_type="SPLINE",
            layer=layer, inferred_layer_type=layer_type,
            coordinates=pts, is_closed=is_closed,
            is_approximated=True, **props,
        )]

    def _ellipse(self, entity, eid, handle, layer, layer_type, units_from,
                 warnings) -> list[RawEntity]:
        # Approximate ELLIPSE as a polyline (never crash — skip-with-warning
        # only if it genuinely yields no usable geometry).
        pts = _flatten_path(entity, self.config.spline_approximation_segments)
        pts = _scale_pts(pts, units_from)
        if len(pts) < 2:
            warnings.append(ParseWarning(
                warning_code="ellipse_approximation_skipped",
                message="Ellipse produced insufficient points",
                entity_id=handle,
            ))
            return []
        # A full ellipse is closed; ezdxf marks this via the param range.
        try:
            full = abs(
                (entity.dxf.end_param - entity.dxf.start_param)
                - 2 * math.pi
            ) < 1e-6
        except Exception:
            full = False
        is_closed = full
        props = _compute_shapely_polyline(pts, is_closed)
        return [RawEntity(
            entity_id=eid, ezdxf_handle=handle, entity_type="ELLIPSE",
            layer=layer, inferred_layer_type=layer_type,
            coordinates=pts, is_closed=is_closed,
            is_approximated=True, **props,
        )]

    def _insert(self, entity, handle, units_from, warnings, depth
                ) -> list[RawEntity]:
        # INSERT (block reference). Explode to primitives in WCS via
        # virtual_entities(). Skip-with-warning if not explodable or too deep.
        if not self.config.explode_inserts:
            warnings.append(ParseWarning(
                warning_code="insert_skipped",
                message=f"INSERT '{getattr(entity.dxf, 'name', '?')}' skipped "
                        "(explode_inserts disabled)",
                entity_id=handle,
            ))
            return []
        if depth >= self.config.max_insert_depth:
            warnings.append(ParseWarning(
                warning_code="insert_skipped",
                message=f"INSERT '{getattr(entity.dxf, 'name', '?')}' skipped "
                        f"(nesting depth > {self.config.max_insert_depth})",
                entity_id=handle,
            ))
            return []
        try:
            virtual = list(entity.virtual_entities())
        except Exception as e:  # noqa: BLE001
            warnings.append(ParseWarning(
                warning_code="insert_skipped",
                message=f"INSERT '{getattr(entity.dxf, 'name', '?')}' "
                        f"not explodable: {e}",
                entity_id=handle,
            ))
            return []

        insert_layer = getattr(entity.dxf, "layer", "0")
        produced: list[RawEntity] = []
        for i, sub in enumerate(virtual):
            # AutoCAD layer-0 inheritance: block geometry drawn on layer "0"
            # adopts the INSERT's layer. ezdxf's virtual_entities() does not
            # apply this, so we do it here (real furniture DXFs rely on it).
            if getattr(sub.dxf, "layer", "0") == "0" and insert_layer != "0":
                sub.dxf.layer = insert_layer
            # Each exploded sub-entity may share the parent's handle (or have
            # none). Derive a unique-but-deterministic id from the INSERT
            # handle + position so MGG node ids never collide.
            sub_suffix = f"-i{handle}-{i}"
            produced.extend(
                self._process_entity(
                    sub, units_from, warnings, depth + 1, id_suffix=sub_suffix
                )
            )
        if not produced:
            warnings.append(ParseWarning(
                warning_code="insert_empty",
                message=f"INSERT '{getattr(entity.dxf, 'name', '?')}' exploded "
                        "to no usable geometry",
                entity_id=handle,
            ))
        return produced

    def _detect_panel_boundary(
        self,
        entities: list[RawEntity],
        largest_closed_entity: RawEntity | None,
        warnings: list[ParseWarning],
    ) -> tuple[PanelBoundary | None, bool]:
        if largest_closed_entity is not None:
            return (
                PanelBoundary(
                    entity_id=largest_closed_entity.entity_id,
                    coordinates=largest_closed_entity.coordinates,
                    bounding_box=largest_closed_entity.bounding_box or [],
                    area_mm2=largest_closed_entity.area_mm2 or 0.0,
                    inferred=False,
                ),
                False,
            )

        # B-006: no explicit boundary -> infer from bbox of all entities + 10mm.
        all_bboxes = [e.bounding_box for e in entities if e.bounding_box]
        if not all_bboxes:
            return None, False

        xmin = min(b[0] for b in all_bboxes) - 10.0
        ymin = min(b[1] for b in all_bboxes) - 10.0
        xmax = max(b[2] for b in all_bboxes) + 10.0
        ymax = max(b[3] for b in all_bboxes) + 10.0
        warnings.append(ParseWarning(
            warning_code="no_panel_boundary",
            message="No explicit panel boundary; using bounding box + 10mm margin.",
        ))
        return (
            PanelBoundary(
                entity_id="ent-inferred-boundary",
                coordinates=[
                    [xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax],
                ],
                bounding_box=[xmin, ymin, xmax, ymax],
                area_mm2=round((xmax - xmin) * (ymax - ymin), 4),
                inferred=True,
            ),
            True,
        )
