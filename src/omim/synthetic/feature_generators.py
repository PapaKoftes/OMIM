"""Feature generators grounded in REAL manufacturer standards.

The numeric constants here ARE the ground truth — they come from published
manufacturer / standards documents, not random geometry:

  - System 32 / 32mm cabinet system: shelf-pin column setback 37 mm, 32 mm pitch,
    5 mm diameter pins (Häfele System 32, Cabinet 32mm).
  - Blum CLIP top concealed hinge: 35 mm cup diameter, 22.5 mm cup-edge distance
    (Blum 70.1900.AC boring pattern).
  - Häfele Confirmat / DIN 68871: 7 mm body bore.
  - DIN 7 dowels: 8 mm or 10 mm diameter.

Each generator places features with bounded retry against the constraint grammar
and returns ``None`` (or an empty list) when placement fails (error E-001).
"""

from __future__ import annotations

import math

import numpy as np

from omim.synthetic.constraint_grammar import (
    GENERATION_MARGIN,
    satisfies_edge_clearance,
    satisfies_wall_thickness,
    within_panel,
)
from omim.synthetic.models import FeatureSpec, PanelSpec

MAX_PLACEMENT_ATTEMPTS = 10

# Layer names (match dxf_writer FEATURE_CLASS_TO_LAYER / parser conventions).
DRILL_LAYER = "DRILL"
CUT_LAYER = "CUT"
POCKET_LAYER = "POCKET"

# ---------------------------------------------------------------------------
# Milled-feature constants (grounded in Manufacturability_Validation MFG-003/004
# and Feature_Taxonomy MILLED_FEATURES dimension tables).
# ---------------------------------------------------------------------------

# MFG-004: pocket width >= default_tool_diameter (6 mm) x 1.2 = 7.2 mm.
# MFG-003: internal corner radius >= min_tool_radius 3 mm.
# Generation margins sit comfortably ABOVE both thresholds so VALID milled
# features never fail the validator at the boundary.
MIN_POCKET_WIDTH_MM = 8.0          # > MFG-004 min 7.2 mm
POCKET_CORNER_RADIUS_MM = 3.5      # > MFG-003 min 3.0 mm
CORNER_ARC_SEGMENTS = 4            # vertices used to approximate a rounded corner

# GROOVE (Feature_Taxonomy): width 4-15 mm, depth 6-12 mm, aspect ratio > 5.
GROOVE_WIDTH_RANGE_MM = (8.0, 12.0)
GROOVE_ASPECT_MIN = 6.0            # length >> width (> 5 per taxonomy)
GROOVE_DEPTH_RANGE_MM = (6.0, 12.0)

# RABBET (Feature_Taxonomy): L-notch along an edge, ~9x12 / 12x12 mm.
RABBET_DEPTH_RANGE_MM = (9.0, 12.0)

# INTERNAL_CUTOUT / THROUGH_POCKET: closed window inside the panel.
INTERNAL_CUTOUT_SIZE_RANGE_MM = (40.0, 120.0)
THROUGH_POCKET_SIZE_RANGE_MM = (20.0, 80.0)

# BLIND_HOLE: a drilled circle that does not pass through (depth metadata).
# Diameter is held in the 11.1-13.9 mm gap BETWEEN the catalog hardware bands
# (Confirmat-head 10 mm +-1 and dowel/Confirmat 15 mm +-1) so a blind hole is a
# genuinely non-catalog generic bore and never pollutes a catalog diameter
# cluster (corpus CLUSTER_TOLERANCE_MM = 1.0 about 5/7/8/10/15/35).
BLIND_HOLE_DIAMETER_RANGE_MM = (11.5, 13.5)

# COUNTERSINK / COUNTERBORE: pilot + enlargement (ratio grounded in standards).
# The visible enlargement diameter is likewise kept in the 11.1-13.9 mm catalog
# gap so these recesses do not collide with the hardware-diameter clusters.
COUNTERSINK_PILOT_DIAMETER_MM = 6.0
COUNTERSINK_OUTER_RATIO = 2.0      # ISO 10642 ~2.0 outer/inner -> 12 mm outer
COUNTERBORE_OUTER_DIAMETER_MM = 13.0

