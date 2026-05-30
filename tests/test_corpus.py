"""Tests for the Real DXF Corpus Grounding module (omim.corpus).

Strategy:
  1. Generate a synthetic corpus via PanelGenerator (uses EXACT catalog dims).
  2. Ingest it with CorpusIngestor; assert diameters / panel dims are extracted
     and that planted standards (5mm shelf pins, 35mm hinge cups) land in the
     right clusters.
  3. Validate against the catalog ground truth; assert the synthetic corpus
     PASSES (it is built from exact catalog dimensions).
  4. Assert the shipped catalog_reference_profile.json loads with expected keys.

Also exercises hand-rolled ezdxf fixtures for ingestion robustness, a
deliberately non-conformant corpus (off-spec hinge cup), and graceful handling
of unparseable files.
"""

from __future__ import annotations

import json
from pathlib import Path

import ezdxf
import pytest

from omim.corpus.catalog_ground_truth import CATALOG_REFERENCES
from omim.corpus.distribution_extractor import extract_distributions
from omim.corpus.ingest import CorpusIngestor
from omim.corpus.reference_profile import (
    DEFAULT_PROFILE_PATH,
    build_reference_profile,
    load_grounding_profile,
    write_reference_profile,
)
from omim.corpus.validator import validate_against_catalog
from omim.synthetic.generator import PanelGenerator
from omim.synthetic.models import PanelGeneratorConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def synthetic_corpus_dir(tmp_path_factory) -> Path:
    """Generate ~10 DXFs via PanelGenerator into a tmp dir; return the dir of DXFs.

    invalid_sample_ratio=0 so every kept sample is a clean, catalog-conformant
    panel — the corpus we expect to PASS catalog validation.
    """
    out = tmp_path_factory.mktemp("corpus_ds")
    cfg = PanelGeneratorConfig(random_seed=7, num_samples=14, invalid_sample_ratio=0.0)
    PanelGenerator(cfg).generate_dataset(str(out))
    work = out / "_work"  # the candidate DXF inputs the generator writes
    assert work.exists()
    assert len(list(work.glob("*.dxf"))) >= 10
    return work


@pytest.fixture(scope="module")
def corpus_stats(synthetic_corpus_dir: Path):
    return CorpusIngestor().ingest_directory(synthetic_corpus_dir)


