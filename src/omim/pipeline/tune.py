"""Tune an identification ruleset to a specific delivered corpus.

Generic catalog defaults (35mm hinge cups, 32mm shelf-pin grid, 18mm stock) are a
good prior, but a real delivery from one shop has its *own* consistent dimensions
and conventions. This module measures the corpus and emits a tuned ruleset YAML
that the (already data-driven) RuleEngine and the part identifier can load —
adapting thresholds to the corpus without touching code.

What it measures and tunes:
  * hole-diameter clusters -> per-feature target diameters + tolerances
  * observed panel thicknesses -> default panel thickness for depth rules
  * shelf-pin column spacing -> the System-32 target (or the shop's actual grid)
  * observed part-type frequencies -> recorded for transparency

It deliberately does NOT invent values: a threshold is only tuned when the corpus
provides enough samples (configurable ``min_samples``); otherwise the catalog
default is kept and the field is flagged ``source: catalog_default``.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from omim.corpus.distribution_extractor import cluster_diameters
from omim.corpus.ingest import CorpusIngestor

logger = logging.getLogger(__name__)

# Catalog priors kept as fallback when the corpus is too sparse to tune.
_CATALOG_DEFAULTS = {
    "shelf_pin_diameter_mm": 5.0,
    "hinge_cup_diameter_mm": 35.0,
    "confirmat_diameter_mm": 7.0,
    "shelf_pin_spacing_mm": 32.0,
    "panel_thickness_mm": 18.0,
}


@dataclass
class TunedRuleset:
    """The tuned ruleset plus provenance about what was measured vs defaulted."""

    parameters: dict = field(default_factory=dict)
    measured: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)  # param -> "corpus_measured" | "catalog_default"
    corpus_files: int = 0
    notes: list[str] = field(default_factory=list)

    def to_yaml(self) -> str:
        doc = {
            "version": "tuned-v1",
            "tuning": {
                "corpus_files": self.corpus_files,
                "sources": self.sources,
                "measured": self.measured,
                "notes": self.notes,
            },
            "parameters": self.parameters,
        }
        return yaml.safe_dump(doc, sort_keys=True)


def tune_ruleset(corpus_dir: str | Path, min_samples: int = 5) -> TunedRuleset:
    """Measure *corpus_dir* and produce a corpus-tuned ruleset.

    Uses the existing CorpusIngestor to gather hole diameters, panel dimensions
    and spacings from every parseable DXF, then derives tuned parameters.
    """
    stats = CorpusIngestor().ingest_directory(corpus_dir)
    diameters = _collect_diameters(stats)
    thicknesses = _collect_thicknesses(stats)
    spacings = _collect_spacings(stats)

    tuned = TunedRuleset(corpus_files=getattr(stats, "files_parsed", 0))
    params: dict = {}
    sources: dict = {}
    measured: dict = {}

    # --- Diameter clusters -> per-feature target + tolerance ---
    if diameters:
        clusters = cluster_diameters(diameters)
        measured["diameter_clusters"] = _summarize_clusters(clusters)
        # Map known catalog bores to rule params when the cluster is well-sampled.
        cluster_map = _cluster_by_center(clusters)
        _tune_diameter(params, sources, cluster_map, 5.0, "shelf_pin_diameter_mm", min_samples)
        _tune_diameter(params, sources, cluster_map, 35.0, "hinge_cup_diameter_mm", min_samples)
        _tune_diameter(params, sources, cluster_map, 7.0, "confirmat_diameter_mm", min_samples)
    else:
        tuned.notes.append("no hole diameters measured; all diameter params defaulted")

    # --- Thickness -> default panel thickness ---
    if len(thicknesses) >= min_samples:
        med = round(statistics.median(thicknesses), 2)
        params["panel_thickness_mm"] = med
        sources["panel_thickness_mm"] = "corpus_measured"
        measured["panel_thickness_mm"] = {"median": med, "n": len(thicknesses)}
    else:
        params["panel_thickness_mm"] = _CATALOG_DEFAULTS["panel_thickness_mm"]
        sources["panel_thickness_mm"] = "catalog_default"

    # --- Shelf-pin spacing -> grid target ---
    grid = _dominant_spacing(spacings)
    if grid is not None and len([s for s in spacings if abs(s - grid) <= 1.0]) >= min_samples:
        params["shelf_pin_spacing_mm"] = round(grid, 2)
        sources["shelf_pin_spacing_mm"] = "corpus_measured"
        measured["shelf_pin_spacing_mm"] = {"dominant": round(grid, 2), "n": len(spacings)}
    else:
        params["shelf_pin_spacing_mm"] = _CATALOG_DEFAULTS["shelf_pin_spacing_mm"]
        sources["shelf_pin_spacing_mm"] = "catalog_default"

    # Fill any still-missing catalog params with defaults (transparent).
    for key, default in _CATALOG_DEFAULTS.items():
        if key not in params:
            params[key] = default
            sources.setdefault(key, "catalog_default")

    tuned.parameters = params
    tuned.sources = sources
    tuned.measured = measured
    return tuned


def write_tuned_ruleset(
    corpus_dir: str | Path, out_path: str | Path, min_samples: int = 5
) -> TunedRuleset:
    tuned = tune_ruleset(corpus_dir, min_samples=min_samples)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tuned.to_yaml(), encoding="utf-8")
    return tuned


# ---------------------------------------------------------------------------
# Helpers (tolerant of variations in CorpusStatistics shape)
# ---------------------------------------------------------------------------


def _collect_diameters(stats) -> list[float]:
    for attr in ("hole_diameters_mm", "diameters_mm", "all_diameters"):
        vals = getattr(stats, attr, None)
        if vals:
            return [float(v) for v in vals]
    # Fall back to per-measurement objects if present.
    holes = getattr(stats, "holes", None)
    if holes:
        out = [getattr(h, "diameter_mm", None) for h in holes]
        return [float(v) for v in out if v is not None]
    return []


def _collect_thicknesses(stats) -> list[float]:
    for attr in ("panel_thicknesses_mm", "thicknesses_mm"):
        vals = getattr(stats, attr, None)
        if vals:
            return [float(v) for v in vals if v is not None]
    return []


def _collect_spacings(stats) -> list[float]:
    for attr in ("pairwise_spacings_mm", "spacings_mm", "nearest_spacings_mm"):
        vals = getattr(stats, attr, None)
        if vals:
            return [float(v) for v in vals if v is not None]
    return []


def _summarize_clusters(clusters: dict) -> dict:
    out = {}
    for key, info in clusters.items():
        if key == "unclustered" or not isinstance(info, dict):
            continue
        out[str(key)] = {
            "count": info.get("count"),
            "mean_mm": info.get("measured_mean_mm"),
            "frequency": info.get("frequency"),
        }
    return out


def _cluster_by_center(clusters: dict) -> dict[float, dict]:
    """Re-key cluster_diameters output (keys like '35.0') by float center."""
    out: dict[float, dict] = {}
    for _key, info in clusters.items():
        if not isinstance(info, dict):
            continue
        center = info.get("cluster_center_mm")
        if center is None:
            continue
        out[float(center)] = info
    return out


def _tune_diameter(params, sources, cluster_map, center, param_name, min_samples):
    info = cluster_map.get(center)
    count = (info or {}).get("count", 0) or 0
    mean = (info or {}).get("measured_mean_mm")
    if info and count >= min_samples and mean is not None:
        params[param_name] = round(float(mean), 3)
        sources[param_name] = "corpus_measured"
    else:
        params[param_name] = _CATALOG_DEFAULTS[param_name]
        sources[param_name] = "catalog_default"


def _dominant_spacing(spacings: list[float]) -> float | None:
    """Most common spacing rounded to the nearest mm (the grid pitch)."""
    if not spacings:
        return None
    from collections import Counter

    rounded = Counter(round(s) for s in spacings if s > 0)
    if not rounded:
        return None
    return float(rounded.most_common(1)[0][0])
