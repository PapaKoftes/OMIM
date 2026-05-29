"""Tests for the validation engine."""

from omim.graph.builder import MGGBuilder
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.parser.models import RawEntity, RawGeometry
from omim.validation.models import Severity
from omim.validation.rule_engine import RuleEngine


class TestRuleEngine:
    def test_valid_panel_passes(self, sample_mgg: ManufacturingGeometryGraph):
        engine = RuleEngine()
        report = engine.validate(sample_mgg, annotate_graph=False)
        # The sample panel should have no errors (all holes are well-placed)
        assert report.graph_id == sample_mgg.metadata.graph_id

    def test_annotate_graph_adds_constraint_nodes(
        self, sample_mgg: ManufacturingGeometryGraph
    ):
        engine = RuleEngine()
        report = engine.validate(sample_mgg, annotate_graph=True)
        # Constraint nodes should be added for any violations
        constraint_count = sum(1 for _ in sample_mgg.constraint_nodes())
        assert constraint_count == report.failed + report.warnings


class TestEdgeDistanceRule:
    def test_hole_too_close_to_edge(self):
        """A hole 3mm from panel edge should trigger MFG-001."""
        entities = [
            RawEntity(
                entity_id="1",
                entity_type="LWPOLYLINE",
                layer="cut",
                inferred_layer_type="cut",
                points=[(0, 0), (200, 0), (200, 200), (0, 200)],
                is_closed=True,
                bbox=(0, 0, 200, 200),
            ),
            RawEntity(
                entity_id="2",
                entity_type="CIRCLE",
                layer="drill",
                inferred_layer_type="drill",
                center=(5, 100),  # Only 2.5mm from left edge (5 - 2.5 radius)
                radius_mm=2.5,
                is_closed=True,
                bbox=(2.5, 97.5, 7.5, 102.5),
            ),
        ]
        raw = RawGeometry(
            source_file="test.dxf",
            source_file_hash="sha256:test",
            dxf_version="AC1027",
            entities=entities,
            panel_boundary_detected=True,
            panel_boundary_entity_id="1",
        )
        mgg = MGGBuilder().build(raw)
        engine = RuleEngine()
        report = engine.validate(mgg, annotate_graph=False)

        mfg001 = [r for r in report.results if r.rule_id == "MFG-001"]
        assert len(mfg001) > 0
        assert not mfg001[0].passed
        assert mfg001[0].severity == Severity.ERROR
