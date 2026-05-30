"""Opt-in noise / perturbation augmentation for synthetic samples.

Generated geometry is unrealistically clean (exact 5.0 mm diameters, perfect
layer names, no duplicates), which lets a model cheat by memorising those
artefacts instead of learning real structure. This module jitters the geometry
to produce realistic-mess data for robustness training.

ALL randomness comes from the per-sample seeded numpy ``rng`` that the generator
already uses, so noise is fully reproducible (seed + sample index). Every knob
defaults to OFF (0.0 / False), so with default config the output is byte-identical
to the clean pipeline and existing tests / reproducibility are unchanged.

Knobs (PanelGeneratorConfig):
  - diameter_noise_sigma_mm : Gaussian jitter (mm) added to every circle DIAMETER.
  - layer_noise             : randomly rename a feature's layer to a realistic alias.
  - duplicate_entity_prob   : per-feature probability of appending a near-duplicate.
  - rotation_deg            : rigid rotation (deg) of all geometry about the panel
                              centre (panel boundary + features rotate together).
"""

from __future__ import annotations

import math

import numpy as np

from omim.synthetic.models import FeatureSpec, PanelSpec

# Realistic layer aliases a messy CAD export might use, keyed by canonical layer.
_LAYER_ALIASES: dict[str, list[str]] = {
    "DRILL": ["DRILL", "BOHREN", "Drill", "DRILLING", "0"],
    "CUT": ["CUT", "CONTOUR", "Cut", "PROFILE", "OUTLINE"],
    "POCKET": ["POCKET", "MILL", "Pocket", "ROUTE", "TASCHE"],
}


def apply_noise(
    panel: PanelSpec,
    features: list[FeatureSpec],
    rng: np.random.Generator,
    *,
    diameter_noise_sigma_mm: float = 0.0,
    layer_noise: bool = False,
    duplicate_entity_prob: float = 0.0,
    rotation_deg: float = 0.0,
) -> list[FeatureSpec]:
    """Return a (possibly perturbed) feature list. Pure when all knobs are off.

    The panel boundary is mutated in place only when ``rotation_deg`` is non-zero;
    otherwise *panel* is left untouched. The function never introduces uuid /
    datetime / set-ordering, so determinism (seed + index) is preserved.
    """
    noisy = features

    # --- Diameter jitter (circles only) ---
    if diameter_noise_sigma_mm and diameter_noise_sigma_mm > 0.0:
        for f in noisy:
            if f.entity_type == "CIRCLE" and f.radius_mm is not None:
                delta = float(rng.normal(0.0, diameter_noise_sigma_mm))
                # delta is a DIAMETER change -> half it onto the radius; clamp > 0.
                f.radius_mm = max(0.05, f.radius_mm + delta / 2.0)

    # --- Layer renaming ---
    if layer_noise:
        for f in noisy:
            aliases = _LAYER_ALIASES.get(f.layer)
            if aliases:
                f.layer = str(aliases[int(rng.integers(0, len(aliases)))])

    # --- Rigid rotation about the panel centre ---
    if rotation_deg:
        theta = math.radians(float(rotation_deg))
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        xs = [p[0] for p in panel.boundary_points]
        ys = [p[1] for p in panel.boundary_points]
        ox, oy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0

        def _rot(x: float, y: float) -> tuple[float, float]:
            dx, dy = x - ox, y - oy
            return (ox + dx * cos_t - dy * sin_t, oy + dx * sin_t + dy * cos_t)

        panel.boundary_points = [_rot(x, y) for x, y in panel.boundary_points]
        for f in noisy:
            if f.center is not None:
                f.center = _rot(f.center[0], f.center[1])
            if f.points:
                f.points = [_rot(px, py) for px, py in f.points]

    # --- Duplicate entities (append near-identical copies) ---
    if duplicate_entity_prob and duplicate_entity_prob > 0.0:
        extras: list[FeatureSpec] = []
        for f in noisy:
            if float(rng.random()) < duplicate_entity_prob:
                jx = float(rng.normal(0.0, 0.02))
                jy = float(rng.normal(0.0, 0.02))
                dup = f.model_copy(deep=True)
                if dup.center is not None:
                    dup.center = (dup.center[0] + jx, dup.center[1] + jy)
                if dup.points:
                    dup.points = [(px + jx, py + jy) for px, py in dup.points]
                extras.append(dup)
        noisy = noisy + extras

    return noisy
