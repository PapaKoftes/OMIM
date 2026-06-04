"""Tests for depth / 2.5D extraction (omim.parser.depth) and end-to-end through
the DXF parser, builder, and MFG-007.

Depth is recovered from (1) real Z elevations (2.5D) and (2) layer-name
conventions, with provenance recorded in depth_source. Pure-2D geometry with no
depth tokens must leave depth as None (never guessed).
"""

from __future__ import annotations

import ezdxf

from omim.graph.builder import MGGBuilder
from omim.parser.depth import (
    depth_from_elevation,
    parse_depth_from_layer,
    parse_thickness_from_layer,
    resolve_depth,
)
from omim.parser.dxf_parser import DXFParser
from omim.validation.rule_engine import RuleEngine

# ---------------------------------------------------------------------------
# Unit: layer-name parsing
# ---------------------------------------------------------------------------


def test_parse_depth_explicit_marker():
    assert parse_depth_from_layer("POCKET_D6") == 6.0
    assert parse_depth_from_layer("GROOVE_DEPTH_12.5") == 12.5
    assert parse_depth_from_layer("ENGRAVE_DP1.5") == 1.5


def test_parse_depth_bare_mm_only_on_depth_layers():
    # Bare "6MM" counts as depth on a pocket layer...
    assert parse_depth_from_layer("POCKET_6MM", "pocket") == 6.0
    # ...but NOT on a non-depth layer (avoids reading panel thickness as depth).
    assert parse_depth_from_layer("PANEL_18MM", "border") is None
    # With no layer-type hint, a bare mm token is accepted.
    assert parse_depth_from_layer("CUT_3MM") == 3.0


def test_parse_depth_rejects_implausible_and_empty():
    assert parse_depth_from_layer("") is None
    assert parse_depth_from_layer("DRILL") is None
    assert parse_depth_from_layer("LAYER2") is None  # 2 has no mm marker


def test_parse_thickness_from_layer():
    assert parse_thickness_from_layer("PANEL_18MM") == 18.0
    assert parse_thickness_from_layer("THK16") == 16.0
    assert parse_thickness_from_layer("T25") == 25.0
    assert parse_thickness_from_layer("DRILL") is None
    # Out of plausible panel range -> rejected.
    assert parse_thickness_from_layer("T200") is None


# ---------------------------------------------------------------------------
# Unit: elevation math + resolution precedence
# ---------------------------------------------------------------------------


def test_depth_from_elevation():
    assert depth_from_elevation(12.0, 18.0) == 6.0  # 6mm below top face
    assert depth_from_elevation(18.0, 18.0) == 0.0  # on the face
    assert depth_from_elevation(None, 18.0) is None
    assert depth_from_elevation(20.0, 18.0) is None  # above face -> not a depth


def test_resolve_depth_precedence_z_beats_layer():
    # Both a Z elevation and a layer token present -> measured Z wins.
    depth, source = resolve_depth(
        layer_name="POCKET_D5", inferred_layer_type="pocket",
        entity_z=10.0, reference_plane_z=18.0,
    )
    assert depth == 8.0 and source == "z_elevation"


def test_resolve_depth_falls_back_to_layer():
    depth, source = resolve_depth(
        layer_name="POCKET_D5", inferred_layer_type="pocket",
        entity_z=None, reference_plane_z=None,
    )
    assert depth == 5.0 and source == "layer_name"


def test_resolve_depth_none_when_no_source():
    depth, source = resolve_depth(
        layer_name="DRILL", inferred_layer_type="drill",
        entity_z=None, reference_plane_z=None,
    )
    assert depth is None and source is None


# ---------------------------------------------------------------------------
# Integration: 2.5D DXF through the parser
# ---------------------------------------------------------------------------


def _write(doc, path):
    doc.saveas(path)


def test_parser_recovers_depth_from_z_elevation(tmp_path):
    """A pocket circle drawn at Z below the panel face -> measured depth."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    # Panel boundary at Z=0 (top face).
    msp.add_lwpolyline(
        [(0, 0), (300, 0), (300, 400), (0, 400)], close=True,
        dxfattribs={"layer": "CUT"},
    )
    # A pocket bottom drawn 6mm below the top face (Z = -6).
    msp.add_circle((150, 200, -6), radius=10, dxfattribs={"layer": "POCKET"})
    path = tmp_path / "pocket25d.dxf"
    _write(doc, path)

    result = DXFParser().parse(path)
    assert result.success
    pocket = [e for e in result.geometry.entities if e.layer == "POCKET"]
    assert len(pocket) == 1
    assert pocket[0].depth_mm == 6.0
    assert pocket[0].depth_source == "z_elevation"
    # A 2.5D-detected warning is emitted.
    assert any(w.warning_code == "depth_2p5d_detected" for w in result.geometry.warnings)


def test_parser_recovers_depth_from_layer_name(tmp_path):
    """A flat (2D) pocket on a POCKET_6MM layer -> inferred depth via layer name."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (300, 0), (300, 400), (0, 400)], close=True,
        dxfattribs={"layer": "CUT"},
    )
    msp.add_lwpolyline(
        [(100, 100), (140, 100), (140, 140), (100, 140)], close=True,
        dxfattribs={"layer": "POCKET_6MM"},
    )
    path = tmp_path / "pocket_layer.dxf"
    _write(doc, path)

    result = DXFParser().parse(path)
    assert result.success
    pocket = [e for e in result.geometry.entities if e.layer == "POCKET_6MM"]
    assert len(pocket) == 1
    assert pocket[0].depth_mm == 6.0
    assert pocket[0].depth_source == "layer_name"


def test_pure_2d_has_no_depth(tmp_path):
    """Plain 2D drilling with no Z and no depth token -> depth stays None."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (300, 0), (300, 400), (0, 400)], close=True,
        dxfattribs={"layer": "CUT"},
    )
    msp.add_circle((150, 200), radius=2.5, dxfattribs={"layer": "DRILL"})
    path = tmp_path / "flat.dxf"
    _write(doc, path)

    result = DXFParser().parse(path)
    drill = [e for e in result.geometry.entities if e.layer == "DRILL"]
    assert len(drill) == 1
    assert drill[0].depth_mm is None
    assert drill[0].depth_source is None


def test_depth_flows_to_geometry_node_and_mfg007(tmp_path):
    """Depth reaches the GeometryNode and MFG-007 fires on an over-deep pocket."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (300, 0), (300, 400), (0, 400)], close=True,
        dxfattribs={"layer": "CUT"},
    )
    # 16mm-deep pocket via layer name: exceeds 0.75*18 = 13.5mm -> MFG-007 WARNING.
    msp.add_lwpolyline(
        [(100, 100), (160, 100), (160, 160), (100, 160)], close=True,
        dxfattribs={"layer": "POCKET_D16"},
    )
    path = tmp_path / "deep_pocket.dxf"
    _write(doc, path)

    result = DXFParser().parse(path)
    mgg = MGGBuilder().build(result.geometry)

    # Depth on the geometry node.
    depths = [d.get("depth_mm") for _n, d in mgg.geometry_nodes() if d.get("depth_mm")]
    assert 16.0 in depths

    report = RuleEngine().validate(mgg, annotate_graph=False)
    mfg007 = [r for r in report.layer2_results if r.rule_id == "MFG-007"]
    assert any(not r.passed and r.severity == "WARNING" for r in mfg007), (
        "MFG-007 should fire on a 16mm pocket in 18mm stock"
    )
