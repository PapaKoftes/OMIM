"""Phase B: CHAMFER + FILLET classification (2D-decidable corner treatments).

These were ontology classes the classifier never emitted. Both are geometry-only
(no depth needed): a short diagonal LINE at a panel corner is a chamfer; a short
ARC is a fillet. Tested with synthetic geometry; the negative cases guard against
over-firing on long edges or features away from the boundary.
"""

from __future__ import annotations

import ezdxf

from omim.graph.builder import MGGBuilder
from omim.parser.dxf_parser import DXFParser
from omim.semantic.classifier import FEATURE_CATEGORIES, FeatureClassifier


def _classify(path):
    mgg = MGGBuilder().build(DXFParser().parse(path).geometry)
    ann = FeatureClassifier().classify(mgg)
    return {a.node_id: a for a in ann.feature_annotations}, {
        a.feature_class for a in ann.feature_annotations
    }


def test_chamfer_and_fillet_are_known_classes():
    assert FEATURE_CATEGORIES.get("CHAMFER") == "PROFILE_FEATURES"
    assert FEATURE_CATEGORIES.get("FILLET") == "PROFILE_FEATURES"


def test_chamfer_detected_at_corner(tmp_path):
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (400, 0), (400, 300), (0, 300)], close=True,
                     dxfattribs={"layer": "CUT"})
    # A short diagonal line clipping the top-left corner (a chamfer cut).
    m.add_line((0, 285), (15, 300), dxfattribs={"layer": "CUT"})
    p = tmp_path / "chamfer.dxf"
    doc.saveas(p)
    _by_id, classes = _classify(p)
    assert "CHAMFER" in classes


def test_fillet_detected_at_corner(tmp_path):
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (400, 0), (400, 300), (0, 300)], close=True,
                     dxfattribs={"layer": "CUT"})
    # A short arc rounding the bottom-right corner (a fillet).
    m.add_arc((390, 10), radius=10, start_angle=0, end_angle=90,
              dxfattribs={"layer": "CUT"})
    p = tmp_path / "fillet.dxf"
    doc.saveas(p)
    _by_id, classes = _classify(p)
    assert "FILLET" in classes


def test_long_interior_line_not_chamfer(tmp_path):
    """A long line in the middle of the panel must NOT be called a chamfer."""
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (400, 0), (400, 300), (0, 300)], close=True,
                     dxfattribs={"layer": "CUT"})
    m.add_line((100, 150), (300, 150), dxfattribs={"layer": "CUT"})  # long, central
    p = tmp_path / "longline.dxf"
    doc.saveas(p)
    _by_id, classes = _classify(p)
    assert "CHAMFER" not in classes


def test_annotation_provenance_is_first_class(tmp_path):
    """Every annotation carries an auditable, self-consistent provenance record
    (record_id + confidence + method + authority level), not just a 3-key dict."""
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True,
                     dxfattribs={"layer": "CUT"})
    m.add_circle((22.5, 100), radius=17.5, dxfattribs={"layer": "HINGE"})
    p = tmp_path / "door.dxf"
    doc.saveas(p)
    by_id, _classes = _classify(p)
    for a in by_id.values():
        prov = a.provenance
        assert prov is not None
        for key in ("record_id", "inference_method", "confidence",
                    "confidence_method", "authority_level"):
            assert key in prov, f"missing provenance key {key}"
        assert prov["authority_level"] == 5  # semantic inference tier
        assert prov["record_id"].startswith("sem-")
