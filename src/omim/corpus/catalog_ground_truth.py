"""Manufacturer catalog ground truth for OMIM corpus grounding.

These values are the AUTHORITATIVE reference distributions for real-world
cabinet / CNC manufacturing geometry. Every number here traces to a published
manufacturer catalog item or a DIN / EN standard — they are NOT heuristics or
guesses. They are the Tier 1 trust source against which any ingested real DXF
corpus is validated (see ``validator.validate_against_catalog``) and from which
the catalog-derived synthetic grounding profile is seeded
(see ``reference_profile``).

Sources (see docs/06_REAL_WORLD_GROUNDING; verified against live manufacturer
catalogs + standards, 2026):
  - Blum CLIP top hinge, item 70.1900.AC  -> HINGE_CUP_HOLE (35mm cup, 13mm bore)
  - Häfele System 32 / Rasterbohr          -> SHELF_PIN_HOLE
  - Häfele Confirmat / DIN 68871           -> CONFIRMAT_HOLE
  - DIN 68150 fluted furniture dowels      -> DOWEL_HOLE (6 / 8 / 10mm)
  - Häfele Minifix 15 cam fitting          -> CAM_HOLE (ø15.0mm x 12.5mm deep)
  - EN 312:2010 (particleboard) / EN 622-5 (MDF) -> panel thicknesses
  - Panel_Dimension_Standards.md           -> sheet / panel sizes, feature counts
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Per-feature catalog reference values (the ground truth for hole geometry)
# ---------------------------------------------------------------------------
#
# Each entry records the *nominal* diameter and the catalog tolerance band
# (``diameter_tol_mm`` is the +/- half-width). ``setback_mm`` / ``spacing_mm``
# are recorded where the catalog defines them; ``None`` means "not constrained
# by the catalog at the geometry level" (e.g. hinge pair spacing depends on door
# width). ``cluster_center_mm`` is the canonical diameter a measured hole is
# snapped to during distribution extraction.

CATALOG_REFERENCES: dict[str, dict[str, Any]] = {
    "SHELF_PIN_HOLE": {
        "description": "System 32 shelf support hole",
        "diameter_mm": 5.0,
        "diameter_tol_mm": 0.5,
        "depth_mm": 15.0,
        "depth_tol_mm": 1.0,
        "setback_mm": 37.0,          # row offset from panel edge
        "setback_tol_mm": 1.0,
        "spacing_mm": 32.0,          # 32 mm grid pitch (System 32)
        "spacing_tol_mm": 0.5,
        "cluster_center_mm": 5.0,
        "source": "Häfele System 32 / Rasterbohr; DIN 68840; "
                  "Cabinet_Standards.md 32mm system (MFG-005)",
    },
    "CONFIRMAT_HOLE": {
        "description": "Confirmat / Euro screw body bore",
        "diameter_mm": 7.0,
        "diameter_tol_mm": 0.2,
        "pilot_diameter_mm": 5.0,
        "pilot_tol_mm": 0.1,
        "depth_mm": 60.0,            # 50-70mm range, midpoint
        "depth_tol_mm": 10.0,
        "setback_mm": 12.0,          # "typically 8-15mm" edge spacing (soft band)
        "setback_tol_mm": 5.0,       # widened: catalog says "typically", not a hard limit
        "spacing_mm": None,
        "cluster_center_mm": 7.0,
        "source": "Häfele Confirmat; DIN 68871 (7mm body / 5mm pilot)",
    },
    "DOWEL_HOLE_LIGHT": {
        "description": "6mm fluted furniture dowel hole (common light-duty)",
        "diameter_mm": 6.0,          # 6mm is one of the two most-stocked sizes
        "diameter_tol_mm": 0.1,
        "depth_mm": 14.0,            # 6x30 dowel; ~half per side
        "depth_tol_mm": 2.0,
        "setback_mm": None,          # at joint position, not edge-referenced
        "setback_tol_mm": None,
        "spacing_mm": 32.0,          # typically on the 32mm system in flat-pack
        "spacing_tol_mm": 1.0,
        "cluster_center_mm": 6.0,
        "source": "DIN 68150 fluted furniture dowel (6mm x 30 most-stocked)",
    },
    "DOWEL_HOLE": {
        "description": "8mm fluted furniture dowel hole (standard construction)",
        "diameter_mm": 8.0,          # 8mm most common; 6mm light, 10mm heavy-duty
        "diameter_tol_mm": 0.1,
        "alt_diameters_mm": [6.0, 8.0, 10.0],
        "depth_mm": 17.0,            # ~thickness/2 per side; ~34mm total joint
        "depth_tol_mm": 2.0,
        "setback_mm": None,          # at joint position, not edge-referenced
        "setback_tol_mm": None,
        "spacing_mm": 32.0,          # typically on the 32mm system in flat-pack
        "spacing_tol_mm": 1.0,
        "cluster_center_mm": 8.0,
        "source": "DIN 68150 fluted furniture dowel (8mm x 40 most-stocked)",
    },
    "DOWEL_HOLE_HEAVY": {
        "description": "10mm fluted furniture dowel hole (heavy-duty)",
        "diameter_mm": 10.0,
        "diameter_tol_mm": 0.1,
        "depth_mm": 17.0,
        "depth_tol_mm": 2.0,
        "setback_mm": None,
        "setback_tol_mm": None,
        "spacing_mm": 32.0,
        "spacing_tol_mm": 1.0,
        "cluster_center_mm": 10.0,
        "source": "DIN 68150 fluted furniture dowel (10mm heavy-duty)",
    },
    "CAM_HOLE": {
        "description": "Minifix 15 cam-housing bore",
        "diameter_mm": 15.0,
        "diameter_tol_mm": 0.3,
        "depth_mm": 12.5,
        "depth_tol_mm": 0.5,
        "setback_mm": None,
        "setback_tol_mm": None,
        "spacing_mm": None,
        "cluster_center_mm": 15.0,
        # NOTE: this is the Häfele Minifix 15 cam housing (ø15.0mm x 12.5mm deep).
        # Previously mislabelled "Rafix" (a different, flat-housing fitting).
        "source": "Häfele Minifix 15 cam housing (ø15.0mm x 12.5mm deep)",
    },
    "HINGE_CUP_HOLE": {
        "description": "European concealed hinge cup bore",
        "diameter_mm": 35.0,
        "diameter_tol_mm": 0.5,
        "depth_mm": 13.0,            # Blum CLIP top published boring depth = 13mm
        "depth_tol_mm": 1.0,         # covers 11.5-13mm competitor/legacy cups
        "setback_mm": 22.5,          # cup-center to edge (= boring distance C 3-6mm
                                     # + 17.5mm cup radius); real range ~20.5-23.5
        "setback_tol_mm": 1.5,       # widened to span the real C=3-6mm range
        "spacing_mm": None,          # pair spacing varies by door width
        "cluster_center_mm": 35.0,
        "source": "Blum CLIP top BLUMOTION (35mm cup, 13mm boring depth); "
                  "Hettich Intermat; Grass Tiomos",
    },
}

# Canonical diameters that a measured hole diameter is clustered to (mm).
# Published catalog nominal bore sizes for the European 32mm cabinet system.
# 6mm is the light-duty fluted dowel; 15mm is the Minifix 15 cam bore.
KNOWN_FEATURE_DIAMETERS_MM: list[float] = [5.0, 6.0, 7.0, 8.0, 10.0, 15.0, 35.0]

# Diameter -> dominant feature class (for cluster labelling). Where a diameter
# is shared (e.g. nothing here), the most common cabinet feature wins.
DIAMETER_TO_FEATURE: dict[float, str] = {
    5.0: "SHELF_PIN_HOLE",
    6.0: "DOWEL_HOLE_LIGHT",
    7.0: "CONFIRMAT_HOLE",
    8.0: "DOWEL_HOLE",
    10.0: "DOWEL_HOLE_HEAVY",
    15.0: "CAM_HOLE",
    35.0: "HINGE_CUP_HOLE",
}


# ---------------------------------------------------------------------------
# Panel / sheet dimension ground truth (EN 309 / EN 622-5 + standards docs)
# ---------------------------------------------------------------------------

# EN 312:2010 (particleboard) + EN 622-5 (MDF) union of standard thicknesses (mm).
VALID_PANEL_THICKNESSES_MM: list[float] = [
    3.0, 4.0, 6.0, 8.0, 9.0, 10.0, 12.0, 15.0, 16.0,
    18.0, 19.0, 22.0, 25.0, 28.0, 30.0, 38.0,
]
DEFAULT_PANEL_THICKNESS_MM: float = 18.0
# Most common cabinet carcass/shelf thicknesses (used as distribution mode).
COMMON_PANEL_THICKNESSES_MM: list[float] = [16.0, 18.0, 19.0]

# Standard single-component panel dimension bounds (Panel_Dimension_Standards).
PANEL_DIMENSION_BOUNDS_MM: dict[str, float] = {
    "min_width_mm": 50.0,
    "max_width_mm": 1200.0,
    "min_height_mm": 50.0,
    "max_height_mm": 2400.0,
}

# Typical realistic component dimensions (used to seed the reference profile).
TYPICAL_WIDTHS_MM: list[float] = [300.0, 400.0, 450.0, 500.0, 600.0,
                                  800.0, 900.0, 1000.0, 1200.0]
TYPICAL_HEIGHTS_MM: list[float] = [300.0, 600.0, 720.0, 900.0,
                                   1980.0, 2100.0, 2200.0]

# Standard full sheet sizes (mm) — context for nesting, not single components.
STANDARD_SHEET_SIZES_MM: list[tuple[float, float]] = [
    (2800.0, 2070.0),   # European primary
    (3050.0, 1220.0),   # European narrow
    (2440.0, 1220.0),   # North American (8' x 4')
]

# MFG-008 nesting table limit (mm).
MAX_NESTING_TABLE_MM: tuple[float, float] = (3600.0, 2100.0)


# ---------------------------------------------------------------------------
# Feature-count expectations by panel type (Panel_Dimension_Standards table)
# ---------------------------------------------------------------------------
# (min_holes, max_holes) inclusive ranges of total drilled holes per panel.

FEATURE_COUNT_BY_PANEL_TYPE: dict[str, dict[str, Any]] = {
    "side_panel": {"hole_count": (8, 28), "typical": 14, "contours": 1},
    "shelf": {"hole_count": (0, 4), "typical": 2, "contours": 1},
    "door": {"hole_count": (2, 2), "typical": 2, "contours": 1},
    "bottom_top": {"hole_count": (4, 8), "typical": 6, "contours": 1},
    "back_panel": {"hole_count": (0, 0), "typical": 0, "contours": 1},
    "generic": {"hole_count": (0, 40), "typical": 8, "contours": 1},
}
# Maximum realistic hole count for any single standard cabinet panel.
MAX_REALISTIC_HOLE_COUNT: int = 40


# A measured diameter is only assigned to a catalog cluster when it lands
# within this band of a known bore size. Holes outside every band (e.g. a
# generic 19mm through-hole) are reported separately as "unclustered" rather
# than being force-snapped into the nearest catalog cluster — which would
# otherwise contaminate that cluster's mean during conformance checking.
#
# Kept at 1.0mm (> the per-feature diameter tolerance of ~0.5) so the validator
# still has a "clustered but off-spec" band: a 34mm hole snaps to the 35mm hinge
# cluster yet fails its ±0.5 check. Adjacent clusters (5/6/7/8mm, 1mm apart)
# resolve to the nearest center; an exact 6mm dowel snaps to 6.0 (the fix is
# that 6.0 is now a cluster at all — previously a 6mm hole mis-snapped to 5mm).
CLUSTER_TOLERANCE_MM: float = 1.0


def cluster_diameter(diameter_mm: float) -> tuple[float, float]:
    """Snap a measured diameter to the nearest known catalog diameter.

    Returns ``(cluster_center_mm, deviation_mm)`` where deviation is the signed
    distance from the measured value to the assigned cluster center.
    """
    nearest = min(KNOWN_FEATURE_DIAMETERS_MM, key=lambda c: abs(c - diameter_mm))
    return nearest, diameter_mm - nearest


def cluster_diameter_gated(
    diameter_mm: float, tolerance_mm: float = CLUSTER_TOLERANCE_MM
) -> tuple[float | None, float]:
    """Like :func:`cluster_diameter` but returns ``(None, deviation)`` when the
    measured diameter is outside *tolerance_mm* of every known catalog bore.
    """
    nearest, dev = cluster_diameter(diameter_mm)
    if abs(dev) > tolerance_mm:
        return None, dev
    return nearest, dev


def feature_for_diameter(diameter_mm: float) -> str:
    """Return the dominant feature class for a measured diameter."""
    center, _ = cluster_diameter(diameter_mm)
    return DIAMETER_TO_FEATURE.get(center, "UNKNOWN")


def reference_for_cluster(cluster_center_mm: float) -> dict[str, Any] | None:
    """Return the CATALOG_REFERENCES entry whose cluster center matches."""
    for ref in CATALOG_REFERENCES.values():
        if abs(ref["cluster_center_mm"] - cluster_center_mm) < 1e-6:
            return ref
    return None
