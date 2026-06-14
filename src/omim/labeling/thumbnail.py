"""Dependency-free SVG thumbnails of a panel, for visual human review.

A carpenter reviewing labels should *see* the panel, not read a node id. This
renders a built MGG to a small self-contained SVG (no matplotlib / no binary
deps): the panel outline plus its holes/pockets/cuts, with an optional highlight
of the one node currently under review. SVG opens in any browser and previews in
file managers, so it drops straight next to the CSV review sheet.
"""

from __future__ import annotations

from omim.graph.mgg import ManufacturingGeometryGraph

# Colour by OMIM canonical layer type (muted, print-friendly).
_STROKE = {
    "cut": "#222222",
    "border": "#222222",
    "drill": "#c0392b",
    "pocket": "#2e86c1",
    "engrave": "#8e44ad",
    "toolpath": "#aaaaaa",
    "cleanup": "#cccccc",
    "unknown": "#999999",
}
_HIGHLIGHT = "#e67e22"


def _poly_points(coords) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in coords or []:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            try:
                out.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError):
                continue
    return out


def _bounds(mgg: ManufacturingGeometryGraph):
    xs: list[float] = []
    ys: list[float] = []
    for _nid, d in mgg.geometry_nodes():
        bb = d.get("bounding_box")
        if bb and len(bb) >= 4:
            xs += [bb[0], bb[2]]
            ys += [bb[1], bb[3]]
    if not xs:
        return 0.0, 0.0, 100.0, 100.0
    return min(xs), min(ys), max(xs), max(ys)


def render_panel_svg(
    mgg: ManufacturingGeometryGraph,
    highlight_node_id: str | None = None,
    size_px: int = 320,
) -> str:
    """Return a standalone SVG string of the panel (Y-up, scaled to *size_px*)."""
    xmin, ymin, xmax, ymax = _bounds(mgg)
    w = max(xmax - xmin, 1.0)
    h = max(ymax - ymin, 1.0)
    pad = 0.04 * max(w, h)
    vb_w, vb_h = w + 2 * pad, h + 2 * pad

    def tx(x: float) -> float:
        return x - xmin + pad

    def ty(y: float) -> float:
        # Flip Y so the SVG reads the same way up as the CAD drawing.
        return (ymax - y) + pad

    sw = max(vb_w, vb_h) / 200.0  # stroke scales with the part
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size_px}" '
        f'height="{int(size_px * vb_h / vb_w)}" viewBox="0 0 {vb_w:.2f} {vb_h:.2f}">',
        f'<rect x="0" y="0" width="{vb_w:.2f}" height="{vb_h:.2f}" '
        f'fill="white" stroke="#eee" stroke-width="{sw:.3f}"/>',
    ]

    for nid, d in mgg.geometry_nodes():
        gtype = d.get("geometry_type", "")
        ltype = d.get("inferred_layer_type", "unknown")
        hot = nid == highlight_node_id
        stroke = _HIGHLIGHT if hot else _STROKE.get(ltype, _STROKE["unknown"])
        swid = sw * (2.5 if hot else 1.0)
        if gtype == "circle":
            c = d.get("centroid")
            r = d.get("radius_mm") or 0
            if c and r:
                parts.append(
                    f'<circle cx="{tx(c[0]):.2f}" cy="{ty(c[1]):.2f}" r="{r:.2f}" '
                    f'fill="none" stroke="{stroke}" stroke-width="{swid:.3f}"/>'
                )
        elif gtype in ("polyline", "lwpolyline", "contour"):
            pts = _poly_points(d.get("coordinates"))
            if len(pts) >= 2:
                pstr = " ".join(f"{tx(x):.2f},{ty(y):.2f}" for x, y in pts)
                closed = d.get("is_closed")
                tag = "polygon" if closed else "polyline"
                parts.append(
                    f'<{tag} points="{pstr}" fill="none" stroke="{stroke}" '
                    f'stroke-width="{swid:.3f}"/>'
                )
        elif gtype == "line":
            pts = _poly_points(d.get("coordinates"))
            if len(pts) >= 2:
                (x1, y1), (x2, y2) = pts[0], pts[-1]
                parts.append(
                    f'<line x1="{tx(x1):.2f}" y1="{ty(y1):.2f}" x2="{tx(x2):.2f}" '
                    f'y2="{ty(y2):.2f}" stroke="{stroke}" stroke-width="{swid:.3f}"/>'
                )

    parts.append("</svg>")
    return "\n".join(parts)
