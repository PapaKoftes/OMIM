"""DXFWriter — render a generated panel + features to a DXF file via ezdxf.

Layer mapping follows the parser's layer conventions so the round-trip
(generate -> write -> parse -> build -> validate) preserves intent:

  hole feature classes        -> DRILL
  POCKET / GROOVE / DADO / ...-> POCKET
  PROFILE_CUT / INTERNAL_CUTOUT -> CUT

The panel outer boundary is always written as a closed LWPOLYLINE on the BORDER
layer so the parser detects it as the panel boundary (largest closed contour).
"""

from __future__ import annotations

from pathlib import Path

import ezdxf

from omim.synthetic.models import FeatureSpec, PanelSpec

BORDER_LAYER = "BORDER"

# Feature class -> DXF layer. Anything ending in _HOLE (and explicit hole types)
# maps to DRILL; milled features to POCKET; profile/cutout to CUT.
FEATURE_CLASS_TO_LAYER: dict[str, str] = {
    # Hole features -> DRILL
    "THROUGH_HOLE": "DRILL",
    "BLIND_HOLE": "DRILL",
    "SHELF_PIN_HOLE": "DRILL",
    "HINGE_CUP_HOLE": "DRILL",
    "CONFIRMAT_HOLE": "DRILL",
    "DOWEL_HOLE": "DRILL",
    "HARDWARE_HOLE": "DRILL",
    "COUNTERSINK": "DRILL",
    "COUNTERBORE": "DRILL",
    # Milled features -> POCKET
    "POCKET": "POCKET",
    "THROUGH_POCKET": "POCKET",
    "GROOVE": "POCKET",
    "DADO": "POCKET",
    "RABBET": "POCKET",
    "OPEN_SLOT": "POCKET",
    # Profile features -> CUT
    "PROFILE_CUT": "CUT",
    "INTERNAL_CUTOUT": "CUT",
}


def _layer_for_feature(feature: FeatureSpec) -> str:
    """Resolve the DXF layer for a feature (explicit map, then heuristic)."""
    if feature.feature_class in FEATURE_CLASS_TO_LAYER:
        return FEATURE_CLASS_TO_LAYER[feature.feature_class]
    # Heuristic fallbacks consistent with the maps above.
    if feature.feature_class.endswith("_HOLE"):
        return "DRILL"
    # Respect any explicit layer the generator set.
    return feature.layer or "DRILL"


class DXFWriter:
    """Write a generated panel + features into a DXF document."""

    def __init__(self, dxf_version: str = "AC1024") -> None:
        self.dxf_version = dxf_version

    def write_panel(
        self,
        panel: PanelSpec,
        features: list[FeatureSpec],
        output_path: str | Path,
    ) -> str:
        """Render *panel* and *features* to *output_path*; return the path str."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = ezdxf.new(self.dxf_version)
        doc.header["$INSUNITS"] = 4  # 4 == millimeters
        msp = doc.modelspace()

        # Ensure the layers we use exist (ezdxf auto-creates on use, but make
        # them explicit for cleanliness).
        for layer_name in {BORDER_LAYER, "CUT", "DRILL", "POCKET"}:
            if layer_name not in doc.layers:
                doc.layers.add(layer_name)

        # --- Panel boundary on BORDER layer (closed lwpolyline) ---
        boundary = [tuple(p) for p in panel.boundary_points]
        if boundary and boundary[0] == boundary[-1]:
            boundary = boundary[:-1]  # ezdxf 'close=True' re-closes it
        msp.add_lwpolyline(
            boundary,
            close=True,
            dxfattribs={"layer": BORDER_LAYER},
        )

        # --- Features ---
        for feature in features:
            # The panel's outer profile cut IS the BORDER boundary already drawn
            # above (per Constraint_Grammar: "the panel boundary is always the
            # outer profile cut"). Drawing it again on CUT would create a
            # duplicate outer rectangle that the parser/classifier then mistakes
            # for an INTERNAL_CUTOUT. The PROFILE_CUT FeatureSpec is retained for
            # ground-truth labels; it is simply not re-rendered as a second entity.
            if feature.feature_class == "PROFILE_CUT":
                continue

            layer = _layer_for_feature(feature)

            if feature.entity_type == "CIRCLE" and feature.center is not None:
                radius = feature.radius_mm or 0.0
                msp.add_circle(
                    center=(feature.center[0], feature.center[1]),
                    radius=radius,
                    dxfattribs={"layer": layer},
                )

            elif feature.entity_type == "LWPOLYLINE" and feature.points:
                pts = [(p[0], p[1]) for p in feature.points]
                # Respect the spec's open/closed intent. For closed contours,
                # drop a duplicated closing vertex and let ezdxf close it.
                if feature.is_closed and len(pts) > 1 and pts[0] == pts[-1]:
                    pts = pts[:-1]
                msp.add_lwpolyline(
                    pts,
                    close=bool(feature.is_closed),
                    dxfattribs={"layer": layer},
                )

        doc.saveas(str(output_path))
        return str(output_path)
