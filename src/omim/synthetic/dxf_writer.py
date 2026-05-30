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

from collections import OrderedDict
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

        # --- DXF byte-reproducibility --------------------------------------
        # ezdxf otherwise stamps each saved file at save time with random
        # header GUIDs ($FINGERPRINTGUID/$VERSIONGUID), wall-clock create/
        # update timestamps ($TDCREATE/$TDUPDATE/...), and an "ezdxf <version>
        # @ <now>" marker string in the AppData dictionary. That makes
        # identical geometry produce different bytes -> a different
        # source_file_hash on every run. ezdxf exposes a single switch that
        # pins ALL of these to fixed constants (CONST_GUID, the year-2000
        # julian date, and a constant marker string); see
        # ezdxf.document._update_metadata / ezdxf_marker_string. We set it for
        # the duration of the save so identical (panel, features) input ->
        # byte-identical .dxf output. The entity-add order below is already
        # deterministic, so handles are stable too.
        prev_fixed_meta = ezdxf.options.write_fixed_meta_data_for_testing
        ezdxf.options.write_fixed_meta_data_for_testing = True
        try:
            return self._write_panel(doc_version=self.dxf_version, panel=panel,
                                     features=features, output_path=output_path)
        finally:
            ezdxf.options.write_fixed_meta_data_for_testing = prev_fixed_meta

    def _write_panel(
        self,
        doc_version: str,
        panel: PanelSpec,
        features: list[FeatureSpec],
        output_path: Path,
    ) -> str:
        doc = ezdxf.new(doc_version)
        doc.header["$INSUNITS"] = 4  # 4 == millimeters
        msp = doc.modelspace()

        # Ensure the layers we use exist (ezdxf auto-creates on use, but make
        # them explicit for cleanliness).
        for layer_name in [BORDER_LAYER, "CUT", "DRILL", "POCKET"]:
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

        # ezdxf decides which extra CLASS definitions to emit by iterating
        # ``entitydb.dxf_types_in_use()`` (a *set* of strings) at save time and
        # appending them in set-iteration order. That order is
        # PYTHONHASHSEED-dependent, so two separate `omim generate` processes
        # emit the CLASSES section in different orders -> different bytes.
        #
        # ``add_class`` keeps already-registered classes in their existing
        # position, so we pre-register every required class HERE in a canonical
        # (sorted) order. When ezdxf re-runs ``add_required_classes`` during
        # ``saveas`` the set-order appends all hit existing keys and become
        # no-ops, leaving the CLASSES section deterministic. We then sort the
        # backing OrderedDict for good measure.
        classes_section = doc.classes
        classes_section.add_required_classes(self.dxf_version)
        for dxftype in sorted(doc.entitydb.dxf_types_in_use()):
            classes_section.add_class(dxftype)
        classes_section.classes = OrderedDict(
            sorted(classes_section.classes.items(), key=lambda kv: kv[0])
        )

        doc.saveas(str(output_path))
        return str(output_path)