# System 32 constants
SYSTEM32_SETBACK_MM = 37.0
SYSTEM32_PITCH_MM = 32.0
SYSTEM32_START_Y_MM = 37.0
SHELF_PIN_RADIUS_MM = 2.5  # 5 mm diameter

# Blum CLIP hinge constants
HINGE_EDGE_DISTANCE_MM = 22.5
HINGE_RADIUS_MM = 17.5  # 35 mm diameter

# Confirmat / DIN 68871
CONFIRMAT_RADIUS_MM = 3.5  # 7 mm diameter

# DIN 7 dowels
DOWEL_DIAMETERS_MM = [8.0, 10.0]

# Catalog hardware diameters (mm) and the +-1 mm band the corpus clusterer gates
# on (omim.corpus CLUSTER_TOLERANCE_MM). A GENERIC through hole must not land in
# any of these bands, otherwise it pollutes a standard hardware cluster's mean.
# The clusterer documents that generic through-holes belong in its *unclustered*
# bucket; we honour that here by resampling THROUGH_HOLE out of the catalog bands.
_CATALOG_DIAMETER_CENTERS_MM = (5.0, 7.0, 8.0, 10.0, 15.0, 35.0)
_CATALOG_BAND_HALF_WIDTH_MM = 1.05  # slightly > corpus tolerance 1.0 for safety


def _in_catalog_band(diameter_mm: float) -> bool:
    return any(
        abs(diameter_mm - c) <= _CATALOG_BAND_HALF_WIDTH_MM
        for c in _CATALOG_DIAMETER_CENTERS_MM
    )


# ---------------------------------------------------------------------------
# Parameter sampling (per spec): the realised diameter for each feature class
# ---------------------------------------------------------------------------


def sample_hole_parameters(feature_class: str, rng: np.random.Generator) -> float:
    """Return a sampled DIAMETER (mm) for a hole feature class.

    SHELF_PIN  -> normal(5.0, 0.05)
    HINGE      -> normal(35.0, 0.1)
    CONFIRMAT  -> normal(7.0, 0.05)
    DOWEL      -> choice([8, 10])
    THROUGH    -> uniform(4, 30), resampled so it never lands in a catalog
                  hardware band (it is a GENERIC bore, not standard hardware).
    """
    if feature_class == "SHELF_PIN_HOLE":
        return float(rng.normal(5.0, 0.05))
    if feature_class == "HINGE_CUP_HOLE":
        return float(rng.normal(35.0, 0.1))
    if feature_class == "CONFIRMAT_HOLE":
        return float(rng.normal(7.0, 0.05))
    if feature_class == "DOWEL_HOLE":
        return float(rng.choice(DOWEL_DIAMETERS_MM))
    if feature_class == "THROUGH_HOLE":
        # Generic bore: resample out of the catalog hardware bands (bounded
        # tries; the bands cover < half of [4, 30] so this converges fast).
        for _ in range(12):
            d = float(rng.uniform(4.0, 30.0))
            if not _in_catalog_band(d):
                return d
        return d
    # Fallback: a generic small hole well above the min-diameter margin.
    return float(rng.uniform(4.0, 12.0))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _panel_bounds(panel: PanelSpec) -> tuple[float, float, float, float]:
    xs = [p[0] for p in panel.boundary_points]
    ys = [p[1] for p in panel.boundary_points]
    return min(xs), min(ys), max(xs), max(ys)


def _placeable(
    feature: FeatureSpec, panel: PanelSpec, existing: list[FeatureSpec]
) -> bool:
    """Constraint-grammar pre-check for a candidate feature."""
    return (
        within_panel(feature, panel)
        and satisfies_edge_clearance(feature, panel)
        and satisfies_wall_thickness(feature, existing)
    )


# ---------------------------------------------------------------------------
# Profile cut — always present (panel outer boundary on CUT layer)
# ---------------------------------------------------------------------------


