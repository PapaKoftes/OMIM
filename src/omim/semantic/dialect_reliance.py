"""Detect whether a panel's feature meaning depends on layer names.

The honest lesson from validating OMIM on real-world panels: geometric feature
inference is *convention-dependent*. A shop that uses catalog-standard hole sizes
(5mm shelf pin on a 32mm grid, 35mm hinge cup, 7mm Confirmat) carries the feature
meaning in the geometry — OMIM recovers it layer-blind. But a shop that drills one
dominant "system" diameter for almost everything carries the meaning in the LAYER
NAME, not the geometry; layer-blind, those holes are genuinely ambiguous.

This module measures that, generically, so OMIM can say honestly: "this dialect
relies on layer names — a layer profile is required for feature meaning," instead
of pretending geometry alone is enough. It is not about any specific shop; it is a
property of the drawing (how concentrated the hole diameters are, and whether they
match known catalog feature sizes).
"""

from __future__ import annotations

from dataclasses import dataclass

from omim.corpus.catalog_ground_truth import KNOWN_FEATURE_DIAMETERS_MM
from omim.graph.mgg import ManufacturingGeometryGraph

# A hole diameter "matches catalog" if within this band of a known feature bore.
_CATALOG_TOL_MM = 0.6
# The dialect is "single-system" when this fraction of holes share one diameter.
_DOMINANCE_THRESHOLD = 0.6


@dataclass
class DialectRelianceReport:
    """How much a panel's feature meaning depends on layer names vs geometry."""

    hole_count: int = 0
    distinct_diameters: int = 0
    dominant_diameter_mm: float | None = None
    dominant_fraction: float = 0.0
    catalog_match_fraction: float = 0.0   # holes whose size matches a catalog bore
    relies_on_layers: bool = False
    message: str = ""


def _matches_catalog(dia: float) -> bool:
    return any(abs(dia - c) <= _CATALOG_TOL_MM for c in KNOWN_FEATURE_DIAMETERS_MM)


def assess_dialect_reliance(mgg: ManufacturingGeometryGraph) -> DialectRelianceReport:
    """Assess whether feature meaning lives in the geometry or in the layer names.

    Reasoning (generic, not shop-specific):
      * If most holes are one diameter that does NOT match a catalog feature size,
        the geometry can't tell a shelf-pin from a dowel from a cam bore — only the
        layer name can. -> relies_on_layers = True (a profile is required).
      * If hole sizes are catalog-diverse, geometry carries the meaning. -> False.
    """
    diameters = [
        round(d["diameter_mm"], 1)
        for _n, d in mgg.geometry_nodes()
        if d.get("geometry_type") == "circle" and d.get("diameter_mm")
        and not d.get("is_outer_boundary")
    ]
    rep = DialectRelianceReport(hole_count=len(diameters))
    if not diameters:
        rep.message = "no holes; dialect reliance not applicable"
        return rep

    counts: dict[float, int] = {}
    for dia in diameters:
        counts[dia] = counts.get(dia, 0) + 1
    rep.distinct_diameters = len(counts)
    dom_dia, dom_n = max(counts.items(), key=lambda kv: kv[1])
    rep.dominant_diameter_mm = dom_dia
    rep.dominant_fraction = round(dom_n / len(diameters), 3)
    rep.catalog_match_fraction = round(
        sum(1 for dia in diameters if _matches_catalog(dia)) / len(diameters), 3
    )

    dominated = rep.dominant_fraction >= _DOMINANCE_THRESHOLD
    dominant_off_catalog = not _matches_catalog(dom_dia)

    if dominated and dominant_off_catalog:
        rep.relies_on_layers = True
        rep.message = (
            f"{rep.dominant_fraction:.0%} of holes share one non-catalog diameter "
            f"({dom_dia}mm): a single-system-hole dialect. Feature meaning lives in "
            f"the layer names, not the geometry — a layer profile is REQUIRED to "
            f"classify these holes correctly."
        )
    elif rep.catalog_match_fraction >= 0.5:
        rep.message = (
            f"{rep.catalog_match_fraction:.0%} of holes match catalog feature sizes: "
            f"geometry carries the feature meaning; layer-blind inference is reliable."
        )
    else:
        rep.message = (
            "mixed dialect: some catalog sizes, some not. Layer-blind inference is "
            "partial; a layer profile improves coverage."
        )
    return rep
