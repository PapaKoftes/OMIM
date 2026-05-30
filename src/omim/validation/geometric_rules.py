"""Geometric validation rules (Layer 1: GEO-001 to GEO-008).

All Layer 1 rules must pass before Layer 2 runs.
All Layer 1 rules have confidence_ceiling = 1.0.
"""

from __future__ import annotations

import math
import time
from typing import Any

from shapely.geometry import LinearRing, Point, Polygon

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.validation.models import RuleResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    rule_id: str,
    rule_name: str,
    passed: bool,
    severity: str,
    message: str,
    affected_node_ids: list[str] | None = None,
    measured_value: float | None = None,
    threshold_value: float | None = None,
    evidence: dict | None = None,
    execution_time_ms: float = 0.0,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_name=rule_name,
        passed=passed,
        severity=severity if not passed else "PASS",
        message=message,
        affected_node_ids=affected_node_ids or [],
        measured_value=measured_value,
        threshold_value=threshold_value,
        evidence=evidence or {},
        execution_time_ms=execution_time_ms,
        confidence=1.0,
    )


def _get_panel_polygon(mgg: ManufacturingGeometryGraph) -> Polygon | None:
    """Build a Shapely Polygon from the outer boundary node."""
    for _nid, data in mgg.geometry_nodes():
        if data.get("is_outer_boundary"):
            coords = data.get("coordinates", [])
            if len(coords) >= 3:
                return Polygon(coords)
    return None


# ---------------------------------------------------------------------------
# GEO-001: Open Contour Detection
# ---------------------------------------------------------------------------