def generate_profile_cut(panel: PanelSpec) -> FeatureSpec:
    """Outer boundary closed polyline on the CUT layer (PROFILE_CUT)."""
    pts = [tuple(p) for p in panel.boundary_points]
    # Ensure closed ring (first point repeated at end) for a clean closed contour.
    if pts[0] != pts[-1]:
        pts = pts + [pts[0]]
    return FeatureSpec(
        feature_class="PROFILE_CUT",
        entity_type="LWPOLYLINE",
        points=pts,
        is_closed=True,
        layer=CUT_LAYER,
        is_valid=True,
    )


# ---------------------------------------------------------------------------
# Shelf pin group — System 32 column
# ---------------------------------------------------------------------------


def generate_shelf_pin_group(
    panel: PanelSpec, rng: np.random.Generator
) -> list[FeatureSpec]:
    """Generate a System 32 shelf-pin column (3..9 holes, 32 mm pitch).

    Column x is 37 mm from the left or right edge; rows start at y=37 and step
    by 32 mm. Holes that would breach edge clearance are dropped, and a group is
    only returned if at least 3 valid holes are produced.

    Source: Häfele System 32 / Cabinet 32mm.
    """
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    margin = GENERATION_MARGIN["edge_clearance_mm"]

    # Choose left or right column.
    if rng.random() < 0.5:
        column_x = xmin + SYSTEM32_SETBACK_MM
    else:
        column_x = xmax - SYSTEM32_SETBACK_MM

    desired_count = int(rng.integers(3, 10))  # 3..9 inclusive
    start_y = ymin + SYSTEM32_START_Y_MM

    group_id = f"shelfpin-{int(rng.integers(0, 1_000_000)):06d}"
    features: list[FeatureSpec] = []

    for i in range(desired_count):
        y = start_y + i * SYSTEM32_PITCH_MM
        diameter = sample_hole_parameters("SHELF_PIN_HOLE", rng)
        radius = diameter / 2.0
        feat = FeatureSpec(
            feature_class="SHELF_PIN_HOLE",
            entity_type="CIRCLE",
            center=(float(column_x), float(y)),
            radius_mm=float(radius),
            layer=DRILL_LAYER,
            group_id=group_id,
            is_valid=True,
        )
        # Stop the column once it would run past the top clearance band.
        if (ymax - y) - radius < margin:
            break
        if _placeable(feat, panel, features):
            features.append(feat)

    # System 32 rows are a pattern of >= 3; drop a too-short column.
    if len(features) < 3:
        return []
    return features


# ---------------------------------------------------------------------------
# Hinge cup — Blum CLIP
# ---------------------------------------------------------------------------


def generate_hinge_cup(
    panel: PanelSpec, rng: np.random.Generator, edge: str | None = None
) -> FeatureSpec | None:
    """Generate a Blum CLIP hinge cup (35 mm dia, 22.5 mm cup-edge distance).

    x is 22.5 mm from the left or right edge; y is sampled in [80, height-80].

    Source: Blum 70.1900.AC.
    """
    xmin, ymin, xmax, ymax = _panel_bounds(panel)

    if edge is None:
        edge = "left" if rng.random() < 0.5 else "right"

    if edge == "left":
        cx = xmin + HINGE_EDGE_DISTANCE_MM
    else:
        cx = xmax - HINGE_EDGE_DISTANCE_MM

    diameter = sample_hole_parameters("HINGE_CUP_HOLE", rng)
    radius = diameter / 2.0

    y_lo = ymin + 80.0
    y_hi = ymax - 80.0
    if y_hi <= y_lo:
        return None

    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        cy = float(rng.uniform(y_lo, y_hi))
        feat = FeatureSpec(
            feature_class="HINGE_CUP_HOLE",
            entity_type="CIRCLE",
            center=(float(cx), cy),
            radius_mm=float(radius),
            layer=DRILL_LAYER,
            is_valid=True,
        )
        if _placeable(feat, panel, []):
            return feat
    return None


# ---------------------------------------------------------------------------
# Confirmat pair — Häfele / DIN 68871
# ---------------------------------------------------------------------------


