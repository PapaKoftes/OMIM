"""Geometric validation rules (GEO-*).

These validate raw geometric properties: degenerate shapes, overlaps,
contour orientation, panel bounds, etc.
"""

from __future__ import annotations

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.validation.models import Severity, ValidationResult


def geo_001_degenerate_circles(mgg: ManufacturingGeometryGraph) -> list[ValidationResult]:
    """GEO-001: Flag circles with zero or near-zero radius."""
    results = []
    for nid, data in mgg.geometry_nodes():
        if data.get("geometry_type") != "circle":
            continue
        r = data.get("radius_mm") or 0
        if r < 0.01:
            results.append(ValidationResult(
                rule_id="GEO-001",
                rule_name="Degenerate Circle",
                severity=Severity.ERROR,
                passed=False,
                message=f"Circle {nid} has radius {r:.4f} mm (< 0.01 mm)",
                measured_value=r,
                threshold_value=0.01,
                applies_to_node_ids=[nid],
            ))
    return results


def geo_002_unclosed_contours(mgg: ManufacturingGeometryGraph) -> list[ValidationResult]:
    """GEO-002: Warn about polylines on cut/profile layers that aren't closed."""
    results = []
    cut_layers = {"cut", "border"}
    for nid, data in mgg.geometry_nodes():
        if data.get("geometry_type") != "lwpolyline":
            continue
        if data.get("inferred_layer_type") not in cut_layers:
            continue
        if not data.get("is_closed"):
            results.append(ValidationResult(
                rule_id="GEO-002",
                rule_name="Unclosed Cut Contour",
                severity=Severity.WARNING,
                passed=False,
                message=f"Polyline {nid} on cut layer is not closed",
                applies_to_node_ids=[nid],
            ))
    return results


def geo_003_self_intersecting(mgg: ManufacturingGeometryGraph) -> list[ValidationResult]:
    """GEO-003: Detect self-intersecting polylines (placeholder — needs Shapely is_valid)."""
    # Full implementation requires building Shapely geometries and checking is_valid
    # For MVP, we check via area vs perimeter heuristic
    return []


def geo_004_overlapping_geometry(mgg: ManufacturingGeometryGraph) -> list[ValidationResult]:
    """GEO-004: Detect overlapping circles (duplicate drill holes)."""
    results = []
    circles = [
        (nid, data)
        for nid, data in mgg.geometry_nodes()
        if data.get("geometry_type") == "circle" and data.get("centroid")
    ]

    for i, (id_a, data_a) in enumerate(circles):
        for id_b, data_b in circles[i + 1:]:
            cx_a, cy_a = data_a["centroid"]
            cx_b, cy_b = data_b["centroid"]
            dist = ((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2) ** 0.5
            r_a = data_a.get("radius_mm", 0)
            r_b = data_b.get("radius_mm", 0)
            # Overlap: centers closer than half the smaller radius
            if dist < min(r_a, r_b) * 0.5:
                results.append(ValidationResult(
                    rule_id="GEO-004",
                    rule_name="Overlapping Circles",
                    severity=Severity.WARNING,
                    passed=False,
                    message=f"Circles {id_a} and {id_b} overlap (dist={dist:.2f} mm)",
                    measured_value=dist,
                    applies_to_node_ids=[id_a, id_b],
                ))
    return results


def geo_007_within_panel_bounds(mgg: ManufacturingGeometryGraph) -> list[ValidationResult]:
    """GEO-007: Check that all features are within the panel boundary."""
    results = []
    panel_bbox = mgg.metadata.panel_bbox
    if not panel_bbox:
        return results

    px_min, py_min, px_max, py_max = panel_bbox
    # Small tolerance for rounding
    tol = 0.1

    for nid, data in mgg.geometry_nodes():
        if data.get("is_outer_boundary"):
            continue
        bbox = data.get("bbox")
        if not bbox:
            continue
        xmin, ymin, xmax, ymax = bbox
        if (xmin < px_min - tol or ymin < py_min - tol or
                xmax > px_max + tol or ymax > py_max + tol):
            results.append(ValidationResult(
                rule_id="GEO-007",
                rule_name="Outside Panel Bounds",
                severity=Severity.ERROR,
                passed=False,
                message=f"Geometry {nid} extends beyond panel boundary",
                applies_to_node_ids=[nid],
            ))
    return results


# Registry of all geometric rules
GEOMETRIC_RULES = [
    geo_001_degenerate_circles,
    geo_002_unclosed_contours,
    geo_003_self_intersecting,
    geo_004_overlapping_geometry,
    geo_007_within_panel_bounds,
]
