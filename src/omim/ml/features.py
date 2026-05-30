"""Node-feature extraction for the GNN layer — PURE NUMPY, no torch required.

This is the testable core of the ML layer. It converts a
:class:`~omim.graph.mgg.ManufacturingGeometryGraph` into a fixed-width
``(N, 16)`` float matrix, one row per geometry node, plus the parallel list of
node IDs.

The 16-dimensional node feature vector (per docs/10_IMPLEMENTATION/ML_Integration.md):

    [0]  area_normalized          area_mm2 / max_area in panel           (0–1)
    [1]  perimeter_normalized     perimeter_mm / max_perimeter in panel   (0–1)
    [2]  aspect_ratio             log-scaled bbox_width / bbox_height     (≈ -1..1)
    [3]  circularity              4π·area / perimeter²                    (0–1; 1=circle)
    [4]  diameter_normalized      diameter_mm / 100mm (circles; 0 else)   (0–~1)
    [5]  is_circle                1.0 if geometry_type == circle          (binary)
    [6]  is_closed                1.0 if closed contour                   (binary)
    [7]  is_outer_boundary        1.0 if panel outer boundary             (binary)
    [8]  centroid_x_normalized    centroid_x / panel_width                (0–1)
    [9]  centroid_y_normalized    centroid_y / panel_height               (0–1)
    [10] layer_cut                one-hot: inferred_layer_type == cut     (binary)
    [11] layer_drill              one-hot: inferred_layer_type == drill   (binary)
    [12] layer_pocket             one-hot: inferred_layer_type == pocket  (binary)
    [13] layer_other              one-hot: any other / unknown layer      (binary)
    [14] n_contained_features     contained-feature count, normalized     (0–1)
    [15] distance_to_edge_norm    dist to nearest panel edge / panel_size (0–1)

All values are guaranteed finite (NaN/Inf are scrubbed) and bounded. The layer
one-hot block ([10:14]) always sums to exactly 1.0.

Importing this module never imports torch.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from omim.graph.mgg import ManufacturingGeometryGraph

#: Dimensionality of the node feature vector. Matches GNN ``in_channels``.
FEATURE_DIM = 16

#: Human-readable names for each feature dimension (index-aligned).
FEATURE_NAMES: list[str] = [
    "area_normalized",
    "perimeter_normalized",
    "aspect_ratio",
    "circularity",
    "diameter_normalized",
    "is_circle",
    "is_closed",
    "is_outer_boundary",
    "centroid_x_normalized",
    "centroid_y_normalized",
    "layer_cut",
    "layer_drill",
    "layer_pocket",
    "layer_other",
    "n_contained_features",
    "distance_to_edge_norm",
]

# Normalization constants (documented, deterministic — not learned).
_DIAMETER_REF_MM = 100.0  # spec: diameter / 100mm
_MAX_CONTAINED_REF = 20.0  # normalize contained-feature counts against this cap

assert len(FEATURE_NAMES) == FEATURE_DIM  # invariant guard


def _f(value: object, default: float = 0.0) -> float:
    """Coerce *value* to a finite float, falling back to *default*."""
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def _panel_dimensions(mgg: ManufacturingGeometryGraph) -> tuple[float, float, float, float]:
    """Return ``(width, height, panel_size, panel_diagonal)`` for normalization.

    Prefers MGG metadata; falls back to the outer-boundary bounding box; falls
    back again to the union bbox of all geometry. All returned dimensions are
    strictly positive (clamped to >= 1.0) so divisions are always safe.
    """
    meta = getattr(mgg, "metadata", None)
    width = _f(getattr(meta, "panel_width_mm", None))
    height = _f(getattr(meta, "panel_height_mm", None))

    bbox = getattr(meta, "panel_bbox", None)
    if (width <= 0.0 or height <= 0.0) and bbox and len(bbox) == 4:
        width = width or (bbox[2] - bbox[0])
        height = height or (bbox[3] - bbox[1])

    if width <= 0.0 or height <= 0.0:
        # Fall back to outer boundary, then the union of all node bboxes.
        xs: list[float] = []
        ys: list[float] = []
        for _nid, data in mgg.geometry_nodes():
            nb = data.get("bounding_box")
            if nb and len(nb) == 4:
                xs.extend([_f(nb[0]), _f(nb[2])])
                ys.extend([_f(nb[1]), _f(nb[3])])
        if xs and ys:
            width = width or (max(xs) - min(xs))
            height = height or (max(ys) - min(ys))

    width = max(width, 1.0)
    height = max(height, 1.0)
    panel_size = max(width, height)
    diagonal = math.hypot(width, height)
    return width, height, panel_size, diagonal


def _panel_bbox(mgg: ManufacturingGeometryGraph) -> tuple[float, float, float, float] | None:
    """Return the panel bounding box ``(xmin, ymin, xmax, ymax)`` or ``None``."""
    meta = getattr(mgg, "metadata", None)
    bbox = getattr(meta, "panel_bbox", None)
    if bbox and len(bbox) == 4:
        return (_f(bbox[0]), _f(bbox[1]), _f(bbox[2]), _f(bbox[3]))
    # Fall back to outer boundary node.
    for _nid, data in mgg.geometry_nodes():
        if data.get("is_outer_boundary"):
            nb = data.get("bounding_box")
            if nb and len(nb) == 4:
                return (_f(nb[0]), _f(nb[1]), _f(nb[2]), _f(nb[3]))
    return None


def _node_feature_row(
    data: dict,
    *,
    max_area: float,
    max_perimeter: float,
    width: float,
    height: float,
    panel_size: float,
    panel_bbox: tuple[float, float, float, float] | None,
) -> list[float]:
    """Build the 16-dim feature row for a single geometry node ``data`` dict."""
    geom_type = str(data.get("geometry_type", "")).lower()
    layer_type = str(data.get("inferred_layer_type", "")).lower()

    area = _f(data.get("area_mm2"))
    perimeter = _f(data.get("perimeter_mm"))
    diameter = _f(data.get("diameter_mm"))

    bbox = data.get("bounding_box")
    if bbox and len(bbox) == 4:
        w = abs(_f(bbox[2]) - _f(bbox[0]))
        h = abs(_f(bbox[3]) - _f(bbox[1]))
    else:
        w = h = 0.0

    centroid = data.get("centroid")
    if centroid and len(centroid) >= 2:
        cx, cy = _f(centroid[0]), _f(centroid[1])
    else:
        cx = cy = 0.0

    # [0] area normalized
    area_norm = area / max_area if max_area > 0.0 else 0.0
    # [1] perimeter normalized
    perim_norm = perimeter / max_perimeter if max_perimeter > 0.0 else 0.0
    # [2] aspect ratio (log-scaled w/h so 1.0 -> 0.0, symmetric about square)
    if w > 0.0 and h > 0.0:
        aspect = math.log10(w / h)
    else:
        aspect = 0.0
    aspect = max(-2.0, min(2.0, aspect))
    # [3] circularity = 4*pi*area / perimeter^2 (0..1)
    if perimeter > 0.0 and area > 0.0:
        circularity = (4.0 * math.pi * area) / (perimeter * perimeter)
    else:
        circularity = 0.0
    circularity = max(0.0, min(1.0, circularity))
    # [4] diameter normalized (circles only)
    if geom_type == "circle" and diameter > 0.0:
        diameter_norm = min(diameter / _DIAMETER_REF_MM, 2.0)
    else:
        diameter_norm = 0.0
    # [5] is_circle
    is_circle = 1.0 if geom_type == "circle" else 0.0
    # [6] is_closed
    is_closed = 1.0 if data.get("is_closed") else 0.0
    # [7] is_outer_boundary
    is_outer = 1.0 if data.get("is_outer_boundary") else 0.0
    # [8],[9] centroid normalized into panel frame
    if panel_bbox is not None:
        xmin, ymin, xmax, ymax = panel_bbox
        cx_norm = (cx - xmin) / width
        cy_norm = (cy - ymin) / height
    else:
        cx_norm = cx / width
        cy_norm = cy / height
    cx_norm = max(0.0, min(1.0, cx_norm))
    cy_norm = max(0.0, min(1.0, cy_norm))
    # [10..13] layer one-hot (exactly one is 1.0)
    layer_cut = 1.0 if layer_type in ("cut", "border") else 0.0
    layer_drill = 1.0 if layer_type == "drill" else 0.0
    layer_pocket = 1.0 if layer_type == "pocket" else 0.0
    layer_other = 1.0 if (layer_cut + layer_drill + layer_pocket) == 0.0 else 0.0
    # [14] contained-feature count, normalized
    contained = data.get("contains_node_ids") or []
    n_contained = min(len(contained) / _MAX_CONTAINED_REF, 1.0)
    # [15] distance to nearest panel edge, normalized by panel_size
    if panel_bbox is not None:
        xmin, ymin, xmax, ymax = panel_bbox
        edge_dist = min(cx - xmin, xmax - cx, cy - ymin, ymax - cy)
        dist_norm = max(0.0, edge_dist) / panel_size
    else:
        dist_norm = 0.0
    dist_norm = max(0.0, min(1.0, dist_norm))

    return [
        area_norm,
        perim_norm,
        aspect,
        circularity,
        diameter_norm,
        is_circle,
        is_closed,
        is_outer,
        cx_norm,
        cy_norm,
        layer_cut,
        layer_drill,
        layer_pocket,
        layer_other,
        n_contained,
        dist_norm,
    ]


def extract_node_features(
    mgg: ManufacturingGeometryGraph,
) -> tuple[list[str], np.ndarray]:
    """Extract per-geometry-node features from an MGG.

    Returns ``(node_ids, feature_matrix)`` where ``feature_matrix`` is a
    ``(N, 16)`` ``float32`` numpy array and ``node_ids[i]`` is the node ID of
    row ``i``. Geometry nodes are taken in MGG iteration order.

    Pure numpy — does NOT require torch. All values are finite and bounded.
    For an MGG with no geometry nodes, returns ``([], (0, 16) array)``.
    """
    nodes = list(mgg.geometry_nodes())
    node_ids = [nid for nid, _ in nodes]

    if not nodes:
        return node_ids, np.zeros((0, FEATURE_DIM), dtype=np.float32)

    # Panel-level normalizers.
    areas = [_f(d.get("area_mm2")) for _, d in nodes]
    perimeters = [_f(d.get("perimeter_mm")) for _, d in nodes]
    max_area = max(areas) if areas else 0.0
    max_perimeter = max(perimeters) if perimeters else 0.0

    width, height, panel_size, _diag = _panel_dimensions(mgg)
    panel_bbox = _panel_bbox(mgg)

    rows = [
        _node_feature_row(
            data,
            max_area=max_area,
            max_perimeter=max_perimeter,
            width=width,
            height=height,
            panel_size=panel_size,
            panel_bbox=panel_bbox,
        )
        for _nid, data in nodes
    ]

    matrix = np.asarray(rows, dtype=np.float32)
    # Defensive scrub: guarantee finiteness regardless of upstream surprises.
    matrix = np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)
    return node_ids, matrix