def generate_confirmat_pair(
    panel: PanelSpec, rng: np.random.Generator
) -> list[FeatureSpec]:
    """Generate a pair of 7 mm Confirmat holes near an edge.

    Source: Häfele Confirmat, DIN 68871.
    """
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    margin = GENERATION_MARGIN["edge_clearance_mm"]
    group_id = f"confirmat-{int(rng.integers(0, 1_000_000)):06d}"

    # Place the pair as a short column set in from one vertical edge.
    if rng.random() < 0.5:
        cx = xmin + max(margin + CONFIRMAT_RADIUS_MM, 16.0)
    else:
        cx = xmax - max(margin + CONFIRMAT_RADIUS_MM, 16.0)

    features: list[FeatureSpec] = []
    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        base_y = float(rng.uniform(ymin + margin + 20.0, ymax - margin - 20.0 - 64.0))
        if base_y <= ymin:
            continue
        candidate: list[FeatureSpec] = []
        ok = True
        for offset in (0.0, 64.0):  # two holes 64 mm apart (typical pair spacing)
            diameter = sample_hole_parameters("CONFIRMAT_HOLE", rng)
            radius = diameter / 2.0
            feat = FeatureSpec(
                feature_class="CONFIRMAT_HOLE",
                entity_type="CIRCLE",
                center=(float(cx), base_y + offset),
                radius_mm=float(radius),
                layer=DRILL_LAYER,
                group_id=group_id,
                is_valid=True,
            )
            if not _placeable(feat, panel, candidate):
                ok = False
                break
            candidate.append(feat)
        if ok and len(candidate) == 2:
            features = candidate
            break

    return features


# ---------------------------------------------------------------------------
# Dowel — DIN 7
# ---------------------------------------------------------------------------


def generate_dowel(
    panel: PanelSpec, rng: np.random.Generator
) -> FeatureSpec | None:
    """Generate an 8 mm or 10 mm dowel hole (DIN 7)."""
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    margin = GENERATION_MARGIN["edge_clearance_mm"]

    diameter = sample_hole_parameters("DOWEL_HOLE", rng)
    radius = diameter / 2.0

    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        cx = float(rng.uniform(xmin + margin + radius, xmax - margin - radius))
        cy = float(rng.uniform(ymin + margin + radius, ymax - margin - radius))
        feat = FeatureSpec(
            feature_class="DOWEL_HOLE",
            entity_type="CIRCLE",
            center=(cx, cy),
            radius_mm=float(radius),
            layer=DRILL_LAYER,
            is_valid=True,
        )
        if _placeable(feat, panel, []):
            return feat
    return None


# ---------------------------------------------------------------------------
# Through hole — generic 4..30 mm
# ---------------------------------------------------------------------------


def generate_through_hole(
    panel: PanelSpec, rng: np.random.Generator
) -> FeatureSpec | None:
    """Generate a generic through hole (4..30 mm diameter)."""
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    margin = GENERATION_MARGIN["edge_clearance_mm"]

    diameter = sample_hole_parameters("THROUGH_HOLE", rng)
    radius = diameter / 2.0

    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        cx = float(rng.uniform(xmin + margin + radius, xmax - margin - radius))
        cy = float(rng.uniform(ymin + margin + radius, ymax - margin - radius))
        feat = FeatureSpec(
            feature_class="THROUGH_HOLE",
            entity_type="CIRCLE",
            center=(cx, cy),
            radius_mm=float(radius),
            layer=DRILL_LAYER,
            is_valid=True,
        )
        if _placeable(feat, panel, []):
            return feat
    return None


# ---------------------------------------------------------------------------
# Geometry helpers for milled / profile contours
# ---------------------------------------------------------------------------


