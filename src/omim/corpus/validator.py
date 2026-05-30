"""Validate an ingested corpus against the manufacturer catalog ground truth.

``validate_against_catalog`` answers the key question:

    "Does this corpus conform to Blum / Hettich / Häfele / System 32 / DIN specs?"

It compares the empirical hole-diameter clusters, edge setbacks, and pairwise
spacings extracted from a corpus against :data:`CATALOG_REFERENCES` and flags
any cluster whose measured center drifts outside the catalog tolerance band
(e.g. a corpus whose "hinge cup" cluster centers at 34mm instead of 35mm).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from omim.corpus.catalog_ground_truth import (
    CATALOG_REFERENCES,
    VALID_PANEL_THICKNESSES_MM,
    reference_for_cluster,
)
from omim.corpus.distribution_extractor import extract_distributions
from omim.corpus.ingest import CorpusStatistics

# Minimum number of holes in a cluster before we judge its conformance — a
# single stray hole should not fail a whole corpus.
MIN_CLUSTER_SUPPORT = 3
# Spacing within this of a 32mm multiple counts as System-32 conformant.
GRID_SPACING_TOL_MM = 0.5


@dataclass
class CheckResult:
    """One conformance check against a catalog reference."""

    feature_class: str
    metric: str               # "diameter" | "edge_setback" | "grid_spacing" | "thickness"
    passed: bool
    measured: float | None
    expected: float | None
    tolerance: float | None
    deviation: float | None
    support: int              # number of measurements backing this check
    source: str
    message: str


@dataclass
class CatalogValidationReport:
    """Full conformance report for a corpus vs. the catalog ground truth."""

    overall_conformant: bool
    checks: list[CheckResult] = field(default_factory=list)
    n_passed: int = 0
    n_failed: int = 0
    n_skipped_low_support: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_conformant": self.overall_conformant,
            "n_passed": self.n_passed,
            "n_failed": self.n_failed,
            "n_skipped_low_support": self.n_skipped_low_support,
            "notes": list(self.notes),
            "checks": [
                {
                    "feature_class": c.feature_class,
                    "metric": c.metric,
                    "passed": c.passed,
                    "measured": c.measured,
                    "expected": c.expected,
                    "tolerance": c.tolerance,
                    "deviation": c.deviation,
                    "support": c.support,
                    "source": c.source,
                    "message": c.message,
                }
                for c in self.checks
            ],
        }


def _nearest_grid_deviation(spacing: float, grid: float = 32.0) -> float:
    """Absolute deviation of *spacing* from the nearest non-zero multiple of grid."""
    if spacing < grid / 2:
        # Too small to be a grid step; compare to one grid unit.
        return abs(spacing - grid)
    multiple = round(spacing / grid)
    multiple = max(1, multiple)
    return abs(spacing - multiple * grid)


def validate_against_catalog(
    stats: CorpusStatistics,
    *,
    min_cluster_support: int = MIN_CLUSTER_SUPPORT,
) -> CatalogValidationReport:
    """Compare extracted distributions to the catalog ground truth.

    A corpus is *conformant* when every well-supported diameter cluster centers
    within the catalog tolerance, edge setbacks for setback-defined features sit
    within tolerance, and shelf-pin spacings lie on the 32mm grid.
    """
    profile = extract_distributions(stats)
    clusters = profile["diameter"]["clusters"]

    report = CatalogValidationReport(overall_conformant=True)

    # --- Diameter cluster conformance ---------------------------------
    for _key, cluster in clusters.items():
        support = cluster["count"]
        center = cluster["cluster_center_mm"]
        if center is None:  # the "unclustered" bucket — no catalog reference
            continue
        ref = reference_for_cluster(center)
        if ref is None:
            continue
        if support < min_cluster_support:
            if support > 0:
                report.n_skipped_low_support += 1
            continue

        measured_mean = cluster["measured_mean_mm"]
        expected = ref["diameter_mm"]
        tol = ref["diameter_tol_mm"]
        deviation = abs(measured_mean - expected)
        passed = deviation <= tol
        report.checks.append(
            CheckResult(
                feature_class=cluster["feature_class"],
                metric="diameter",
                passed=passed,
                measured=round(measured_mean, 4),
                expected=expected,
                tolerance=tol,
                deviation=round(deviation, 4),
                support=support,
                source=ref["source"],
                message=(
                    f"{cluster['feature_class']} cluster mean {measured_mean:.3f}mm "
                    f"vs catalog {expected}mm ±{tol}mm "
                    f"({'OK' if passed else 'DEVIATION'})"
                ),
            )
        )

    # --- Edge setback conformance (per setback-defined feature) -------
    # Setbacks are pooled per corpus; we test the dominant setback features
    # (hinge cup 22.5mm, shelf pin 37mm) when the corresponding diameter
    # cluster is well-supported.
    setback_features = {
        fc: ref
        for fc, ref in CATALOG_REFERENCES.items()
        if ref.get("setback_mm") is not None
    }
    for fc, ref in setback_features.items():
        center = ref["cluster_center_mm"]
        cluster = clusters.get(f"{center:.1f}")
        if cluster is None or cluster["count"] < min_cluster_support:
            continue
        # Collect setbacks for holes whose diameter snaps to this cluster.
        relevant = [
            h.edge_setback_mm
            for h in stats.holes
            if h.edge_setback_mm is not None
            and abs(round(h.diameter_mm) - round(center)) < 0.51
        ]
        if len(relevant) < min_cluster_support:
            continue
        # Use the minimum-mode setback: hardware sits at a fixed setback, so the
        # smallest common setback is the catalog reference (other holes of the
        # same diameter may be elsewhere). Use the median as a robust estimate.
        relevant_sorted = sorted(relevant)
        measured = relevant_sorted[len(relevant_sorted) // 2]
        expected = ref["setback_mm"]
        tol = ref.get("setback_tol_mm") or 1.0
        deviation = abs(measured - expected)
        passed = deviation <= tol
        report.checks.append(
            CheckResult(
                feature_class=fc,
                metric="edge_setback",
                passed=passed,
                measured=round(measured, 4),
                expected=expected,
                tolerance=tol,
                deviation=round(deviation, 4),
                support=len(relevant),
                source=ref["source"],
                message=(
                    f"{fc} median setback {measured:.2f}mm vs catalog "
                    f"{expected}mm ±{tol}mm "
                    f"({'OK' if passed else 'DEVIATION'})"
                ),
            )
        )

    # --- System-32 grid spacing conformance ---------------------------
    shelf_cluster = clusters.get("5.0")
    if shelf_cluster and shelf_cluster["count"] >= min_cluster_support:
        # Shelf-pin spacings: those near a 32mm multiple.
        grid_spacings = [
            s for s in stats.pairwise_spacings_mm if 20.0 <= s <= 200.0
        ]
        if len(grid_spacings) >= min_cluster_support:
            deviations = [_nearest_grid_deviation(s, 32.0) for s in grid_spacings]
            on_grid = sum(1 for d in deviations if d <= GRID_SPACING_TOL_MM)
            frac_on_grid = on_grid / len(grid_spacings)
            mean_dev = sum(deviations) / len(deviations)
            passed = frac_on_grid >= 0.5
            report.checks.append(
                CheckResult(
                    feature_class="SHELF_PIN_HOLE",
                    metric="grid_spacing",
                    passed=passed,
                    measured=round(mean_dev, 4),
                    expected=0.0,
                    tolerance=GRID_SPACING_TOL_MM,
                    deviation=round(mean_dev, 4),
                    support=len(grid_spacings),
                    source=CATALOG_REFERENCES["SHELF_PIN_HOLE"]["source"],
                    message=(
                        f"{frac_on_grid:.0%} of shelf-pin spacings on the 32mm grid "
                        f"(mean deviation {mean_dev:.3f}mm) "
                        f"({'OK' if passed else 'OFF-GRID'})"
                    ),
                )
            )

    # --- Panel thickness conformance (EN 309 / EN 622-5) --------------
    thicknesses = stats.thicknesses_mm
    if thicknesses:
        nonstandard = [
            t for t in thicknesses
            if min(abs(t - v) for v in VALID_PANEL_THICKNESSES_MM) > 0.5
        ]
        passed = len(nonstandard) == 0
        report.checks.append(
            CheckResult(
                feature_class="PANEL",
                metric="thickness",
                passed=passed,
                measured=float(len(nonstandard)),
                expected=0.0,
                tolerance=0.0,
                deviation=float(len(nonstandard)),
                support=len(thicknesses),
                source="EN 309 (particleboard); EN 622-5 (MDF)",
                message=(
                    f"{len(nonstandard)}/{len(thicknesses)} panel thicknesses "
                    f"off the EN 309 / EN 622-5 standard set "
                    f"({'OK' if passed else 'NON-STANDARD'})"
                ),
            )
        )

    # --- Tally ---------------------------------------------------------
    report.n_passed = sum(1 for c in report.checks if c.passed)
    report.n_failed = sum(1 for c in report.checks if not c.passed)
    report.overall_conformant = report.n_failed == 0 and report.n_passed > 0

    if report.n_passed == 0:
        report.notes.append(
            "No well-supported catalog clusters found; corpus too small or "
            "out-of-domain to judge conformance."
        )
    if report.n_skipped_low_support:
        report.notes.append(
            f"{report.n_skipped_low_support} diameter cluster(s) had fewer than "
            f"{min_cluster_support} holes and were not judged."
        )

    return report
