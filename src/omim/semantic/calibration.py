"""Confidence calibration for the semantic layer.

This module is the single source of truth for *how confident* a heuristic hole
classification is allowed to be, and for *measuring* whether those confidences
are honest (i.e. whether a "0.80" really means ~80% correct).

It implements, verbatim from
``docs/08_PROVENANCE_AND_CONFIDENCE/Confidence_Model.md``:

  * ``RULE_TYPE_CONFIDENCE_CEILINGS`` / ``INFERENCE_METHOD_CONFIDENCE_CEILINGS``
    and ``get_confidence_ceiling`` — the epistemic ceiling by inference method.
  * ``CONFIDENCE_THRESHOLDS`` and ``apply_confidence_threshold`` — accept (>=0.60)
    / flag (0.30-0.59) / reject (<0.30 -> UNKNOWN_FEATURE).
  * ``combine_confidence`` — conservative ``min`` combination.
  * ``compute_hole_classification_confidence`` — graded diameter-match confidence.

It additionally provides a small *calibration harness* used by the tests to
quantify calibration on real data:

  * ``reliability_curve`` — bins (confidence, correct?) pairs.
  * ``expected_calibration_error`` — the scalar ECE.

Nothing here mutates the MGG; this is a pure functions module.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Confidence ceilings (per Confidence_Model.md, Rule 1)
# ---------------------------------------------------------------------------

# InferenceMethod ceilings. The semantic classifier only ever uses the
# rule-based / heuristic / deterministic tiers; ML is listed for completeness.
INFERENCE_METHOD_CONFIDENCE_CEILINGS: dict[str, float] = {
    "deterministic": 1.0,
    "rule_based": 0.95,
    "heuristic": 0.75,
    "ml_inference": 0.60,
}

# Rule-type ceilings. These match SEMANTIC_CONFIDENCE_CEILINGS in the classifier
# and the Trust-Hierarchy table in the Confidence Model.
RULE_TYPE_CONFIDENCE_CEILINGS: dict[str, float] = {
    "geometric": 1.0,
    "deterministic": 1.0,
    "standards_derived": 0.95,
    "hardware_spec": 0.90,
    "shop_convention": 0.75,
    "material_heuristic": 0.70,
    "machine_heuristic": 0.65,
    "none": 0.0,
}


def get_confidence_ceiling(
    inference_method: str,
    rule_type: str | None = None,
) -> float:
    """Return the maximum warranted confidence for an inference method/rule type.

    Mirrors ``get_confidence_ceiling`` in the Confidence Model: the effective
    ceiling is the *minimum* of the method ceiling and (if given) the rule-type
    ceiling. Unknown methods fall back to the heuristic ceiling so we never
    silently allow over-confidence.
    """
    method_ceiling = INFERENCE_METHOD_CONFIDENCE_CEILINGS.get(
        inference_method,
        INFERENCE_METHOD_CONFIDENCE_CEILINGS["heuristic"],
    )
    if rule_type:
        rule_ceiling = RULE_TYPE_CONFIDENCE_CEILINGS.get(rule_type, method_ceiling)
        return min(method_ceiling, rule_ceiling)
    return method_ceiling


# ---------------------------------------------------------------------------
# Decision thresholds (per Confidence_Model.md, "Confidence Thresholds")
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "accept": 0.60,  # Feature class accepted as primary label
    "flag_for_review": 0.30,  # Tentative label kept but flagged for review
    "reject": 0.00,  # Below 0.30 -> relabel as UNKNOWN_FEATURE
}

# Review-status string constants (the SemanticAnnotations models do not carry a
# review_status field, so the classifier records this in evidence/provenance).
REVIEW_AUTO_VALIDATED = "auto_validated"
REVIEW_FLAGGED = "flagged"


def apply_confidence_threshold(
    feature_class: str,
    confidence: float,
) -> tuple[str, str]:
    """Apply the accept/flag/reject policy to a (class, confidence) pair.

    Returns ``(effective_feature_class, review_status)``:

      * ``confidence >= 0.60``           -> (class, "auto_validated")
      * ``0.30 <= confidence < 0.60``    -> (class, "flagged")  [tentative kept]
      * ``confidence < 0.30``            -> ("UNKNOWN_FEATURE", "flagged")

    Per the Confidence Model, an annotation below the reject threshold is
    relabelled ``UNKNOWN_FEATURE`` regardless of the top hypothesis.
    """
    if confidence >= CONFIDENCE_THRESHOLDS["accept"]:
        return feature_class, REVIEW_AUTO_VALIDATED
    if confidence >= CONFIDENCE_THRESHOLDS["flag_for_review"]:
        return feature_class, REVIEW_FLAGGED
    return "UNKNOWN_FEATURE", REVIEW_FLAGGED


# ---------------------------------------------------------------------------
# Confidence combination (per Confidence_Model.md, "Combination Rules")
# ---------------------------------------------------------------------------


def combine_confidence(sources: list[float]) -> float:
    """Combine confidence from independent evidence sources conservatively.

    Uses minimum (not probabilistic product): two weak sources do not produce
    false confidence. Empty input yields 0.0.
    """
    if not sources:
        return 0.0
    return min(sources)


# ---------------------------------------------------------------------------
# Graded hole-classification confidence (per Confidence_Model.md)
# ---------------------------------------------------------------------------


def compute_hole_classification_confidence(
    diameter_mm: float,
    expected_diameter_mm: float,
    diameter_tolerance_mm: float,
    context_match: bool = False,
    pattern_match: bool = False,
    ceiling: float = 1.0,
) -> float:
    """Graded heuristic confidence for a hole classification.

    Per the Confidence Model:

        distance = abs(diameter_mm - expected_diameter_mm)
        base     = max(0, 1 - distance / diameter_tolerance_mm)
        +0.05 if context_match  (geometric context matches expected pattern)
        +0.08 if pattern_match  (part of a confirmed group, e.g. shelf-pin row)
        return min(1.0, base + bonuses)

    The result is then capped at the rule-type ``ceiling`` (the function's
    extension over the doc snippet, which says the result "is capped at the
    applicable confidence_ceiling for the rule type"). This makes confidence a
    *reflection of match quality* rather than a fixed per-rule constant:

      * an exact-diameter hit scores near ``ceiling``,
      * an off-spec diameter scores proportionally lower,
      * a diameter further than ``tolerance`` from expected scores 0 before
        bonuses (and therefore well below the accept threshold).
    """
    if diameter_tolerance_mm <= 0:
        raise ValueError("diameter_tolerance_mm must be positive")
    distance = abs(diameter_mm - expected_diameter_mm)
    base = max(0.0, 1.0 - distance / diameter_tolerance_mm)
    context_bonus = 0.05 if context_match else 0.0
    pattern_bonus = 0.08 if pattern_match else 0.0
    raw = min(1.0, base + context_bonus + pattern_bonus)
    return min(raw, ceiling)


# ---------------------------------------------------------------------------
# Manufacturable through-hole window (for the generic / fallback rules)
# ---------------------------------------------------------------------------

# Per Feature_Taxonomy.md THROUGH_HOLE has a general diameter range of 2-60mm,
# but the *manufacturable & confidently-a-drilled-hole* window for cabinet work
# is narrower: routine wood drilling tooling covers roughly 3-25mm. We grade a
# generic drill-layer circle by how central its diameter sits in this window so
# that a clean 5mm/8mm hole is confidently a hole while a 50mm bore (too big to
# drill; really a routed bore) or a sub-3mm circle (below drill range; likely a
# marking/artifact) score LOW and get flagged rather than asserted as a
# confident THROUGH_HOLE.
THROUGH_HOLE_MIN_MM = 3.0
THROUGH_HOLE_MAX_MM = 30.0
# Soft margin over which confidence ramps to zero outside the window.
THROUGH_HOLE_EDGE_RAMP_MM = 4.0


def compute_through_hole_confidence(
    diameter_mm: float,
    ceiling: float,
) -> float:
    """Graded confidence that a generic drill-layer circle is a THROUGH_HOLE.

    Inside ``[THROUGH_HOLE_MIN_MM, THROUGH_HOLE_MAX_MM]`` the diameter is a
    plausible drilled hole and confidence sits at ``ceiling``. Outside the
    window confidence ramps linearly to 0 over ``THROUGH_HOLE_EDGE_RAMP_MM`` so
    that:

      * a 50mm circle -> 0.0 (far above the drill window) -> rejected/UNKNOWN,
      * a 2mm circle  -> well below ceiling and under the accept threshold,
      * a 5/8/12mm circle -> full ceiling.
    """
    if diameter_mm is None:
        return 0.0
    if THROUGH_HOLE_MIN_MM <= diameter_mm <= THROUGH_HOLE_MAX_MM:
        return ceiling
    if diameter_mm < THROUGH_HOLE_MIN_MM:
        deficit = THROUGH_HOLE_MIN_MM - diameter_mm
    else:
        deficit = diameter_mm - THROUGH_HOLE_MAX_MM
    frac = max(0.0, 1.0 - deficit / THROUGH_HOLE_EDGE_RAMP_MM)
    return ceiling * frac


# ---------------------------------------------------------------------------
# Calibration harness
# ---------------------------------------------------------------------------


@dataclass
class ReliabilityBin:
    """One bin of a reliability diagram."""

    lower: float  # bin lower edge (inclusive)
    upper: float  # bin upper edge (exclusive, except the last bin)
    count: int  # number of predictions in this bin
    mean_confidence: float  # average predicted confidence in the bin
    empirical_accuracy: float  # fraction actually correct in the bin

    @property
    def gap(self) -> float:
        """Absolute calibration gap |confidence - accuracy| for this bin."""
        return abs(self.mean_confidence - self.empirical_accuracy)


def reliability_curve(
    pairs: list[tuple[float, bool]],
    n_bins: int = 10,
) -> list[ReliabilityBin]:
    """Bin (confidence, correct?) pairs into a reliability diagram.

    Parameters
    ----------
    pairs:
        ``(confidence, is_correct)`` tuples. ``confidence`` is clamped to
        ``[0, 1]``.
    n_bins:
        Number of equal-width bins over ``[0, 1]``.

    Returns one ``ReliabilityBin`` per bin (empty bins included with count 0 so
    the curve always has ``n_bins`` entries). A perfectly calibrated model has
    ``mean_confidence == empirical_accuracy`` in every populated bin.
    """
    if n_bins <= 0:
        raise ValueError("n_bins must be positive")

    edges = [i / n_bins for i in range(n_bins + 1)]
    sums_conf = [0.0] * n_bins
    sums_correct = [0] * n_bins
    counts = [0] * n_bins

    for conf, correct in pairs:
        c = min(1.0, max(0.0, float(conf)))
        # Bin index; the top edge (1.0) falls into the last bin.
        idx = min(n_bins - 1, int(c * n_bins))
        sums_conf[idx] += c
        sums_correct[idx] += 1 if correct else 0
        counts[idx] += 1

    bins: list[ReliabilityBin] = []
    for i in range(n_bins):
        n = counts[i]
        mean_conf = (sums_conf[i] / n) if n else 0.0
        emp_acc = (sums_correct[i] / n) if n else 0.0
        bins.append(
            ReliabilityBin(
                lower=edges[i],
                upper=edges[i + 1],
                count=n,
                mean_confidence=mean_conf,
                empirical_accuracy=emp_acc,
            )
        )
    return bins


def expected_calibration_error(
    pairs: list[tuple[float, bool]],
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error (ECE) for (confidence, correct?) pairs.

    ECE = sum_b (count_b / N) * |mean_confidence_b - accuracy_b|

    A value of 0 means perfect calibration; larger values mean confidences are
    systematically wrong (over- or under-confident). Always in ``[0, 1]``.
    Empty input returns 0.0.
    """
    total = len(pairs)
    if total == 0:
        return 0.0
    bins = reliability_curve(pairs, n_bins=n_bins)
    ece = 0.0
    for b in bins:
        if b.count == 0:
            continue
        ece += (b.count / total) * b.gap
    return ece


# ---------------------------------------------------------------------------
# Learned calibration (isotonic regression via Pool-Adjacent-Violators)
# ---------------------------------------------------------------------------


def _pav(points: list[tuple[float, float, float]]) -> list[tuple[float, float]]:
    """Weighted Pool-Adjacent-Violators on (x, mean_y, weight) points sorted by x.

    Each point must have a UNIQUE x (aggregate ties before calling). Returns
    (x_threshold, calibrated_value) breakpoints of the fitted monotonic
    non-decreasing step function. Pure Python — no sklearn dependency.
    """
    # Blocks of [sum_wy, weight, x_right]. Merge while the running mean decreases.
    blocks: list[list[float]] = []
    for x, mean_y, w in points:
        blocks.append([mean_y * w, w, x])
        while len(blocks) >= 2 and (
            (blocks[-2][0] / blocks[-2][1]) > (blocks[-1][0] / blocks[-1][1])
        ):
            sy2, w2, _x2 = blocks.pop()
            sy1, w1, _x1 = blocks.pop()
            blocks.append([sy1 + sy2, w1 + w2, x])  # pooled block keeps the right x
    return [(b[2], b[0] / b[1]) for b in blocks]


class IsotonicCalibrator:
    """A learned, monotonic confidence calibrator.

    Fits isotonic regression mapping raw confidence -> empirical correctness
    probability on a labelled ``(confidence, is_correct)`` set, then remaps future
    confidences. Monotonic (preserves ranking), reduces ECE, needs no sklearn.

    Honesty note: fitting on synthetic data only recalibrates against synthetic
    ground truth. A genuine real-world calibration guarantee still requires a
    held-out set of expert-labelled real parts — this class does not manufacture
    that guarantee, it only makes the mapping learnable once such data exists.
    """

    def __init__(self) -> None:
        self._breakpoints: list[tuple[float, float]] = []
        self.fitted = False

    def fit(self, pairs: list[tuple[float, bool]]) -> IsotonicCalibrator:
        if not pairs:
            return self
        # Aggregate by unique confidence value: (mean correctness, count). Without
        # this, sorting individual 0/1 outcomes fabricates a monotonic ramp and
        # PAV never pools (the classic isotonic-on-binary-labels pitfall).
        agg: dict[float, list[float]] = {}
        for c, y in pairs:
            cc = min(1.0, max(0.0, float(c)))
            bucket = agg.setdefault(cc, [0.0, 0.0])
            bucket[0] += 1.0 if y else 0.0
            bucket[1] += 1.0
        points = [
            (x, total_correct / count, count)
            for x, (total_correct, count) in sorted(agg.items())
        ]
        self._breakpoints = _pav(points)
        self.fitted = bool(self._breakpoints)
        return self

    def calibrate(self, confidence: float) -> float:
        """Map a raw confidence to its calibrated value (identity if unfitted)."""
        if not self.fitted:
            return confidence
        c = min(1.0, max(0.0, float(confidence)))
        # Step function: take the value of the last breakpoint whose x <= c.
        val = self._breakpoints[0][1]
        for x_thr, v in self._breakpoints:
            if c >= x_thr:
                val = v
            else:
                break
        return round(val, 6)

    # -- persistence -------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise the fitted mapping (JSON-friendly)."""
        return {
            "kind": "isotonic",
            "fitted": self.fitted,
            "breakpoints": [[round(x, 6), round(v, 6)] for x, v in self._breakpoints],
        }

    @classmethod
    def from_dict(cls, data: dict) -> IsotonicCalibrator:
        cal = cls()
        cal._breakpoints = [(float(x), float(v)) for x, v in data.get("breakpoints", [])]
        cal.fitted = bool(data.get("fitted") and cal._breakpoints)
        return cal

    def save(self, path) -> None:
        """Persist the calibrator to a JSON file."""
        import json
        from pathlib import Path

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path) -> IsotonicCalibrator:
        import json
        from pathlib import Path

        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