def _rounded_rect_points(
    cx: float,
    cy: float,
    width: float,
    height: float,
    corner_radius: float,
) -> list[tuple[float, float]]:
    """Return a CLOSED rounded-rectangle polyline centred at (cx, cy).

    Corners are approximated by ``CORNER_ARC_SEGMENTS`` short chords so the
    realised internal corner radius equals ``corner_radius`` (>= MFG-003 min tool
    radius). The first vertex is repeated at the end (closed ring).
    """
    r = max(0.0, min(corner_radius, width / 2.0 - 0.01, height / 2.0 - 0.01))
    hw = width / 2.0
    hh = height / 2.0
    corners = [
        (cx + hw - r, cy + hh - r, 0.0),      # top-right, sweep 0 -> 90
        (cx - hw + r, cy + hh - r, 90.0),     # top-left
        (cx - hw + r, cy - hh + r, 180.0),    # bottom-left
        (cx + hw - r, cy - hh + r, 270.0),    # bottom-right
    ]
    pts: list[tuple[float, float]] = []
    for ccx, ccy, start_deg in corners:
        for s in range(CORNER_ARC_SEGMENTS + 1):
            ang = math.radians(start_deg + 90.0 * s / CORNER_ARC_SEGMENTS)
            pts.append((ccx + r * math.cos(ang), ccy + r * math.sin(ang)))
    pts.append(pts[0])  # close the ring
    return _as_clockwise(pts)


def _signed_area(pts: list[tuple[float, float]]) -> float:
    """Twice the signed area (shoelace); > 0 == CCW, < 0 == CW."""
    ring = pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts
    s = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s


