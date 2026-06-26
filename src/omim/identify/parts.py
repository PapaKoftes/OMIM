"""Part-type identification: classify a whole panel as a furniture part.

Pure, read-only inference over a built MGG plus its feature annotations (from the
semantic FeatureClassifier). Produces a :class:`PartIdentification` with
confidence, ranked alternatives, evidence, and provenance — it never mutates the
MGG, consistent with the authority hierarchy (this is heuristic, Level 4-5).

Signals used (all derivable from 2D geometry + features):
  * feature mix (hinge cups -> DOOR; confirmat/dowel edge holes -> carcass part)
  * shelf-pin columns (the 32mm system) -> SIDE_PANEL (holds adjustable shelves)
  * panel dimensions / aspect ratio
  * thickness (when recovered via depth/2.5D or layer convention)

Thresholds are overridable via ``params`` so a corpus-tuned ruleset can adjust
them (Wave 11) without code changes.

CALIBRATION CAVEAT (read before trusting the confidences)
---------------------------------------------------------
Unlike the *feature* layer — whose thresholds are grounded in real manufacturer
catalogs (Blum 35mm cup, 32mm system, Confirmat 7mm; see
``omim.corpus.catalog_ground_truth``) — the *part-type* confidences here are
HAND-SET engineering estimates, NOT catalog-derived and NOT yet validated against
real drawings. The catalogs tell you "a 35mm bore 22.5mm from the edge is a hinge
cup"; they do NOT tell you "this whole panel is a DOOR". That judgement is a
heuristic over the feature mix, and its numeric confidence is currently a
plausible guess, not a measured accuracy. Treat part identifications as advisory
and route them through human review until calibrated on a real, expert-labelled
panel corpus. See docs/STRATEGY.md ("the identification gap").
"""

from __future__ import annotations

from typing import Any

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.identify.models import PartIdentification
from omim.semantic.models import SemanticAnnotations


def _feature_summary(annotations: SemanticAnnotations) -> dict[str, int]:
    summary: dict[str, int] = {}
    for fa in annotations.feature_annotations:
        summary[fa.feature_class] = summary.get(fa.feature_class, 0) + 1
    return summary


def _panel_thickness(mgg: ManufacturingGeometryGraph) -> float | None:
    """The panel's STOCK thickness from metadata (layer convention or 2.5D Z
    extent), or None when the DXF carries no thickness cue.

    Deliberately NOT derived from feature ``depth_mm`` — a pocket/blind-hole depth
    is not the panel thickness. Returns None rather than guessing.
    """
    return mgg.metadata.panel_thickness_mm


