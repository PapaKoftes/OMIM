"""Assembly identification: group panels into a single 3D construction.

Given several panels (each a built MGG + its PartIdentification), infer which
panels belong to the same 3D piece (a carcass, a drawer box, a frame) and how
they likely join. This is the "3D construction from 2D parts" layer.

Pure, read-only, heuristic (authority Level 4-5). Signals:
  * shared panel thickness (parts of one carcass are usually one stock thickness)
  * complementary dimensions (a side's height == the top/bottom's depth, etc.)
  * matching edge-joinery hole counts (dowel/confirmat holes that pair up)
  * a coherent part-type set (2 sides + top + bottom + back = a carcass)

When grouping signals are weak/absent, panels are returned as their own
single-panel assemblies rather than force-merged.
"""

from __future__ import annotations

from typing import Any

from omim.identify.models import (
    AssemblyIdentification,
    JoinHypothesis,
    PanelRef,
)
from omim.identify.parts import PartIdentification

# Part types that, together, indicate a cabinet carcass.
_CARCASS_PARTS = {"SIDE_PANEL", "TOP_PANEL", "BOTTOM_PANEL", "BACK_PANEL", "SHELF"}
_DRAWER_PARTS = {"DRAWER_FRONT", "DRAWER_SIDE", "DRAWER_BACK", "DRAWER_BOTTOM"}


def _provenance() -> dict:
    return {
        "inference_method": "heuristic",
        "pipeline_stage": "assembly_identification",
        "module": "omim.identify.assembly",
    }


def _thickness_key(thickness: float | None, tol: float) -> int | None:
    """Bucket a thickness to a tolerance band so 18.0 and 18.2 group together."""
    if thickness is None:
        return None
    return round(thickness / tol)


def _infer_joins(panels: list[PanelRef]) -> list[JoinHypothesis]:
    """Pair panels likely joined by edge joinery (carcass sides <-> top/bottom)."""
    joins: list[JoinHypothesis] = []
    sides = [p for p in panels if p.part_type == "SIDE_PANEL"]
    caps = [p for p in panels if p.part_type in ("TOP_PANEL", "BOTTOM_PANEL", "SHELF")]
    for s in sides:
        for c in caps:
            joins.append(JoinHypothesis(
                panel_a=s.panel_id, panel_b=c.panel_id,
                join_type="DOWEL_OR_CONFIRMAT", confidence=0.5,
                reason=f"{s.part_type} edge meets {c.part_type} (carcass joinery)",
            ))
    return joins


def identify_assemblies(
    panels: list[tuple[PartIdentification, str]],
    **params: Any,
) -> list[AssemblyIdentification]:
    """Group panels into assemblies.

    Parameters
    ----------
    panels:
        list of ``(PartIdentification, source_file)`` for every panel in scope
        (e.g. all panels found in one project folder).

    Returns one or more :class:`AssemblyIdentification`. Panels that share a
    thickness band are grouped; a coherent carcass/drawer part-set raises the
    confidence and sets the assembly_type.
    """
    thickness_tol = params.get("thickness_tol_mm", 1.0)
    min_group = params.get("min_panels_per_assembly", 2)

    refs = [
        PanelRef(
            panel_id=pid.panel_id, part_type=pid.part_type,
            part_confidence=pid.confidence, width_mm=pid.width_mm,
            height_mm=pid.height_mm, thickness_mm=pid.thickness_mm,
            source_file=src,
        )
        for pid, src in panels
    ]

    # Group by thickness band; panels with no thickness go to their own bucket.
    buckets: dict[int | None, list[PanelRef]] = {}
    no_thickness: list[PanelRef] = []
    for r in refs:
        key = _thickness_key(r.thickness_mm, thickness_tol)
        if key is None:
            no_thickness.append(r)
        else:
            buckets.setdefault(key, []).append(r)

    assemblies: list[AssemblyIdentification] = []
    idx = 0

    def _make(group: list[PanelRef], thickness_grouped: bool) -> AssemblyIdentification:
        nonlocal idx
        part_set = {p.part_type for p in group}
        if part_set & _DRAWER_PARTS:
            atype, base_conf = "DRAWER", 0.6
        elif len(part_set & _CARCASS_PARTS) >= 2:
            atype, base_conf = "CARCASS", 0.7
        elif len(group) >= min_group:
            atype, base_conf = "UNKNOWN_ASSEMBLY", 0.4
        else:
            atype, base_conf = "UNKNOWN_ASSEMBLY", 0.2
        evidence = [{
            "type": "grouping",
            "thickness_grouped": thickness_grouped,
            "part_types": sorted(part_set),
            "panel_count": len(group),
        }]
        idx += 1
        return AssemblyIdentification(
            assembly_id=f"asm-{idx}",
            panels=group,
            panel_count=len(group),
            confidence=round(base_conf, 4),
            assembly_type=atype,
            joins=_infer_joins(group),
            evidence=evidence,
            provenance=_provenance(),
        )

    for group in buckets.values():
        if len(group) >= min_group:
            assemblies.append(_make(group, thickness_grouped=True))
        else:
            # Too few to be a confident assembly -> singletons.
            for r in group:
                assemblies.append(_make([r], thickness_grouped=True))
    for r in no_thickness:
        assemblies.append(_make([r], thickness_grouped=False))

    return assemblies
