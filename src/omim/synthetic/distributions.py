"""Realistic manufacturing distributions for synthetic panel generation.

These distributions are derived from the spec (NOT uniform) and reflect real
cabinetry panel populations. All sampling takes an explicit numpy ``rng`` so
generation stays fully deterministic (seed + sample index).

Realism references:
  - R-004: panel-type -> allowed feature classes
  - Cabinet 32mm system / Häfele / Blum hardware standards
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Panel type distribution
# ---------------------------------------------------------------------------

PANEL_TYPE_DISTRIBUTION: dict[str, float] = {
    "generic": 0.35,
    "side_panel": 0.30,
    "shelf": 0.15,
    "door": 0.10,
    "back_panel": 0.05,
    "bottom_top": 0.05,
}


# ---------------------------------------------------------------------------
# Dimension distributions (realistic, weighted — NOT uniform)
# ---------------------------------------------------------------------------

WIDTH_VALUES = [300, 400, 450, 500, 600, 800, 900, 1000, 1200]
WIDTH_WEIGHTS = [0.10, 0.10, 0.10, 0.15, 0.25, 0.10, 0.10, 0.05, 0.05]

HEIGHT_VALUES = [300, 600, 720, 900, 1980, 2100, 2200]
HEIGHT_WEIGHTS = [0.10, 0.20, 0.25, 0.10, 0.15, 0.10, 0.10]

THICKNESS_VALUES = [12.0, 15.0, 16.0, 18.0, 22.0, 25.0]
THICKNESS_WEIGHTS = [0.05, 0.10, 0.15, 0.55, 0.10, 0.05]


# ---------------------------------------------------------------------------
# Panel-type -> allowed feature classes (Realism R-004)
# ---------------------------------------------------------------------------

PANEL_TYPE_ALLOWED_FEATURES: dict[str, list[str]] = {
    "side_panel": [
        "SHELF_PIN_HOLE",
        "HINGE_CUP_HOLE",
        "DOWEL_HOLE",
        "CONFIRMAT_HOLE",
        "THROUGH_HOLE",
        "BLIND_HOLE",
        "GROOVE",
        "DADO",
        "RABBET",
        "POCKET",
    ],
    "door": ["HINGE_CUP_HOLE", "THROUGH_HOLE", "POCKET", "INTERNAL_CUTOUT", "COUNTERSINK"],
    "shelf": ["THROUGH_HOLE", "DOWEL_HOLE", "GROOVE", "DADO", "RABBET", "BLIND_HOLE"],
    "back_panel": ["THROUGH_HOLE", "GROOVE", "INTERNAL_CUTOUT"],
    "bottom_top": [
        "DOWEL_HOLE",
        "CONFIRMAT_HOLE",
        "THROUGH_HOLE",
        "GROOVE",
        "RABBET",
        "OPEN_SLOT",
    ],
    "generic": ["ALL"],
}

# Every concrete feature class the generator can place (used when panel allows "ALL").
ALL_FEATURE_CLASSES: list[str] = [
    # Hole features (dominant population)
    "SHELF_PIN_HOLE",
    "HINGE_CUP_HOLE",
    "DOWEL_HOLE",
    "CONFIRMAT_HOLE",
    "THROUGH_HOLE",
    "BLIND_HOLE",
    "COUNTERSINK",
    "COUNTERBORE",
    # Milled features (less common)
    "POCKET",
    "THROUGH_POCKET",
    "GROOVE",
    "DADO",
    "RABBET",
    "OPEN_SLOT",
    # Profile features
    "INTERNAL_CUTOUT",
]

# Relative sampling weight per class (used for the weighted per-feature draw).
# Holes dominate; milled/profile features are deliberately rarer
# (Dataset_Distribution_Policy). Classes absent here default to weight 1.0.
FEATURE_CLASS_WEIGHTS: dict[str, float] = {
    "SHELF_PIN_HOLE": 6.0,
    "HINGE_CUP_HOLE": 4.0,
    "DOWEL_HOLE": 5.0,
    "CONFIRMAT_HOLE": 4.0,
    "THROUGH_HOLE": 6.0,
    "BLIND_HOLE": 2.0,
    "COUNTERSINK": 1.5,
    "COUNTERBORE": 1.5,
    "POCKET": 1.4,
    "THROUGH_POCKET": 1.0,
    "GROOVE": 1.5,
    "DADO": 1.2,
    "RABBET": 1.4,
    "OPEN_SLOT": 1.0,
    "INTERNAL_CUTOUT": 1.0,
}


# ---------------------------------------------------------------------------
# Hole-count distribution (Poisson, per panel type)
# ---------------------------------------------------------------------------

HOLE_COUNT_LAMBDA_DEFAULT = 8.0
HOLE_COUNT_LAMBDA_BY_TYPE: dict[str, float] = {
    "side_panel": 14.0,
    "door": 2.0,
    "shelf": 2.0,
    "back_panel": 0.2,
}
HOLE_COUNT_MIN = 0
HOLE_COUNT_MAX = 40


# ---------------------------------------------------------------------------
# Sampling helpers
# ---------------------------------------------------------------------------


def sample_from_distribution(values, weights, rng: np.random.Generator):
    """Sample one element from *values* using *weights* (need not sum to 1)."""
    w = np.asarray(weights, dtype=float)
    probs = w / w.sum()
    idx = rng.choice(len(values), p=probs)
    return values[idx]


def sample_panel_type(rng: np.random.Generator) -> str:
    """Sample a panel type from PANEL_TYPE_DISTRIBUTION."""
    types = list(PANEL_TYPE_DISTRIBUTION.keys())
    weights = list(PANEL_TYPE_DISTRIBUTION.values())
    return sample_from_distribution(types, weights, rng)


def sample_width(rng: np.random.Generator) -> float:
    """Sample a realistic panel width (mm)."""
    return float(sample_from_distribution(WIDTH_VALUES, WIDTH_WEIGHTS, rng))


def sample_height(rng: np.random.Generator) -> float:
    """Sample a realistic panel height (mm)."""
    return float(sample_from_distribution(HEIGHT_VALUES, HEIGHT_WEIGHTS, rng))


def sample_thickness(rng: np.random.Generator) -> float:
    """Sample a realistic panel thickness (mm)."""
    return float(sample_from_distribution(THICKNESS_VALUES, THICKNESS_WEIGHTS, rng))


def sample_hole_count(panel_type: str, rng: np.random.Generator) -> int:
    """Sample a hole count via Poisson, clamped to [HOLE_COUNT_MIN, HOLE_COUNT_MAX]."""
    lam = HOLE_COUNT_LAMBDA_BY_TYPE.get(panel_type, HOLE_COUNT_LAMBDA_DEFAULT)
    count = int(rng.poisson(lam))
    return int(max(HOLE_COUNT_MIN, min(HOLE_COUNT_MAX, count)))


# Milled / profile features are occasional: most panels have 0-2 of them. A low
# Poisson mean keeps them rarer than holes while ensuring non-trivial counts
# accumulate across a dataset.
MILLED_COUNT_LAMBDA = 1.2
MILLED_COUNT_MAX = 4


def sample_milled_count(rng: np.random.Generator) -> int:
    """Sample how many milled/profile features a panel gets (small, Poisson)."""
    count = int(rng.poisson(MILLED_COUNT_LAMBDA))
    return int(max(0, min(MILLED_COUNT_MAX, count)))


def allowed_feature_classes(panel_type: str) -> list[str]:
    """Return the concrete feature classes allowed for *panel_type* (R-004)."""
    allowed = PANEL_TYPE_ALLOWED_FEATURES.get(panel_type, ["ALL"])
    if allowed == ["ALL"]:
        return list(ALL_FEATURE_CLASSES)
    return list(allowed)


def sample_feature_class(allowed: list[str], rng: np.random.Generator) -> str:
    """Sample one feature class from *allowed* using FEATURE_CLASS_WEIGHTS.

    Weighting keeps holes dominant while still letting rarer milled/profile
    features appear. Classes absent from the weight table fall back to 1.0.
    """
    weights = [FEATURE_CLASS_WEIGHTS.get(c, 1.0) for c in allowed]
    return str(sample_from_distribution(allowed, weights, rng))
