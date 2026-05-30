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


# ---------------------------------------------------------------------------
# Parameter sampling (per spec): the realised diameter for each feature class
# ---------------------------------------------------------------------------


def sample_hole_parameters(feature_class: str, rng: np.random.Generator) -> float:
    """Return a sampled DIAMETER (mm) for a hole feature class.

    SHELF_PIN  -> normal(5.0, 0.05)
    HINGE      -> normal(35.0, 0.1)
    CONFIRMAT  -> normal(7.0, 0.05)
    DOWEL      -> choice([8, 10])
    THROUGH    -> uniform(4, 30)
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
        return float(rng.uniform(4.0, 30.0))
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
# Dispatch by feature class (single-feature generators)
# ---------------------------------------------------------------------------

SINGLE_FEATURE_GENERATORS = {
    "HINGE_CUP_HOLE": generate_hinge_cup,
    "DOWEL_HOLE": generate_dowel,
    "THROUGH_HOLE": generate_through_hole,
}
