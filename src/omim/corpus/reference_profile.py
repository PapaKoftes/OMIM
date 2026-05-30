"""Catalog-derived synthetic grounding profile.

Since no license-clear, domain-matched real DXF corpus is available offline
(see docs/06_REAL_WORLD_GROUNDING/Real_DXF_Corpus_Sources.md), this module
builds a **Tier 1** grounding profile seeded purely from the manufacturer
catalog ground truth (:data:`CATALOG_REFERENCES`) plus the panel-dimension and
feature-count standards. It has the *same JSON shape* as a profile produced by
``distribution_extractor.extract_distributions`` over a real corpus, so the
synthetic generator can consume either interchangeably.

When a real corpus becomes available, ingest it and write a Tier 2 profile that
supersedes this one — the catalog profile remains the conformance reference.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omim.corpus.catalog_ground_truth import (
    CATALOG_REFERENCES,
    COMMON_PANEL_THICKNESSES_MM,
    FEATURE_COUNT_BY_PANEL_TYPE,
    KNOWN_FEATURE_DIAMETERS_MM,
    TYPICAL_HEIGHTS_MM,
    TYPICAL_WIDTHS_MM,
    VALID_PANEL_THICKNESSES_MM,
    feature_for_diameter,
)
from omim.corpus.distribution_extractor import PROFILE_SCHEMA_VERSION

# Default on-disk location of the shipped catalog-derived profile.
DEFAULT_PROFILE_PATH = (
    Path(__file__).resolve().parents[3]
    / "data" / "grounding" / "catalog_reference_profile.json"
)

# Weights reflect how common each feature is on a real cabinet panel: shelf
# pins dominate by count (long System-32 columns), confirmat/dowel joinery is
# frequent, hinge cups and cams are sparse. Derived from the feature-count
# table in Panel_Dimension_Standards.md.
_DIAMETER_FREQUENCY_WEIGHTS: dict[float, float] = {
    5.0: 0.55,    # shelf pins — many per side panel
    7.0: 0.12,    # confirmat
    8.0: 0.18,    # dowels (8mm common)
    10.0: 0.05,   # dowels (10mm heavy)
    15.0: 0.02,   # cam fittings
    35.0: 0.08,   # hinge cups
}


def _diameter_clusters() -> dict[str, Any]:
    """Catalog-perfect diameter clusters (measured == nominal, zero deviation)."""
    out: dict[str, Any] = {}
    for center in KNOWN_FEATURE_DIAMETERS_MM:
        freq = _DIAMETER_FREQUENCY_WEIGHTS.get(center, 0.0)
        out[f"{center:.1f}"] = {
            "cluster_center_mm": center,
            "feature_class": feature_for_diameter(center),
            "count": int(round(freq * 1000)),  # nominal support per 1000 holes
            "frequency": round(freq, 4),
            "measured_mean_mm": center,
            "measured_stdev_mm": 0.0,
            "mean_deviation_mm": 0.0,
            "max_abs_deviation_mm": 0.0,
        }
    return out


def _stats_from_nominal(center: float, tol: float, n: int = 1000) -> dict[str, Any]:
    """A degenerate 'distribution' centered on a single catalog nominal."""
    return {
        "n": n,
        "min": round(center - tol, 4),
        "max": round(center + tol, 4),
        "mean": center,
        "stdev": round(tol / 3.0, 4),  # treat tol as ~3 sigma
        "median": center,
        "p05": round(center - tol, 4),
        "p95": round(center + tol, 4),
    }


def _value_weight_pairs(
    values: list[float], weights: list[float] | None = None
) -> dict[str, list[float]]:
    if weights is None:
        weights = [round(1.0 / len(values), 4)] * len(values)
    return {"values": [float(v) for v in values], "weights": weights}


def build_reference_profile() -> dict[str, Any]:
    """Construct the catalog-derived (Tier 1) grounding profile dict."""
    # Diameter summary stats spanning the known bore set.
    diam_stats = {
        "n": 1000,
        "min": min(KNOWN_FEATURE_DIAMETERS_MM),
        "max": max(KNOWN_FEATURE_DIAMETERS_MM),
        "mean": round(
            sum(c * _DIAMETER_FREQUENCY_WEIGHTS.get(c, 0.0)
                for c in KNOWN_FEATURE_DIAMETERS_MM), 4
        ),
        "stdev": None,
        "median": 5.0,
        "p05": 5.0,
        "p95": 35.0,
    }

    # Panel width / height weights favour common cabinet sizes (600mm width,
    # 720/600mm heights) per the standards docs.
    width_weights = [0.10, 0.10, 0.10, 0.15, 0.25, 0.10, 0.10, 0.05, 0.05]
    height_weights = [0.10, 0.20, 0.25, 0.10, 0.15, 0.10, 0.10]

    # Thickness: 18mm dominant, 16/19mm common, rest sparse but standard.
    thickness_values = VALID_PANEL_THICKNESSES_MM
    thickness_weights = [
        0.40 if v == 18.0 else (0.12 if v in COMMON_PANEL_THICKNESSES_MM else 0.02)
        for v in thickness_values
    ]
    tw_sum = sum(thickness_weights)
    thickness_weights = [round(w / tw_sum, 4) for w in thickness_weights]

    # Edge setbacks: the catalog setback values (22.5mm hinge, 37mm shelf row,
    # 11.5mm confirmat).
    setback_values = sorted(
        {ref["setback_mm"] for ref in CATALOG_REFERENCES.values()
         if ref.get("setback_mm") is not None}
    )

    # Hole-count expectations per panel type (from the feature-count table).
    hole_count_by_type = {
        ptype: {
            "min": spec["hole_count"][0],
            "max": spec["hole_count"][1],
            "typical": spec["typical"],
            "poisson_lambda": float(spec["typical"]),
        }
        for ptype, spec in FEATURE_COUNT_BY_PANEL_TYPE.items()
    }

    profile: dict[str, Any] = {
        "$schema": PROFILE_SCHEMA_VERSION,
        "profile_version": "v0.1.0",
        "trust_tier": 1,  # catalog-derived ground truth
        "source": {
            "kind": "catalog_derived",
            "note": "Seeded from manufacturer catalogs + EN/DIN standards; no "
                    "real corpus ingested. Replace with a Tier 2 profile once a "
                    "real DXF corpus is available.",
            "references": sorted(
                {ref["source"] for ref in CATALOG_REFERENCES.values()}
            ),
        },
        "diameter": {
            "stats": diam_stats,
            "clusters": _diameter_clusters(),
        },
        "panel_width": {
            "stats": _describe_values(TYPICAL_WIDTHS_MM, width_weights),
            **_value_weight_pairs(TYPICAL_WIDTHS_MM, width_weights),
        },
        "panel_height": {
            "stats": _describe_values(TYPICAL_HEIGHTS_MM, height_weights),
            **_value_weight_pairs(TYPICAL_HEIGHTS_MM, height_weights),
        },
        "panel_thickness": {
            "stats": _describe_values(thickness_values, thickness_weights),
            **_value_weight_pairs(thickness_values, thickness_weights),
            "default_mm": 18.0,
        },
        "edge_setback": {
            "stats": _stats_from_nominal(22.5, 14.5),
            "catalog_setbacks_mm": setback_values,
            "by_feature": {
                fc: {
                    "setback_mm": ref["setback_mm"],
                    "tolerance_mm": ref.get("setback_tol_mm"),
                }
                for fc, ref in CATALOG_REFERENCES.items()
                if ref.get("setback_mm") is not None
            },
        },
        "pairwise_spacing": {
            "stats": _stats_from_nominal(32.0, 0.5),
            "grid_pitch_mm": 32.0,
            "note": "System 32 grid pitch (Häfele / Blum / Hettich / Grass).",
        },
        "hole_count": {
            "by_panel_type": hole_count_by_type,
            "max_realistic": 40,
        },
        "catalog_references": CATALOG_REFERENCES,
    }
    return profile


def _describe_values(values: list[float], weights: list[float]) -> dict[str, Any]:
    """Weighted summary stats for a value/weight distribution."""
    total = sum(weights)
    if total == 0:
        return {"n": 0, "mean": None}
    mean = sum(v * w for v, w in zip(values, weights)) / total
    return {
        "n": len(values),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(mean, 4),
        "stdev": None,
        "median": round(sorted(values)[len(values) // 2], 4),
        "p05": round(min(values), 4),
        "p95": round(max(values), 4),
    }


def write_reference_profile(path: str | Path | None = None) -> Path:
    """Build the catalog-derived profile and write it to *path* as JSON."""
    path = Path(path) if path is not None else DEFAULT_PROFILE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = build_reference_profile()
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return path


def load_grounding_profile(path: str | Path | None = None) -> dict[str, Any]:
    """Load a grounding profile JSON the synthetic generator can consume.

    Accepts either the shipped catalog-derived profile (Tier 1) or a profile
    produced by ingesting a real corpus (Tier 2). If the default profile does
    not yet exist on disk, it is built and written on first access.
    """
    path = Path(path) if path is not None else DEFAULT_PROFILE_PATH
    if not path.exists():
        if path == DEFAULT_PROFILE_PATH:
            write_reference_profile(path)
        else:
            raise FileNotFoundError(f"Grounding profile not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
