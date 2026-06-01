"""Manufacturing validation rules (Layer 2: MFG-001 to MFG-012).

Layer 2 rules only run if Layer 1 passes (no geometric ERRORs).
Each rule has its own confidence_ceiling.
NO access to the semantic layer.
"""

from __future__ import annotations

import math
import time
from typing import Any

from shapely.geometry import Polygon

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.validation.models import RuleResult

try:  # shapely >= 2.1 — GEOS-backed largest inscribed circle (gives the radius).
    from shapely import maximum_inscribed_circle as _max_inscribed_circle
except ImportError:  # pragma: no cover - fallback for shapely < 2.1
    _max_inscribed_circle = None


def _inscribed_diameter_mm(coords: list[list[float]]) -> float | None:
    """Largest inscribed-circle *diameter* (mm) of a closed polygon, or None.

    This is the widest tool that fits inside the pocket. Uses GEOS'
    ``maximum_inscribed_circle`` (shapely >= 2.1) when available — it returns a
    segment from the pole of inaccessibility to the nearest boundary point, whose
    length is the inscribed *radius*. Falls back to ``shapely.ops.polylabel`` plus
    a boundary-distance measurement on older shapely. Returns None on degenerate
    or invalid geometry.
    """
    try:
        poly = Polygon(coords)
    except (TypeError, ValueError):
        return None
    if not poly.is_valid or poly.area <= 0:
        return None
    if _max_inscribed_circle is not None:
        seg = _max_inscribed_circle(poly)
        return float(seg.length) * 2.0
    # Fallback: pole of inaccessibility + distance to boundary.
    from shapely.ops import polylabel

    center = polylabel(poly, tolerance=0.1)
    return float(center.distance(poly.exterior)) * 2.0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    rule_id: str,
    rule_name: str,
    passed: bool,
    severity: str,
    message: str,
    confidence: float = 1.0,
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
        confidence=confidence,
    )


def _circles(mgg: ManufacturingGeometryGraph) -> list[tuple[str, dict]]:
    """Return all non-boundary circle geometry nodes."""
    return [
        (nid, data)
        for nid, data in mgg.geometry_nodes()
        if data.get("geometry_type") == "circle"
        and data.get("centroid")
        and not data.get("is_outer_boundary")
    ]


# ---------------------------------------------------------------------------
# MFG-001: Edge Clearance
# ---------------------------------------------------------------------------