def _as_clockwise(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return *pts* oriented CLOCKWISE.

    Interior (non-boundary) contours must be CW (GEO-005 contour orientation);
    emitting CW here keeps every VALID milled/profile feature warning-free.
    """
    if _signed_area(pts) > 0:  # currently CCW -> reverse
        return list(reversed(pts))
    return pts


def _polyline_centroid(pts: list[tuple[float, float]]) -> tuple[float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _polyline_within(pts: list[tuple[float, float]], panel: PanelSpec) -> bool:
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    return all(xmin <= px <= xmax and ymin <= py <= ymax for px, py in pts)


def _polyline_centroid_clear(
    pts: list[tuple[float, float]], panel: PanelSpec, margin: float
) -> bool:
    """Mirror MFG-001 (centroid >= margin from every edge) for a polyline."""
    cx, cy = _polyline_centroid(pts)
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    return min(cx - xmin, xmax - cx, cy - ymin, ymax - cy) >= margin


# ---------------------------------------------------------------------------
# POCKET / THROUGH_POCKET — closed rounded-corner rectangle (POCKET layer)
# ---------------------------------------------------------------------------


def _generate_closed_rect_feature(
    panel: PanelSpec,
    rng: np.random.Generator,
    feature_class: str,
    layer: str,
    size_range: tuple[float, float],
    *,
    with_depth: bool,
) -> FeatureSpec | None:
    """Shared placement of a closed rounded rectangle satisfying MFG-003/004."""
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    margin = GENERATION_MARGIN["edge_clearance_mm"]
    lo, hi = size_range

    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        width = float(rng.uniform(lo, hi))
        height = float(rng.uniform(lo, hi))
        if (xmax - xmin) < width + 2 * margin or (ymax - ymin) < height + 2 * margin:
            continue
        cx = float(rng.uniform(xmin + margin + width / 2, xmax - margin - width / 2))
        cy = float(rng.uniform(ymin + margin + height / 2, ymax - margin - height / 2))
        pts = _rounded_rect_points(cx, cy, width, height, POCKET_CORNER_RADIUS_MM)
        if _polyline_within(pts, panel) and _polyline_centroid_clear(pts, panel, margin):
            depth = (
                float(rng.uniform(5.0, max(6.0, panel.thickness_mm - 2.0)))
                if with_depth
                else None
            )
            return FeatureSpec(
                feature_class=feature_class,
                entity_type="LWPOLYLINE",
                points=pts,
                is_closed=True,
                layer=layer,
                depth_mm=depth,
                is_valid=True,
            )
    return None


def generate_pocket(panel: PanelSpec, rng: np.random.Generator) -> FeatureSpec | None:
    """Closed rounded-rectangle milled recess on the POCKET layer.

    Width/height >= MIN_POCKET_WIDTH_MM (> MFG-004 7.2 mm) with corner radius
    POCKET_CORNER_RADIUS_MM (> MFG-003 3 mm), so a VALID pocket satisfies both
    manufacturing rules. Source: Feature_Taxonomy POCKET; CNC routing.
    """
    return _generate_closed_rect_feature(
        panel, rng, "POCKET", POCKET_LAYER,
        (MIN_POCKET_WIDTH_MM, max(MIN_POCKET_WIDTH_MM + 1.0, 60.0)), with_depth=True,
    )


def generate_through_pocket(
    panel: PanelSpec, rng: np.random.Generator
) -> FeatureSpec | None:
    """Closed rounded-rectangle recess passing fully through (POCKET layer).

    Source: Feature_Taxonomy THROUGH_POCKET (closed contour inside panel).
    """
    return _generate_closed_rect_feature(
        panel, rng, "THROUGH_POCKET", POCKET_LAYER,
        THROUGH_POCKET_SIZE_RANGE_MM, with_depth=False,
    )


def generate_internal_cutout(
    panel: PanelSpec, rng: np.random.Generator
) -> FeatureSpec | None:
    """Closed rectangular window fully inside the panel, on the CUT layer.

    Smaller than the panel so it is never mistaken for the boundary.
    Source: Feature_Taxonomy INTERNAL_CUTOUT (closed contour inside panel, cut).
    """
    return _generate_closed_rect_feature(
        panel, rng, "INTERNAL_CUTOUT", CUT_LAYER,
        INTERNAL_CUTOUT_SIZE_RANGE_MM, with_depth=False,
    )


# ---------------------------------------------------------------------------
# GROOVE / DADO — long narrow closed slot (POCKET layer)
# ---------------------------------------------------------------------------


def _generate_slot(
    panel: PanelSpec,
    rng: np.random.Generator,
    feature_class: str,
    *,
    perpendicular_to_long_axis: bool,
) -> FeatureSpec | None:
    """Shared long-narrow-slot generator for GROOVE / DADO (aspect > 5)."""
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    margin = GENERATION_MARGIN["edge_clearance_mm"]
    panel_w = xmax - xmin
    panel_h = ymax - ymin
    long_axis_is_x = panel_w >= panel_h
    run_along_x = long_axis_is_x != perpendicular_to_long_axis

    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        width = float(rng.uniform(*GROOVE_WIDTH_RANGE_MM))  # the NARROW dimension
        aspect = float(rng.uniform(GROOVE_ASPECT_MIN, GROOVE_ASPECT_MIN + 6.0))
        length = width * aspect
        if run_along_x:
            slot_w, slot_h = length, width
        else:
            slot_w, slot_h = width, length
        if panel_w < slot_w + 2 * margin or panel_h < slot_h + 2 * margin:
            continue
        cx = float(rng.uniform(xmin + margin + slot_w / 2, xmax - margin - slot_w / 2))
        cy = float(rng.uniform(ymin + margin + slot_h / 2, ymax - margin - slot_h / 2))
        corner_r = min(slot_w, slot_h) / 2.0 - 0.01  # true rounded slot ends
        pts = _rounded_rect_points(cx, cy, slot_w, slot_h, corner_r)
        if _polyline_within(pts, panel) and _polyline_centroid_clear(pts, panel, margin):
            return FeatureSpec(
                feature_class=feature_class,
                entity_type="LWPOLYLINE",
                points=pts,
                is_closed=True,
                layer=POCKET_LAYER,
                depth_mm=float(rng.uniform(*GROOVE_DEPTH_RANGE_MM)),
                is_valid=True,
            )
    return None


def generate_groove(panel: PanelSpec, rng: np.random.Generator) -> FeatureSpec | None:
    """Long narrow slot along the panel's long axis (GROOVE)."""
    return _generate_slot(panel, rng, "GROOVE", perpendicular_to_long_axis=False)


def generate_dado(panel: PanelSpec, rng: np.random.Generator) -> FeatureSpec | None:
    """Groove perpendicular to the panel's long axis (DADO)."""
    return _generate_slot(panel, rng, "DADO", perpendicular_to_long_axis=True)


# ---------------------------------------------------------------------------
# RABBET / OPEN_SLOT — recess at the panel edge (POCKET layer)
# ---------------------------------------------------------------------------


def generate_rabbet(panel: PanelSpec, rng: np.random.Generator) -> FeatureSpec | None:
    """L-notch recess along a panel edge (RABBET / REBATE).

    Realised as a closed rectangle with ONE side coincident with a panel edge.
    Closed (so it does not trip GEO-001) with its centroid inboard (so MFG-012
    feature-on-edge is not triggered). Source: Feature_Taxonomy RABBET (~9x12 mm).
    """
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    panel_w = xmax - xmin
    panel_h = ymax - ymin

    depth = float(rng.uniform(*RABBET_DEPTH_RANGE_MM))   # how far IN from the edge
    length = float(rng.uniform(40.0, 120.0))             # run ALONG the edge

    edge = int(rng.integers(0, 4))
    if edge in (0, 1):  # left / right edge
        if panel_h < length + 2.0 or panel_w < depth + 2.0:
            return None
        y0 = float(rng.uniform(ymin + 1.0, ymax - length - 1.0))
        y1 = y0 + length
        x0, x1 = (xmin, xmin + depth) if edge == 0 else (xmax - depth, xmax)
    else:  # bottom / top edge
        if panel_w < length + 2.0 or panel_h < depth + 2.0:
            return None
        x0 = float(rng.uniform(xmin + 1.0, xmax - length - 1.0))
        x1 = x0 + length
        y0, y1 = (ymin, ymin + depth) if edge == 2 else (ymax - depth, ymax)

    pts = _as_clockwise([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
    if not _polyline_within(pts, panel):
        return None
    return FeatureSpec(
        feature_class="RABBET",
        entity_type="LWPOLYLINE",
        points=pts,
        is_closed=True,
        layer=POCKET_LAYER,
        depth_mm=depth,
        is_valid=True,
    )


def generate_open_slot(panel: PanelSpec, rng: np.random.Generator) -> FeatureSpec | None:
    """Elongated slot opening at a panel edge (OPEN_SLOT).

    Realised as a closed elongated rectangle whose short side lies on a panel edge
    — a slot milled from the edge inward. Closed (no GEO-001), centroid inboard
    (no MFG-012). Source: Feature_Taxonomy OPEN_SLOT.
    """
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    panel_w = xmax - xmin
    panel_h = ymax - ymin

    width = float(rng.uniform(*GROOVE_WIDTH_RANGE_MM))   # narrow dimension
    depth = float(rng.uniform(30.0, 90.0))               # how far in from edge

    edge = int(rng.integers(0, 4))
    if edge in (0, 1):  # opens from left / right
        if panel_w < depth + 2.0 or panel_h < width + 2.0:
            return None
        cy = float(rng.uniform(ymin + width / 2 + 1.0, ymax - width / 2 - 1.0))
        y0, y1 = cy - width / 2, cy + width / 2
        x0, x1 = (xmin, xmin + depth) if edge == 0 else (xmax - depth, xmax)
    else:  # opens from bottom / top
        if panel_h < depth + 2.0 or panel_w < width + 2.0:
            return None
        cx = float(rng.uniform(xmin + width / 2 + 1.0, xmax - width / 2 - 1.0))
        x0, x1 = cx - width / 2, cx + width / 2
        y0, y1 = (ymin, ymin + depth) if edge == 2 else (ymax - depth, ymax)

    pts = _as_clockwise([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])
    if not _polyline_within(pts, panel):
        return None
    return FeatureSpec(
        feature_class="OPEN_SLOT",
        entity_type="LWPOLYLINE",
        points=pts,
        is_closed=True,
        layer=POCKET_LAYER,
        is_valid=True,
    )


# ---------------------------------------------------------------------------
# BLIND_HOLE — drilled circle with depth metadata (DRILL layer)
# ---------------------------------------------------------------------------


def generate_blind_hole(panel: PanelSpec, rng: np.random.Generator) -> FeatureSpec | None:
    """Circular hole that does not pass through; carries depth metadata.

    Source: Feature_Taxonomy BLIND_HOLE (requires depth metadata).
    """
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    margin = GENERATION_MARGIN["edge_clearance_mm"]
    diameter = float(rng.uniform(*BLIND_HOLE_DIAMETER_RANGE_MM))
    radius = diameter / 2.0
    # Blind depth stays under MFG-007's 0.75 x thickness so a valid sample passes.
    depth = float(rng.uniform(2.0, max(2.0, 0.7 * panel.thickness_mm)))

    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        cx = float(rng.uniform(xmin + margin + radius, xmax - margin - radius))
        cy = float(rng.uniform(ymin + margin + radius, ymax - margin - radius))
        feat = FeatureSpec(
            feature_class="BLIND_HOLE",
            entity_type="CIRCLE",
            center=(cx, cy),
            radius_mm=radius,
            layer=DRILL_LAYER,
            depth_mm=depth,
            is_valid=True,
        )
        if _placeable(feat, panel, []):
            return feat
    return None


# ---------------------------------------------------------------------------
# COUNTERSINK / COUNTERBORE — fastener-recess circle (DRILL layer)
# ---------------------------------------------------------------------------
#
# NOTE on representation: the taxonomy describes these as *concentric* circles
# (pilot + enlargement). In a 2D cut file the manufacturable, validator-passing
# representation is the visible enlargement circle on the recess layer carrying
# the feature_class + depth metadata. A second concentric circle is NOT emitted
# because MFG-002 (feature spacing) treats every circle pair as drill holes and
# concentric circles have wall = -(r_a + r_b) < 3 mm -> an MFG-002 ERROR that the
# gatekeeper would (correctly) reject. The enlargement diameter / standard pilot
# ratio is recorded for downstream concentric inference.


def _generate_recess_circle(
    panel: PanelSpec,
    rng: np.random.Generator,
    feature_class: str,
    diameter: float,
) -> FeatureSpec | None:
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    margin = GENERATION_MARGIN["edge_clearance_mm"]
    radius = diameter / 2.0
    depth = float(rng.uniform(2.0, max(2.0, 0.6 * panel.thickness_mm)))

    for _ in range(MAX_PLACEMENT_ATTEMPTS):
        cx = float(rng.uniform(xmin + margin + radius, xmax - margin - radius))
        cy = float(rng.uniform(ymin + margin + radius, ymax - margin - radius))
        feat = FeatureSpec(
            feature_class=feature_class,
            entity_type="CIRCLE",
            center=(cx, cy),
            radius_mm=radius,
            layer=DRILL_LAYER,
            depth_mm=depth,
            is_valid=True,
        )
        if _placeable(feat, panel, []):
            return feat
    return None


def generate_countersink(
    panel: PanelSpec, rng: np.random.Generator
) -> FeatureSpec | None:
    """Countersink recess (conical enlargement, ratio ~2.0). Source: ISO 10642."""
    outer_d = COUNTERSINK_PILOT_DIAMETER_MM * COUNTERSINK_OUTER_RATIO
    return _generate_recess_circle(panel, rng, "COUNTERSINK", outer_d)


def generate_counterbore(
    panel: PanelSpec, rng: np.random.Generator
) -> FeatureSpec | None:
    """Counterbore recess (cylindrical enlargement). Source: ISO 6194."""
    return _generate_recess_circle(
        panel, rng, "COUNTERBORE", COUNTERBORE_OUTER_DIAMETER_MM
    )


# ---------------------------------------------------------------------------
# Dispatch by feature class (single-feature generators)
# ---------------------------------------------------------------------------

SINGLE_FEATURE_GENERATORS = {
    "HINGE_CUP_HOLE": generate_hinge_cup,
    "DOWEL_HOLE": generate_dowel,
    "THROUGH_HOLE": generate_through_hole,
    "BLIND_HOLE": generate_blind_hole,
    "COUNTERSINK": generate_countersink,
    "COUNTERBORE": generate_counterbore,
    "POCKET": generate_pocket,
    "THROUGH_POCKET": generate_through_pocket,
    "GROOVE": generate_groove,
    "DADO": generate_dado,
    "RABBET": generate_rabbet,
    "OPEN_SLOT": generate_open_slot,
    "INTERNAL_CUTOUT": generate_internal_cutout,
}
