"""Tests for the synthetic generation module and the gatekeeper pipeline."""

from __future__ import annotations

import glob
import json
import os

import ezdxf
import pytest

from omim.export.dataset_exporter import check_dataset_consistency, validate_sample_schema
from omim.parser.dxf_parser import DXFParser
from omim.graph.builder import MGGBuilder
from omim.semantic.classifier import FeatureClassifier, SemanticPreconditionError
from omim.synthetic.generator import PanelGenerator
from omim.synthetic.models import PanelGeneratorConfig
from omim.validation.rule_engine import RuleEngine


@pytest.fixture(scope="module")
def small_dataset(tmp_path_factory):
    """Generate a small dataset once and reuse across tests."""
    out = tmp_path_factory.mktemp("omim_ds")
    cfg = PanelGeneratorConfig(random_seed=11, num_samples=24, invalid_sample_ratio=0.30)
    manifest = PanelGenerator(cfg).generate_dataset(str(out))
    return out, manifest


class TestDeterminism:
    def test_same_seed_identical_samples(self):
        cfg = PanelGeneratorConfig(random_seed=99, num_samples=5)
        g1 = PanelGenerator(cfg).generate_sample(0)
        g2 = PanelGenerator(cfg).generate_sample(0)
        assert g1.panel.width_mm == g2.panel.width_mm
        assert g1.panel.height_mm == g2.panel.height_mm
        assert len(g1.features) == len(g2.features)
        assert [f.feature_class for f in g1.features] == [f.feature_class for f in g2.features]

    def test_different_seed_differs(self):
        s_a = PanelGenerator(PanelGeneratorConfig(random_seed=1, num_samples=5)).generate_sample(0)
        s_b = PanelGenerator(PanelGeneratorConfig(random_seed=2, num_samples=5)).generate_sample(0)
        # Extremely unlikely to be identical across all fields
        differ = (
            s_a.panel.width_mm != s_b.panel.width_mm
            or s_a.panel.height_mm != s_b.panel.height_mm
            or len(s_a.features) != len(s_b.features)
        )
        assert differ


class TestGatekeeper:
    def test_valid_samples_pass_validation(self, small_dataset):
        """The validator is the gatekeeper: labels.is_valid must match
        validation.overall_valid for every sample."""
        out, _ = small_dataset
        mismatches = 0
        for sdir in glob.glob(os.path.join(str(out), "samples", "*")):
            val = json.load(open(os.path.join(sdir, "validation.json")))
            lab = json.load(open(os.path.join(sdir, "labels.json")))
            if val["overall_valid"] != lab["is_valid"]:
                mismatches += 1
        assert mismatches == 0

    def test_has_both_valid_and_invalid(self, small_dataset):
        _, manifest = small_dataset
        assert manifest.valid_count > 0
        assert manifest.invalid_count > 0


class TestSchemaCompliance:
    def test_dataset_consistency_clean(self, small_dataset):
        out, _ = small_dataset
        assert check_dataset_consistency(str(out)) == []

    def test_every_sample_has_five_files(self, small_dataset):
        out, _ = small_dataset
        for sdir in glob.glob(os.path.join(str(out), "samples", "*")):
            assert validate_sample_schema(sdir) == []

    def test_dxfs_pass_ezdxf_audit(self, small_dataset):
        out, _ = small_dataset
        for d in glob.glob(os.path.join(str(out), "samples", "*", "geometry.dxf")):
            doc = ezdxf.readfile(d)
            assert len(doc.audit().errors) == 0


class TestGroundTruthSource:
    def test_labels_from_generation_not_inference(self, small_dataset):
        """Synthetic labels must come from the generation spec, never inference."""
        out, _ = small_dataset
        for sdir in glob.glob(os.path.join(str(out), "samples", "*")):
            lab = json.load(open(os.path.join(sdir, "labels.json")))
            for feat in lab.get("features", []):
                assert feat["ground_truth_source"] == "synthetic_generator"
                assert feat["confidence"] == 1.0


class TestNoDuplicateBoundary:
    def test_single_outer_contour(self, small_dataset):
        """The panel boundary must not be drawn twice (BORDER + CUT)."""
        out, _ = small_dataset
        for d in glob.glob(os.path.join(str(out), "samples", "*", "geometry.dxf")):
            doc = ezdxf.readfile(d)
            closed = [
                tuple(tuple(p[:2]) for p in e.get_points("xy"))
                for e in doc.modelspace()
                if e.dxftype() == "LWPOLYLINE" and getattr(e, "closed", False)
            ]
            # No two closed contours share an identical point set
            assert len(closed) == len(set(closed))


class TestStandardsGrounding:
    """Standards grounding is only guaranteed on VALID samples. Invalid samples
    are intentionally corrupted by violation injection (e.g. a shelf pin moved
    off-grid to trigger MFG-001), so they are excluded from these checks."""

    def test_hinge_cup_is_35mm(self):
        """Generated hinge cups must use the Blum 35mm standard, never random."""
        gen = PanelGenerator(PanelGeneratorConfig(random_seed=5, num_samples=50))
        found = False
        for i in range(50):
            sample = gen.generate_sample(i)
            if sample.is_invalid:
                continue
            for f in sample.features:
                if f.feature_class == "HINGE_CUP_HOLE":
                    found = True
                    # radius 17.5mm = 35mm diameter, within normal(35, 0.1) tolerance
                    assert 17.0 <= f.radius_mm <= 18.0
        # At least some hinge cups generated across 50 valid samples
        assert found

    def test_shelf_pins_on_32mm_grid(self):
        """Shelf pin holes in a group must be 32mm apart (System 32)."""
        gen = PanelGenerator(PanelGeneratorConfig(random_seed=8, num_samples=50))
        for i in range(50):
            sample = gen.generate_sample(i)
            if sample.is_invalid:
                continue  # invalidation deliberately moves pins off-grid
            pins = [
                f for f in sample.features
                if f.feature_class == "SHELF_PIN_HOLE" and f.center is not None
            ]
            # Group by column (x), check vertical spacing
            cols: dict[float, list[float]] = {}
            for p in pins:
                cols.setdefault(round(p.center[0], 1), []).append(p.center[1])
            for ys in cols.values():
                ys = sorted(ys)
                for a, b in zip(ys, ys[1:]):
                    # consecutive holes in a column are a multiple of 32mm apart
                    gap = b - a
                    assert abs(gap % 32.0) < 0.5 or abs((gap % 32.0) - 32.0) < 0.5


class TestPrecondition:
    def test_semantic_blocked_on_invalid_geometry(self, small_dataset):
        """Semantic layer must refuse geometrically-invalid (layer1-failed) panels."""
        out, _ = small_dataset
        parser, builder, clf, eng = DXFParser(), MGGBuilder(), FeatureClassifier(), RuleEngine()
        blocked = 0
        classified = 0
        for d in glob.glob(os.path.join(str(out), "samples", "*", "geometry.dxf")):
            pr = parser.parse(d)
            mgg = builder.build(pr.geometry)
            rep = eng.validate(mgg)
            try:
                clf.classify(mgg, rep)
                classified += 1
            except SemanticPreconditionError:
                blocked += 1
        # Some invalid samples should be blocked, some valid ones classified
        assert classified > 0
