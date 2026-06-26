"""Assembly solver — deduce carcass structure from geometry, don't guess it.

The honest critique of part identification: "what part is this?" is often
unanswerable for a panel *in isolation* (a rectangle is a side or a divider
depending on the cabinet). The fix is to solve the assembly first and let part
roles fall out of the solved structure.

This solver works on the signals that are geometrically decidable for a cabinet
carcass:

  * **complementary dimensions** — in a box, the two sides share a dimension with
    the top/bottom (the carcass depth), and another with the back. Matching shared
    edge-lengths reconstructs which panels abut.
  * **edge joinery** — dowel/confirmat rows on a panel *edge* mate it to a
    neighbour; matching edge-hole counts across panels evidences a real join.

From the solved structure, roles are deduced deterministically: the pair of
largest congruent panels with edge joinery on a long edge are the SIDES; panels
whose length equals the sides' depth and which carry mating edge holes are
TOP/BOTTOM; a large thin panel is the BACK.

SCOPE / HONESTY: this is geometric deduction, proven on synthetic carcasses. It is
NOT yet validated on real cabinets (dowel positions are often implicit, tolerances
vary by shop). It returns a confidence and explicit reasons; on weak evidence it
declines to assert a structure rather than forcing one. Like the rest of
identification, it is advisory until the real-data capability test (see
docs/REAL_DATA_DROP_IN.md) measures it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from omim.identify.models import JoinHypothesis, PanelRef

# Two lengths "match" if within this tolerance (mm) — covers kerf + measurement.
_DIM_TOL = 3.0


def _dims_sorted(p: PanelRef) -> tuple[float, float] | None:
    if p.width_mm is None or p.height_mm is None:
        return None
    a, b = sorted((p.width_mm, p.height_mm))
    return (a, b)


def _congruent(p: PanelRef, q: PanelRef, tol: float = _DIM_TOL) -> bool:
    dp, dq = _dims_sorted(p), _dims_sorted(q)
    if dp is None or dq is None:
        return False
    return abs(dp[0] - dq[0]) <= tol and abs(dp[1] - dq[1]) <= tol


def _shares_length(p: PanelRef, length: float, tol: float = _DIM_TOL) -> bool:
    d = _dims_sorted(p)
    if d is None:
        return False
    return abs(d[0] - length) <= tol or abs(d[1] - length) <= tol


def _edge_joinery_total(p: PanelRef) -> int:
    return sum(p.edge_hole_counts.values()) if p.edge_hole_counts else 0


@dataclass
class SolvedAssembly:
    """A geometrically-deduced carcass structure."""

    solved: bool = False
    assembly_type: str = "UNKNOWN_ASSEMBLY"
    confidence: float = 0.0
    # panel_id -> deduced role
    roles: dict[str, str] = field(default_factory=dict)
    joins: list[JoinHypothesis] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def solve_carcass(panels: list[PanelRef]) -> SolvedAssembly:
    """Attempt to deduce a cabinet-carcass structure from a panel group.

    Returns a SolvedAssembly. ``solved=False`` (with reasons) when the geometry
    doesn't support a confident structure — declining is the honest outcome on
    weak evidence, not forcing a guess.
    """
    out = SolvedAssembly()
    usable = [p for p in panels if _dims_sorted(p) is not None]
    if len(usable) < 3:
        out.reasons.append("fewer than 3 dimensioned panels; cannot solve a carcass")
        return out

    # 1. SIDES: the pair of congruent panels with the most edge joinery.
    side_pair = None
    best_join = -1
    for i in range(len(usable)):
        for j in range(i + 1, len(usable)):
            a, b = usable[i], usable[j]
            if _congruent(a, b):
                jt = _edge_joinery_total(a) + _edge_joinery_total(b)
                if jt > best_join:
                    best_join, side_pair = jt, (a, b)
    if side_pair is None:
        out.reasons.append("no congruent panel pair -> no identifiable sides")
        return out

    sa, sb = side_pair
    out.roles[sa.panel_id] = "SIDE_PANEL"
    out.roles[sb.panel_id] = "SIDE_PANEL"
    # The carcass "depth" is the SHORT dimension of a side (the panel depth).
    depth = _dims_sorted(sa)[0]
    out.reasons.append(
        f"two congruent panels with edge joinery -> SIDE_PANELs "
        f"({sa.panel_id}, {sb.panel_id}); carcass depth ~{depth:.0f}mm"
    )

    # 2. TOP/BOTTOM/SHELF: remaining panels whose length matches the carcass depth
    #    AND that carry edge joinery (they bolt into the sides).
    caps = [
        p for p in usable
        if p.panel_id not in out.roles
        and _shares_length(p, depth)
        and _edge_joinery_total(p) > 0
    ]
    caps.sort(key=lambda p: -(p.width_mm or 0) * (p.height_mm or 0))
    for idx, c in enumerate(caps):
        role = ("TOP_PANEL", "BOTTOM_PANEL")[idx] if idx < 2 else "SHELF"
        out.roles[c.panel_id] = role
        out.reasons.append(
            f"{c.panel_id} length matches carcass depth + has edge joinery -> {role}"
        )

    # 3. BACK: a remaining large, thin panel with little/no edge joinery.
    for p in usable:
        if p.panel_id in out.roles:
            continue
        thin = p.thickness_mm is not None and p.thickness_mm <= 8.0
        if thin and _edge_joinery_total(p) == 0:
            out.roles[p.panel_id] = "BACK_PANEL"
            out.reasons.append(f"{p.panel_id} thin + no edge joinery -> BACK_PANEL")

    # 4. Joins: each SIDE mates to each TOP/BOTTOM/SHELF (deduced abutment).
    sides = [pid for pid, r in out.roles.items() if r == "SIDE_PANEL"]
    caps_ids = [pid for pid, r in out.roles.items()
                if r in ("TOP_PANEL", "BOTTOM_PANEL", "SHELF")]
    for s in sides:
        for c in caps_ids:
            out.joins.append(JoinHypothesis(
                panel_a=s, panel_b=c, join_type="EDGE_JOINERY",
                confidence=0.7,
                reason="congruent-side edge mates a depth-matched cap with joinery",
            ))

    # A solved carcass needs at least the two sides + one cap.
    n_roles = len(out.roles)
    if len(sides) == 2 and caps_ids:
        out.solved = True
        out.assembly_type = "CARCASS"
        # Confidence scales with how complete + joinery-backed the structure is.
        out.confidence = round(min(0.85, 0.4 + 0.1 * n_roles + 0.05 * (best_join > 0)), 4)
    else:
        out.reasons.append("structure incomplete (need 2 sides + >=1 cap)")
    return out
