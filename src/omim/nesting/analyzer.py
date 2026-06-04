"""Multi-panel nesting analysis over a built MGG.

Given an MGG that may represent a whole nest (a stock sheet carrying many panels),
:func:`analyze_nesting` determines:

  * which closed contours are *panels* vs the *sheet* vs interior features;
  * how features distribute across panels (Shapely containment);
  * utilization (panel area / sheet area), overlapping panels, panels outside the
    sheet — physical-sanity signals for a nest.

Uses only shapely (already a dependency). Optional :mod:`rectpack` adds an ideal
packing comparison when installed, but its absence never breaks analysis.
"""

from __future__ import annotations

import logging

from shapely.geometry import Point, Polygon

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.nesting.models import NestedPanel, NestingLayout

logger = logging.getLogger(__name__)

# Layer-name keywords that denote the stock sheet (not a panel).
_SHEET_KEYWORDS = ("SHEET", "STOCK", "MATERIAL", "BLANK", "NEST")

# A panel candidate must be a closed contour at least this fraction of the largest
# closed contour's area — filters out small interior cutouts/pockets.
_PANEL_AREA_FRACTION = 0.05
# Minimum absolute panel area (mm^2) — a 50x50mm panel is ~2500; be permissive.
_MIN_PANEL_AREA_MM2 = 1000.0


def _polygon(coords) -> Polygon | None:
    try:
        if not (isinstance(coords, list) and len(coords) >= 3
                and isinstance(coords[0], list)):
            return None
        poly = Polygon(coords)
        return poly if poly.is_valid and poly.area > 0 else None
    except (TypeError, ValueError):
        return None


def _closed_contours(mgg: ManufacturingGeometryGraph) -> list[tuple[str, dict, Polygon]]:
    """Return (node_id, data, polygon) for every valid closed polyline/contour."""
    out: list[tuple[str, dict, Polygon]] = []
    for nid, data in mgg.geometry_nodes():
        if data.get("geometry_type") not in ("polyline", "lwpolyline", "contour"):
            continue
        if not data.get("is_closed"):
            continue
        poly = _polygon(data.get("coordinates"))
        if poly is not None:
            out.append((nid, data, poly))
    return out


def _is_sheet_layer(data: dict) -> bool:
    layer = (data.get("layer") or "").upper()
    return any(k in layer for k in _SHEET_KEYWORDS)


