"""Compute empirical distributions from corpus statistics.

Turns a :class:`omim.corpus.ingest.CorpusStatistics` into a JSON-serialisable
**grounding profile**: histograms, means / stdev, percentiles, and clustered
hole-diameter frequencies. The profile is structured to mirror the constants
the synthetic generator consumes in ``omim.synthetic.distributions`` (value
lists + weight lists, thickness options, hole-count lambdas), so the generator
can be re-grounded from a data file rather than from hard-coded guesses.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from omim.corpus.catalog_ground_truth import (
    CLUSTER_TOLERANCE_MM,
    KNOWN_FEATURE_DIAMETERS_MM,
    cluster_diameter_gated,
    feature_for_diameter,
)
from omim.corpus.ingest import CorpusStatistics

PROFILE_SCHEMA_VERSION = "omim-grounding-profile-v0.1.0"


def _describe(values: list[float]) -> dict[str, Any]:
    """Summary statistics for a 1-D numeric sample."""
    if not values:
        return {
            "n": 0, "min": None, "max": None, "mean": None,
            "stdev": None, "median": None, "p05": None, "p95": None,
        }
    vs = sorted(values)
    n = len(vs)

    def pct(p: float) -> float:
        if n == 1:
            return float(vs[0])
        idx = p * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return round(vs[lo] + (vs[hi] - vs[lo]) * frac, 4)

    return {
        "n": n,
        "min": round(vs[0], 4),
        "max": round(vs[-1], 4),
        "mean": round(statistics.fmean(vs), 4),
        "stdev": round(statistics.pstdev(vs), 4) if n > 1 else 0.0,
        "median": round(statistics.median(vs), 4),
        "p05": pct(0.05),
        "p95": pct(0.95),
    }


def _histogram(values: list[float], bin_width: float) -> dict[str, int]:
    """Fixed-width histogram keyed by bin lower edge (as a string)."""
    hist: Counter = Counter()
    for v in values:
        lo = (int(v // bin_width)) * bin_width
        hist[f"{lo:.1f}"] += 1
    return dict(sorted(hist.items(), key=lambda kv: float(kv[0])))


def _value_weight_lists(values: list[float]) -> tuple[list[float], list[float]]:
    """Collapse a sample to (distinct_values, normalised_weights).

    Mirrors the ``WIDTH_VALUES`` / ``WIDTH_WEIGHTS`` shape the generator uses.
    Values are rounded to the nearest mm so near-identical dims merge.
    """
    counts: Counter = Counter(round(v) for v in values)
    if not counts:
        return [], []
    total = sum(counts.values())
    vals = sorted(counts)
    weights = [round(counts[v] / total, 4) for v in vals]
    return [float(v) for v in vals], weights


def cluster_diameters(
    diameters: list[float], tolerance_mm: float = CLUSTER_TOLERANCE_MM
) -> dict[str, Any]:
    """Cluster measured diameters to the nearest known catalog diameter.

    A diameter is only assigned to a cluster when it lands within *tolerance_mm*
    of that catalog bore; diameters outside every band are pooled into an
    ``unclustered`` bucket (e.g. generic through-holes) so they do not pollute
    the catalog clusters' means. Returns per-cluster frequency, mean measured
    value, mean deviation from the catalog nominal, and the dominant feature
    class. Answers: "how often does each standard bore size appear, and how
    tight is it?"
    """
    clusters: dict[float, list[float]] = {c: [] for c in KNOWN_FEATURE_DIAMETERS_MM}
    deviations: dict[float, list[float]] = {c: [] for c in KNOWN_FEATURE_DIAMETERS_MM}
    unclustered: list[float] = []
    for d in diameters:
        center, dev = cluster_diameter_gated(d, tolerance_mm)
        if center is None:
            unclustered.append(d)
            continue
        clusters[center].append(d)
        deviations[center].append(dev)

    total = len(diameters)
    out: dict[str, Any] = {}
    for center in KNOWN_FEATURE_DIAMETERS_MM:
        members = clusters[center]
        devs = deviations[center]
        out[f"{center:.1f}"] = {
            "cluster_center_mm": center,
            "feature_class": feature_for_diameter(center),
            "count": len(members),
            "frequency": round(len(members) / total, 4) if total else 0.0,
            "measured_mean_mm": round(statistics.fmean(members), 4) if members else None,
            "measured_stdev_mm": (
                round(statistics.pstdev(members), 4) if len(members) > 1 else 0.0
            ),
            "mean_deviation_mm": round(statistics.fmean(devs), 4) if devs else None,
            "max_abs_deviation_mm": (
                round(max(abs(x) for x in devs), 4) if devs else None
            ),
        }
    out["unclustered"] = {
        "cluster_center_mm": None,
        "feature_class": "UNKNOWN",
        "count": len(unclustered),
        "frequency": round(len(unclustered) / total, 4) if total else 0.0,
        "measured_mean_mm": (
            round(statistics.fmean(unclustered), 4) if unclustered else None
        ),
        "measured_stdev_mm": (
            round(statistics.pstdev(unclustered), 4) if len(unclustered) > 1 else 0.0
        ),
        "mean_deviation_mm": None,
        "max_abs_deviation_mm": None,
    }
    return out


def _hole_count_lambda(hole_counts: list[int]) -> float | None:
    """Best Poisson-lambda estimate (the mean) for per-panel hole counts."""
    if not hole_counts:
        return None
    return round(statistics.fmean(hole_counts), 4)


def extract_distributions(stats: CorpusStatistics) -> dict[str, Any]:
    """Build the full grounding profile dict from corpus statistics."""
    diameters = stats.diameters_mm
    widths = stats.panel_widths_mm
    heights = stats.panel_heights_mm
    thicknesses = stats.thicknesses_mm
    setbacks = stats.edge_setbacks_mm
    spacings = stats.pairwise_spacings_mm
    hole_counts = stats.hole_counts

    width_vals, width_weights = _value_weight_lists(widths)
    height_vals, height_weights = _value_weight_lists(heights)
    thick_vals, thick_weights = _value_weight_lists(thicknesses)

    profile: dict[str, Any] = {
        "$schema": PROFILE_SCHEMA_VERSION,
        "profile_version": "v0.1.0",
        "trust_tier": 2,  # empirical corpus = Tier 2 (see data/grounding/README.md)
        "source": {
            "kind": "ingested_corpus",
            "source_dir": stats.source_dir,
            "files_total": stats.files_total,
            "files_parsed": stats.files_parsed,
            "files_failed": stats.files_failed,
        },
        "summary": stats.summary(),
        # --- Hole diameters ---
        "diameter": {
            "stats": _describe(diameters),
            "histogram_0p5mm": _histogram(diameters, 0.5),
            "clusters": cluster_diameters(diameters),
        },
        # --- Panel dimensions (generator-compatible value/weight lists) ---
        "panel_width": {
            "stats": _describe(widths),
            "values": width_vals,
            "weights": width_weights,
        },
        "panel_height": {
            "stats": _describe(heights),
            "values": height_vals,
            "weights": height_weights,
        },
        "panel_thickness": {
            "stats": _describe(thicknesses),
            "values": thick_vals,
            "weights": thick_weights,
        },
        # --- Edge clearance / setback ---
        "edge_setback": {
            "stats": _describe(setbacks),
            "histogram_5mm": _histogram(setbacks, 5.0),
        },
        # --- Pairwise spacing (recovers 32mm grid, pair spacings) ---
        "pairwise_spacing": {
            "stats": _describe(spacings),
            "histogram_5mm": _histogram(spacings, 5.0),
        },
        # --- Hole counts per panel ---
        "hole_count": {
            "stats": _describe([float(c) for c in hole_counts]),
            "poisson_lambda": _hole_count_lambda(hole_counts),
            "histogram_1": _histogram([float(c) for c in hole_counts], 1.0),
        },
    }
    return profile
