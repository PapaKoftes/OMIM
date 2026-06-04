"""Split a multi-panel nest into one RawGeometry per panel.

When a DXF is a nest (a stock sheet carrying many panels), the dataset should get
one labeled record *per panel*, not one for the whole sheet. This module does the
split at the RawGeometry level — before MGG construction — so each panel is then
built into a proper, independent MGG (its own boundary, thickness, contains edges,
features), exactly as a single-panel file would be.

Strategy: identify panel-boundary contours (large closed contours that contain
other geometry), then assign every entity to the panel whose boundary contains its
centroid. The sheet contour itself is dropped (it is stock, not a part). Entities
not inside any panel are attached to the nearest panel as a fallback so nothing is
silently lost.
"""

from __future__ import annotations

from shapely.geometry import Point, Polygon

from omim.parser.models import PanelBoundary, RawEntity, RawGeometry


def _polygon(coords) -> Polygon | None:
    try:
        if not (isinstance(coords, list) and len(coords) >= 3
                and isinstance(coords[0], list)):
            return None
        poly = Polygon([(p[0], p[1]) for p in coords])
        return poly if poly.is_valid and poly.area > 0 else None
    except (TypeError, ValueError, IndexError):
        return None


def _entity_centroid(ent: RawEntity) -> tuple[float, float] | None:
    if ent.centroid and len(ent.centroid) >= 2:
        return (ent.centroid[0], ent.centroid[1])
    return None


def split_raw_geometry_by_panels(
    raw: RawGeometry,
    sheet_keywords: tuple[str, ...] = ("SHEET", "STOCK", "MATERIAL", "BLANK", "NEST"),
    min_panel_area_fraction: float = 0.05,
) -> list[RawGeometry]:
    """Split *raw* into one RawGeometry per detected panel.

    Returns ``[raw]`` unchanged when fewer than two panels are detected (i.e. the
    file is a single panel — the common case). Each returned RawGeometry has its
    own panel_boundary and the subset of entities that fall inside that panel.
    """
    # Closed contours that could be panels or the sheet.
    closed: list[tuple[RawEntity, Polygon]] = []
    for e in raw.entities:
        if e.entity_type not in ("LWPOLYLINE", "POLYLINE") or not e.is_closed:
            continue
        poly = _polygon(e.coordinates)
        if poly is not None:
            closed.append((e, poly))
    if len(closed) < 2:
        return [raw]

    max_area = max(p.area for _e, p in closed)

    # The sheet: an explicit sheet-layer contour, else the single largest contour
    # that contains >= 2 others.
    sheet_ent: RawEntity | None = None
    explicit = [
        (e, p) for e, p in closed
        if any(k in (e.layer or "").upper() for k in sheet_keywords)
    ]
    if explicit:
        sheet_ent = max(explicit, key=lambda t: t[1].area)[0]
    else:
        largest_e, largest_p = max(closed, key=lambda t: t[1].area)
        contained = sum(
            1 for e, p in closed
            if e.entity_id != largest_e.entity_id
            and largest_p.contains(p.representative_point())
        )
        if contained >= 2:
            sheet_ent = largest_e

    # Panel contours: closed contours that are not the sheet, big enough, and not
    # contained by another (larger) panel candidate.
    candidates = [
        (e, p) for e, p in closed
        if (sheet_ent is None or e.entity_id != sheet_ent.entity_id)
        and p.area >= min_panel_area_fraction * max_area
    ]
    panels: list[tuple[RawEntity, Polygon]] = []
    for e, p in candidates:
        rep = p.representative_point()
        inside_other = any(
            oe.entity_id != e.entity_id and op.area > p.area and op.contains(rep)
            for oe, op in candidates
        )
        if not inside_other:
            panels.append((e, p))

    if len(panels) < 2:
        return [raw]

    # Assign every non-panel-boundary entity to the panel whose polygon contains
    # its centroid; fall back to the nearest panel so nothing is dropped.
    panel_entities: dict[str, list[RawEntity]] = {e.entity_id: [] for e, _ in panels}
    panel_ids = {e.entity_id for e, _ in panels}
    sheet_id = sheet_ent.entity_id if sheet_ent else None

    for e in raw.entities:
        if e.entity_id == sheet_id:
            continue
        if e.entity_id in panel_ids:
            continue  # panel boundaries are added as each sub-geometry's boundary
        c = _entity_centroid(e)
        target: str | None = None
        if c is not None:
            pt = Point(c)
            for pe, pp in panels:
                if pp.contains(pt):
                    target = pe.entity_id
                    break
            if target is None:
                # nearest panel by centroid distance
                target = min(
                    panels, key=lambda t: t[1].distance(pt)
                )[0].entity_id
        if target is not None:
            panel_entities[target].append(e)

    # Build one RawGeometry per panel.
    out: list[RawGeometry] = []
    for pe, pp in panels:
        bbox = list(pp.bounds)
        ents = [pe, *panel_entities[pe.entity_id]]
        out.append(RawGeometry(
            source_file=raw.source_file,
            source_file_hash=f"{raw.source_file_hash}#panel-{pe.entity_id}",
            dxf_version=raw.dxf_version,
            units_original=raw.units_original,
            units_normalized_to=raw.units_normalized_to,
            entities=ents,
            panel_boundary=PanelBoundary(
                entity_id=pe.entity_id,
                coordinates=pe.coordinates,
                bounding_box=pe.bounding_box or list(bbox),
                area_mm2=pe.area_mm2 or pp.area,
                inferred=False,
            ),
            panel_boundary_inferred=False,
            entity_counts={},
            warnings=list(raw.warnings),
        ))
    return out
