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
    ],
    "door": ["HINGE_CUP_HOLE", "THROUGH_HOLE"],
    "shelf": ["THROUGH_HOLE", "DOWEL_HOLE"],
    "back_panel": ["THROUGH_HOLE"],
    "bottom_top": ["DOWEL_HOLE", "CONFIRMAT_HOLE", "THROUGH_HOLE"],
    "generic": ["ALL"],
}

# Every concrete feature class the generator can place (used when panel allows "ALL").
ALL_FEATURE_CLASSES: list[str] = [
    "SHELF_PIN_HOLE",
    "HINGE_CUP_HOLE",
    "DOWEL_HOLE",
    "CONFIRMAT_HOLE",
    "THROUGH_HOLE",
]


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


def allowed_feature_classes(panel_type: str) -> list[str]:
    """Return the concrete feature classes allowed for *panel_type* (R-004)."""
    allowed = PANEL_TYPE_ALLOWED_FEATURES.get(panel_type, ["ALL"])
    if allowed == ["ALL"]:
        return list(ALL_FEATURE_CLASSES)
    return list(allowed)
