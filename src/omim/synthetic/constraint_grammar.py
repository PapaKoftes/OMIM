"""Constraint grammar for the generation side.

These margins are intentionally TIGHTER than the validator thresholds so that a
'valid' generated sample never accidentally fails the validator at the boundary:

  MFG-001 edge clearance min ........ 8.0 mm  -> generation margin 8.5 mm
  MFG-002 wall thickness min ........ 3.0 mm  -> generation margin 3.5 mm
  MFG-011 min hole diameter ......... 3.0 mm  -> generation margin 3.2 mm (dia)

The grammar is geometric only: it operates on FeatureSpec / PanelSpec, before
any DXF is written. The deterministic validator remains the gatekeeper.
"""

from __future__ import annotations

import math

from omim.synthetic.models import FeatureSpec, PanelSpec

GENERATION_MARGIN = {
    "edge_clearance_mm": 8.5,    # > MFG-001 min 8.0
    "wall_thickness_mm": 3.5,    # > MFG-002 min 3.0
    "min_diameter_mm": 3.2,      # > MFG-011 min 3.0
}


# ---------------------------------------------------------------------------
# Internal geometry helpers
# ---------------------------------------------------------------------------


def _feature_centroid(feature: FeatureSpec) -> tuple[float, float] | None:
    """Return the centroid of a feature (circle center or polyline mean)."""
    if feature.center is not None:
        return feature.center
    if feature.points:
        xs = [p[0] for p in feature.points]
        ys = [p[1] for p in feature.points]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    return None


def _panel_bounds(panel: PanelSpec) -> tuple[float, float, float, float]:
    """Return (xmin, ymin, xmax, ymax) of the panel boundary."""
    xs = [p[0] for p in panel.boundary_points]
    ys = [p[1] for p in panel.boundary_points]
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------------------
# Constraint predicates
# ---------------------------------------------------------------------------


def satisfies_edge_clearance(
    feature: FeatureSpec, panel: PanelSpec, margin: float | None = None
) -> bool:
    """True iff the feature CENTROID is >= ``margin`` from every panel edge.

    Mirrors MFG-001 exactly, which measures the centroid-to-edge distance (it
    does NOT subtract the radius). Subtracting the radius here would wrongly
    reject large-diameter standard features such as the 35 mm Blum hinge cup,
    whose centroid sits a legitimate 22.5 mm from the edge. Rim containment is
    handled separately by ``within_panel`` (mirrors GEO-007).
    """
    if margin is None:
        margin = GENERATION_MARGIN["edge_clearance_mm"]

    centroid = _feature_centroid(feature)
    if centroid is None:
        return False

    cx, cy = centroid
    xmin, ymin, xmax, ymax = _panel_bounds(panel)

    distances = [
        cx - xmin,  # left
        xmax - cx,  # right
        cy - ymin,  # bottom
        ymax - cy,  # top
    ]
    return min(distances) >= margin


def satisfies_wall_thickness(
    feature: FeatureSpec,
    other_features: list[FeatureSpec],
    margin: float | None = None,
) -> bool:
    """True iff *feature* keeps >= ``margin`` wall thickness to every other circle.

    Wall thickness for two circles is ``center_dist - rA - rB`` (mirrors MFG-002).
    Non-circle features (no center/radius) are ignored.
    """
    if margin is None:
        margin = GENERATION_MARGIN["wall_thickness_mm"]

    if feature.center is None or feature.radius_mm is None:
        return True

    ax, ay = feature.center
    r_a = feature.radius_mm

    for other in other_features:
        if other is feature:
            continue
        if other.center is None or other.radius_mm is None:
            continue
        bx, by = other.center
        r_b = other.radius_mm
        center_dist = math.hypot(ax - bx, ay - by)
        wall = center_dist - r_a - r_b
        if wall < margin:
            return False
    return True


def within_panel(feature: FeatureSpec, panel: PanelSpec) -> bool:
    """True iff the entire feature lies inside the panel boundary.

    For circles the full disc must fit; for polylines every vertex must be
    inside the panel bounds. Mirrors GEO-007 (geometry within panel bounds).
    """
    xmin, ymin, xmax, ymax = _panel_bounds(panel)

    if feature.center is not None and feature.radius_mm is not None:
        cx, cy = feature.center
        r = feature.radius_mm
        return (
            cx - r >= xmin
            and cx + r <= xmax
            and cy - r >= ymin
            and cy + r <= ymax
        )

    if feature.points:
        for px, py in feature.points:
            if not (xmin <= px <= xmax and ymin <= py <= ymax):
                return False
        return True

    return False
