"""The 'delete the layer names' adversarial test — does OMIM actually infer?

If classification collapses when layer names are removed, OMIM is a lookup table.
If features still recover from pure geometry (diameter, the 32mm grid, edge
signatures), the 'semantic inference' claim is earned. These tests pin a minimum
layer-blind recovery so the geometric inference can never silently regress into
pure layer-name dependence.

Synthetic geometry only; the same harness is what a real labelled corpus plugs
into to earn the inference claim on real data.
"""

from __future__ import annotations

import ezdxf

from omim.graph.builder import MGGBuilder
from omim.parser.dxf_parser import DXFParser
from omim.semantic.layer_blind import layer_blind_report, strip_layers


def _realistic_panel(tmp_path):
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (600, 0), (600, 800), (0, 800)], close=True,
                     dxfattribs={"layer": "CUT"})
    # Shelf-pin column on the 32mm grid (geometry-decidable).
    for i in range(6):
        m.add_circle((37, 100 + 32 * i), radius=2.5, dxfattribs={"layer": "DRILL"})
    # Hinge cups (35mm + edge distance).
    m.add_circle((22.5, 150), radius=17.5, dxfattribs={"layer": "HINGE"})
    m.add_circle((22.5, 650), radius=17.5, dxfattribs={"layer": "HINGE"})
    # Confirmat 7mm + dowel 8mm (diameter-decidable).
    m.add_circle((300, 50), radius=3.5, dxfattribs={"layer": "DRILL"})
    m.add_circle((300, 750), radius=4.0, dxfattribs={"layer": "DRILL"})
    p = tmp_path / "panel.dxf"
    doc.saveas(p)
    return MGGBuilder().build(DXFParser().parse(p).geometry)


def test_strip_layers_removes_all_layer_signal(tmp_path):
    mgg = _realistic_panel(tmp_path)
    blind = strip_layers(mgg)
    for _nid, d in blind.geometry_nodes():
        assert d["layer"] == ""
        assert d["inferred_layer_type"] == "unknown"
    # Original is untouched (copy semantics).
    aware_layers = {d["layer"] for _n, d in mgg.geometry_nodes()}
    assert aware_layers != {""}


def test_catalog_convention_features_recover_without_layer_names(tmp_path):
    """For a CATALOG-CONVENTION panel (standard 5/35/7/8mm bores), geometry alone
    recovers most features — meaning is in the geometry, not the layer names.

    NOTE: this is convention-dependent and NOT a universal guarantee. A shop that
    drills one dominant non-catalog 'system' diameter for everything carries
    feature meaning in its layer names instead, and recovers near zero here — see
    test_single_system_dialect_does_not_recover_layer_blind below. That is correct
    behaviour, not a defect (the omim.semantic.dialect_reliance detector flags it).
    """
    rep = layer_blind_report(_realistic_panel(tmp_path))
    assert rep.total_features == 11
    # Geometry alone recovers the large majority of CATALOG-convention features.
    assert rep.blind_known_ratio >= 0.8, rep.per_class_blind
    assert rep.agreement_ratio >= 0.8


def test_single_system_dialect_does_not_recover_layer_blind(tmp_path):
    """Honest counter-case: when every hole is one off-catalog diameter, geometry
    CANNOT recover feature meaning layer-blind — and shouldn't pretend to."""
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (600, 0), (600, 800), (0, 800)], close=True,
                     dxfattribs={"layer": "CUT"})
    for i in range(8):
        for j in range(8):
            m.add_circle((50 + i * 40, 100 + j * 40), radius=2.0,  # Ø4, off-catalog
                         dxfattribs={"layer": "DRILL"})
    p = tmp_path / "system.dxf"
    doc.saveas(p)
    mgg = MGGBuilder().build(DXFParser().parse(p).geometry)
    rep = layer_blind_report(mgg)
    # Layer-blind, the off-catalog system holes collapse to the GENERIC fallback
    # (THROUGH_HOLE) — geometry recovers no SPECIFIC feature meaning. A shelf-pin,
    # a dowel, and a cam bore at this diameter are indistinguishable without the
    # layer name. That is the honest limit, not a defect.
    specific = {k: v for k, v in rep.per_class_blind.items()
                if k not in ("THROUGH_HOLE", "PROFILE_CUT", "UNKNOWN_FEATURE")}
    assert not specific, f"unexpected specific recovery: {specific}"


def test_grid_shelf_pins_are_geometric(tmp_path):
    """Shelf pins recover layer-blind because the 32mm grid is pure geometry."""
    rep = layer_blind_report(_realistic_panel(tmp_path))
    assert rep.per_class_blind.get("SHELF_PIN_HOLE", 0) >= 5


def test_hinge_cups_are_geometric(tmp_path):
    """35mm + edge-distance recovers hinge cups without a HINGE layer."""
    rep = layer_blind_report(_realistic_panel(tmp_path))
    assert rep.per_class_blind.get("HINGE_CUP_HOLE", 0) >= 1
