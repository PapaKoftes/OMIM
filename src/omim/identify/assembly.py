"""Assembly identification: group panels into a single 3D construction.

Given several panels (each a built MGG + its PartIdentification), infer which
panels belong to the same 3D piece (a carcass, a drawer box, a frame) and how
they likely join. This is the "3D construction from 2D parts" layer.

Pure, read-only, heuristic (authority Level 4-5).

CALIBRATION CAVEAT: like part identification, assembly grouping is NOT
catalog-grounded — manufacturer catalogs define hole/feature geometry, not which
panels form one cabinet. The grouping signals and confidences here are hand-set
and validated only on synthetic fixtures. Assembly/project identifications are
the least-certain OMIM output; they are routed through the human review queue and
must not be trusted as ground truth until calibrated on a real labelled corpus.
See docs/STRATEGY.md.

Grouping signals actually used (kept deliberately conservative):
  * source file/delivery scope — panels from different DXF files are never merged
    (the primary guard against conflating unrelated cabinets in a flat pile)
  * shared stock thickness within that scope (parts of one carcass share thickness)
  * coherent part-type set raises confidence + sets assembly_type (>=2 carcass
    parts -> CARCASS; any drawer part -> DRAWER)

The ``assembly_type`` / confidence reflect the part-set; ``joins`` are *hypotheses*
(side<->cap) for downstream review, not asserted facts. When the grouping signal
is weak/absent, panels are returned as single-panel assemblies rather than
force-merged. NOTE: complementary-dimension and joinery-hole matching are not yet
used as grouping signals — they are candidate future refinements.
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

    # Group by (source_file, thickness band). Scoping by source_file FIRST is the
    # key guard: panels from different DXF deliveries are never merged into one
    # assembly just because they share a common stock thickness (e.g. a flat pile
    # of 18mm panels from 5 different cabinets stays 5 groups, not one). Panels
    # with no recovered thickness fall back to grouping by source_file alone.
    buckets: dict[tuple[str, int | None], list[PanelRef]] = {}
    for r in refs:
        key = (r.source_file, _thickness_key(r.thickness_mm, thickness_tol))
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

    for (_src, band), group in buckets.items():
        grouped = band is not None and len(group) >= min_group
        if grouped:
            assemblies.append(_make(group, thickness_grouped=True))
        else:
            # Too few, or no thickness signal -> emit as singletons (honest: we
            # won't assert a multi-panel assembly without a real grouping signal).
            for r in group:
                assemblies.append(_make([r], thickness_grouped=band is not None))

    return assemblies