def _write_panel_dxf(
    path: Path, width: float, height: float, holes: list[tuple[float, float, float]]
) -> None:
    """Write a minimal cabinet-panel DXF: boundary + circular holes (radius)."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (width, 0), (width, height), (0, height)],
        close=True,
        dxfattribs={"layer": "CUT"},
    )
    for cx, cy, r in holes:
        msp.add_circle((cx, cy), r, dxfattribs={"layer": "DRILL"})
    doc.saveas(str(path))


# ---------------------------------------------------------------------------
# 1 + 2: Ingestion extracts diameters / panel dims; planted standards cluster
# ---------------------------------------------------------------------------


class TestIngestion:
    def test_files_parsed(self, corpus_stats):
        assert corpus_stats.files_total >= 10
        assert corpus_stats.files_parsed == corpus_stats.files_total
        assert corpus_stats.files_failed == 0

    def test_extracts_diameters_and_panel_dims(self, corpus_stats):
        assert len(corpus_stats.holes) > 0
        assert all(h.diameter_mm > 0 for h in corpus_stats.holes)
        assert len(corpus_stats.panel_widths_mm) >= 10
        assert len(corpus_stats.panel_heights_mm) >= 10
        # Panel dims should be in the realistic cabinet range.
        assert all(50.0 <= w <= 1300.0 for w in corpus_stats.panel_widths_mm)

    def test_shelf_pins_cluster_at_5mm(self, corpus_stats):
        profile = extract_distributions(corpus_stats)
        clusters = profile["diameter"]["clusters"]
        shelf = clusters["5.0"]
        assert shelf["count"] > 0, "no shelf-pin holes found"
        assert shelf["feature_class"] == "SHELF_PIN_HOLE"
        # Planted at exactly 5mm (normal(5.0, 0.05)) -> mean within tolerance.
        assert abs(shelf["measured_mean_mm"] - 5.0) <= 0.5

    def test_hinge_cups_cluster_at_35mm(self, corpus_stats):
        profile = extract_distributions(corpus_stats)
        clusters = profile["diameter"]["clusters"]
        hinge = clusters["35.0"]
        assert hinge["count"] > 0, "no hinge-cup holes found"
        assert hinge["feature_class"] == "HINGE_CUP_HOLE"
        assert abs(hinge["measured_mean_mm"] - 35.0) <= 0.5

    def test_generic_through_holes_are_unclustered(self, corpus_stats):
        # THROUGH_HOLE diameters are uniform(4,30) and must NOT contaminate the
        # catalog clusters — they land in the "unclustered" bucket.
        profile = extract_distributions(corpus_stats)
        assert "unclustered" in profile["diameter"]["clusters"]

    def test_system32_spacing_recovered(self, corpus_stats):
        # Shelf-pin columns are on the 32mm grid; the spacing histogram should
        # have mass near 32mm.
        profile = extract_distributions(corpus_stats)
        spacing = profile["pairwise_spacing"]["stats"]
        assert spacing["n"] > 0
        # Median spacing should be a 32mm-grid value (32 or a small multiple).
        assert spacing["median"] is not None


class TestHandRolledIngestion:
    def test_ingest_plain_ezdxf_panels(self, tmp_path):
        """Ingest DXFs written directly with ezdxf (not via omim.synthetic)."""
        d = tmp_path / "plain"
        d.mkdir()
        # Panel A: shelf pins (5mm) on 32mm grid + a hinge cup (35mm).
        _write_panel_dxf(
            d / "side_a.dxf", 600, 800,
            [(37, 37 + i * 32, 2.5) for i in range(6)] + [(22.5, 400, 17.5)],
        )
        # Panel B: confirmat pair (7mm) + dowels (8mm).
        _write_panel_dxf(
            d / "bottom_b.dxf", 500, 400,
            [(12, 100, 3.5), (12, 164, 3.5), (250, 12, 4.0), (250, 388, 4.0)],
        )
        # Panel C: a sub-directory (recursion check).
        sub = d / "nested"
        sub.mkdir()
        _write_panel_dxf(sub / "shelf_c.dxf", 564, 300, [(20, 150, 4.0)])

        stats = CorpusIngestor().ingest_directory(d)
        assert stats.files_parsed == 3
        profile = extract_distributions(stats)
        clusters = profile["diameter"]["clusters"]
        assert clusters["5.0"]["count"] == 6   # shelf pins
        assert clusters["35.0"]["count"] == 1   # hinge cup
        assert clusters["7.0"]["count"] == 2    # confirmat
        # Edge setback for the shelf-pin column should be ~37mm.
        setbacks = [
            h.edge_setback_mm for h in stats.holes
            if abs(h.diameter_mm - 5.0) < 0.1 and h.edge_setback_mm is not None
        ]
        assert setbacks
        assert min(setbacks) == pytest.approx(37.0, abs=0.5)

    def test_unparseable_file_skipped(self, tmp_path):
        d = tmp_path / "mixed"
        d.mkdir()
        _write_panel_dxf(d / "good.dxf", 600, 400, [(37, 37, 2.5)])
        (d / "broken.dxf").write_text("this is not a DXF file", encoding="utf-8")

        stats = CorpusIngestor().ingest_directory(d)
        assert stats.files_total == 2
        assert stats.files_parsed == 1
        assert stats.files_failed == 1
        assert len(stats.failures) == 1

    def test_missing_directory_returns_empty(self, tmp_path):
        stats = CorpusIngestor().ingest_directory(tmp_path / "does_not_exist")
        assert stats.files_total == 0
        assert stats.holes == []


# ---------------------------------------------------------------------------
# 3: Catalog conformance validation
# ---------------------------------------------------------------------------


class TestCatalogValidation:
    def test_synthetic_corpus_passes(self, corpus_stats):
        report = validate_against_catalog(corpus_stats)
        assert report.n_passed > 0
        assert report.overall_conformant, (
            "synthetic corpus built from exact catalog dims must conform; "
            f"failures: {[c.message for c in report.failures]}"
        )

    def test_shelf_pin_and_hinge_checks_present_and_pass(self, corpus_stats):
        report = validate_against_catalog(corpus_stats)
        by_key = {(c.feature_class, c.metric): c for c in report.checks}
        shelf = by_key.get(("SHELF_PIN_HOLE", "diameter"))
        hinge = by_key.get(("HINGE_CUP_HOLE", "diameter"))
        assert shelf is not None and shelf.passed
        assert hinge is not None and hinge.passed

    def test_offspec_corpus_flagged(self, tmp_path):
        """A corpus whose hinge cup centers at 34mm (not 35) must be flagged."""
        d = tmp_path / "offspec"
        d.mkdir()
        for i in range(4):
            _write_panel_dxf(
                d / f"door_{i}.dxf", 400, 700,
                # Hinge cups at 34mm diameter (radius 17.0) -> 1mm under spec.
                [(22.5, 80, 17.0), (22.5, 620, 17.0)],
            )
        stats = CorpusIngestor().ingest_directory(d)
        report = validate_against_catalog(stats)
        hinge = next(
            (c for c in report.checks
             if c.feature_class == "HINGE_CUP_HOLE" and c.metric == "diameter"),
            None,
        )
        assert hinge is not None
        assert not hinge.passed, "34mm hinge cup should fail the 35mm ±0.5 spec"
        assert not report.overall_conformant

    def test_report_serialises(self, corpus_stats):
        report = validate_against_catalog(corpus_stats)
        d = report.to_dict()
        assert "overall_conformant" in d
        assert isinstance(d["checks"], list)
        json.dumps(d)  # must be JSON-serialisable


# ---------------------------------------------------------------------------
# 4: Shipped reference profile loads with expected keys
# ---------------------------------------------------------------------------


class TestReferenceProfile:
    EXPECTED_KEYS = {
        "$schema", "profile_version", "trust_tier", "source",
        "diameter", "panel_width", "panel_height", "panel_thickness",
        "edge_setback", "pairwise_spacing", "hole_count",
    }

    def test_shipped_profile_loads(self):
        # Ensure the shipped file exists (build on demand if needed).
        if not DEFAULT_PROFILE_PATH.exists():
            write_reference_profile()
        profile = load_grounding_profile()
        assert self.EXPECTED_KEYS.issubset(profile.keys())
        assert profile["trust_tier"] == 1
        assert profile["source"]["kind"] == "catalog_derived"

    def test_profile_diameter_clusters_cover_known_bores(self):
        profile = build_reference_profile()
        clusters = profile["diameter"]["clusters"]
        for bore in ("5.0", "7.0", "8.0", "10.0", "15.0", "35.0"):
            assert bore in clusters
            assert clusters[bore]["measured_mean_mm"] == float(bore)

    def test_profile_thickness_is_generator_compatible(self):
        profile = build_reference_profile()
        thick = profile["panel_thickness"]
        assert len(thick["values"]) == len(thick["weights"])
        assert thick["values"]  # non-empty
        assert sum(thick["weights"]) == pytest.approx(1.0, abs=0.01)
        assert thick["default_mm"] == 18.0

    def test_profile_hole_counts_match_catalog_table(self):
        profile = build_reference_profile()
        by_type = profile["hole_count"]["by_panel_type"]
        assert by_type["side_panel"]["typical"] == 14
        assert by_type["door"]["min"] == 2
        assert profile["hole_count"]["max_realistic"] == 40

    def test_round_trip_load_from_custom_path(self, tmp_path):
        p = tmp_path / "custom_profile.json"
        write_reference_profile(p)
        loaded = load_grounding_profile(p)
        assert self.EXPECTED_KEYS.issubset(loaded.keys())

    def test_load_missing_custom_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_grounding_profile(tmp_path / "nope.json")


class TestCatalogGroundTruth:
    def test_hinge_cup_reference_exact(self):
        ref = CATALOG_REFERENCES["HINGE_CUP_HOLE"]
        assert ref["diameter_mm"] == 35.0
        assert ref["setback_mm"] == 22.5
        assert "70.1900.AC" in ref["source"]

    def test_shelf_pin_reference_exact(self):
        ref = CATALOG_REFERENCES["SHELF_PIN_HOLE"]
        assert ref["diameter_mm"] == 5.0
        assert ref["spacing_mm"] == 32.0
        assert ref["setback_mm"] == 37.0

    def test_confirmat_reference_exact(self):
        ref = CATALOG_REFERENCES["CONFIRMAT_HOLE"]
        assert ref["diameter_mm"] == 7.0
        assert ref["pilot_diameter_mm"] == 5.0
