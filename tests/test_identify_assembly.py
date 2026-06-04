"""Tests for assembly + project-structure identification.

Uses lightweight PartIdentification objects directly (the part layer is tested
separately) to verify grouping logic: thickness banding, carcass recognition,
join hypotheses, and the project tree.
"""

from __future__ import annotations

from omim.identify import build_project_structure, identify_assemblies
from omim.identify.models import PartIdentification


def _part(pid, part_type, thickness, w=600, h=800, conf=0.8):
    return PartIdentification(
        panel_id=pid, part_type=part_type, confidence=conf,
        width_mm=w, height_mm=h, thickness_mm=thickness,
    )


def _carcass_panels(src="proj1"):
    return [
        (_part("p_side_l", "SIDE_PANEL", 18.0, 600, 800), src),
        (_part("p_side_r", "SIDE_PANEL", 18.0, 600, 800), src),
        (_part("p_top", "TOP_PANEL", 18.0, 600, 400), src),
        (_part("p_bottom", "BOTTOM_PANEL", 18.0, 600, 400), src),
        (_part("p_back", "BACK_PANEL", 6.0, 580, 780), src),
    ]


def test_carcass_grouped_by_thickness():
    """The four 18mm carcass panels group together; the 6mm back is separate."""
    asms = identify_assemblies(_carcass_panels())
    # One 18mm assembly (4 panels) + the 6mm back as its own group.
    by_count = sorted(a.panel_count for a in asms)
    assert 4 in by_count
    carcass = max(asms, key=lambda a: a.panel_count)
    assert carcass.assembly_type == "CARCASS"
    assert carcass.confidence >= 0.7


def test_join_hypotheses_between_sides_and_caps():
    asms = identify_assemblies(_carcass_panels())
    carcass = max(asms, key=lambda a: a.panel_count)
    # 2 sides x 2 caps (top, bottom) = 4 join hypotheses (shelf also counts as cap).
    assert carcass.joins
    assert all(j.join_type for j in carcass.joins)


def test_drawer_assembly_type():
    panels = [
        (_part("d_front", "DRAWER_FRONT", 16.0), "p"),
        (_part("d_side1", "DRAWER_SIDE", 16.0), "p"),
        (_part("d_side2", "DRAWER_SIDE", 16.0), "p"),
        (_part("d_back", "DRAWER_BACK", 16.0), "p"),
    ]
    asms = identify_assemblies(panels)
    drawer = max(asms, key=lambda a: a.panel_count)
    assert drawer.assembly_type == "DRAWER"


def test_no_thickness_panels_are_singletons():
    panels = [
        (_part("a", "UNKNOWN_PART", None), "p"),
        (_part("b", "UNKNOWN_PART", None), "p"),
    ]
    asms = identify_assemblies(panels)
    assert all(a.panel_count == 1 for a in asms)


def test_project_structure_tree():
    proj = build_project_structure(_carcass_panels(), project_id="proj1", name="Cabinet")
    assert proj.project_id == "proj1"
    assert proj.name == "Cabinet"
    assert proj.panel_count == 5
    # The 4-panel carcass is a grouped assembly; the lone 6mm back is ungrouped.
    assert proj.assembly_count >= 1
    assert any(a.panel_count == 4 for a in proj.assemblies)
    assert any(p.part_type == "BACK_PANEL" for p in proj.ungrouped_panels)


def test_thickness_tolerance_groups_close_values():
    """18.0 and 18.3mm panels group together within 1mm tolerance."""
    panels = [
        (_part("a", "SIDE_PANEL", 18.0), "p"),
        (_part("b", "TOP_PANEL", 18.3), "p"),
    ]
    asms = identify_assemblies(panels, thickness_tol_mm=1.0)
    assert any(a.panel_count == 2 for a in asms)
