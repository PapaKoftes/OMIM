"""Tests for omim.integrity -- check_graph_integrity & check_ontology_consistency.

Each structural fault (orphan geometry, dangling edge, self-loop, bad
confidence, non-ontology feature class, non-positive dimension) is injected
and asserted to be caught; a clean MGG must return ``[]``.
"""

from __future__ import annotations

from pathlib import Path

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.graph.models import EdgeType, FeatureNode, GeometryNode, GraphMetadata
from omim.integrity import check_graph_integrity, check_ontology_consistency
from omim.ontology.loader import Ontology, OperationDefinition, load_ontology

DATA_DIR = Path(__file__).parent.parent / "data"
ONTOLOGY_DIR = DATA_DIR / "ontology"
RULES_DIR = DATA_DIR / "rules"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _geometry_node(node_id: str, **overrides) -> GeometryNode:
    kwargs = dict(
        node_id=node_id,
        geometry_type="circle",
        layer="drill",
        inferred_layer_type="drill",
        coordinates=[10.0, 10.0, 2.5],
        is_closed=True,
        diameter_mm=5.0,
        radius_mm=2.5,
        area_mm2=19.635,
        centroid=[10.0, 10.0],
        source_entity_id=node_id,
    )
    kwargs.update(overrides)
    return GeometryNode(**kwargs)


def _feature_node(node_id: str, geometry_ids: list[str], **overrides) -> FeatureNode:
    kwargs = dict(
        node_id=node_id,
        feature_class="SHELF_PIN_HOLE",
        confidence=0.9,
        geometry_node_ids=geometry_ids,
    )
    kwargs.update(overrides)
    return FeatureNode(**kwargs)


def _clean_mgg() -> ManufacturingGeometryGraph:
    """A small structurally-clean MGG: one boundary, one geom referenced by a feature."""
    mgg = ManufacturingGeometryGraph(GraphMetadata(graph_id="integrity-test"))
    boundary = _geometry_node(
        "geom-boundary",
        geometry_type="lwpolyline",
        inferred_layer_type="cut",
        layer="cut",
        coordinates=[[0, 0], [100, 0], [100, 100], [0, 100]],
        diameter_mm=None,
        radius_mm=None,
        area_mm2=10000.0,
        centroid=[50.0, 50.0],
        is_outer_boundary=True,
    )
    mgg.add_geometry_node(boundary)
    mgg.add_geometry_node(_geometry_node("geom-1"))
    mgg.add_feature_node(_feature_node("feat-1", ["geom-1"]))
    return mgg


# ---------------------------------------------------------------------------
# check_graph_integrity
# ---------------------------------------------------------------------------


