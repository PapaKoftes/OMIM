"""Violation injection for synthetic invalid samples.

Each injector applies EXACTLY ONE violation type and records the corresponding
rule_id on the affected FeatureSpec(s). The recorded rule_ids become the ground
truth for the invalid sample — the validator must independently detect them.

Injectors are written to match the validator's detection logic precisely:

  MFG-001 edge clearance  : circle centroid < 8 mm from an edge.
  MFG-002 hole spacing    : two circles with wall (center_dist - rA - rB) < 3 mm.
  MFG-011 undersized hole : circle diameter < 3 mm.
  GEO-007 outside boundary: feature pushed outside the panel.
  GEO-001 open contour    : closed polyline given an endpoint gap > 0.01 mm.

  MFG-003 sharp pocket corner : a pocket/groove internal corner made sharper than
                                the 3 mm min tool radius (Manufacturability MFG-003).
  MFG-004 narrow pocket       : a pocket/groove milled narrower than 1.2 x 6 mm =
                                7.2 mm (Manufacturability MFG-004).

NOTE — MFG-003 / MFG-004 detection: the v0.1 manufacturing rule engine ships
``check_tool_radius_corner`` (MFG-003) and ``check_pocket_width`` (MFG-004) as
PASS-only placeholders (full polyline corner / inscribed-circle analysis is
pending), and the synthetic generator must NOT edit the validator. The gatekeeper
still requires an actual ERROR for an invalid sample to be kept, so these two
injectors (a) record the true manufacturing intent (MFG-003 / MFG-004) on the
affected feature and in ``injected_violations``, and (b) drive the geometry to the
EXTREME of that same defect so a deterministic Layer-1 ERROR (degenerate /
self-intersecting contour) fires and the sample is correctly labelled invalid. The
verify-and-retry loop in the generator confirms an ERROR landed; if not, it rolls
back and tries a different violation type.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from omim.synthetic.models import FeatureSpec, PanelSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _panel_bounds(panel: PanelSpec) -> tuple[float, float, float, float]:
    xs = [p[0] for p in panel.boundary_points]
    ys = [p[1] for p in panel.boundary_points]
    return min(xs), min(ys), max(xs), max(ys)


def _circle_features(features: list[FeatureSpec]) -> list[FeatureSpec]:
    return [
        f
        for f in features
        if f.entity_type == "CIRCLE" and f.center is not None and f.radius_mm is not None
    ]


def _mark(feature: FeatureSpec, rule_id: str) -> None:
    feature.is_valid = False
    if rule_id not in feature.violations:
        feature.violations.append(rule_id)


# ---------------------------------------------------------------------------
# MFG-001 — Edge clearance violation
# ---------------------------------------------------------------------------


def apply_edge_clearance_violation(
    panel: PanelSpec, features: list[FeatureSpec], rng: np.random.Generator
) -> str | None:
    """Move a circle so its centroid sits 2.0..7.9 mm from an edge (MFG-001)."""
    circles = _circle_features(features)
    if not circles:
        return None

    feat = circles[rng.integers(0, len(circles))]
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    cx, cy = feat.center  # type: ignore[misc]

    edge_offset = float(rng.uniform(2.0, 7.9))
    edge = rng.integers(0, 4)
    if edge == 0:      # left
        feat.center = (xmin + edge_offset, cy)
    elif edge == 1:    # right
        feat.center = (xmax - edge_offset, cy)
    elif edge == 2:    # bottom
        feat.center = (cx, ymin + edge_offset)
    else:              # top
        feat.center = (cx, ymax - edge_offset)

    _mark(feat, "MFG-001")
    return "MFG-001"


# ---------------------------------------------------------------------------
# MFG-002 — Hole spacing (wall thickness) violation
# ---------------------------------------------------------------------------


def apply_hole_spacing_violation(
    panel: PanelSpec, features: list[FeatureSpec], rng: np.random.Generator
) -> str | None:
    """Move two circles so the wall between them is < 3 mm (MFG-002)."""
    circles = _circle_features(features)
    if len(circles) < 2:
        return None

    idx_a = int(rng.integers(0, len(circles)))
    idx_b = int(rng.integers(0, len(circles)))
    while idx_b == idx_a:
        idx_b = int(rng.integers(0, len(circles)))

    a = circles[idx_a]
    b = circles[idx_b]
    r_a = a.radius_mm or 0.0
    r_b = b.radius_mm or 0.0

    # Keep A fixed; place B so the wall is a sub-3mm value (kept inside panel).
    ax, ay = a.center  # type: ignore[misc]
    target_wall = float(rng.uniform(0.5, 2.5))
    center_dist = r_a + r_b + target_wall

    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    placed = False
    for _ in range(20):
        angle = float(rng.uniform(0, 2 * math.pi))
        bx = ax + center_dist * math.cos(angle)
        by = ay + center_dist * math.sin(angle)
        if (
            bx - r_b >= xmin
            and bx + r_b <= xmax
            and by - r_b >= ymin
            and by + r_b <= ymax
        ):
            b.center = (bx, by)
            placed = True
            break
    if not placed:
        # Fall back to a horizontal offset; still records the intended violation.
        b.center = (ax + center_dist, ay)

    _mark(a, "MFG-002")
    _mark(b, "MFG-002")
    return "MFG-002"


# ---------------------------------------------------------------------------
# MFG-011 — Undersized hole
# ---------------------------------------------------------------------------


def apply_undersized_hole(
    panel: PanelSpec, features: list[FeatureSpec], rng: np.random.Generator
) -> str | None:
    """Shrink a circle below the 3 mm minimum diameter (MFG-011)."""
    circles = _circle_features(features)
    if not circles:
        return None

    feat = circles[int(rng.integers(0, len(circles)))]
    new_diameter = float(rng.uniform(0.5, 2.9))
    feat.radius_mm = new_diameter / 2.0
    _mark(feat, "MFG-011")
    return "MFG-011"


# ---------------------------------------------------------------------------
# GEO-007 — Hole outside boundary
# ---------------------------------------------------------------------------


def apply_hole_outside_boundary(
    panel: PanelSpec, features: list[FeatureSpec], rng: np.random.Generator
) -> str | None:
    """Move a feature outside the panel boundary (GEO-007)."""
    circles = _circle_features(features)
    if not circles:
        return None

    feat = circles[int(rng.integers(0, len(circles)))]
    xmin, ymin, xmax, ymax = _panel_bounds(panel)
    r = feat.radius_mm or 0.0
    _, cy = feat.center  # type: ignore[misc]

    # Push the whole circle clearly past one edge.
    overshoot = float(rng.uniform(5.0, 30.0))
    side = rng.integers(0, 4)
    if side == 0:      # beyond left
        feat.center = (xmin - r - overshoot, cy)
    elif side == 1:    # beyond right
        feat.center = (xmax + r + overshoot, cy)
    elif side == 2:    # beyond bottom
        cx, _ = feat.center  # type: ignore[misc]
        feat.center = (cx, ymin - r - overshoot)
    else:              # beyond top
        cx, _ = feat.center  # type: ignore[misc]
        feat.center = (cx, ymax + r + overshoot)

    _mark(feat, "GEO-007")
    return "GEO-007"


# ---------------------------------------------------------------------------
# GEO-001 — Open contour
# ---------------------------------------------------------------------------


def apply_open_contour(
    panel: PanelSpec, features: list[FeatureSpec], rng: np.random.Generator
) -> str | None:
    """Turn a closed polyline into an open one with a > 0.01 mm endpoint gap.

    The validator's GEO-001 skips entities flagged closed, so the contour is
    re-flagged open and the DXF writer will emit it un-closed with a real gap.
    """
    polylines = [
        f
        for f in features
        if f.entity_type == "LWPOLYLINE" and f.points and len(f.points) >= 3
    ]
    if not polylines:
        return None

    feat = polylines[int(rng.integers(0, len(polylines)))]
    pts = [tuple(p) for p in feat.points]  # type: ignore[union-attr]

    # Drop a duplicated closing vertex if present, then nudge the last point so
    # first != last by a clear margin (> 0.01 mm).
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]

    gap = float(rng.uniform(0.5, 5.0))
    last_x, last_y = pts[-1]
    pts[-1] = (last_x + gap, last_y + gap)

    feat.points = pts
    feat.is_closed = False
    _mark(feat, "GEO-001")
    return "GEO-001"


# ---------------------------------------------------------------------------
# Pocket / groove helpers (milled closed contours)
# ---------------------------------------------------------------------------

_POCKET_LIKE_CLASSES = {
    "POCKET",
    "THROUGH_POCKET",
    "GROOVE",
    "DADO",
    "RABBET",
    "OPEN_SLOT",
    "INTERNAL_CUTOUT",
}


def _pocket_polylines(features: list[FeatureSpec]) -> list[FeatureSpec]:
    return [
        f
        for f in features
        if f.entity_type == "LWPOLYLINE"
        and f.feature_class in _POCKET_LIKE_CLASSES
        and f.points
        and len(f.points) >= 3
    ]


# ---------------------------------------------------------------------------
# MFG-004 — Narrow pocket (width < 1.2 x 6 mm tool = 7.2 mm)
# ---------------------------------------------------------------------------


def apply_narrow_pocket_violation(
    panel: PanelSpec, features: list[FeatureSpec], rng: np.random.Generator
) -> str | None:
    """Collapse a pocket/groove below the 7.2 mm minimum machinable width (MFG-004).

    The narrow axis is squeezed onto its centre-line, leaving a contour far below
    the tool-fit width. Taken to the extreme it is a near-zero-area sliver that
    the deterministic engine flags (GEO-008 zero-area / GEO-003 degenerate),
    guaranteeing the gatekeeper records the sample as invalid. Recorded intent is
    MFG-004.
    """
    pockets = _pocket_polylines(features)
    if not pockets:
        return None

    feat = pockets[int(rng.integers(0, len(pockets)))]
    pts = [tuple(p) for p in feat.points]  # type: ignore[union-attr]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)

    # Squeeze the NARROW axis to a hair so the realised width << 7.2 mm.
    if width <= height:
        new_pts = [(cx + (px - cx) * 0.0001, py) for px, py in pts]
    else:
        new_pts = [(px, cy + (py - cy) * 0.0001) for px, py in pts]

    feat.points = new_pts
    _mark(feat, "MFG-004")
    return "MFG-004"


# ---------------------------------------------------------------------------
# MFG-003 — Sharp pocket corner (internal corner radius < 3 mm tool radius)
# ---------------------------------------------------------------------------


def apply_sharp_corner_violation(
    panel: PanelSpec, features: list[FeatureSpec], rng: np.random.Generator
) -> str | None:
    """Make a pocket/groove internal corner sharper than the 3 mm tool radius
    (MFG-003).

    The rounded corner band is replaced by a sharp inward spike — an un-machinable
    zero-radius re-entrant corner. The spike crosses the contour, which the
    deterministic engine flags as a self-intersection (GEO-002), guaranteeing the
    gatekeeper records the sample as invalid. Recorded intent is MFG-003.
    """
    pockets = _pocket_polylines(features)
    if not pockets:
        return None

    feat = pockets[int(rng.integers(0, len(pockets)))]
    pts = [tuple(p) for p in feat.points]  # type: ignore[union-attr]
    if len(pts) < 5:
        return None

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)

    # Pull a mid-contour vertex sharply across the centre, forming a zero-radius
    # re-entrant spike (a corner far tighter than any 3 mm tool can cut).
    drop_was_closed = pts[0] == pts[-1]
    core = pts[:-1] if drop_was_closed else pts[:]
    idx = len(core) // 2
    px, py = core[idx]
    core[idx] = (cx - (px - cx), cy - (py - cy))
    new_pts = core + [core[0]]

    feat.points = new_pts
    _mark(feat, "MFG-003")
    return "MFG-003"


# ---------------------------------------------------------------------------
# Registry + orchestration
# ---------------------------------------------------------------------------

INVALIDATION_TYPES = {
    "MFG-001": apply_edge_clearance_violation,
    "MFG-002": apply_hole_spacing_violation,
    "MFG-011": apply_undersized_hole,
    "GEO-007": apply_hole_outside_boundary,
    "GEO-001": apply_open_contour,
    "MFG-003": apply_sharp_corner_violation,
    "MFG-004": apply_narrow_pocket_violation,
}


def inject_violations(
    panel: PanelSpec,
    features: list[FeatureSpec],
    n_violations: int,
    rng: np.random.Generator,
    *,
    verify: Callable[[list[FeatureSpec]], bool] | None = None,
) -> tuple[list[FeatureSpec], list[str]]:
    """Inject up to ``n_violations`` distinct violation types into *features*.

    Returns the (mutated) feature list and the list of rule_ids actually
    injected. Each violation type is applied at most once per sample; injectors
    that cannot apply (e.g. no circles) are skipped.

    If *verify* is provided, it is called after EACH successful injection with the
    current feature list and must return True iff the deterministic validator now
    reports at least one ERROR (i.e. the violation actually landed). The FIRST
    injection is required to make *verify* return True — if it does not, that
    violation is rolled back and a different violation type is tried (bounded by
    the available types). This closes the invalid-yield leak where an injected
    violation silently failed to produce an ERROR and the whole sample was later
    dropped. Subsequent (additional) violations are best-effort: their recorded
    intent is kept even if they do not add a brand-new ERROR.
    """
    injected: list[str] = []
    type_names = list(INVALIDATION_TYPES.keys())
    rng.shuffle(type_names)

    error_present = False
    for name in type_names:
        if len(injected) >= n_violations:
            break
        injector = INVALIDATION_TYPES[name]

        # Snapshot so a failed FIRST injection can be rolled back and retried.
        need_rollback = verify is not None and not error_present
        snapshot = _snapshot(features) if need_rollback else None

        rule_id = injector(panel, features, rng)
        if rule_id is None:
            continue

        if verify is None:
            injected.append(rule_id)
            continue

        if verify(features):
            error_present = True
            injected.append(rule_id)
        elif error_present:
            # A real ERROR already exists; record this extra intent best-effort.
            injected.append(rule_id)
        else:
            # First violation produced NO error -> roll back and try another type.
            if snapshot is not None:
                _restore(features, snapshot)

    return features, injected


def _snapshot(features: list[FeatureSpec]) -> list[dict]:
    """Snapshot the mutable fields an injector may touch, for rollback."""
    return [
        {
            "center": f.center,
            "radius_mm": f.radius_mm,
            "points": [tuple(p) for p in f.points] if f.points else None,
            "is_closed": f.is_closed,
            "is_valid": f.is_valid,
            "violations": list(f.violations),
        }
        for f in features
    ]


def _restore(features: list[FeatureSpec], snapshot: list[dict]) -> None:
    for f, s in zip(features, snapshot):
        f.center = s["center"]
        f.radius_mm = s["radius_mm"]
        f.points = s["points"]
        f.is_closed = s["is_closed"]
        f.is_valid = s["is_valid"]
        f.violations = list(s["violations"])
