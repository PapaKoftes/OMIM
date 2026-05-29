"""DXF Parser implementation using ezdxf."""

import hashlib
import logging
from pathlib import Path

import ezdxf

from omim.parser.models import (
    ParseError,
    ParseResult,
    ParseWarning,
    RawEntity,
    RawGeometry,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 50

# Layer name → inferred operation type
LAYER_TYPE_MAP = {
    "cut": "cut",
    "profile": "cut",
    "contour": "cut",
    "outline": "cut",
    "border": "border",
    "drill": "drill",
    "hole": "drill",
    "bore": "drill",
    "pocket": "pocket",
    "rout": "pocket",
    "mill": "pocket",
    "engrave": "engrave",
    "mark": "engrave",
    "text": "engrave",
}


def _infer_layer_type(layer_name: str) -> str:
    """Infer operation type from layer name (case-insensitive substring match)."""
    lower = layer_name.lower().strip()
    for keyword, layer_type in LAYER_TYPE_MAP.items():
        if keyword in lower:
            return layer_type
    return "unknown"


def _file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


class DXFParser:
    """Parse a DXF file into RawGeometry."""

    def parse(self, filepath: str | Path) -> ParseResult:
        filepath = Path(filepath)

        # A-001: File not found
        if not filepath.exists():
            return ParseResult(
                success=False,
                errors=[ParseError(error_code="FILE_NOT_FOUND", message=str(filepath))],
            )

        # A-004: File too large
        size_mb = filepath.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            return ParseResult(
                success=False,
                errors=[
                    ParseError(
                        error_code="DXF_TOO_LARGE",
                        message=f"{size_mb:.1f}MB exceeds {MAX_FILE_SIZE_MB}MB limit",
                    )
                ],
            )

        # Parse with ezdxf
        try:
            doc = ezdxf.readfile(str(filepath))
        except ezdxf.DXFStructureError as e:
            return ParseResult(
                success=False,
                errors=[ParseError(error_code="DXF_CORRUPT", message=str(e))],
            )
        except Exception as e:
            return ParseResult(
                success=False,
                errors=[ParseError(error_code="DXF_READ_ERROR", message=str(e))],
            )

        file_hash = _file_hash(filepath)
        dxf_version = doc.dxfversion

        # Check units
        warnings: list[ParseWarning] = []
        units = "mm"
        units_normalized_from = None
        insunits = doc.header.get("$INSUNITS", 0)
        if insunits == 1:  # inches
            units_normalized_from = "inches"
            warnings.append(
                ParseWarning(warning_code="units_converted", message="Inches → mm conversion applied")
            )

        # Extract entities from modelspace
        msp = doc.modelspace()
        entities: list[RawEntity] = []
        panel_boundary_id: str | None = None
        largest_area = 0.0

        for entity in msp:
            etype = entity.dxftype()
            handle = entity.dxf.handle
            layer = entity.dxf.layer if hasattr(entity.dxf, "layer") else "0"
            layer_type = _infer_layer_type(layer)

            if etype == "CIRCLE":
                cx, cy, _ = entity.dxf.center
                r = entity.dxf.radius
                if units_normalized_from == "inches":
                    cx, cy, r = cx * 25.4, cy * 25.4, r * 25.4
                if r <= 0:
                    warnings.append(
                        ParseWarning(
                            warning_code="degenerate_circle_skipped",
                            message=f"Circle radius={r}",
                            entity_id=handle,
                        )
                    )
                    continue
                entities.append(
                    RawEntity(
                        entity_id=handle,
                        entity_type="CIRCLE",
                        layer=layer,
                        inferred_layer_type=layer_type,
                        center=(cx, cy),
                        radius_mm=r,
                        is_closed=True,
                        bbox=(cx - r, cy - r, cx + r, cy + r),
                    )
                )

            elif etype == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in entity.get_points(format="xy")]
                if units_normalized_from == "inches":
                    pts = [(x * 25.4, y * 25.4) for x, y in pts]
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

                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                bbox = (min(xs), min(ys), max(xs), max(ys))

                raw = RawEntity(
                    entity_id=handle,
                    entity_type="LWPOLYLINE",
                    layer=layer,
                    inferred_layer_type=layer_type,
                    points=pts,
                    is_closed=is_closed,
                    bbox=bbox,
                )
                entities.append(raw)

                # Track largest closed contour for panel boundary detection
                if is_closed and len(pts) >= 3:
                    area = abs(sum(
                        pts[i][0] * pts[(i + 1) % len(pts)][1]
                        - pts[(i + 1) % len(pts)][0] * pts[i][1]
                        for i in range(len(pts))
                    ) / 2.0)
                    if area > largest_area:
                        largest_area = area
                        panel_boundary_id = handle

            elif etype == "LINE":
                sx, sy, _ = entity.dxf.start
                ex, ey, _ = entity.dxf.end
                if units_normalized_from == "inches":
                    sx, sy, ex, ey = sx * 25.4, sy * 25.4, ex * 25.4, ey * 25.4
                entities.append(
                    RawEntity(
                        entity_id=handle,
                        entity_type="LINE",
                        layer=layer,
                        inferred_layer_type=layer_type,
                        points=[(sx, sy), (ex, ey)],
                        is_closed=False,
                        bbox=(min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey)),
                    )
                )

            elif etype == "ARC":
                cx, cy, _ = entity.dxf.center
                r = entity.dxf.radius
                if units_normalized_from == "inches":
                    cx, cy, r = cx * 25.4, cy * 25.4, r * 25.4
                entities.append(
                    RawEntity(
                        entity_id=handle,
                        entity_type="ARC",
                        layer=layer,
                        inferred_layer_type=layer_type,
                        center=(cx, cy),
                        radius_mm=r,
                        is_closed=False,
                        bbox=(cx - r, cy - r, cx + r, cy + r),
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

        # A-005: Empty DXF
        if len(entities) == 0:
            warnings.append(
                ParseWarning(warning_code="empty_file", message="No geometric entities found")
            )

        geometry = RawGeometry(
            source_file=str(filepath),
            source_file_hash=file_hash,
            dxf_version=dxf_version,
            units=units,
            units_normalized_from=units_normalized_from,
            entities=entities,
            warnings=warnings,
            panel_boundary_detected=panel_boundary_id is not None,
            panel_boundary_entity_id=panel_boundary_id,
        )

        return ParseResult(success=True, geometry=geometry)
