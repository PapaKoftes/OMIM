"""Depth / 2.5D extraction for DXF entities.

A flat 2D DXF does **not** contain machining depth — depth is the Z dimension and
is simply absent from a top-down face drawing. OMIM therefore recovers depth from
three real, separable sources, each with its own trust level (recorded as
``depth_source`` so downstream consumers never confuse a measured value with an
inferred one):

1. ``z_elevation`` — TRUE 2.5D geometry. The entity carries a non-zero Z/elevation
   (a pocket bottom drawn below the top face). Depth = reference_plane_z - entity_z.
   This is a real measurement, the highest-trust source.
2. ``layer_name`` — a depth encoded in the layer name by shop convention, e.g.
   ``POCKET_6MM``, ``GROOVE_D6``, ``ENGRAVE_1.5``. Heuristic but common.
3. (panel thickness) — ``PANEL_18MM`` / ``THK18`` style tokens give the *stock
   thickness*, not a feature depth; surfaced separately via :func:`parse_thickness_from_layer`.

Nothing here invents data: if no source is present, depth stays ``None`` and the
caller (e.g. MFG-007) skips rather than guessing.
"""

from __future__ import annotations

import re

# A dimension immediately followed by a mm marker, e.g. "6MM", "6 mm", "12.5MM".
_MM_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*MM\b", re.IGNORECASE)
# Explicit depth markers: D6, D=6, DEPTH6, DEPTH_6, DP6, DEEP6. The marker is
# preceded by a non-letter (start, underscore, space, etc.) — NOT \b, because
# "_D" has no word boundary (underscore is a word char) yet is the common case.
_DEPTH_RE = re.compile(
    r"(?<![A-Za-z])(?:DEPTH|DEEP|DP|D)[\s_=:-]*(\d{1,3}(?:\.\d+)?)\b", re.IGNORECASE
)
# Explicit thickness markers: T18, THK18, THICK18, S18 (German Stärke), ST18.
_THICK_RE = re.compile(
    r"(?<![A-Za-z])(?:THICKNESS|THICK|THK|STAERKE|STARKE|ST|S|T)[\s_=:-]*"
    r"(\d{1,3}(?:\.\d+)?)\b",
    re.IGNORECASE,
)

# Plausible physical bounds (mm) to reject spurious matches (e.g. layer "LAYER2").
_MIN_DEPTH_MM = 0.1
_MAX_DEPTH_MM = 100.0
_MIN_THICK_MM = 3.0
_MAX_THICK_MM = 80.0

# Layer types for which a layer-name dimension means *feature depth*.
_DEPTH_LAYER_TYPES = {"pocket", "engrave", "drill"}


def _first_match(pattern: re.Pattern[str], text: str, lo: float, hi: float) -> float | None:
    for m in pattern.finditer(text):
        try:
            val = float(m.group(1))
        except (TypeError, ValueError):
            continue
        if lo <= val <= hi:
            return val
    return None


def parse_depth_from_layer(layer_name: str, inferred_layer_type: str | None = None) -> float | None:
    """Extract a feature *depth* (mm) encoded in a layer name, or ``None``.

    Recognises ``..._6MM``, ``..._D6``, ``DEPTH_6`` style tokens. When
    *inferred_layer_type* is given, a bare ``NMM`` token is only treated as depth
    for depth-bearing layer types (pocket/engrave/drill) so that ``PANEL_18MM`` is
    not misread as an 18 mm-deep feature. Explicit ``D``/``DEPTH`` markers are
    honoured regardless of layer type.
    """
    if not layer_name:
        return None
    # Explicit depth marker wins (unambiguous).
    explicit = _first_match(_DEPTH_RE, layer_name, _MIN_DEPTH_MM, _MAX_DEPTH_MM)
    if explicit is not None:
        return explicit
    # Bare "NMM" token: only count as depth on a depth-bearing layer.
    if inferred_layer_type is None or inferred_layer_type in _DEPTH_LAYER_TYPES:
        return _first_match(_MM_RE, layer_name, _MIN_DEPTH_MM, _MAX_DEPTH_MM)
    return None


def parse_thickness_from_layer(layer_name: str) -> float | None:
    """Extract a panel *thickness* (mm) from a layer name, or ``None``.

    Recognises ``PANEL_18MM``, ``THK18``, ``T18``, ``S18`` (Stärke). Bounded to a
    plausible panel range so an arbitrary number is not mistaken for thickness.
    """
    if not layer_name:
        return None
    explicit = _first_match(_THICK_RE, layer_name, _MIN_THICK_MM, _MAX_THICK_MM)
    if explicit is not None:
        return explicit
    return _first_match(_MM_RE, layer_name, _MIN_THICK_MM, _MAX_THICK_MM)


def resolve_panel_thickness(
    layers: list[str],
    z_values: list[float] | None = None,
) -> tuple[float | None, str | None]:
    """Resolve a panel's STOCK thickness (mm) and its provenance source.

    This is the panel's material thickness — NOT a feature depth. It is recovered,
    in precedence order:
      1. ``z_extent`` — a true 2.5D solid spans a Z range; thickness = max-min Z.
      2. ``layer_name`` — a thickness convention on any layer (PANEL_18MM/THK18).
    Returns ``(None, None)`` when a flat 2D DXF carries no thickness cue — the
    value is never guessed.
    """
    # 1. 2.5D Z extent (a genuine measurement when present).
    if z_values:
        zs = [z for z in z_values if z is not None]
        if zs:
            extent = max(zs) - min(zs)
            if _MIN_THICK_MM <= extent <= _MAX_THICK_MM:
                return round(extent, 3), "z_extent"
    # 2. Layer-name convention (first plausible match wins, deterministic order).
    for layer in layers:
        t = parse_thickness_from_layer(layer)
        if t is not None:
            return t, "layer_name"
    return None, None


def depth_from_elevation(
    entity_z: float | None, reference_plane_z: float
) -> float | None:
    """Depth (mm) of a feature whose geometry sits at *entity_z*, given the
    top-face *reference_plane_z*.

    Returns a positive depth when the entity is below the reference plane, ``0.0``
    when it is on it, and ``None`` when *entity_z* is unknown. (A feature above the
    reference plane returns ``None`` — that is not a machining depth.)
    """
    if entity_z is None:
        return None
    depth = reference_plane_z - float(entity_z)
    if depth < 0:
        return None
    return round(depth, 6)


def resolve_depth(
    *,
    layer_name: str,
    inferred_layer_type: str | None,
    entity_z: float | None,
    reference_plane_z: float | None,
) -> tuple[float | None, str | None]:
    """Resolve a single entity's depth and its provenance source.

    Precedence: a real Z elevation (2.5D) beats a layer-name convention, because a
    measured value is more trustworthy than an inferred one. Returns
    ``(depth_mm, depth_source)`` where ``depth_source`` is ``"z_elevation"``,
    ``"layer_name"``, or ``None`` when no depth could be recovered.
    """
    # 1. True 2.5D elevation (only meaningful when a reference plane exists and the
    #    entity actually sits off it).
    if entity_z is not None and reference_plane_z is not None:
        d = depth_from_elevation(entity_z, reference_plane_z)
        if d is not None and d > 1e-6:
            return d, "z_elevation"
    # 2. Layer-name convention.
    d = parse_depth_from_layer(layer_name, inferred_layer_type)
    if d is not None:
        return d, "layer_name"
    return None, None
