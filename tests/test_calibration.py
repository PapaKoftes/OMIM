"""Calibration harness tests + a MEASURED ECE on synthetic data.

These tests answer the question the audit raised: when the classifier says
"0.80", is it actually right ~80% of the time? We:

  1. unit-test ``reliability_curve`` / ``expected_calibration_error`` on
     synthetic pairs with a known answer,
  2. generate a real synthetic dataset (omim.synthetic), classify every VALID
     panel, join each prediction to the ground-truth label (by position, via the
     canonical benchmark join), build (confidence, correct?) pairs, and compute
     the empirical ECE + reliability curve.

The ECE is REPORTED (printed) rather than asserted against a tight bound: a
high ECE is a legitimate finding about calibration honesty, not a test failure.
We only assert it is a well-formed number in [0, 1].
"""

from __future__ import annotations

import glob
import os

import pytest

from omim.benchmarks.tasks import load_sample
from omim.semantic.calibration import (
    ReliabilityBin,
    expected_calibration_error,
    reliability_curve,
)
from omim.semantic.classifier import FeatureClassifier, SemanticPreconditionError
from omim.synthetic.generator import PanelGenerator
from omim.synthetic.models import PanelGeneratorConfig

# ---------------------------------------------------------------------------
# Pure harness unit tests (known answers)
# ---------------------------------------------------------------------------


class TestHarness:
    def test_ece_empty_is_zero(self):
        assert expected_calibration_error([]) == 0.0

    def test_perfectly_calibrated_low_ece(self):
        # 10 preds at conf 0.8, exactly 8 correct -> bin accuracy 0.8 == conf.
        pairs = [(0.8, True)] * 8 + [(0.8, False)] * 2
        ece = expected_calibration_error(pairs, n_bins=10)
        assert ece == pytest.approx(0.0, abs=1e-9)

    def test_overconfident_has_high_ece(self):
        # Always 0.9 confident but only 10% correct -> ECE ~0.8.
        pairs = [(0.9, True)] * 1 + [(0.9, False)] * 9
        ece = expected_calibration_error(pairs, n_bins=10)
        assert ece == pytest.approx(0.8, abs=1e-9)

    def test_ece_bounded_0_1(self):
        pairs = [(0.0, True), (1.0, False), (0.5, True), (0.3, False)]
        ece = expected_calibration_error(pairs)
        assert 0.0 <= ece <= 1.0

    def test_reliability_curve_shape(self):
        pairs = [(0.05, False), (0.95, True), (0.95, True), (0.55, False)]
        bins = reliability_curve(pairs, n_bins=10)
        assert len(bins) == 10
        assert all(isinstance(b, ReliabilityBin) for b in bins)
        # Total count across bins equals number of pairs.
        assert sum(b.count for b in bins) == len(pairs)
        # The 0.95 bin (index 9) holds 2 correct -> accuracy 1.0.
        assert bins[9].count == 2
        assert bins[9].empirical_accuracy == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Measured calibration on a real synthetic dataset
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dataset_dir(tmp_path_factory) -> str:
    d = tmp_path_factory.mktemp("omim_calib_ds")
    cfg = PanelGeneratorConfig(random_seed=42, num_samples=40, invalid_sample_ratio=0.3)
    PanelGenerator(cfg).generate_dataset(str(d))
    return str(d)


def _build_pairs(dataset_dir: str) -> list[tuple[float, bool]]:
    """Classify every VALID sample; pair each annotation's confidence with
    whether the predicted feature_class matches the ground-truth label."""
    clf = FeatureClassifier()
    pairs: list[tuple[float, bool]] = []
    for sdir in sorted(glob.glob(os.path.join(dataset_dir, "samples", "*"))):
        sample = load_sample(sdir)
        if not sample.is_valid:
            continue  # semantic layer only runs on geometrically-valid panels
        try:
            anns = clf.classify(sample.mgg.copy())
        except SemanticPreconditionError:
            continue
        truth = sample.node_truth  # node_id -> ground-truth feature_class
        for a in anns.feature_annotations:
            gt = truth.get(a.node_id)
            if gt is None:
                continue
            correct = a.feature_class == gt
            pairs.append((a.confidence, correct))
    return pairs


class TestMeasuredCalibration:
    def test_ece_and_curve_measured(self, dataset_dir, capsys):
        pairs = _build_pairs(dataset_dir)
        assert pairs, "expected classified annotations to score"

        ece = expected_calibration_error(pairs, n_bins=10)
        curve = reliability_curve(pairs, n_bins=10)

        # ECE is a well-formed number in [0, 1].
        assert isinstance(ece, float)
        assert 0.0 <= ece <= 1.0

        n = len(pairs)
        overall_acc = sum(1 for _, c in pairs if c) / n
        mean_conf = sum(conf for conf, _ in pairs) / n

        # REPORT the measured calibration (visible with `pytest -s`).
        with capsys.disabled():
            print("\n=== MEASURED CALIBRATION (synthetic, valid panels) ===")
            print(f"predictions scored : {n}")
            print(f"overall accuracy   : {overall_acc:.3f}")
            print(f"mean confidence    : {mean_conf:.3f}")
            print(f"mean - accuracy    : {mean_conf - overall_acc:+.3f} "
                  f"({'over' if mean_conf > overall_acc else 'under'}-confident)")
            print(f"Expected Calib Err : {ece:.4f}")
            quality = (
                "GOOD" if ece < 0.10 else "MODERATE" if ece < 0.20 else "POOR"
            )
            print(f"calibration verdict: {quality} (ECE {ece:.4f})")
            print("reliability curve (populated bins):")
            for b in curve:
                if b.count:
                    print(f"  [{b.lower:.1f},{b.upper:.1f}) n={b.count:3d} "
                          f"conf={b.mean_confidence:.3f} "
                          f"acc={b.empirical_accuracy:.3f} gap={b.gap:.3f}")

        # Sanity: bins cover all pairs.
        assert sum(b.count for b in curve) == n
