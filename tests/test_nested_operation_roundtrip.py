"""Forward/reverse round-trip over a nested, layer-per-operation panel DXF.

A panel CAM pipeline emits, for a nested stock sheet, one layer per CNC operation
(a common production-nesting-cell convention):

    PLATE    the stock sheet boundary (not a part)
    OUTSIDE  a part's freeing outer profile      -> PROFILE_CUT
    INSIDE   an interior through cut / bored cut  -> INTERNAL_CUTOUT
    POCKET   a partial-depth recess               -> POCKET / GROOVE
    DRILL    a small bored hole                    -> a HOLE feature
    ENGRAVE  a shallow surface marking             -> ENGRAVING
    RELIEF   an inside-corner dogbone              -> CORNER_RELIEF (not a hole)

This test generates such a sheet with KNOWN ground truth and round-trips it through
OMIM (parse -> nest split -> classify), asserting the recovered feature classes.
It is the regression guard for three nested-sheet behaviours:

  * a stock sheet carrying a single part is still split (stock dropped), so the
    part outline is PROFILE_CUT, not a stock-sized boundary;
  * inside-corner relief dogbones are recognised, not counted as drilled holes;
  * a wide circle on a cut layer is a milled round cutout, not a hardware hole.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf

from omim.graph.builder import MGGBuilder
from omim.nesting import split_raw_geometry_by_panels
from omim.parser.dxf_parser import DXFParser
from omim.parser.models import ParserConfig
from omim.semantic.classifier import FEATURE_CATEGORIES, FEATURE_TO_OPERATIONS, FeatureClassifier

# Map the operation-layer dialect onto OMIM's canonical types. RELIEF is left
# unmapped on purpose: relief is recognised by layer NAME, not by a profile, so
# it must work even without a dialect entry.
_PROFILE = ParserConfig(layer_conventions={
    "cut": ["OUTSIDE", "INSIDE"],
    "drill": ["DRILL"],
    "pocket": ["POCKET"],
    "engrave": ["ENGRAVE"],
    "border": ["PLATE"],
})


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _add_part(msp, ox, oy, *, bored=False):
    """Draw one part at offset (ox, oy): outline + pocket + relief + drill +
    engrave (+ optional wide bored cut). Mirrors a CAM op-per-layer export."""
    msp.add_lwpolyline([(x + ox, y + oy) for x, y in _rect(0, 0, 600, 400)],
                       close=True, dxfattribs={"layer": "OUTSIDE"})
    # a partial-depth pocket (connector slot)
    msp.add_lwpolyline([(x + ox, y + oy) for x, y in _rect(200, 150, 400, 250)],
                       close=True, dxfattribs={"layer": "POCKET"})
    # four inside-corner relief dogbones (small circles on the RELIEF layer)
    for cx, cy in [(200, 150), (400, 150), (400, 250), (200, 250)]:
        msp.add_circle((cx + ox, cy + oy), 4.0, dxfattribs={"layer": "RELIEF"})
    # a small drilled hole
    msp.add_circle((100 + ox, 100 + oy), 4.0, dxfattribs={"layer": "DRILL"})
    # an engraved registration tick (open polyline)
    msp.add_lwpolyline([(500 + ox, 350 + oy), (560 + ox, 350 + oy)],
                       close=False, dxfattribs={"layer": "ENGRAVE"})
    if bored:
        # a 40mm round cut (> drill window) on the INSIDE (cut) layer
        msp.add_circle((480 + ox, 120 + oy), 20.0, dxfattribs={"layer": "INSIDE"})


def _nested_sheet(tmp_path: Path, n_parts: int) -> Path:
    doc = ezdxf.new("R2000")
    msp = doc.modelspace()
    for lay in ("PLATE", "OUTSIDE", "INSIDE", "POCKET", "DRILL", "ENGRAVE", "RELIEF"):
        doc.layers.add(lay)
    # stock sheet boundary (the largest closed contour)
    msp.add_lwpolyline(_rect(0, 0, 2000, 1000), close=True,
                       dxfattribs={"layer": "PLATE"})
    offsets = [(50, 300), (750, 300), (1350, 300)][:n_parts]
    for i, (ox, oy) in enumerate(offsets):
        _add_part(msp, ox, oy, bored=(i == 0))
    p = tmp_path / f"nest_{n_parts}.dxf"
    doc.saveas(str(p))
    return p


def _classify_panels(path: Path):
    """Parse -> split into panels -> classify; return list of {layer: [classes]}."""
    result = DXFParser(_PROFILE).parse(path)
    assert result.success, result.errors
    panels = split_raw_geometry_by_panels(result.geometry)
    clf = FeatureClassifier()
    out = []
    for pg in panels:
        mgg = MGGBuilder().build(pg)
        ann = clf.classify(mgg)
        node_layer = {nid: d.get("layer", "") for nid, d in mgg.geometry_nodes()}
        by_layer: dict[str, list[str]] = {}
        for fa in ann.feature_annotations:
            by_layer.setdefault(node_layer.get(fa.node_id, "?"), []).append(
                fa.feature_class)
        out.append(by_layer)
    return out


def test_corner_relief_in_taxonomy():
    """CORNER_RELIEF is a first-class milled feature, mapped to routing."""
    assert FEATURE_CATEGORIES.get("CORNER_RELIEF") == "MILLED_FEATURES"
    assert FEATURE_TO_OPERATIONS.get("CORNER_RELIEF") == ["CNC_ROUTING"]


def test_two_part_nest_splits_and_classifies(tmp_path):
    panels = _classify_panels(_nested_sheet(tmp_path, n_parts=2))
    # stock dropped -> exactly two part-panels, no PLATE among classified layers
    assert len(panels) == 2
    for by_layer in panels:
        assert "PLATE" not in by_layer
        # the freeing outer profile is a profile cut, not an internal cutout
        assert by_layer.get("OUTSIDE") == ["PROFILE_CUT"]
        # the connector slot is a milled pocket/groove
        assert by_layer.get("POCKET", [""])[0] in ("POCKET", "GROOVE")
        # engraving recognised
        assert by_layer.get("ENGRAVE") == ["ENGRAVING"]
        # relief dogbones are CORNER_RELIEF, never a hole
        relief = by_layer.get("RELIEF", [])
        assert relief and all(c == "CORNER_RELIEF" for c in relief)
        assert not any(c.endswith("HOLE") for c in relief)


def test_wide_circle_on_cut_layer_is_cutout(tmp_path):
    """The 40mm bore on the INSIDE (cut) layer -> INTERNAL_CUTOUT, not a hole."""
    panels = _classify_panels(_nested_sheet(tmp_path, n_parts=2))
    bored = [by_layer for by_layer in panels if "INSIDE" in by_layer]
    assert bored, "expected a part with an INSIDE bored cut"
    assert "INTERNAL_CUTOUT" in bored[0]["INSIDE"]
    assert not any(c.endswith("HOLE") for c in bored[0]["INSIDE"])


def test_single_part_on_stock_is_split(tmp_path):
    """A stock sheet carrying ONE part is still a nest: the stock is dropped and
    the part outline is a PROFILE_CUT (regression for the <2-panel guard)."""
    panels = _classify_panels(_nested_sheet(tmp_path, n_parts=1))
    assert len(panels) == 1
    by_layer = panels[0]
    assert "PLATE" not in by_layer
    assert by_layer.get("OUTSIDE") == ["PROFILE_CUT"]


def test_drill_is_a_hole(tmp_path):
    """A small circle on a DRILL layer remains a HOLE-category feature."""
    panels = _classify_panels(_nested_sheet(tmp_path, n_parts=1))
    drill_classes = panels[0].get("DRILL", [])
    assert drill_classes
    assert all(FEATURE_CATEGORIES.get(c) == "HOLE_FEATURES" for c in drill_classes)
