"""Tests for the learned IsotonicCalibrator.

Proves the calibrator (a) is monotonic, (b) actually reduces ECE on a
deliberately mis-calibrated set, and (c) is an identity map until fitted.
"""

from __future__ import annotations

from omim.semantic.calibration import (
    IsotonicCalibrator,
    expected_calibration_error,
)


def _miscalibrated_pairs():
    """Build an over-confident set: predictions at confidence 0.9 that are only
    ~50% correct, plus a well-behaved high band. ECE should be sizeable."""
    pairs: list[tuple[float, bool]] = []
    # 100 predictions at 0.9 confidence, only 50% actually correct (over-confident).
    for i in range(100):
        pairs.append((0.9, i % 2 == 0))
    # 100 predictions at 0.6 confidence, 60% correct (well calibrated).
    for i in range(100):
        pairs.append((0.6, i % 10 < 6))
    return pairs


def test_calibrator_identity_until_fitted():
    cal = IsotonicCalibrator()
    assert cal.fitted is False
    assert cal.calibrate(0.83) == 0.83  # passthrough


def test_calibrator_is_monotonic():
    cal = IsotonicCalibrator().fit(_miscalibrated_pairs())
    assert cal.fitted
    xs = [i / 20 for i in range(21)]
    ys = [cal.calibrate(x) for x in xs]
    assert all(b >= a - 1e-9 for a, b in zip(ys, ys[1:])), "calibration must be monotonic"


def test_calibrator_reduces_ece():
    pairs = _miscalibrated_pairs()
    cal = IsotonicCalibrator().fit(pairs)

    raw_ece = expected_calibration_error(pairs)
    calibrated = [(cal.calibrate(c), y) for c, y in pairs]
    cal_ece = expected_calibration_error(calibrated)

    # The over-confident 0.9 band (50% correct) should be pulled down toward 0.5,
    # cutting ECE substantially.
    assert cal_ece < raw_ece
    assert cal_ece < 0.1, f"calibrated ECE should be small, got {cal_ece:.3f}"


def test_calibrator_maps_overconfident_band_down():
    """The 0.9-confidence/50%-correct band should calibrate to about 0.5."""
    cal = IsotonicCalibrator().fit(_miscalibrated_pairs())
    assert cal.calibrate(0.9) < 0.75  # pulled down from 0.9 toward ~0.5
