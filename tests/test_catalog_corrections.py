"""Wave 13: lock in the catalog ground-truth corrections found by web research.

Each test pins a corrected value so it can't silently regress:
  * 6mm fluted dowel is a recognised cluster + classifier class (was missing ->
    real 6mm holes mis-snapped to 5mm shelf-pin / mislabelled)
  * Blum hinge boring depth = 13mm (was 12.5)
  * CAM_HOLE labelled Minifix, not Rafix
  * drill-max reconciled to 40mm across rule files
"""

from __future__ import annotations

from omim.corpus.catalog_ground_truth import (
    CATALOG_REFERENCES,
    DIAMETER_TO_FEATURE,
    KNOWN_FEATURE_DIAMETERS_MM,
    cluster_diameter,
    feature_for_diameter,
)
from omim.graph.builder import MGGBuilder
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry
from omim.semantic.classifier import FeatureClassifier

# ---------------------------------------------------------------------------
# 6mm dowel cluster (the highest-impact fix)
# ---------------------------------------------------------------------------


def test_6mm_is_a_known_cluster():
    assert 6.0 in KNOWN_FEATURE_DIAMETERS_MM
    assert DIAMETER_TO_FEATURE[6.0] == "DOWEL_HOLE_LIGHT"
    assert "DOWEL_HOLE_LIGHT" in CATALOG_REFERENCES


def test_6mm_hole_clusters_to_6_not_5():
    """A real 6mm dowel must snap to the 6mm cluster, not the 5mm shelf-pin."""
    center, dev = cluster_diameter(6.0)
    assert center == 6.0 and dev == 0.0
    assert feature_for_diameter(6.0) == "DOWEL_HOLE_LIGHT"
    # A slightly-off 6.1mm hole still resolves to 6, not 5 or 7.
    assert cluster_diameter(6.1)[0] == 6.0


def _circle_panel(dia):
    boundary = [[0, 0], [400, 0], [400, 600], [0, 600]]
    r = dia / 2.0
    ents = [
        RawEntity(
            entity_id="P", ezdxf_handle="P", entity_type="LWPOLYLINE",
            layer="CUT", inferred_layer_type="cut", coordinates=boundary,
            is_closed=True, bounding_box=[0, 0, 400, 600], centroid=[200.0, 300.0],
            area_mm2=240000.0, perimeter_mm=2000.0,
        ),
        RawEntity(
            entity_id="h", ezdxf_handle="h", entity_type="CIRCLE",
            layer="DRILL", inferred_layer_type="drill", coordinates=[200, 300, r],
            is_closed=True, bounding_box=[200 - r, 300 - r, 200 + r, 300 + r],
            centroid=[200, 300], area_mm2=3.14159 * r * r, perimeter_mm=2 * 3.14159 * r,
            diameter_mm=float(dia), radius_mm=r,
        ),
    ]
    raw = RawGeometry(
        source_file="t.dxf", source_file_hash="sha256:t", dxf_version="AC1027",
        entities=ents,
        panel_boundary=PanelBoundary(
            entity_id="P", coordinates=boundary, bounding_box=[0, 0, 400, 600],
            area_mm2=240000.0, inferred=False,
        ),
        panel_boundary_inferred=False, entity_counts={},
    )
    return MGGBuilder().build(raw)


def test_classifier_labels_6mm_dowel():
    """A 6mm hole on a drill layer is classified DOWEL_HOLE (was mislabelled)."""
    mgg = _circle_panel(6.0)
    ann = FeatureClassifier().classify(mgg)
    by_id = {a.node_id: a for a in ann.feature_annotations}
    assert by_id["geom-h"].feature_class == "DOWEL_HOLE"


def test_classifier_still_distinguishes_5_and_7():
    """6mm must not have blurred the 5mm shelf-pin / 7mm confirmat boundaries."""
    clf = FeatureClassifier()
    # 5mm alone (no grid) won't be SHELF_PIN, but must NOT become a dowel.
    a5 = {a.node_id: a for a in clf.classify(_circle_panel(5.0)).feature_annotations}
    assert a5["geom-h"].feature_class != "DOWEL_HOLE"
    a7 = {a.node_id: a for a in clf.classify(_circle_panel(7.0)).feature_annotations}
    assert a7["geom-h"].feature_class == "CONFIRMAT_HOLE"


# ---------------------------------------------------------------------------
# Hinge boring depth + Minifix relabel + standards
# ---------------------------------------------------------------------------


def test_hinge_boring_depth_is_13mm():
    assert CATALOG_REFERENCES["HINGE_CUP_HOLE"]["depth_mm"] == 13.0


def test_cam_hole_is_minifix_not_rafix():
    src = CATALOG_REFERENCES["CAM_HOLE"]["source"]
    assert "Minifix" in src
    assert "Rafix" not in src


def test_dowel_sources_cite_din_68150():
    for key in ("DOWEL_HOLE_LIGHT", "DOWEL_HOLE", "DOWEL_HOLE_HEAVY"):
        assert "68150" in CATALOG_REFERENCES[key]["source"]


def test_dowel_alt_diameters_include_6():
    assert 6.0 in CATALOG_REFERENCES["DOWEL_HOLE"]["alt_diameters_mm"]


def test_drill_max_reconciled_to_40():
    """panel_cnc_rules.yaml max drill diameter aligned to MFG-011's 40mm."""
    import yaml

    from omim.config import get_settings
    path = get_settings().rules_dir / "panel_cnc_rules.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["thresholds"]["max_drill_diameter_mm"] == 40.0
