"""The assembly solver: deduce carcass structure from geometry, not guess it.

Synthetic carcasses with congruent sides + depth-matched caps + edge joinery must
solve to the right roles; loose unrelated panels must honestly decline. This is
the capability that makes part-ID well-posed (roles fall out of the solved
assembly). It is proven here synthetically; real-cabinet validation is gated on
the real-data capability test.
"""

from __future__ import annotations

from omim.identify.assembly_solver import solve_carcass
from omim.identify.models import PanelRef


def _panel(pid, w, h, t=18.0, edges=None):
    return PanelRef(
        panel_id=pid, width_mm=w, height_mm=h, thickness_mm=t,
        edge_hole_counts=edges or {},
    )


def _carcass_panels():
    # Two sides 600(depth) x 800(height), edge joinery on the vertical edges.
    side_l = _panel("side_l", 600, 800, edges={"top": 4, "bottom": 4})
    side_r = _panel("side_r", 600, 800, edges={"top": 4, "bottom": 4})
    # Top + bottom: 600(depth) x 500(width), edge joinery on the ends that bolt
    # into the sides.
    top = _panel("top", 500, 600, edges={"left": 4, "right": 4})
    bottom = _panel("bottom", 500, 600, edges={"left": 4, "right": 4})
    # Back: large, thin, no edge joinery.
    back = _panel("back", 480, 780, t=6.0)
    return [side_l, side_r, top, bottom, back]


def test_solver_deduces_carcass_roles():
    sol = solve_carcass(_carcass_panels())
    assert sol.solved
    assert sol.assembly_type == "CARCASS"
    # Both sides deduced.
    sides = [pid for pid, r in sol.roles.items() if r == "SIDE_PANEL"]
    assert set(sides) == {"side_l", "side_r"}
    # Top + bottom deduced as caps (depth-matched + edge joinery).
    caps = {r for pid, r in sol.roles.items() if pid in ("top", "bottom")}
    assert caps <= {"TOP_PANEL", "BOTTOM_PANEL"}
    assert "top" in sol.roles and "bottom" in sol.roles
    # Back deduced (thin, no joinery).
    assert sol.roles.get("back") == "BACK_PANEL"


def test_solver_emits_side_to_cap_joins():
    sol = solve_carcass(_carcass_panels())
    # Each side mates each cap -> 2 sides x 2 caps = 4 joins.
    pairs = {(j.panel_a, j.panel_b) for j in sol.joins}
    assert ("side_l", "top") in pairs
    assert ("side_r", "bottom") in pairs


def test_solver_declines_on_unrelated_panels():
    """Three differently-sized loose panels do NOT form a carcass."""
    loose = [
        _panel("a", 300, 400),
        _panel("b", 700, 200),
        _panel("c", 550, 950),
    ]
    sol = solve_carcass(loose)
    assert not sol.solved
    assert sol.reasons  # explains why


def test_solver_declines_with_too_few_panels():
    sol = solve_carcass([_panel("a", 600, 800), _panel("b", 600, 800)])
    assert not sol.solved
    assert "fewer than 3" in " ".join(sol.reasons)


def test_solver_confidence_is_bounded_and_honest():
    sol = solve_carcass(_carcass_panels())
    assert 0.0 < sol.confidence <= 0.85  # never overclaims certainty
    assert sol.reasons  # always explains its deduction


def test_identify_assemblies_uses_deduced_roles():
    """Full path: PartIdentifications with edge-hole data -> identify_assemblies
    runs the solver and overrides weak per-panel guesses with deduced roles."""
    from omim.identify.assembly import identify_assemblies
    from omim.identify.models import PartIdentification

    def pid(panel_id, w, h, t=18.0, edges=None, guess="UNKNOWN_PART"):
        return PartIdentification(
            panel_id=panel_id, part_type=guess, confidence=0.3,
            width_mm=w, height_mm=h, thickness_mm=t, edge_hole_counts=edges or {},
        )

    # Same carcass, but every per-panel guess is wrong/unknown — the SOLVER must
    # fix the roles from geometry.
    parts = [
        (pid("side_l", 600, 800, edges={"top": 4, "bottom": 4}), "cab.dxf"),
        (pid("side_r", 600, 800, edges={"top": 4, "bottom": 4}), "cab.dxf"),
        (pid("top", 500, 600, edges={"left": 4, "right": 4}), "cab.dxf"),
        (pid("bottom", 500, 600, edges={"left": 4, "right": 4}), "cab.dxf"),
        (pid("back", 480, 780, t=6.0), "cab.dxf"),
    ]
    asms = identify_assemblies(parts)
    carcass = max(asms, key=lambda a: a.panel_count)
    assert carcass.assembly_type == "CARCASS"
    roles = {p.panel_id: p.part_type for p in carcass.panels}
    assert roles["side_l"] == "SIDE_PANEL"
    assert roles["side_r"] == "SIDE_PANEL"
    assert roles["back"] == "BACK_PANEL"
    # The deduction beat the UNKNOWN guesses.
    assert carcass.evidence[0]["type"] == "geometric_solve"