def identify_part(
    mgg: ManufacturingGeometryGraph,
    annotations: SemanticAnnotations,
    **params: Any,
) -> PartIdentification:
    """Classify the panel represented by *mgg* into a part type.

    Ordered, first-confident-match heuristics; everything falls through to
    UNKNOWN_PART with the strongest alternatives recorded.
    """
    shelf_pin_min = params.get("shelf_pin_min_for_side", 4)
    door_min_area_mm2 = params.get("door_min_area_mm2", 80_000.0)
    back_panel_max_thickness = params.get("back_panel_max_thickness_mm", 8.0)
    long_aspect = params.get("long_aspect_ratio", 3.0)

    summary = _feature_summary(annotations)
    w = mgg.metadata.panel_width_mm
    h = mgg.metadata.panel_height_mm
    thickness = _panel_thickness(mgg)
    area = (w * h) if (w and h) else None
    aspect = (max(w, h) / min(w, h)) if (w and h and min(w, h) > 0) else None

    n_hinge = summary.get("HINGE_CUP_HOLE", 0)
    n_shelf_pin = summary.get("SHELF_PIN_HOLE", 0)
    n_confirmat = summary.get("CONFIRMAT_HOLE", 0)
    n_dowel = summary.get("DOWEL_HOLE", 0)
    n_hardware = summary.get("HARDWARE_HOLE", 0)

    candidates: list[tuple[str, float, str]] = []  # (part_type, confidence, reason)

    # DOOR: hinge cups are an almost unambiguous door signal.
    if n_hinge >= 1:
        conf = 0.90 if n_hinge >= 2 else 0.75
        candidates.append(("DOOR", conf, f"{n_hinge} hinge cup hole(s)"))

    # SIDE_PANEL: shelf-pin column(s) on the 32mm system + carcass joinery.
    if n_shelf_pin >= shelf_pin_min:
        conf = 0.85 if (n_confirmat or n_dowel) else 0.72
        candidates.append((
            "SIDE_PANEL", conf,
            f"{n_shelf_pin} shelf-pin holes (32mm system)"
            + (
                f" + {n_confirmat + n_dowel} edge joinery holes"
                if (n_confirmat or n_dowel) else ""
            ),
        ))

    # BACK_PANEL: large, very thin panel with few/no machining features.
    if (
        thickness is not None and thickness <= back_panel_max_thickness
        and area is not None and area >= door_min_area_mm2
        and (n_hinge + n_shelf_pin + n_confirmat) == 0
    ):
        candidates.append((
            "BACK_PANEL", 0.70,
            f"thin ({thickness:.0f}mm) large panel, no carcass features",
        ))

    # SHELF: long aspect ratio, edge dowel/confirmat holes on the short ends,
    # but NOT a shelf-pin column (that's the side it sits in).
    if (
        aspect is not None and aspect >= long_aspect
        and (n_dowel + n_confirmat) >= 1
        and n_shelf_pin < shelf_pin_min
    ):
        candidates.append((
            "SHELF", 0.62,
            f"elongated panel (aspect {aspect:.1f}) with edge joinery holes",
        ))

    # DRAWER_FRONT: door-like but with handle/hardware holes and no hinge.
    if n_hardware >= 1 and n_hinge == 0 and area is not None and area >= door_min_area_mm2 * 0.4:
        candidates.append((
            "DRAWER_FRONT", 0.55,
            f"{n_hardware} hardware/handle hole(s), no hinge",
        ))

    candidates.sort(key=lambda c: c[1], reverse=True)

    evidence = [{
        "type": "feature_summary",
        "features": summary,
        "panel_width_mm": w,
        "panel_height_mm": h,
        "thickness_mm": thickness,
        "aspect_ratio": round(aspect, 2) if aspect else None,
    }]

    if candidates:
        part_type, confidence, reason = candidates[0]
        evidence.append({"type": "primary_signal", "reason": reason})
        alternatives = [
            {"part_type": pt, "confidence": round(c, 4), "reason": r}
            for pt, c, r in candidates[1:4]
        ]
    else:
        part_type, confidence = "UNKNOWN_PART", 0.0
        alternatives = []

    return PartIdentification(
        panel_id=mgg.metadata.graph_id,
        part_type=part_type,
        confidence=round(confidence, 4),
        evidence=evidence,
        alternatives=alternatives,
        provenance={
            "inference_method": "heuristic",
            "pipeline_stage": "part_identification",
            "module": "omim.identify.parts",
        },
        width_mm=w,
        height_mm=h,
        thickness_mm=thickness,
        feature_summary=summary,
        edge_hole_counts=_edge_hole_counts(mgg),
    )


def _edge_hole_counts(mgg: ManufacturingGeometryGraph, band_mm: float = 50.0) -> dict[str, int]:
    """Count holes within *band_mm* of each panel edge (left/right/top/bottom).

    Edge joinery (dowel/confirmat rows along an edge) is the geometric signal the
    assembly solver uses to deduce which panels mate. Returns {} when the panel
    bbox is unknown.
    """
    bbox = mgg.metadata.panel_bbox
    if not bbox or len(bbox) < 4:
        return {}
    xmin, ymin, xmax, ymax = bbox
    counts = {"left": 0, "right": 0, "top": 0, "bottom": 0}
    for _nid, d in mgg.geometry_nodes():
        if d.get("geometry_type") != "circle" or d.get("is_outer_boundary"):
            continue
        c = d.get("centroid")
        if not c:
            continue
        if abs(c[0] - xmin) <= band_mm:
            counts["left"] += 1
        if abs(c[0] - xmax) <= band_mm:
            counts["right"] += 1
        if abs(c[1] - ymin) <= band_mm:
            counts["bottom"] += 1
        if abs(c[1] - ymax) <= band_mm:
            counts["top"] += 1
    return {k: v for k, v in counts.items() if v > 0}