class TestGraphIntegrity:
    def test_clean_mgg_returns_empty(self):
        assert check_graph_integrity(_clean_mgg()) == []

    def test_orphan_geometry_detected(self):
        mgg = _clean_mgg()
        # Add a geometry node referenced by nobody and not a boundary.
        mgg.add_geometry_node(_geometry_node("geom-orphan"))
        violations = check_graph_integrity(mgg)
        assert any(v.startswith("ORPHAN_GEOMETRY: geom-orphan") for v in violations), violations

    def test_panel_boundary_not_orphan(self):
        # A boundary node with no feature reference must NOT be flagged.
        mgg = _clean_mgg()
        violations = check_graph_integrity(mgg)
        assert not any("geom-boundary" in v for v in violations), violations

    def test_geometry_referenced_via_composes_edge_not_orphan(self):
        mgg = ManufacturingGeometryGraph(GraphMetadata(graph_id="composes"))
        mgg.add_geometry_node(_geometry_node("geom-1"))
        mgg.add_feature_node(_feature_node("feat-1", []))  # no explicit geometry_node_ids
        mgg.add_edge("geom-1", "feat-1", EdgeType.COMPOSES)
        violations = check_graph_integrity(mgg)
        assert not any(v.startswith("ORPHAN_GEOMETRY") for v in violations), violations

    def test_self_loop_detected(self):
        mgg = _clean_mgg()
        mgg.add_edge("geom-1", "geom-1", EdgeType.ADJACENT_TO)
        violations = check_graph_integrity(mgg)
        assert any(v.startswith("SELF_LOOP: node geom-1") for v in violations), violations

    def test_bad_confidence_detected(self):
        mgg = _clean_mgg()
        mgg.add_feature_node(
            _feature_node("feat-bad", ["geom-1"], confidence=1.5)
        )
        violations = check_graph_integrity(mgg)
        assert any(
            v.startswith("INVALID_CONFIDENCE: feat-bad") for v in violations
        ), violations

    def test_negative_confidence_detected(self):
        mgg = _clean_mgg()
        mgg.add_feature_node(
            _feature_node("feat-neg", ["geom-1"], confidence=-0.1)
        )
        violations = check_graph_integrity(mgg)
        assert any(
            v.startswith("INVALID_CONFIDENCE: feat-neg") for v in violations
        ), violations

    def test_non_ontology_feature_class_detected(self):
        mgg = _clean_mgg()
        mgg.ontology = load_ontology(ONTOLOGY_DIR)  # attach ontology to enable check 5
        mgg.add_feature_node(
            _feature_node("feat-x", ["geom-1"], feature_class="NOT_A_REAL_FEATURE")
        )
        violations = check_graph_integrity(mgg)
        assert any(
            v.startswith("UNKNOWN_FEATURE_CLASS: feat-x") for v in violations
        ), violations

    def test_unknown_feature_sentinel_allowed(self):
        mgg = _clean_mgg()
        mgg.ontology = load_ontology(ONTOLOGY_DIR)
        mgg.add_feature_node(
            _feature_node("feat-u", ["geom-1"], feature_class="UNKNOWN_FEATURE")
        )
        violations = check_graph_integrity(mgg)
        assert not any("feat-u" in v for v in violations), violations

    def test_feature_class_check_skipped_without_ontology(self):
        # No ontology attached -> check 5 is skipped, no false positive.
        mgg = _clean_mgg()
        mgg.add_feature_node(
            _feature_node("feat-x", ["geom-1"], feature_class="MADE_UP")
        )
        violations = check_graph_integrity(mgg)
        assert not any(v.startswith("UNKNOWN_FEATURE_CLASS") for v in violations), violations

    def test_non_positive_diameter_detected(self):
        mgg = _clean_mgg()
        mgg.add_geometry_node(_geometry_node("geom-bad", diameter_mm=0.0))
        mgg.add_feature_node(_feature_node("feat-bad-geom", ["geom-bad"]))
        violations = check_graph_integrity(mgg)
        assert any(
            v.startswith("NON_POSITIVE_DIAMETER: geom-bad") for v in violations
        ), violations

    def test_negative_area_detected(self):
        mgg = _clean_mgg()
        mgg.add_geometry_node(_geometry_node("geom-narea", area_mm2=-5.0))
        mgg.add_feature_node(_feature_node("feat-narea", ["geom-narea"]))
        violations = check_graph_integrity(mgg)
        assert any(
            v.startswith("NEGATIVE_AREA: geom-narea") for v in violations
        ), violations


# ---------------------------------------------------------------------------
# check_ontology_consistency
# ---------------------------------------------------------------------------


class TestOntologyConsistency:
    def test_real_ontology_is_consistent(self):
        ontology = load_ontology(ONTOLOGY_DIR)
        violations = check_ontology_consistency(ontology, rules_dir=RULES_DIR)
        assert violations == [], violations

    def test_rule_referencing_unknown_feature_detected(self):
        ontology = load_ontology(ONTOLOGY_DIR)
        # Stub the rule-reference accessor to point at a non-existent feature.
        ontology.get_rule_feature_references = lambda: {  # type: ignore[method-assign]
            "MFG-999": ["TOTALLY_FAKE_FEATURE"]
        }
        violations = check_ontology_consistency(ontology)
        assert any(
            "RULE_REFERENCES_UNKNOWN_FEATURE" in v and "TOTALLY_FAKE_FEATURE" in v
            for v in violations
        ), violations

    def test_feature_to_operations_targets_exist(self):
        # The real ontology defines DRILLING / CNC_ROUTING / PROFILE_CUTTING /
        # NESTING, which cover every FEATURE_TO_OPERATIONS target.
        ontology = load_ontology(ONTOLOGY_DIR)
        violations = check_ontology_consistency(ontology, rules_dir=RULES_DIR)
        assert not any(
            v.startswith("FEATURE_TO_OPERATIONS_UNKNOWN_OPERATION") for v in violations
        ), violations

    def test_missing_operation_detected(self):
        # An ontology that has features mapping to operations but is missing the
        # operation definitions should flag FEATURE_TO_OPERATIONS targets.
        ontology = Ontology(version="v0.1.0")
        # Give it one operation so the "operations defined" guard passes, but
        # omit DRILLING which FEATURE_TO_OPERATIONS needs.
        ontology.operations["NESTING"] = OperationDefinition(id="NESTING")
        violations = check_ontology_consistency(ontology)
        assert any(
            v.startswith("FEATURE_TO_OPERATIONS_UNKNOWN_OPERATION") and "DRILLING" in v
            for v in violations
        ), violations

    def test_empty_ontology_no_operation_false_positives(self):
        # With no operations defined at all, the operation checks are skipped.
        ontology = Ontology(version="v0.1.0")
        violations = check_ontology_consistency(ontology)
        assert not any(
            v.startswith("FEATURE_TO_OPERATIONS_UNKNOWN_OPERATION") for v in violations
        ), violations
