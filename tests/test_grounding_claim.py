"""The defining OMIM grounding claim, made executable.

    "Can OMIM reproduce valid cabinet manufacturing geometry that conforms to
     Blum/Hettich/Häfele specifications and passes all deterministic validation
     rules?"

If these tests pass, the synthetic generator is grounded in real manufacturing
reality (manufacturer catalogs) rather than producing arbitrary CAD shapes.

This ties together the whole thesis in one place:
    Manufacturing Standards -> Generator -> Validator (all rules pass)
                                         -> Corpus catalog conformance (Blum/Hettich)
"""

from __future__ import annotations

import glob
import os

import pytest

from omim.corpus.ingest import CorpusIngestor
from omim.corpus.validator import validate_against_catalog
from omim.graph.builder import MGGBuilder
from omim.parser.dxf_parser import DXFParser
from omim.synthetic.generator import PanelGenerator
from omim.synthetic.models import PanelGeneratorConfig
from omim.validation.rule_engine import RuleEngine


@pytest.fixture(scope="module")
def valid_only_dataset(tmp_path_factory):
    """Generate an all-valid dataset (invalid_ratio=0) — the geometry OMIM
    claims to reproduce faithfully."""
    out = tmp_path_factory.mktemp("omim_grounding")
    cfg = PanelGeneratorConfig(
        random_seed=2026,
        num_samples=40,
        invalid_sample_ratio=0.0,  # claim is about VALID geometry
    )
    manifest = PanelGenerator(cfg).generate_dataset(str(out))
    return out, manifest


class TestGroundingClaim:
    def test_all_generated_valid_samples_pass_every_rule(self, valid_only_dataset):
        """Part 1: every generated 'valid' panel passes ALL deterministic rules.

        This is the gatekeeper guarantee — geometry produced from standards is
        not merely labeled valid, it is *verified* valid by the rule engine.
        """
        out, manifest = valid_only_dataset
        assert manifest.invalid_count == 0

        parser, builder, engine = DXFParser(), MGGBuilder(), RuleEngine()
        checked = 0
        for dxf in glob.glob(os.path.join(str(out), "samples", "*", "geometry.dxf")):
            result = parser.parse(dxf)
            assert result.success and result.geometry is not None
            mgg = builder.build(result.geometry)
            report = engine.validate(mgg)
            failed = [
                r.rule_id
                for r in report.layer1_results + report.layer2_results
                if not r.passed
            ]
            assert report.overall_valid, f"{dxf} failed validation: {failed}"
            checked += 1
        assert checked > 0

    def test_generated_geometry_conforms_to_manufacturer_catalogs(self, valid_only_dataset):
        """Part 2: the generated corpus conforms to Blum/Hettich/Häfele catalog specs.

        Ingest the generated DXFs as if they were a real corpus, then run the
        catalog-conformance validator. Conformance here means hole diameters,
        edge setbacks, and the 32mm grid match the manufacturer ground truth.
        """
        out, _ = valid_only_dataset
        samples_dir = os.path.join(str(out), "samples")
        stats = CorpusIngestor().ingest_directory(samples_dir)
        report = validate_against_catalog(stats)
        assert report.overall_conformant, (
            "Generated geometry does not conform to manufacturer catalogs: "
            f"{[c for c in report.checks if not getattr(c, 'passed', True)]}"
        )
        assert report.n_failed == 0

    def test_planted_standards_are_present(self, valid_only_dataset):
        """The corpus actually contains the named standard features (not just
        conformant-by-vacuum): 35mm hinge cups, 5mm shelf pins, 7mm confirmat."""
        out, _ = valid_only_dataset
        stats = CorpusIngestor().ingest_directory(os.path.join(str(out), "samples"))
        # Each ingested hole is a HoleMeasurement with a diameter_mm field.
        diameters = [h.diameter_mm for h in stats.holes if h.diameter_mm is not None]
        assert diameters, "ingestion found no holes"

        def has_near(target, tol=0.6):
            return any(abs(d - target) <= tol for d in diameters)

        assert has_near(5.0), "no 5mm shelf-pin holes found (System 32)"
        assert has_near(35.0), "no 35mm hinge-cup holes found (Blum CLIP top)"
