"""Coverage / yield / noise acceptance tests for the synthetic generator.

These guard the gaps closed in the milled-feature + invalid-yield + noise work:

  1. A 300-sample dataset exercises >= 12 distinct feature classes with
     non-trivial counts (previously only 6 classes were ever produced).
  2. MFG-003 and MFG-004 violations are injectable and appear among the
     injected violations of invalid samples (pockets now exist to violate).
  3. The realised invalid ratio tracks the requested ratio within a few percent
     (the verify-and-retry loop closes the silent-drop leak).
  4. Noise knobs jitter geometry when enabled and are a pure no-op (still
     byte-reproducible) when disabled.
"""

from __future__ import annotations

import glob
import json
import os
from collections import Counter

import pytest

from omim.synthetic.generator import PanelGenerator
from omim.synthetic.models import PanelGeneratorConfig

REQUESTED_INVALID_RATIO = 0.30
NUM_SAMPLES = 300
SEED = 42


@pytest.fixture(scope="module")
def coverage_dataset(tmp_path_factory):
    """Generate a 300-sample dataset once for the coverage assertions."""
    out = tmp_path_factory.mktemp("omim_cov")
    cfg = PanelGeneratorConfig(
        random_seed=SEED,
        num_samples=NUM_SAMPLES,
        invalid_sample_ratio=REQUESTED_INVALID_RATIO,
    )
    manifest = PanelGenerator(cfg).generate_dataset(str(out))
    return out, manifest


def _label_files(out):
    return glob.glob(os.path.join(str(out), "samples", "*", "labels.json"))


def _class_counts(out) -> Counter:
    counts: Counter = Counter()
    for path in _label_files(out):
        lab = json.load(open(path))
        for feat in lab["features"]:
            counts[feat["feature_class"]] += 1
    return counts


def _injected_violation_counts(out) -> Counter:
    counts: Counter = Counter()
    for path in _label_files(out):
        lab = json.load(open(path))
        for rule_id in lab.get("injected_violations", []):
            counts[rule_id] += 1
    return counts


class TestFeatureClassCoverage:
    def test_at_least_twelve_distinct_classes(self, coverage_dataset):
        out, _ = coverage_dataset
        counts = _class_counts(out)
        # Exclude PROFILE_CUT (always present) from the "learnable variety" count.
        non_profile = {c: n for c, n in counts.items() if c != "PROFILE_CUT"}
        assert len(non_profile) >= 12, (
            f"only {len(non_profile)} non-profile classes generated: "
            f"{sorted(non_profile)}"
        )

    def test_milled_and_profile_classes_present(self, coverage_dataset):
        """The previously-missing milled / profile classes must now appear."""
        out, _ = coverage_dataset
        counts = _class_counts(out)
        expected_now_present = [
            "POCKET",
            "GROOVE",
            "DADO",
            "RABBET",
            "INTERNAL_CUTOUT",
            "BLIND_HOLE",
            "COUNTERSINK",
            "COUNTERBORE",
        ]
        missing = [c for c in expected_now_present if counts.get(c, 0) == 0]
        assert not missing, f"expected classes never generated: {missing}"

    def test_counts_are_non_trivial(self, coverage_dataset):
        """Holes stay dominant; milled features appear with non-trivial counts."""
        out, _ = coverage_dataset
        counts = _class_counts(out)
        # Holes remain the bulk of the population.
        assert counts["SHELF_PIN_HOLE"] > counts["POCKET"]
        # A handful of distinct milled classes each clear a small floor.
        milled = ["POCKET", "GROOVE", "DADO", "RABBET"]
        for c in milled:
            assert counts.get(c, 0) >= 5, f"{c} count too low: {counts.get(c, 0)}"


class TestInvalidYield:
    def test_realized_ratio_matches_requested(self, coverage_dataset):
        _, manifest = coverage_dataset
        realized = manifest.invalid_count / max(1, manifest.total_samples)
        assert abs(realized - REQUESTED_INVALID_RATIO) <= 0.05, (
            f"realized invalid ratio {realized:.3f} not within 5% of "
            f"{REQUESTED_INVALID_RATIO}"
        )

    def test_invalid_samples_actually_fail_validation(self, coverage_dataset):
        """Every sample labelled invalid must have failed the validator (gatekeeper)."""
        out, _ = coverage_dataset
        for sdir in glob.glob(os.path.join(str(out), "samples", "*")):
            lab = json.load(open(os.path.join(sdir, "labels.json")))
            val = json.load(open(os.path.join(sdir, "validation.json")))
            assert val["overall_valid"] == lab["is_valid"]


class TestNewViolationsInjectable:
    def test_mfg003_and_mfg004_appear(self, coverage_dataset):
        out, _ = coverage_dataset
        viol = _injected_violation_counts(out)
        assert viol.get("MFG-003", 0) > 0, "MFG-003 never injected"
        assert viol.get("MFG-004", 0) > 0, "MFG-004 never injected"


class TestNoise:
    def test_diameter_noise_changes_diameters(self):
        clean_cfg = PanelGeneratorConfig(random_seed=SEED, num_samples=20)
        noisy_cfg = PanelGeneratorConfig(
            random_seed=SEED, num_samples=20, diameter_noise_sigma_mm=0.5
        )
        clean = PanelGenerator(clean_cfg)
        noisy = PanelGenerator(noisy_cfg)

        def radii(gen):
            out = []
            for i in range(20):
                for f in gen.generate_sample(i).features:
                    if f.radius_mm is not None:
                        out.append(round(f.radius_mm, 4))
            return out

        assert radii(clean) != radii(noisy)

    def test_noise_off_is_unchanged_and_reproducible(self):
        cfg = PanelGeneratorConfig(random_seed=SEED, num_samples=15)
        a = PanelGenerator(cfg)
        b = PanelGenerator(cfg)

        def key(gen):
            return [
                [(f.feature_class, f.center, f.radius_mm, f.points) for f in
                 gen.generate_sample(i).features]
                for i in range(15)
            ]

        assert key(a) == key(b)

    def test_noisy_generation_is_reproducible(self):
        cfg = PanelGeneratorConfig(
            random_seed=SEED,
            num_samples=15,
            diameter_noise_sigma_mm=0.3,
            layer_noise=True,
            duplicate_entity_prob=0.1,
            rotation_deg=2.0,
        )
        a = PanelGenerator(cfg)
        b = PanelGenerator(cfg)

        def key(gen):
            return [
                [(f.feature_class, f.layer, f.center, f.radius_mm, f.points) for f in
                 gen.generate_sample(i).features]
                for i in range(15)
            ]

        assert key(a) == key(b)
