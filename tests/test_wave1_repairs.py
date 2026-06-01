"""Regression tests for Wave 1 core repairs.

Each test pins a specific fix so it cannot silently regress:

* GEO-005 no longer false-positives on legitimate CCW interior cutouts, and
  still flags a CW outer boundary.
* execution_time_ms is stamped uniformly by the engine on every RuleResult.
* serializer.load_mgg raises a clear ValueError on malformed/invalid input and
  round-trips a saved MGG.
* mgg_to_cytoscape returns the expected envelope.
* ontology.get_rule_feature_references() is no longer a stub.
* GNNPredictor reports fallback honestly when no checkpoint is loaded.
"""

from __future__ import annotations

import json

import pytest

from omim.graph.builder import MGGBuilder
from omim.graph.serializer import load_mgg, mgg_to_cytoscape, save_mgg
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry
from omim.validation.geometric_rules import check_contour_orientation
from omim.validation.rule_engine import RuleEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _panel_with_interior(interior_coords: list[list[float]], *, outer_ccw: bool = True):
    """Build an MGG: a square panel boundary + one interior closed contour."""
    outer = [[0, 0], [200, 0], [200, 200], [0, 200]]
    if not outer_ccw:
        outer = list(reversed(outer))
    entities = [
        RawEntity(
            entity_id="1", ezdxf_handle="h1", entity_type="LWPOLYLINE",
            layer="cut", inferred_layer_type="cut", coordinates=outer,
            is_closed=True, bounding_box=[0, 0, 200, 200], centroid=[100.0, 100.0],
            area_mm2=40000.0, perimeter_mm=800.0,
        ),
        RawEntity(
            entity_id="2", ezdxf_handle="h2", entity_type="LWPOLYLINE",
            layer="cut", inferred_layer_type="cut", coordinates=interior_coords,
            is_closed=True,
            bounding_box=[
                min(p[0] for p in interior_coords), min(p[1] for p in interior_coords),
                max(p[0] for p in interior_coords), max(p[1] for p in interior_coords),
            ],
            centroid=[
                sum(p[0] for p in interior_coords) / len(interior_coords),
                sum(p[1] for p in interior_coords) / len(interior_coords),
            ],
            area_mm2=400.0, perimeter_mm=80.0,
        ),
    ]
    raw = RawGeometry(
        source_file="t.dxf", source_file_hash="sha256:t", dxf_version="AC1027",
        entities=entities,
        panel_boundary=PanelBoundary(
            entity_id="1", coordinates=outer, bounding_box=[0, 0, 200, 200],
            area_mm2=40000.0, inferred=False,
        ),
        panel_boundary_inferred=False,
        entity_counts={"LWPOLYLINE": 2},
    )
    return MGGBuilder().build(raw)


# ---------------------------------------------------------------------------
# GEO-005 contour orientation
# ---------------------------------------------------------------------------


def test_geo005_ccw_interior_cutout_not_flagged_as_warning():
    """A CCW interior cutout inside a CCW outer boundary must NOT be a WARNING.

    The previous absolute rule flagged every CCW interior contour, producing
    constant false positives on legitimate parts. Now interior winding is judged
    relative to its container and only ever reported at INFO severity.
    """
    # CCW square hole (counter-clockwise winding).
    interior_ccw = [[50, 50], [70, 50], [70, 70], [50, 70]]
    mgg = _panel_with_interior(interior_ccw, outer_ccw=True)
    results = check_contour_orientation(mgg)
    warnings = [r for r in results if not r.passed and r.severity == "WARNING"]
    assert warnings == [], f"unexpected WARNING(s): {[w.message for w in warnings]}"


def test_geo005_flags_cw_outer_boundary():
    """A clockwise outer boundary is a genuine convention violation -> WARNING."""
    interior_ccw = [[50, 50], [70, 50], [70, 70], [50, 70]]
    mgg = _panel_with_interior(interior_ccw, outer_ccw=False)
    results = check_contour_orientation(mgg)
    outer_warn = [
        r for r in results
        if not r.passed and r.severity == "WARNING" and r.evidence.get("is_outer")
    ]
    assert len(outer_warn) == 1


# ---------------------------------------------------------------------------
# execution_time_ms timing fix (engine-level)
# ---------------------------------------------------------------------------


def test_execution_time_ms_stamped_on_all_results():
    """Every RuleResult gets a non-negative execution_time_ms from the engine."""
    interior = [[50, 50], [70, 50], [70, 70], [50, 70]]
    mgg = _panel_with_interior(interior, outer_ccw=True)
    report = RuleEngine().validate(mgg, annotate_graph=False)
    all_results = report.layer1_results + report.layer2_results
    assert all_results
    assert all(r.execution_time_ms >= 0.0 for r in all_results)


# ---------------------------------------------------------------------------
# serializer
# ---------------------------------------------------------------------------


def test_load_mgg_roundtrip(tmp_path):
    interior = [[50, 50], [70, 50], [70, 70], [50, 70]]
    mgg = _panel_with_interior(interior, outer_ccw=True)
    path = save_mgg(mgg, tmp_path / "mgg.json")
    loaded = load_mgg(path)
    assert loaded.metadata.graph_id == mgg.metadata.graph_id
    assert loaded.node_count == mgg.node_count


def test_load_mgg_malformed_json_raises_clear_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed MGG JSON"):
        load_mgg(bad)


def test_load_mgg_missing_metadata_raises(tmp_path):
    nometa = tmp_path / "nometa.json"
    nometa.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid MGG document"):
        load_mgg(nometa)


def test_load_mgg_missing_file_raises(tmp_path):
    with pytest.raises(ValueError, match="Cannot read MGG file"):
        load_mgg(tmp_path / "does_not_exist.json")


def test_mgg_to_cytoscape_shape():
    interior = [[50, 50], [70, 50], [70, 70], [50, 70]]
    mgg = _panel_with_interior(interior, outer_ccw=True)
    cyto = mgg_to_cytoscape(mgg)
    assert set(cyto) == {"metadata", "elements"}
    node_elems = [e for e in cyto["elements"] if e["group"] == "nodes"]
    assert node_elems
    assert all("id" in e["data"] for e in node_elems)


# ---------------------------------------------------------------------------
# ontology rule feature references (was a stub returning {})
# ---------------------------------------------------------------------------


def test_get_rule_feature_references_not_stub():
    from omim.config import get_settings
    from omim.ontology.loader import load_ontology

    ont = load_ontology(get_settings().ontology_dir)
    assert ont.rules, "rules should auto-load from sibling data/rules dir"
    refs = ont.get_rule_feature_references()
    # MFG-010 references CONFIRMAT_HOLE by name in the rule YAML.
    assert refs.get("MFG-010") == ["CONFIRMAT_HOLE"]


# ---------------------------------------------------------------------------
# GNNPredictor honest fallback (no torch required — exercises the guard)
# ---------------------------------------------------------------------------


def test_predictor_untrained_reports_fallback():
    """With no checkpoints, predict() must report fallback=True (random weights)."""
    from omim.ml.predictor import GNNPredictor

    pred = GNNPredictor()  # no checkpoints
    assert pred.trained is False
    interior = [[50, 50], [70, 50], [70, 70], [50, 70]]
    mgg = _panel_with_interior(interior, outer_ccw=True)
    out = pred.predict(mgg)
    assert out["fallback"] is True
    assert out["trained"] is False