def check_open_contour(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """GEO-001: For each LWPOLYLINE, check endpoint gap <= 0.01mm."""
    t0 = time.perf_counter()
    tolerance = params.get("tolerance_mm", 0.01)
    results: list[RuleResult] = []

    for nid, data in mgg.geometry_nodes():
        if data.get("geometry_type") not in ("lwpolyline", "polyline"):
            continue
        coords = data.get("coordinates", [])
        if len(coords) < 2:
            continue
        # Skip entities already marked as closed
        if data.get("is_closed"):
            continue

        first = coords[0]
        last = coords[-1]
        gap = math.sqrt((first[0] - last[0]) ** 2 + (first[1] - last[1]) ** 2)

        if gap > tolerance:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="GEO-001",
                rule_name="Open Contour Detection",
                passed=False,
                severity="ERROR",
                message=f"Polyline {nid} has endpoint gap {gap:.4f} mm (> {tolerance} mm)",
                affected_node_ids=[nid],
                measured_value=gap,
                threshold_value=tolerance,
                evidence={"gap_mm": gap, "first_point": list(first), "last_point": list(last)},
                execution_time_ms=elapsed,
            ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="GEO-001",
            rule_name="Open Contour Detection",
            passed=True,
            severity="PASS",
            message="All contours are closed or within tolerance",
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# GEO-002: Self-Intersection Detection
# ---------------------------------------------------------------------------


def check_self_intersection(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """GEO-002: Check polylines for self-intersection using Shapely LinearRing.is_simple."""
    t0 = time.perf_counter()
    results: list[RuleResult] = []

    for nid, data in mgg.geometry_nodes():
        if data.get("geometry_type") not in ("lwpolyline", "polyline"):
            continue
        coords = data.get("coordinates", [])
        if len(coords) < 4:
            continue

        try:
            ring = LinearRing(coords)
            if not ring.is_simple:
                elapsed = (time.perf_counter() - t0) * 1000
                results.append(_make_result(
                    rule_id="GEO-002",
                    rule_name="Self-Intersection Detection",
                    passed=False,
                    severity="ERROR",
                    message=f"Polyline {nid} is self-intersecting",
                    affected_node_ids=[nid],
                    evidence={"is_simple": False},
                    execution_time_ms=elapsed,
                ))
        except Exception:
            # If we can't build a ring, skip (degenerate geometry caught by GEO-003)
            pass

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="GEO-002",
            rule_name="Self-Intersection Detection",
            passed=True,
            severity="PASS",
            message="No self-intersecting contours found",
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# GEO-003: Degenerate Geometry
# ---------------------------------------------------------------------------


def check_degenerate_geometry(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """GEO-003: Flag geometry with radius < 0.001mm, length < 0.001mm, or area < 0.001mm2."""
    t0 = time.perf_counter()
    min_radius = params.get("min_radius_mm", 0.001)
    min_length = params.get("min_length_mm", 0.001)
    min_area = params.get("min_area_mm2", 0.001)
    results: list[RuleResult] = []

    for nid, data in mgg.geometry_nodes():
        gtype = data.get("geometry_type", "")

        # Check circle radius
        if gtype == "circle":
            r = data.get("radius_mm") or 0
            if r < min_radius:
                elapsed = (time.perf_counter() - t0) * 1000
                results.append(_make_result(
                    rule_id="GEO-003",
                    rule_name="Degenerate Geometry",
                    passed=False,
                    severity="ERROR",
                    message=f"Circle {nid} has radius {r:.6f} mm (< {min_radius} mm)",
                    affected_node_ids=[nid],
                    measured_value=r,
                    threshold_value=min_radius,
                    evidence={"check": "radius", "value_mm": r},
                    execution_time_ms=elapsed,
                ))
            continue

        # Check perimeter / length
        perim = data.get("perimeter_mm")
        if perim is not None and perim < min_length:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="GEO-003",
                rule_name="Degenerate Geometry",
                passed=False,
                severity="ERROR",
                message=f"Geometry {nid} has perimeter {perim:.6f} mm (< {min_length} mm)",
                affected_node_ids=[nid],
                measured_value=perim,
                threshold_value=min_length,
                evidence={"check": "length", "value_mm": perim},
                execution_time_ms=elapsed,
            ))
            continue

        # Check area for closed shapes
        area = data.get("area_mm2")
        if area is not None and data.get("is_closed") and area < min_area:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="GEO-003",
                rule_name="Degenerate Geometry",
                passed=False,
                severity="ERROR",
                message=f"Geometry {nid} has area {area:.6f} mm2 (< {min_area} mm2)",
                affected_node_ids=[nid],
                measured_value=area,
                threshold_value=min_area,
                evidence={"check": "area", "value_mm2": area},
                execution_time_ms=elapsed,
            ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="GEO-003",
            rule_name="Degenerate Geometry",
            passed=True,
            severity="PASS",
            message="No degenerate geometry found",
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# GEO-004: Coordinate Range
# ---------------------------------------------------------------------------


def check_coordinate_range(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """GEO-004: All coordinates must be within [-100, 5000] on both axes."""
    t0 = time.perf_counter()
    coord_min = params.get("coord_min", -100.0)
    coord_max = params.get("coord_max", 5000.0)
    results: list[RuleResult] = []

    for nid, data in mgg.geometry_nodes():
        bbox = data.get("bounding_box")
        if not bbox or len(bbox) < 4:
            continue

        xmin, ymin, xmax, ymax = bbox
        out_of_range = (
            xmin < coord_min or ymin < coord_min or xmax > coord_max or ymax > coord_max
        )

        if out_of_range:
            extremes = [xmin, ymin, xmax, ymax]
            worst = min(extremes) if min(extremes) < coord_min else max(extremes)
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="GEO-004",
                rule_name="Coordinate Range",
                passed=False,
                severity="ERROR",
                message=(
                    f"Geometry {nid} has coordinates outside [{coord_min}, {coord_max}]: "
                    f"bbox=[{xmin:.1f}, {ymin:.1f}, {xmax:.1f}, {ymax:.1f}]"
                ),
                affected_node_ids=[nid],
                measured_value=worst,
                evidence={"bbox": bbox, "range": [coord_min, coord_max]},
                execution_time_ms=elapsed,
            ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="GEO-004",
            rule_name="Coordinate Range",
            passed=True,
            severity="PASS",
            message=f"All coordinates within [{coord_min}, {coord_max}]",
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# GEO-005: Contour Orientation
# ---------------------------------------------------------------------------


def check_contour_orientation(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """GEO-005: Outer contours should be CCW, inner contours CW (Shapely is_ccw)."""
    t0 = time.perf_counter()
    results: list[RuleResult] = []

    for nid, data in mgg.geometry_nodes():
        if data.get("geometry_type") not in ("lwpolyline", "polyline"):
            continue
        if not data.get("is_closed"):
            continue
        coords = data.get("coordinates", [])
        if len(coords) < 3:
            continue

        try:
            ring = LinearRing(coords)
        except Exception:
            continue

        is_outer = data.get("is_outer_boundary", False)

        if is_outer and not ring.is_ccw:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="GEO-005",
                rule_name="Contour Orientation",
                passed=False,
                severity="WARNING",
                message=f"Outer contour {nid} is CW (expected CCW)",
                affected_node_ids=[nid],
                evidence={"expected": "CCW", "actual": "CW", "is_outer": True},
                execution_time_ms=elapsed,
            ))
        elif not is_outer and ring.is_ccw:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="GEO-005",
                rule_name="Contour Orientation",
                passed=False,
                severity="WARNING",
                message=f"Inner contour {nid} is CCW (expected CW)",
                affected_node_ids=[nid],
                evidence={"expected": "CW", "actual": "CCW", "is_outer": False},
                execution_time_ms=elapsed,
            ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="GEO-005",
            rule_name="Contour Orientation",
            passed=True,
            severity="PASS",
            message="All contour orientations are correct",
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# GEO-006: Duplicate Geometry
# ---------------------------------------------------------------------------


def check_duplicate_geometry(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """GEO-006: Two circles with centers within 0.1mm and radii within 1%."""
    t0 = time.perf_counter()
    center_tolerance = params.get("center_tolerance_mm", 0.1)
    radius_tolerance_pct = params.get("radius_tolerance_pct", 0.01)
    results: list[RuleResult] = []

    circles = [
        (nid, data)
        for nid, data in mgg.geometry_nodes()
        if data.get("geometry_type") == "circle" and data.get("centroid")
    ]

    for i, (id_a, data_a) in enumerate(circles):
        ca = data_a["centroid"]
        r_a = data_a.get("radius_mm", 0)
        for id_b, data_b in circles[i + 1:]:
            cb = data_b["centroid"]
            r_b = data_b.get("radius_mm", 0)

            center_dist = math.sqrt((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2)
            if center_dist > center_tolerance:
                continue

            # Check radii within 1%
            avg_r = (r_a + r_b) / 2.0 if (r_a + r_b) > 0 else 1.0
            radius_diff_pct = abs(r_a - r_b) / avg_r

            if radius_diff_pct <= radius_tolerance_pct:
                elapsed = (time.perf_counter() - t0) * 1000
                results.append(_make_result(
                    rule_id="GEO-006",
                    rule_name="Duplicate Geometry",
                    passed=False,
                    severity="WARNING",
                    message=(
                        f"Circles {id_a} and {id_b} appear to be duplicates "
                        f"(center dist={center_dist:.4f} mm, radius diff={radius_diff_pct:.2%})"
                    ),
                    affected_node_ids=[id_a, id_b],
                    measured_value=center_dist,
                    threshold_value=center_tolerance,
                    evidence={
                        "center_distance_mm": center_dist,
                        "radius_diff_pct": radius_diff_pct,
                    },
                    execution_time_ms=elapsed,
                ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="GEO-006",
            rule_name="Duplicate Geometry",
            passed=True,
            severity="PASS",
            message="No duplicate geometry detected",
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# GEO-007: Geometry Within Panel Bounds
# ---------------------------------------------------------------------------


def check_within_panel_bounds(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """GEO-007: All features must be within the panel boundary (Shapely contains/touches)."""
    t0 = time.perf_counter()
    results: list[RuleResult] = []

    panel_poly = _get_panel_polygon(mgg)
    if panel_poly is None:
        # Fall back to bbox check
        panel_bbox = mgg.metadata.panel_bbox
        if not panel_bbox:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="GEO-007",
                rule_name="Geometry Within Panel Bounds",
                passed=True,
                severity="PASS",
                message="No panel boundary defined; skipping bounds check",
                execution_time_ms=elapsed,
            ))
            return results
        panel_poly = Polygon([
            [panel_bbox[0], panel_bbox[1]],
            [panel_bbox[2], panel_bbox[1]],
            [panel_bbox[2], panel_bbox[3]],
            [panel_bbox[0], panel_bbox[3]],
        ])

    tol = params.get("tolerance_mm", 0.1)

    for nid, data in mgg.geometry_nodes():
        if data.get("is_outer_boundary"):
            continue

        gtype = data.get("geometry_type", "")
        centroid = data.get("centroid")

        if gtype == "circle" and centroid:
            r = data.get("radius_mm", 0)
            pt = Point(centroid[0], centroid[1])
            circle_geom = pt.buffer(r)
            if not (panel_poly.contains(circle_geom) or panel_poly.touches(circle_geom)):
                # Check with tolerance
                buffered_panel = panel_poly.buffer(tol)
                if not buffered_panel.contains(circle_geom):
                    elapsed = (time.perf_counter() - t0) * 1000
                    results.append(_make_result(
                        rule_id="GEO-007",
                        rule_name="Geometry Within Panel Bounds",
                        passed=False,
                        severity="ERROR",
                        message=f"Geometry {nid} extends beyond panel boundary",
                        affected_node_ids=[nid],
                        evidence={"centroid": list(centroid), "radius_mm": r},
                        execution_time_ms=elapsed,
                    ))
        elif centroid:
            bbox = data.get("bounding_box")
            if bbox and len(bbox) >= 4:
                feat_poly = Polygon([
                    [bbox[0], bbox[1]],
                    [bbox[2], bbox[1]],
                    [bbox[2], bbox[3]],
                    [bbox[0], bbox[3]],
                ])
                if not (panel_poly.contains(feat_poly) or panel_poly.touches(feat_poly)):
                    buffered_panel = panel_poly.buffer(tol)
                    if not buffered_panel.contains(feat_poly):
                        elapsed = (time.perf_counter() - t0) * 1000
                        results.append(_make_result(
                            rule_id="GEO-007",
                            rule_name="Geometry Within Panel Bounds",
                            passed=False,
                            severity="ERROR",
                            message=f"Geometry {nid} extends beyond panel boundary",
                            affected_node_ids=[nid],
                            evidence={"bbox": bbox},
                            execution_time_ms=elapsed,
                        ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="GEO-007",
            rule_name="Geometry Within Panel Bounds",
            passed=True,
            severity="PASS",
            message="All geometry is within panel bounds",
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# GEO-008: Zero-Area Closed Contour
# ---------------------------------------------------------------------------


def check_zero_area_contour(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """GEO-008: Closed polyline with area < 1.0mm2."""
    t0 = time.perf_counter()
    min_area = params.get("min_area_mm2", 1.0)
    results: list[RuleResult] = []

    for nid, data in mgg.geometry_nodes():
        if data.get("geometry_type") not in ("lwpolyline", "polyline"):
            continue
        if not data.get("is_closed"):
            continue
        if data.get("is_outer_boundary"):
            continue

        area = data.get("area_mm2")
        if area is not None and area < min_area:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="GEO-008",
                rule_name="Zero-Area Closed Contour",
                passed=False,
                severity="ERROR",
                message=f"Closed contour {nid} has area {area:.4f} mm2 (< {min_area} mm2)",
                affected_node_ids=[nid],
                measured_value=area,
                threshold_value=min_area,
                evidence={"area_mm2": area},
                execution_time_ms=elapsed,
            ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="GEO-008",
            rule_name="Zero-Area Closed Contour",
            passed=True,
            severity="PASS",
            message="No zero-area closed contours found",
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# Handler registry — maps rule_id -> check function
# ---------------------------------------------------------------------------

GEOMETRIC_HANDLERS: dict[str, Any] = {
    "GEO-001": check_open_contour,
    "GEO-002": check_self_intersection,
    "GEO-003": check_degenerate_geometry,
    "GEO-004": check_coordinate_range,
    "GEO-005": check_contour_orientation,
    "GEO-006": check_duplicate_geometry,
    "GEO-007": check_within_panel_bounds,
    "GEO-008": check_zero_area_contour,
}
