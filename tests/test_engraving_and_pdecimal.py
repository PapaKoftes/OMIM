"""Wave 18: generic capabilities surfaced from a real-corpus gap analysis.

Two domain-agnostic additions, tested with synthetic geometry only (no external
data): (1) P/V-as-decimal layer-name depth (e.g. POCKET_6P0MM -> 6.0mm), a common
CAM naming convention; (2) an ENGRAVING feature class for shallow marking cuts
drawn as polylines on an engrave/mark layer (not DXF TEXT entities).
"""

from __future__ import annotations

import ezdxf

from omim.graph.builder import MGGBuilder
from omim.parser.depth import parse_depth_from_layer, parse_thickness_from_layer
from omim.parser.dxf_parser import DXFParser
from omim.semantic.classifier import FEATURE_CATEGORIES, FeatureClassifier

# --- P/V-as-decimal depth marker -------------------------------------------


def test_p_decimal_depth_marker():
    assert parse_depth_from_layer("POCKET_6P0MM", "pocket") == 6.0
    assert parse_depth_from_layer("POCKET_12P5MM", "pocket") == 12.5
    assert parse_depth_from_layer("POCKET_0P5MM", "pocket") == 0.5


def test_v_decimal_depth_marker():
    assert parse_depth_from_layer("GROOVE_6V0MM", "pocket") == 6.0


def test_decimal_marker_does_not_touch_words():
    # The 'P' in POCKET / 'V' in a word is not digit-flanked -> untouched.
    assert parse_depth_from_layer("POCKET", "pocket") is None
    # A normal decimal still works.
    assert parse_depth_from_layer("POCKET_6MM", "pocket") == 6.0
    # Thickness path also normalises.
    assert parse_thickness_from_layer("PANEL_18P0MM") == 18.0


# --- ENGRAVING feature class -----------------------------------------------


def test_engraving_in_ontology_and_categories():
    assert FEATURE_CATEGORIES.get("ENGRAVING") == "MILLED_FEATURES"


def _engrave_dxf(tmp_path, layer="ENGRAVE"):
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (400, 0), (400, 300), (0, 300)], close=True,
                     dxfattribs={"layer": "CUT"})
    # A small lettering-like closed polyline on an engrave layer.
    m.add_lwpolyline([(50, 50), (60, 50), (60, 70), (50, 70)], close=True,
                     dxfattribs={"layer": layer})
    p = tmp_path / "engrave.dxf"
    doc.saveas(p)
    return p


def test_engraving_classified_on_engrave_layer(tmp_path):
    mgg = MGGBuilder().build(DXFParser().parse(_engrave_dxf(tmp_path)).geometry)
    ann = FeatureClassifier().classify(mgg)
    classes = {a.feature_class for a in ann.feature_annotations}
    assert "ENGRAVING" in classes


def test_engraving_on_mark_layer(tmp_path):
    mgg = MGGBuilder().build(DXFParser().parse(_engrave_dxf(tmp_path, "MARK_LOGO")).geometry)
    ann = FeatureClassifier().classify(mgg)
    assert "ENGRAVING" in {a.feature_class for a in ann.feature_annotations}


def test_non_engrave_layer_not_engraving(tmp_path):
    # Same geometry on a plain CUT layer must NOT become ENGRAVING.
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (400, 0), (400, 300), (0, 300)], close=True,
                     dxfattribs={"layer": "CUT"})
    m.add_circle((200, 150), radius=2.5, dxfattribs={"layer": "DRILL"})
    p = tmp_path / "plain.dxf"
    doc.saveas(p)
    ann = FeatureClassifier().classify(MGGBuilder().build(DXFParser().parse(p).geometry))
    assert "ENGRAVING" not in {a.feature_class for a in ann.feature_annotations}
