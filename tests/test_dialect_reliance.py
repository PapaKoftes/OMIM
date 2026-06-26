"""Dialect-reliance detector: does feature meaning live in geometry or layer names?

Generic capability (no shop-specific data): a panel whose holes are catalog-diverse
carries meaning in its geometry (layer-blind inference is reliable); a panel that
drills one dominant non-catalog 'system' diameter for everything carries meaning in
its layer names (a profile is required). Synthetic geometry only.
"""

from __future__ import annotations

import ezdxf

from omim.graph.builder import MGGBuilder
from omim.parser.dxf_parser import DXFParser
from omim.semantic.dialect_reliance import assess_dialect_reliance


def _panel(circles):
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (600, 0), (600, 800), (0, 800)], close=True,
                     dxfattribs={"layer": "CUT"})
    for cx, cy, dia in circles:
        m.add_circle((cx, cy), radius=dia / 2, dxfattribs={"layer": "DRILL"})
    import tempfile
    from pathlib import Path
    p = Path(tempfile.mkdtemp()) / "t.dxf"
    doc.saveas(p)
    return MGGBuilder().build(DXFParser().parse(p).geometry)


def test_catalog_diverse_panel_does_not_rely_on_layers():
    mgg = _panel(
        [(37, 100 + 32 * i, 5.0) for i in range(6)]   # shelf pins
        + [(22.5, 400, 35.0), (300, 50, 7.0), (300, 750, 8.0)]  # hinge, confirmat, dowel
    )
    rep = assess_dialect_reliance(mgg)
    assert rep.relies_on_layers is False
    assert rep.catalog_match_fraction >= 0.5
    assert "geometry carries" in rep.message


def test_single_system_hole_dialect_relies_on_layers():
    """One dominant off-catalog diameter -> meaning is in the layer names."""
    mgg = _panel([(50 + i * 40, 100 + j * 40, 4.0) for i in range(8) for j in range(8)])
    rep = assess_dialect_reliance(mgg)
    assert rep.relies_on_layers is True
    assert rep.dominant_diameter_mm == 4.0
    assert rep.dominant_fraction >= 0.6
    assert "profile is REQUIRED" in rep.message


def test_no_holes_is_not_applicable():
    mgg = _panel([])
    rep = assess_dialect_reliance(mgg)
    assert rep.hole_count == 0
    assert rep.relies_on_layers is False
    assert "not applicable" in rep.message


def test_mixed_dialect_is_partial():
    # Half catalog (5mm), half an off-catalog 4mm, none dominant past threshold.
    mgg = _panel(
        [(50 + i * 30, 100, 5.0) for i in range(4)]
        + [(50 + i * 30, 200, 4.0) for i in range(4)]
    )
    rep = assess_dialect_reliance(mgg)
    # 4mm and 5mm each 50% -> neither dominates past 0.6 -> not 'relies_on_layers'
    assert rep.relies_on_layers is False