def check_edge_clearance(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-001: Centroid distance from panel boundary >= 8mm. confidence_ceiling=0.75."""
    t0 = time.perf_counter()
    min_distance = params.get("min_distance_mm", 8.0)
    results: list[RuleResult] = []

    panel_bbox = mgg.metadata.panel_bbox
    if not panel_bbox:
        elapsed = (time.perf_counter() - t0) * 1000
        return [_make_result(
            rule_id="MFG-001",
            rule_name="Edge Clearance",
            passed=True,
            severity="PASS",
            message="No panel boundary defined; skipping edge clearance check",
            confidence=0.75,
            execution_time_ms=elapsed,
        )]

    px_min, py_min, px_max, py_max = panel_bbox

    for nid, data in _circles(mgg):
        centroid = data["centroid"]
        cx, cy = centroid[0], centroid[1]

        # Distance from centroid to each panel edge
        distances = [
            cx - px_min,   # left
            px_max - cx,   # right
            cy - py_min,   # bottom
            py_max - cy,   # top
        ]
        min_dist = min(distances)

        if min_dist < min_distance:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="MFG-001",
                rule_name="Edge Clearance",
                passed=False,
                severity="ERROR",
                message=(
                    f"Hole {nid} centroid is {min_dist:.1f} mm from panel edge "
                    f"(minimum: {min_distance} mm)"
                ),
                confidence=0.75,
                affected_node_ids=[nid],
                measured_value=min_dist,
                threshold_value=min_distance,
                evidence={"distances": distances, "centroid": list(centroid)},
                execution_time_ms=elapsed,
            ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="MFG-001",
            rule_name="Edge Clearance",
            passed=True,
            severity="PASS",
            message="All features meet edge clearance requirements",
            confidence=0.75,
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# MFG-002: Feature Spacing (wall thickness)
# ---------------------------------------------------------------------------


def check_feature_spacing(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-002: Wall thickness (center_dist - r_A - r_B) >= 3mm. confidence_ceiling=0.70."""
    t0 = time.perf_counter()
    min_wall = params.get("min_wall_thickness_mm", 3.0)
    results: list[RuleResult] = []

    circles = _circles(mgg)

    for i, (id_a, data_a) in enumerate(circles):
        ca = data_a["centroid"]
        r_a = data_a.get("radius_mm", 0)
        for id_b, data_b in circles[i + 1:]:
            cb = data_b["centroid"]
            r_b = data_b.get("radius_mm", 0)

            center_dist = math.sqrt((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2)
            wall = center_dist - r_a - r_b

            if wall < min_wall:
                elapsed = (time.perf_counter() - t0) * 1000
                results.append(_make_result(
                    rule_id="MFG-002",
                    rule_name="Feature Spacing",
                    passed=False,
                    severity="ERROR",
                    message=(
                        f"Wall thickness between {id_a} and {id_b} is {wall:.1f} mm "
                        f"(minimum: {min_wall} mm)"
                    ),
                    confidence=0.70,
                    affected_node_ids=[id_a, id_b],
                    measured_value=wall,
                    threshold_value=min_wall,
                    evidence={
                        "center_distance_mm": center_dist,
                        "radius_a_mm": r_a,
                        "radius_b_mm": r_b,
                        "wall_thickness_mm": wall,
                    },
                    execution_time_ms=elapsed,
                ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="MFG-002",
            rule_name="Feature Spacing",
            passed=True,
            severity="PASS",
            message="All feature spacing meets minimum wall thickness",
            confidence=0.70,
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# MFG-003: Tool Radius Corner
# ---------------------------------------------------------------------------


def _interior_sharp_corners(
    coords: list[list[float]], min_angle_deg: float
) -> list[float]:
    """Return interior-corner angles (deg) sharper than *min_angle_deg*.

    A milled inside corner cannot be sharper than the tool can produce; a true
    sharp vertex (small interior angle) leaves an uncuttable corner. We measure
    the angle at each vertex of the (assumed simple, closed) ring and report
    concave vertices whose interior angle is below the threshold. Collinear or
    near-collinear vertices (flattened arc chords) are ignored.
    """
    pts = [p[:2] for p in coords if isinstance(p, list | tuple) and len(p) >= 2]
    # Drop a duplicated closing vertex.
    if len(pts) >= 2 and abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9:
        pts = pts[:-1]
    n = len(pts)
    if n < 3:
        return []

    try:
        ring_ccw = Polygon(pts).exterior.is_ccw
    except (TypeError, ValueError):
        return []

    sharp: list[float] = []
    for i in range(n):
        a = pts[(i - 1) % n]
        b = pts[i]
        c = pts[(i + 1) % n]
        v1 = (a[0] - b[0], a[1] - b[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        m1 = math.hypot(*v1)
        m2 = math.hypot(*v2)
        if m1 < 1e-6 or m2 < 1e-6:
            continue
        cos_a = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (m1 * m2)))
        angle = math.degrees(math.acos(cos_a))
        # Skip near-straight vertices (flattened arcs / collinear points).
        if angle > 175.0:
            continue
        # Concavity: the cross product sign relative to the ring winding tells us
        # whether this vertex turns into the interior (a concave inside corner).
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        is_concave = (cross > 0) if ring_ccw else (cross < 0)
        if is_concave and angle < min_angle_deg:
            sharp.append(round(angle, 1))
    return sharp


def check_tool_radius_corner(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-003: internal milled corners must not be sharper than the tool can
    produce. confidence_ceiling=0.65.

    For each interior closed polyline on a pocket/cut layer, flag concave inside
    corners with an interior angle below ``min_corner_angle_deg`` (default 90°: a
    round router bit physically cannot cut an inside corner sharper than a right
    angle to a true point, so it leaves an uncut radius). Bulge-flattened /
    approximated polylines are skipped — their many near-collinear chord vertices
    would false-positive — so this is conservative by design.
    """
    t0 = time.perf_counter()
    min_radius = params.get("min_corner_radius_mm", 3.0)
    min_angle = params.get("min_corner_angle_deg", 90.0)
    results: list[RuleResult] = []

    for nid, data in mgg.geometry_nodes():
        if data.get("is_outer_boundary"):
            continue
        if data.get("geometry_type") not in ("polyline", "lwpolyline", "contour"):
            continue
        if not data.get("is_closed"):
            continue
        if data.get("is_approximated"):
            continue  # flattened arcs would false-positive
        if data.get("inferred_layer_type") not in ("pocket", "cut", "engrave"):
            continue
        coords = data.get("coordinates", [])
        if not (isinstance(coords, list) and len(coords) >= 3
                and isinstance(coords[0], list)):
            continue

        sharp = _interior_sharp_corners(coords, min_angle)
        if sharp:
            results.append(_make_result(
                rule_id="MFG-003",
                rule_name="Tool Radius Corner",
                passed=False,
                severity="WARNING",
                message=(
                    f"Pocket {nid} has {len(sharp)} sharp internal corner(s) "
                    f"(angles {sharp} deg) that a {min_radius} mm-radius tool "
                    f"cannot fully cut"
                ),
                confidence=0.65,
                affected_node_ids=[nid],
                measured_value=min(sharp),
                threshold_value=min_angle,
                evidence={
                    "sharp_corner_angles_deg": sharp,
                    "min_corner_radius_mm": min_radius,
                    "min_corner_angle_deg": min_angle,
                },
            ))

    if not results:
        results.append(_make_result(
            rule_id="MFG-003",
            rule_name="Tool Radius Corner",
            passed=True,
            severity="PASS",
            message="No sharp internal corners detected (or none on milled layers)",
            confidence=0.65,
            threshold_value=min_radius,
        ))
    elapsed = (time.perf_counter() - t0) * 1000
    for r in results:
        r.execution_time_ms = elapsed
    return results


# ---------------------------------------------------------------------------
# MFG-004: Pocket Width
# ---------------------------------------------------------------------------


def check_pocket_width(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-004: a pocket/closed milled region must admit the tool — its maximum
    inscribed circle diameter must be >= tool_diameter * multiplier (default
    6mm * 1.2 = 7.2mm). confidence_ceiling=0.65.

    Computes the real largest-inscribed-circle diameter (the widest cutter that
    fits) for each interior closed polyline/contour on a pocket/cut layer. A
    pocket narrower than the tool can reach is flagged WARNING.
    """
    t0 = time.perf_counter()
    tool_diameter = params.get("tool_diameter_mm", 6.0)
    multiplier = params.get("multiplier", 1.2)
    min_width = tool_diameter * multiplier  # 7.2mm
    results: list[RuleResult] = []

    for nid, data in mgg.geometry_nodes():
        if data.get("is_outer_boundary"):
            continue
        if data.get("geometry_type") not in ("polyline", "lwpolyline", "contour"):
            continue
        if not data.get("is_closed"):
            continue
        if data.get("inferred_layer_type") not in ("pocket", "cut", "engrave"):
            continue
        coords = data.get("coordinates", [])
        if not (isinstance(coords, list) and len(coords) >= 3
                and isinstance(coords[0], list)):
            continue

        inscribed = _inscribed_diameter_mm(coords)
        if inscribed is None:
            continue

        if inscribed < min_width:
            results.append(_make_result(
                rule_id="MFG-004",
                rule_name="Pocket Width",
                passed=False,
                severity="WARNING",
                message=(
                    f"Pocket {nid} inscribed width {inscribed:.2f} mm is below the "
                    f"minimum {min_width:.1f} mm for a {tool_diameter} mm tool "
                    f"(x{multiplier})"
                ),
                confidence=0.65,
                affected_node_ids=[nid],
                measured_value=round(inscribed, 3),
                threshold_value=min_width,
                evidence={
                    "inscribed_diameter_mm": round(inscribed, 3),
                    "tool_diameter_mm": tool_diameter,
                    "min_width_mm": min_width,
                },
            ))

    if not results:
        results.append(_make_result(
            rule_id="MFG-004",
            rule_name="Pocket Width",
            passed=True,
            severity="PASS",
            message="All pockets admit the tool (inscribed width >= minimum)",
            confidence=0.65,
            threshold_value=min_width,
        ))
    elapsed = (time.perf_counter() - t0) * 1000
    for r in results:
        r.execution_time_ms = elapsed
    return results


# ---------------------------------------------------------------------------
# MFG-005: Shelf Pin Grid
# ---------------------------------------------------------------------------


def check_shelf_pin_grid(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-005: 5mm circles at 32mm +/- 0.5mm spacing. confidence_ceiling=0.90."""
    t0 = time.perf_counter()
    target_diameter = params.get("target_diameter_mm", 5.0)
    target_spacing = params.get("target_spacing_mm", 32.0)
    spacing_tolerance = params.get("spacing_tolerance_mm", 0.5)
    diameter_tolerance = params.get("diameter_tolerance_mm", 0.5)
    results: list[RuleResult] = []

    # Find circles matching shelf pin diameter
    shelf_pins = [
        (nid, data)
        for nid, data in _circles(mgg)
        if data.get("diameter_mm") is not None
        and abs(data["diameter_mm"] - target_diameter) <= diameter_tolerance
    ]

    if len(shelf_pins) < 2:
        elapsed = (time.perf_counter() - t0) * 1000
        return [_make_result(
            rule_id="MFG-005",
            rule_name="Shelf Pin Grid",
            passed=True,
            severity="PASS",
            message="Fewer than 2 shelf-pin-diameter holes; grid check not applicable",
            confidence=0.90,
            execution_time_ms=elapsed,
        )]

    # Check spacing between collinear shelf pins
    for i, (id_a, data_a) in enumerate(shelf_pins):
        ca = data_a["centroid"]
        for id_b, data_b in shelf_pins[i + 1:]:
            cb = data_b["centroid"]
            dist = math.sqrt((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2)

            # Check if distance is a multiple of target spacing
            if dist < target_spacing * 0.5:
                continue
            remainder = dist % target_spacing
            spacing_error = min(remainder, target_spacing - remainder)

            if spacing_error > spacing_tolerance:
                elapsed = (time.perf_counter() - t0) * 1000
                results.append(_make_result(
                    rule_id="MFG-005",
                    rule_name="Shelf Pin Grid",
                    passed=False,
                    severity="WARNING",
                    message=(
                        f"Shelf pin holes {id_a} and {id_b} spacing {dist:.1f} mm "
                        f"not on {target_spacing} mm grid (error: {spacing_error:.2f} mm)"
                    ),
                    confidence=0.90,
                    affected_node_ids=[id_a, id_b],
                    measured_value=dist,
                    threshold_value=target_spacing,
                    evidence={
                        "distance_mm": dist,
                        "target_spacing_mm": target_spacing,
                        "spacing_error_mm": spacing_error,
                    },
                    execution_time_ms=elapsed,
                ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="MFG-005",
            rule_name="Shelf Pin Grid",
            passed=True,
            severity="PASS",
            message="Shelf pin grid spacing is within tolerance",
            confidence=0.90,
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# MFG-006: Hinge Cup Edge Distance
# ---------------------------------------------------------------------------


def check_hinge_cup_edge_distance(
    mgg: ManufacturingGeometryGraph, **params: Any
) -> list[RuleResult]:
    """MFG-006: 35mm circles at 22.5mm +/- 1mm from edge. confidence_ceiling=0.90."""
    t0 = time.perf_counter()
    target_diameter = params.get("target_diameter_mm", 35.0)
    target_edge_dist = params.get("target_edge_distance_mm", 22.5)
    edge_tolerance = params.get("edge_tolerance_mm", 1.0)
    diameter_tolerance = params.get("diameter_tolerance_mm", 1.0)
    results: list[RuleResult] = []

    panel_bbox = mgg.metadata.panel_bbox
    if not panel_bbox:
        elapsed = (time.perf_counter() - t0) * 1000
        return [_make_result(
            rule_id="MFG-006",
            rule_name="Hinge Cup Edge Distance",
            passed=True,
            severity="PASS",
            message="No panel boundary defined; skipping hinge cup edge distance check",
            confidence=0.90,
            execution_time_ms=elapsed,
        )]

    px_min, py_min, px_max, py_max = panel_bbox

    # Find circles matching hinge cup diameter
    hinge_cups = [
        (nid, data)
        for nid, data in _circles(mgg)
        if data.get("diameter_mm") is not None
        and abs(data["diameter_mm"] - target_diameter) <= diameter_tolerance
    ]

    for nid, data in hinge_cups:
        centroid = data["centroid"]
        cx, cy = centroid[0], centroid[1]

        # Minimum distance from centroid to any edge
        distances = [cx - px_min, px_max - cx, cy - py_min, py_max - cy]
        min_dist = min(distances)

        error = abs(min_dist - target_edge_dist)
        if error > edge_tolerance:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="MFG-006",
                rule_name="Hinge Cup Edge Distance",
                passed=False,
                severity="WARNING",
                message=(
                    f"Hinge cup {nid} is {min_dist:.1f} mm from edge "
                    f"(expected: {target_edge_dist} +/- {edge_tolerance} mm)"
                ),
                confidence=0.90,
                affected_node_ids=[nid],
                measured_value=min_dist,
                threshold_value=target_edge_dist,
                evidence={
                    "edge_distance_mm": min_dist,
                    "target_mm": target_edge_dist,
                    "error_mm": error,
                },
                execution_time_ms=elapsed,
            ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="MFG-006",
            rule_name="Hinge Cup Edge Distance",
            passed=True,
            severity="PASS",
            message="Hinge cup edge distances are within tolerance",
            confidence=0.90,
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# MFG-007: Blind Feature Depth
# ---------------------------------------------------------------------------


def check_blind_feature_depth(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-007: depth <= 0.75 * 18mm thickness. confidence_ceiling=0.70. Skip if no depth info."""
    t0 = time.perf_counter()
    panel_thickness = params.get("panel_thickness_mm", 18.0)
    max_depth_ratio = params.get("max_depth_ratio", 0.75)
    max_depth = panel_thickness * max_depth_ratio  # 13.5mm
    results: list[RuleResult] = []

    for nid, data in mgg.geometry_nodes():
        if data.get("is_outer_boundary"):
            continue
        # Check for depth info in node data (populated from 2.5D Z elevations or
        # layer-name conventions by the parser; None for pure-2D features).
        depth = data.get("depth_mm")
        if depth is None:
            continue
        depth_source = data.get("depth_source")

        if depth > max_depth:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="MFG-007",
                rule_name="Blind Feature Depth",
                passed=False,
                severity="WARNING",
                message=(
                    f"Feature {nid} depth {depth:.1f} mm exceeds "
                    f"{max_depth_ratio * 100:.0f}% of {panel_thickness} mm "
                    f"thickness ({max_depth:.1f} mm) [depth via {depth_source}]"
                ),
                confidence=0.70,
                affected_node_ids=[nid],
                measured_value=depth,
                threshold_value=max_depth,
                evidence={
                    "depth_mm": depth,
                    "depth_source": depth_source,
                    "panel_thickness_mm": panel_thickness,
                    "max_depth_mm": max_depth,
                },
                execution_time_ms=elapsed,
            ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="MFG-007",
            rule_name="Blind Feature Depth",
            passed=True,
            severity="PASS",
            message="No blind features exceed depth limit (or no depth info available)",
            confidence=0.70,
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# MFG-008: Feature Density
# ---------------------------------------------------------------------------


def check_feature_density(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-008: Total hole area / panel area <= 0.30. confidence_ceiling=0.70."""
    t0 = time.perf_counter()
    max_density = params.get("max_density_ratio", 0.30)
    results: list[RuleResult] = []

    panel_bbox = mgg.metadata.panel_bbox
    if not panel_bbox:
        elapsed = (time.perf_counter() - t0) * 1000
        return [_make_result(
            rule_id="MFG-008",
            rule_name="Feature Density",
            passed=True,
            severity="PASS",
            message="No panel boundary defined; skipping feature density check",
            confidence=0.70,
            execution_time_ms=elapsed,
        )]

    px_min, py_min, px_max, py_max = panel_bbox
    panel_area = (px_max - px_min) * (py_max - py_min)
    if panel_area <= 0:
        elapsed = (time.perf_counter() - t0) * 1000
        return [_make_result(
            rule_id="MFG-008",
            rule_name="Feature Density",
            passed=True,
            severity="PASS",
            message="Panel area is zero; skipping feature density check",
            confidence=0.70,
            execution_time_ms=elapsed,
        )]

    total_hole_area = 0.0
    for nid, data in mgg.geometry_nodes():
        if data.get("is_outer_boundary"):
            continue
        area = data.get("area_mm2")
        if area and area > 0:
            total_hole_area += area

    density = total_hole_area / panel_area

    if density > max_density:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="MFG-008",
            rule_name="Feature Density",
            passed=False,
            severity="WARNING",
            message=(
                f"Feature density {density:.2%} exceeds maximum {max_density:.0%} "
                f"(hole area: {total_hole_area:.1f} mm2, panel area: {panel_area:.1f} mm2)"
            ),
            confidence=0.70,
            measured_value=density,
            threshold_value=max_density,
            evidence={
                "total_hole_area_mm2": total_hole_area,
                "panel_area_mm2": panel_area,
                "density_ratio": density,
            },
            execution_time_ms=elapsed,
        ))
    else:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="MFG-008",
            rule_name="Feature Density",
            passed=True,
            severity="PASS",
            message=f"Feature density {density:.2%} is within limits",
            confidence=0.70,
            execution_time_ms=elapsed,
        ))

    return results


# ---------------------------------------------------------------------------
# MFG-009: Panel Dimensions
# ---------------------------------------------------------------------------


def check_panel_dimensions(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-009: 50-3600mm range, min area 5000mm2. confidence_ceiling=0.75."""
    t0 = time.perf_counter()
    min_dim = params.get("min_dimension_mm", 50.0)
    max_dim = params.get("max_dimension_mm", 3600.0)
    min_area = params.get("min_area_mm2", 5000.0)
    results: list[RuleResult] = []

    w = mgg.metadata.panel_width_mm
    h = mgg.metadata.panel_height_mm

    if w is None or h is None:
        elapsed = (time.perf_counter() - t0) * 1000
        return [_make_result(
            rule_id="MFG-009",
            rule_name="Panel Dimensions",
            passed=True,
            severity="PASS",
            message="Panel dimensions not available; skipping check",
            confidence=0.75,
            execution_time_ms=elapsed,
        )]

    # Check width range
    if w < min_dim:
        results.append(_make_result(
            rule_id="MFG-009",
            rule_name="Panel Dimensions",
            passed=False,
            severity="WARNING",
            message=f"Panel width {w:.1f} mm below minimum {min_dim} mm",
            confidence=0.75,
            measured_value=w,
            threshold_value=min_dim,
            evidence={"dimension": "width", "value_mm": w},
        ))
    elif w > max_dim:
        results.append(_make_result(
            rule_id="MFG-009",
            rule_name="Panel Dimensions",
            passed=False,
            severity="WARNING",
            message=f"Panel width {w:.1f} mm exceeds maximum {max_dim} mm",
            confidence=0.75,
            measured_value=w,
            threshold_value=max_dim,
            evidence={"dimension": "width", "value_mm": w},
        ))

    # Check height range
    if h < min_dim:
        results.append(_make_result(
            rule_id="MFG-009",
            rule_name="Panel Dimensions",
            passed=False,
            severity="WARNING",
            message=f"Panel height {h:.1f} mm below minimum {min_dim} mm",
            confidence=0.75,
            measured_value=h,
            threshold_value=min_dim,
            evidence={"dimension": "height", "value_mm": h},
        ))
    elif h > max_dim:
        results.append(_make_result(
            rule_id="MFG-009",
            rule_name="Panel Dimensions",
            passed=False,
            severity="WARNING",
            message=f"Panel height {h:.1f} mm exceeds maximum {max_dim} mm",
            confidence=0.75,
            measured_value=h,
            threshold_value=max_dim,
            evidence={"dimension": "height", "value_mm": h},
        ))

    # Check minimum area
    area = w * h
    if area < min_area:
        results.append(_make_result(
            rule_id="MFG-009",
            rule_name="Panel Dimensions",
            passed=False,
            severity="WARNING",
            message=f"Panel area {area:.1f} mm2 below minimum {min_area} mm2",
            confidence=0.75,
            measured_value=area,
            threshold_value=min_area,
            evidence={"dimension": "area", "value_mm2": area},
        ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="MFG-009",
            rule_name="Panel Dimensions",
            passed=True,
            severity="PASS",
            message=f"Panel dimensions {w:.1f} x {h:.1f} mm are within valid range",
            confidence=0.75,
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# MFG-010: Confirmat Pair
# ---------------------------------------------------------------------------


def check_confirmat_pair(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-010: INFO only, notes multi-panel context needed. confidence_ceiling=0.90."""
    t0 = time.perf_counter()
    # Confirmat screw detection requires multi-panel context (adjacent panel data)
    # which is not available in single-panel validation
    elapsed = (time.perf_counter() - t0) * 1000
    return [_make_result(
        rule_id="MFG-010",
        rule_name="Confirmat Pair",
        passed=True,
        severity="INFO",
        message=(
            "Confirmat pair validation requires multi-panel context. "
            "Single-panel check not applicable."
        ),
        confidence=0.90,
        execution_time_ms=elapsed,
    )]


# ---------------------------------------------------------------------------
# MFG-011: Drill Diameter Range
# ---------------------------------------------------------------------------


def check_drill_diameter_range(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-011: Drill diameter 3-40mm. confidence_ceiling=0.75."""
    t0 = time.perf_counter()
    min_diameter = params.get("min_diameter_mm", 3.0)
    max_diameter = params.get("max_diameter_mm", 40.0)
    results: list[RuleResult] = []

    for nid, data in _circles(mgg):
        d = data.get("diameter_mm")
        if d is None:
            continue

        if d < min_diameter:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="MFG-011",
                rule_name="Drill Diameter Range",
                passed=False,
                severity="ERROR",
                message=f"Hole {nid} diameter {d:.1f} mm below minimum {min_diameter} mm",
                confidence=0.75,
                affected_node_ids=[nid],
                measured_value=d,
                threshold_value=min_diameter,
                evidence={"diameter_mm": d, "bound": "min"},
                execution_time_ms=elapsed,
            ))
        elif d > max_diameter:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="MFG-011",
                rule_name="Drill Diameter Range",
                passed=False,
                severity="ERROR",
                message=f"Hole {nid} diameter {d:.1f} mm exceeds maximum {max_diameter} mm",
                confidence=0.75,
                affected_node_ids=[nid],
                measured_value=d,
                threshold_value=max_diameter,
                evidence={"diameter_mm": d, "bound": "max"},
                execution_time_ms=elapsed,
            ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="MFG-011",
            rule_name="Drill Diameter Range",
            passed=True,
            severity="PASS",
            message=f"All drill diameters within {min_diameter}-{max_diameter} mm range",
            confidence=0.75,
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# MFG-012: No Feature on Sheet Edge
# ---------------------------------------------------------------------------


def check_no_feature_on_edge(mgg: ManufacturingGeometryGraph, **params: Any) -> list[RuleResult]:
    """MFG-012: Centroid not on boundary (0.1mm tolerance). confidence_ceiling=0.75."""
    t0 = time.perf_counter()
    tolerance = params.get("tolerance_mm", 0.1)
    results: list[RuleResult] = []

    panel_bbox = mgg.metadata.panel_bbox
    if not panel_bbox:
        elapsed = (time.perf_counter() - t0) * 1000
        return [_make_result(
            rule_id="MFG-012",
            rule_name="No Feature on Sheet Edge",
            passed=True,
            severity="PASS",
            message="No panel boundary defined; skipping edge feature check",
            confidence=0.75,
            execution_time_ms=elapsed,
        )]

    px_min, py_min, px_max, py_max = panel_bbox

    for nid, data in mgg.geometry_nodes():
        if data.get("is_outer_boundary"):
            continue
        centroid = data.get("centroid")
        if not centroid:
            continue

        cx, cy = centroid[0], centroid[1]

        # Check if centroid is on any boundary edge (within tolerance)
        on_edge = (
            abs(cx - px_min) <= tolerance
            or abs(cx - px_max) <= tolerance
            or abs(cy - py_min) <= tolerance
            or abs(cy - py_max) <= tolerance
        )

        if on_edge:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append(_make_result(
                rule_id="MFG-012",
                rule_name="No Feature on Sheet Edge",
                passed=False,
                severity="ERROR",
                message=f"Feature {nid} centroid is on the panel boundary",
                confidence=0.75,
                affected_node_ids=[nid],
                evidence={"centroid": list(centroid), "tolerance_mm": tolerance},
                execution_time_ms=elapsed,
            ))

    if not results:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(_make_result(
            rule_id="MFG-012",
            rule_name="No Feature on Sheet Edge",
            passed=True,
            severity="PASS",
            message="No features on sheet edge",
            confidence=0.75,
            execution_time_ms=elapsed,
        ))
    return results


# ---------------------------------------------------------------------------
# Handler registry — maps rule_id -> check function
# ---------------------------------------------------------------------------

MANUFACTURING_HANDLERS: dict[str, Any] = {
    "MFG-001": check_edge_clearance,
    "MFG-002": check_feature_spacing,
    "MFG-003": check_tool_radius_corner,
    "MFG-004": check_pocket_width,
    "MFG-005": check_shelf_pin_grid,
    "MFG-006": check_hinge_cup_edge_distance,
    "MFG-007": check_blind_feature_depth,
    "MFG-008": check_feature_density,
    "MFG-009": check_panel_dimensions,
    "MFG-010": check_confirmat_pair,
    "MFG-011": check_drill_diameter_range,
    "MFG-012": check_no_feature_on_edge,
}