def analyze_nesting(mgg: ManufacturingGeometryGraph) -> NestingLayout:
    """Analyse an MGG for a multi-panel nest layout.

    Detection strategy:
      1. Collect all valid closed contours.
      2. A contour on an explicit SHEET/STOCK layer (or the single largest contour
         that geometrically contains the others) is the *sheet*.
      3. The remaining large closed contours that are NOT contained by another
         non-sheet contour are *panels* (top-level parts on the sheet).
      4. Features (holes, small cutouts) are assigned to the panel that contains
         them.
    """
    contours = _closed_contours(mgg)
    warnings: list[str] = []

    if not contours:
        return NestingLayout(is_nested=False, panel_count=0, sheet_source="none",
                             warnings=["no closed contours found"])

    # --- Identify the sheet ------------------------------------------------
    sheet = None
    sheet_source = "none"
    explicit_sheets = [(nid, d, p) for nid, d, p in contours if _is_sheet_layer(d)]
    if explicit_sheets:
        # Largest explicit sheet-layer contour.
        sheet = max(explicit_sheets, key=lambda t: t[2].area)
        sheet_source = "sheet_layer"
    else:
        # Heuristic: the single largest contour that contains >= 2 others is the
        # sheet. If nothing contains multiple contours, there is no distinct sheet
        # (single-panel file).
        largest = max(contours, key=lambda t: t[2].area)
        contained = sum(
            1 for nid, _d, p in contours
            if nid != largest[0] and largest[2].contains(p.representative_point())
        )
        if contained >= 2:
            sheet = largest
            sheet_source = "convex_hull"

    sheet_id = sheet[0] if sheet else None
    sheet_poly = sheet[2] if sheet else None

    # --- Identify panels ---------------------------------------------------
    # Candidate panels: closed contours that are not the sheet, large enough, and
    # not contained by another non-sheet candidate (i.e. top-level parts).
    max_area = max(p.area for _n, _d, p in contours)
    candidates = [
        (nid, d, p) for nid, d, p in contours
        if nid != sheet_id
        and p.area >= max(_MIN_PANEL_AREA_MM2, _PANEL_AREA_FRACTION * max_area)
    ]

    panels: list[tuple[str, dict, Polygon]] = []
    for nid, d, p in candidates:
        rep = p.representative_point()
        # Skip if contained by another (larger) candidate -> it's an interior
        # cutout of that panel, not a panel itself.
        inside_other = any(
            onid != nid and op.area > p.area and op.contains(rep)
            for onid, _od, op in candidates
        )
        if not inside_other:
            panels.append((nid, d, p))

    # If we found a sheet but only one (or zero) panels, fall back: treat all
    # candidates as panels (the sheet heuristic may have mis-fired on a lone part).
    if sheet_source == "convex_hull" and len(panels) <= 1:
        sheet, sheet_id, sheet_poly, sheet_source = None, None, None, "none"
        panels = [(nid, d, p) for nid, d, p in candidates]

    # --- Assign features to panels ----------------------------------------
    feature_nodes = [
        (nid, data) for nid, data in mgg.geometry_nodes()
        if nid != sheet_id
        and not any(nid == pnid for pnid, _pd, _pp in panels)
        and data.get("centroid")
    ]

    nested_panels: list[NestedPanel] = []
    for pnid, _pd, ppoly in panels:
        bbox = list(ppoly.bounds)  # (xmin, ymin, xmax, ymax)
        feat_ids: list[str] = []
        for fnid, fdata in feature_nodes:
            c = fdata.get("centroid")
            if c and ppoly.contains(Point(c[0], c[1])):
                feat_ids.append(fnid)
        nested_panels.append(NestedPanel(
            panel_id=pnid,
            bounding_box=[round(v, 4) for v in bbox],
            area_mm2=round(ppoly.area, 4),
            width_mm=round(bbox[2] - bbox[0], 4),
            height_mm=round(bbox[3] - bbox[1], 4),
            feature_node_ids=feat_ids,
            feature_count=len(feat_ids),
        ))

    panel_count = len(nested_panels)
    total_panel_area = round(sum(p.area_mm2 for p in nested_panels), 4)

    # --- Sanity metrics ----------------------------------------------------
    overlapping: list[list[str]] = []
    for i in range(len(panels)):
        for j in range(i + 1, len(panels)):
            pi, pj = panels[i][2], panels[j][2]
            inter = pi.intersection(pj).area
            # Tolerate touching edges; flag real area overlap.
            if inter > 1.0 and inter > 0.01 * min(pi.area, pj.area):
                overlapping.append([panels[i][0], panels[j][0]])

    outside: list[str] = []
    utilization = None
    sheet_area = None
    if sheet_poly is not None:
        sheet_area = round(sheet_poly.area, 4)
        buffered = sheet_poly.buffer(0.5)
        for pnid, _pd, ppoly in panels:
            if not buffered.contains(ppoly):
                outside.append(pnid)
        if sheet_area > 0:
            utilization = round(total_panel_area / sheet_area, 4)

    if overlapping:
        warnings.append(f"{len(overlapping)} overlapping panel pair(s) detected")
    if outside:
        warnings.append(f"{len(outside)} panel(s) extend outside the sheet")

    # --- Optional packing comparison --------------------------------------
    packing_available, packing_note = _packing_analysis(nested_panels, sheet_area)

    return NestingLayout(
        is_nested=panel_count > 1,
        panel_count=panel_count,
        sheet_boundary_id=sheet_id,
        sheet_bounding_box=[round(v, 4) for v in sheet_poly.bounds] if sheet_poly else None,
        sheet_area_mm2=sheet_area,
        sheet_source=sheet_source,
        panels=nested_panels,
        total_panel_area_mm2=total_panel_area,
        utilization=utilization,
        overlapping_panel_pairs=overlapping,
        panels_outside_sheet=outside,
        packing_available=packing_available,
        packing_note=packing_note,
        warnings=warnings,
    )


def _packing_analysis(
    panels: list[NestedPanel], sheet_area: float | None
) -> tuple[bool, str]:
    """Optional: compare against an ideal rectangle packing via rectpack.

    Degrades gracefully — returns (False, reason) when rectpack is not installed,
    mirroring the ML layer's optional-dependency pattern.
    """
    try:
        import rectpack  # noqa: F401
    except ImportError:
        return False, "rectpack not installed; install 'omim[nesting]' for packing analysis"
    if not panels or sheet_area is None or sheet_area <= 0:
        return True, "insufficient data for packing analysis"
    try:
        from rectpack import newPacker

        # Derive a square-ish bin from the sheet area as a reference container.
        side = sheet_area ** 0.5
        packer = newPacker(rotation=True)
        for p in panels:
            packer.add_rect(max(1, round(p.width_mm)), max(1, round(p.height_mm)), rid=p.panel_id)
        packer.add_bin(round(side * 1.5), round(side * 1.5))
        packer.pack()
        packed = sum(len(b) for b in packer)
        return True, f"rectpack: packed {packed}/{len(panels)} panels into a reference bin"
    except Exception as exc:  # noqa: BLE001 — packing is advisory only
        return True, f"packing analysis error: {exc}"
