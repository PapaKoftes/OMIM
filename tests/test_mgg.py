"""Tests for the Manufacturing Geometry Graph."""

from omim.graph.builder import MGGBuilder
from omim.graph.models import EdgeType, FeatureNode, GraphMetadata
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.parser.models import RawGeometry


class TestMGGBuilder:
    def test_build_creates_geometry_nodes(self, sample_raw_geometry: RawGeometry):
        mgg = MGGBuilder().build(sample_raw_geometry)
        geom_count = sum(1 for _ in mgg.geometry_nodes())
        # 1 panel + 4 shelf pins + 1 hinge cup = 6
        assert geom_count == 6

    def test_build_detects_panel(self, sample_raw_geometry: RawGeometry):
        mgg = MGGBuilder().build(sample_raw_geometry)
        assert mgg.metadata.panel_width_mm == 600.0
        assert mgg.metadata.panel_height_mm == 400.0

    def test_panel_boundary_marked(self, sample_raw_geometry: RawGeometry):
        mgg = MGGBuilder().build(sample_raw_geometry)
        panel = mgg.get_node("geom-100")
        assert panel is not None
        assert panel["is_outer_boundary"] is True

    def test_shapely_enrichment(self, sample_raw_geometry: RawGeometry):
        mgg = MGGBuilder().build(sample_raw_geometry)
        # Check a circle node got enriched
        hole = mgg.get_node("geom-201")
        assert hole is not None
        assert hole["diameter_mm"] == 5.0
        assert hole["centroid"] == [37, 100]
        assert hole["area_mm2"] is not None
        assert hole["area_mm2"] > 0


class TestMGG:
    def test_add_and_get_node(self):
        meta = GraphMetadata(graph_id="test-1")
        mgg = ManufacturingGeometryGraph(meta)
        feat = FeatureNode(
            node_id="feat-1",
            feature_class="SHELF_PIN_HOLE",
            confidence=0.95,
        )
        mgg.add_feature_node(feat)
        assert mgg.has_node("feat-1")
        data = mgg.get_node("feat-1")
        assert data["feature_class"] == "SHELF_PIN_HOLE"

    def test_edge_operations(self):
        meta = GraphMetadata(graph_id="test-2")
        mgg = ManufacturingGeometryGraph(meta)
        feat_a = FeatureNode(node_id="f1", feature_class="A", confidence=0.9)
        feat_b = FeatureNode(node_id="f2", feature_class="B", confidence=0.8)
        mgg.add_feature_node(feat_a)
        mgg.add_feature_node(feat_b)

        mgg.add_edge("f1", "f2", EdgeType.SAME_GROUP)
        assert mgg.edge_count == 1
        edges = mgg.edges_by_type(EdgeType.SAME_GROUP)
        assert len(edges) == 1
        assert edges[0][0] == "f1"
        assert edges[0][1] == "f2"

    def test_serialization_roundtrip(self, sample_mgg: ManufacturingGeometryGraph):
        json_str = sample_mgg.to_json()
        restored = ManufacturingGeometryGraph.from_json(json_str)
        assert restored.node_count == sample_mgg.node_count
        assert restored.metadata.graph_id == sample_mgg.metadata.graph_id
