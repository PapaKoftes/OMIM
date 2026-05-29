"""Manufacturing validation rules (MFG-*).

These validate manufacturing feasibility: edge distances, drill ranges,
feature density, min panel dimensions, etc.
"""

from __future__ import annotations

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.validation.models import Severity, ValidationResult

# Default thresholds (mm) — can be overridden via rules YAML
DEFAULTS = {
    "min_edge_distance_mm": 8.0,
    "min_drill_diameter_mm": 3.0,
    "max_drill_diameter_mm": 35.0,
    "min_hole_spacing_mm": 5.0,
    "min_panel_width_mm": 50.0,
    "min_panel_height_mm": 50.0,
}


def mfg_001_edge_distance(
    mgg: ManufacturingGeometryGraph,
    min_distance_mm: float = DEFAULTS["min_edge_distance_mm"],
) -> list[ValidationResult]:
    """MFG-001: Holes must be at least *min_distance_mm* from panel edge."""
    results = []
    panel_bbox = mgg.metadata.panel_bbox
    if not panel_bbox:
        return results

    px_min, py_min, px_max, py_max = panel_bbox

    for nid, data in mgg.geometry_nodes():
        if data.get("is_outer_boundary"):
            continue
        if data.get("geometry_type") != "circle":
            continue
        centroid = data.get("centroid")
        if not centroid:
            continue
        cx, cy = centroid
        r = data.get("radius_mm", 0)

        # Distance from circle edge to panel edge
        distances = [
            cx - r - px_min,  # left
            py_max - (cy + r),  # top (DXF Y up)
            px_max - (cx + r),  # right
            cy - r - py_min,  # bottom
        ]
        min_dist = min(distances)

        if min_dist < min_distance_mm:
            results.append(ValidationResult(
                rule_id="MFG-001",
                rule_name="Edge Distance Violation",
                severity=Severity.ERROR,
                passed=False,
                message=(
                    f"Hole {nid} is {min_dist:.1f} mm from panel edge "
                    f"(minimum: {min_distance_mm} mm)"
                ),
                measured_value=min_dist,
                threshold_value=min_distance_mm,
                applies_to_node_ids=[nid],
            ))
    return results


def mfg_002_hole_spacing(
    mgg: ManufacturingGeometryGraph,
    min_spacing_mm: float = DEFAULTS["min_hole_spacing_mm"],
) -> list[ValidationResult]:
    """MFG-002: Minimum center-to-center distance between holes."""
    results = []
    circles = [
        (nid, data)
        for nid, data in mgg.geometry_nodes()
        if data.get("geometry_type") == "circle"
        and data.get("centroid")
        and not data.get("is_outer_boundary")
    ]

    for i, (id_a, data_a) in enumerate(circles):
        cx_a, cy_a = data_a["centroid"]
        for id_b, data_b in circles[i + 1:]:
            cx_b, cy_b = data_b["centroid"]
            dist = ((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2) ** 0.5
            if dist < min_spacing_mm:
                results.append(ValidationResult(
                    rule_id="MFG-002",
                    rule_name="Hole Spacing Violation",
                    severity=Severity.ERROR,
                    passed=False,
                    message=(
                        f"Holes {id_a} and {id_b} are {dist:.1f} mm apart "
                        f"(minimum: {min_spacing_mm} mm)"
                    ),
                    measured_value=dist,
                    threshold_value=min_spacing_mm,
                    applies_to_node_ids=[id_a, id_b],
                ))
    return results


def mfg_011_drill_diameter_range(
    mgg: ManufacturingGeometryGraph,
    min_diameter_mm: float = DEFAULTS["min_drill_diameter_mm"],
    max_diameter_mm: float = DEFAULTS["max_drill_diameter_mm"],
) -> list[ValidationResult]:
    """MFG-011: Drill hole diameter must be within tooling range."""
    results = []
    for nid, data in mgg.geometry_nodes():
        if data.get("geometry_type") != "circle":
            continue
        if data.get("is_outer_boundary"):
            continue
        d = data.get("diameter_mm")
        if d is None:
            continue
        if d < min_diameter_mm:
            results.append(ValidationResult(
                rule_id="MFG-011",
                rule_name="Drill Diameter Too Small",
                severity=Severity.ERROR,
                passed=False,
                message=f"Hole {nid} diameter {d:.1f} mm < min {min_diameter_mm} mm",
                measured_value=d,
                threshold_value=min_diameter_mm,
                applies_to_node_ids=[nid],
            ))
        elif d > max_diameter_mm:
            results.append(ValidationResult(
                rule_id="MFG-011",
                rule_name="Drill Diameter Too Large",
                severity=Severity.WARNING,
                passed=False,
                message=f"Hole {nid} diameter {d:.1f} mm > max {max_diameter_mm} mm",
                measured_value=d,
                threshold_value=max_diameter_mm,
                applies_to_node_ids=[nid],
            ))
    return results


def mfg_009_min_panel_dimensions(
    mgg: ManufacturingGeometryGraph,
    min_width_mm: float = DEFAULTS["min_panel_width_mm"],
    min_height_mm: float = DEFAULTS["min_panel_height_mm"],
) -> list[ValidationResult]:
    """MFG-009: Panel must meet minimum dimensions for CNC fixturing."""
    results = []
    w = mgg.metadata.panel_width_mm
    h = mgg.metadata.panel_height_mm

    if w is not None and w < min_width_mm:
        results.append(ValidationResult(
            rule_id="MFG-009",
            rule_name="Panel Too Narrow",
            severity=Severity.WARNING,
            passed=False,
            message=f"Panel width {w:.1f} mm < minimum {min_width_mm} mm",
            measured_value=w,
            threshold_value=min_width_mm,
        ))
    if h is not None and h < min_height_mm:
        results.append(ValidationResult(
            rule_id="MFG-009",
            rule_name="Panel Too Short",
            severity=Severity.WARNING,
            passed=False,
            message=f"Panel height {h:.1f} mm < minimum {min_height_mm} mm",
            measured_value=h,
            threshold_value=min_height_mm,
        ))
    return results


# Registry of all manufacturing rules
MANUFACTURING_RULES = [
    mfg_001_edge_distance,
    mfg_002_hole_spacing,
    mfg_011_drill_diameter_range,
    mfg_009_min_panel_dimensions,
]
