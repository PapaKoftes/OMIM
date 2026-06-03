"""Tests for multi-panel nesting comprehension (omim.nesting).

Builds real nested-sheet DXFs with ezdxf and asserts that OMIM detects multiple
panels, assigns features to the correct panel, recognises the sheet boundary, and
flags overlap / out-of-sheet layouts.
"""

from __future__ import annotations

import ezdxf

from omim.graph.builder import MGGBuilder
from omim.nesting import analyze_nesting
from omim.parser.dxf_parser import DXFParser


def _mgg_from_doc(doc, tmp_path, name="nest.dxf"):
    path = tmp_path / name
    doc.saveas(path)
    result = DXFParser().parse(path)
    assert result.success, result.errors
    return MGGBuilder().build(result.geometry)


def _rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def test_single_panel_not_nested(tmp_path):
    """A lone panel with holes is NOT a nest."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(_rect(0, 0, 300, 400), close=True, dxfattribs={"layer": "CUT"})
    msp.add_circle((150, 200), radius=2.5, dxfattribs={"layer": "DRILL"})
    mgg = _mgg_from_doc(doc, tmp_path)
    layout = analyze_nesting(mgg)
    assert layout.is_nested is False
    assert layout.panel_count == 1


def test_multi_panel_nest_on_sheet(tmp_path):
    """A SHEET-layer stock with three panels -> nested, 3 panels, sheet detected."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    # Stock sheet 1220x800 on a SHEET layer.
    msp.add_lwpolyline(_rect(0, 0, 1220, 800), close=True, dxfattribs={"layer": "SHEET"})
    # Three panels cut from it.
    msp.add_lwpolyline(_rect(20, 20, 400, 300), close=True, dxfattribs={"layer": "CUT"})
    msp.add_lwpolyline(_rect(450, 20, 400, 300), close=True, dxfattribs={"layer": "CUT"})
    msp.add_lwpolyline(_rect(20, 350, 400, 300), close=True, dxfattribs={"layer": "CUT"})
    mgg = _mgg_from_doc(doc, tmp_path)
    layout = analyze_nesting(mgg)
    assert layout.is_nested is True
    assert layout.panel_count == 3
    assert layout.sheet_source == "sheet_layer"
    assert layout.sheet_area_mm2 is not None
    # Utilization = sum(panel areas) / sheet area; 3 * 120000 / 976000 ~ 0.37.
    assert layout.utilization is not None and 0.0 < layout.utilization < 1.0
    assert not layout.overlapping_panel_pairs
    assert not layout.panels_outside_sheet


def test_features_assigned_to_correct_panel(tmp_path):
    """Each drilled hole is attributed to the panel that contains it."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(_rect(0, 0, 1000, 500), close=True, dxfattribs={"layer": "SHEET"})
    # Panel A (left) with 2 holes, Panel B (right) with 1 hole.
    msp.add_lwpolyline(_rect(20, 20, 400, 400), close=True, dxfattribs={"layer": "CUT"})
    msp.add_lwpolyline(_rect(500, 20, 400, 400), close=True, dxfattribs={"layer": "CUT"})
    msp.add_circle((100, 100), radius=2.5, dxfattribs={"layer": "DRILL"})
    msp.add_circle((200, 200), radius=2.5, dxfattribs={"layer": "DRILL"})
    msp.add_circle((600, 100), radius=2.5, dxfattribs={"layer": "DRILL"})
    mgg = _mgg_from_doc(doc, tmp_path)
    layout = analyze_nesting(mgg)
    assert layout.panel_count == 2
    counts = sorted(p.feature_count for p in layout.panels)
    assert counts == [1, 2]
    total_assigned = sum(p.feature_count for p in layout.panels)
    assert total_assigned == 3


def test_overlapping_panels_flagged(tmp_path):
    """Two panels that overlap are flagged (a nesting error)."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(_rect(0, 0, 1000, 500), close=True, dxfattribs={"layer": "SHEET"})
    msp.add_lwpolyline(_rect(20, 20, 400, 400), close=True, dxfattribs={"layer": "CUT"})
    # Overlaps the first panel.
    msp.add_lwpolyline(_rect(200, 20, 400, 400), close=True, dxfattribs={"layer": "CUT"})
    mgg = _mgg_from_doc(doc, tmp_path)
    layout = analyze_nesting(mgg)
    assert layout.panel_count == 2
    assert layout.overlapping_panel_pairs, "expected an overlap to be flagged"


def test_packing_degrades_without_rectpack(tmp_path):
    """Packing analysis is optional and never breaks the core result."""
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(_rect(0, 0, 1000, 500), close=True, dxfattribs={"layer": "SHEET"})
    msp.add_lwpolyline(_rect(20, 20, 400, 400), close=True, dxfattribs={"layer": "CUT"})
    msp.add_lwpolyline(_rect(500, 20, 400, 400), close=True, dxfattribs={"layer": "CUT"})
    mgg = _mgg_from_doc(doc, tmp_path)
    layout = analyze_nesting(mgg)
    # Whether or not rectpack is installed, packing_note is populated and the
    # core analysis succeeded.
    assert isinstance(layout.packing_available, bool)
    assert layout.packing_note
    assert layout.panel_count == 2
