"""Tests for the validation engine."""

from omim.graph.builder import MGGBuilder
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry
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
        all_results = report.layer1_results + report.layer2_results
        failed_count = sum(1 for r in all_results if not r.passed)
        assert constraint_count == failed_count

    def test_layer2_skipped_on_layer1_error(self):
        """If Layer 1 has ERRORs, Layer 2 should not run."""
        # Create a panel with geometry that has coordinates out of range
        panel_pts = [[0, 0], [200, 0], [200, 200], [0, 200]]
        entities = [
            RawEntity(
                entity_id="1",
                ezdxf_handle="h1",
                entity_type="LWPOLYLINE",
                layer="cut",
                inferred_layer_type="cut",
                coordinates=panel_pts,
                is_closed=True,
                bounding_box=[0, 0, 200, 200],
                centroid=[100.0, 100.0],
                area_mm2=40000.0,
                perimeter_mm=800.0,
            ),
            # Circle with coordinates outside [-100, 5000] range
            RawEntity(
                entity_id="2",
                ezdxf_handle="h2",
                entity_type="CIRCLE",
                layer="drill",
                inferred_layer_type="drill",
                coordinates=[6000, 100, 2.5],
                is_closed=True,
                bounding_box=[5997.5, 97.5, 6002.5, 102.5],
                centroid=[6000, 100],
                area_mm2=19.635,
                perimeter_mm=15.708,
                diameter_mm=5.0,
                radius_mm=2.5,
            ),
        ]
        raw = RawGeometry(
            source_file="test.dxf",
            source_file_hash="sha256:test",
            dxf_version="AC1027",
            entities=entities,
            panel_boundary=PanelBoundary(
                entity_id="1",
                coordinates=panel_pts,
                bounding_box=[0, 0, 200, 200],
                area_mm2=40000.0,
                inferred=False,
            ),
            panel_boundary_inferred=False,
            entity_counts={"LWPOLYLINE": 1, "CIRCLE": 1},
        )
        mgg = MGGBuilder().build(raw)
        engine = RuleEngine()
        report = engine.validate(mgg, annotate_graph=False)

        # Layer 1 should fail (GEO-004 coordinate range + GEO-007 out of bounds)
        assert not report.layer1_passed
        # Layer 2 should not have run
        assert len(report.layer2_results) == 0


class TestEdgeDistanceRule:
    def test_hole_too_close_to_edge(self):
        """A hole 3mm from panel edge should trigger MFG-001."""
        panel_pts = [[0, 0], [200, 0], [200, 200], [0, 200]]
        entities = [
            RawEntity(
                entity_id="1",
                ezdxf_handle="h1",
                entity_type="LWPOLYLINE",
                layer="cut",
                inferred_layer_type="cut",
                coordinates=panel_pts,
                is_closed=True,
                bounding_box=[0, 0, 200, 200],
                centroid=[100.0, 100.0],
                area_mm2=40000.0,
                perimeter_mm=800.0,
            ),
            RawEntity(
                entity_id="2",
                ezdxf_handle="h2",
                entity_type="CIRCLE",
                layer="drill",
                inferred_layer_type="drill",
                coordinates=[5, 100, 2.5],  # Only 5mm from left edge (centroid)
                is_closed=True,
                bounding_box=[2.5, 97.5, 7.5, 102.5],
                centroid=[5, 100],
                area_mm2=19.635,
                perimeter_mm=15.708,
                diameter_mm=5.0,
                radius_mm=2.5,
            ),
        ]
        raw = RawGeometry(
            source_file="test.dxf",
            source_file_hash="sha256:test",
            dxf_version="AC1027",
            entities=entities,
            panel_boundary=PanelBoundary(
                entity_id="1",
                coordinates=panel_pts,
                bounding_box=[0, 0, 200, 200],
                area_mm2=40000.0,
                inferred=False,
            ),
            panel_boundary_inferred=False,
            entity_counts={"LWPOLYLINE": 1, "CIRCLE": 1},
        )
        mgg = MGGBuilder().build(raw)
        engine = RuleEngine()
        report = engine.validate(mgg, annotate_graph=False)

        mfg001 = [r for r in report.layer2_results if r.rule_id == "MFG-001"]
        assert len(mfg001) > 0
        assert not mfg001[0].passed
        assert mfg001[0].severity == "ERROR"
