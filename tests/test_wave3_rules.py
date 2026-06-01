"""Wave 3: real MFG-003 / MFG-004 implementations + expanded classifier coverage.

These rules were previously pass-only placeholders. MFG-004 now computes the real
maximum-inscribed-circle width; MFG-003 detects sharp internal corners. The
classifier now emits HARDWARE_HOLE and GROOVE (both 2D-detectable, verifiable).
"""

from __future__ import annotations

from omim.graph.builder import MGGBuilder
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry
from omim.semantic.classifier import FeatureClassifier
from omim.validation.manufacturing_rules import check_pocket_width, check_tool_radius_corner


def _poly(eid, coords, layer="POCKET", inferred="pocket", approximated=False):
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return RawEntity(
        entity_id=eid, ezdxf_handle=f"h{eid}", entity_type="LWPOLYLINE",
        layer=layer, inferred_layer_type=inferred, coordinates=coords,
        is_closed=True, bounding_box=[min(xs), min(ys), max(xs), max(ys)],
        centroid=[sum(xs) / len(xs), sum(ys) / len(ys)],
        area_mm2=1000.0, perimeter_mm=200.0, is_approximated=approximated,
    )


def _circle(eid, cx, cy, dia, layer="DRILL", inferred="drill"):
    r = dia / 2.0
    return RawEntity(
        entity_id=eid, ezdxf_handle=f"h{eid}", entity_type="CIRCLE",
        layer=layer, inferred_layer_type=inferred, coordinates=[cx, cy, r],
        is_closed=True, bounding_box=[cx - r, cy - r, cx + r, cy + r],
        centroid=[cx, cy], area_mm2=3.14159 * r * r, perimeter_mm=2 * 3.14159 * r,
        diameter_mm=float(dia), radius_mm=float(r),
    )


def _build(entities, boundary_coords):
    xs = [p[0] for p in boundary_coords]
    ys = [p[1] for p in boundary_coords]
    bbox = [min(xs), min(ys), max(xs), max(ys)]
    raw = RawGeometry(
        source_file="t.dxf", source_file_hash="sha256:t", dxf_version="AC1027",
        entities=entities,
        panel_boundary=PanelBoundary(
            entity_id=entities[0].entity_id, coordinates=boundary_coords,
            bounding_box=bbox, area_mm2=(bbox[2] - bbox[0]) * (bbox[3] - bbox[1]),
            inferred=False,
        ),
        panel_boundary_inferred=False, entity_counts={},
    )
    return MGGBuilder().build(raw)


# ---------------------------------------------------------------------------
# MFG-004 pocket width (real inscribed-circle computation)
# ---------------------------------------------------------------------------


def test_mfg004_flags_narrow_pocket():
    """A 4mm-wide slot pocket cannot admit a 6mm tool (min 7.2mm) -> WARNING."""
    boundary = [[0, 0], [300, 0], [300, 300], [0, 300]]
    narrow = [[100, 100], [200, 100], [200, 104], [100, 104]]  # 4mm wide
    mgg = _build([_poly("1", boundary, layer="CUT", inferred="cut"),
                  _poly("2", narrow)], boundary)
    results = check_pocket_width(mgg)
    failed = [r for r in results if not r.passed]
    assert failed and failed[0].severity == "WARNING"
    assert failed[0].measured_value < 7.2


def test_mfg004_passes_wide_pocket():
    """A 40x40mm pocket easily admits the tool -> PASS."""
    boundary = [[0, 0], [300, 0], [300, 300], [0, 300]]
    wide = [[100, 100], [140, 100], [140, 140], [100, 140]]
    mgg = _build([_poly("1", boundary, layer="CUT", inferred="cut"),
                  _poly("2", wide)], boundary)
    results = check_pocket_width(mgg)
    assert all(r.passed for r in results)


# ---------------------------------------------------------------------------
# MFG-003 tool radius corner (real corner-angle analysis)
# ---------------------------------------------------------------------------


def test_mfg003_flags_sharp_internal_corner():
    """An arrow/chevron pocket with an acute concave notch -> WARNING.

    The notch vertex turns into the pocket interior at ~71 deg, sharper than the
    90 deg a round router bit can cut to a point.
    """
    boundary = [[0, 0], [300, 0], [300, 300], [0, 300]]
    arrow = [[100, 100], [200, 100], [200, 200], [150, 130], [100, 200]]
    mgg = _build([_poly("1", boundary, layer="CUT", inferred="cut"),
                  _poly("2", arrow)], boundary)
    results = check_tool_radius_corner(mgg)
    failed = [r for r in results if not r.passed]
    assert failed, "expected a sharp-corner warning"
    assert failed[0].severity == "WARNING"


def test_mfg003_passes_rectangular_pocket():
    """A plain rectangle has only 90-degree corners -> PASS (no sharp corners)."""
    boundary = [[0, 0], [300, 0], [300, 300], [0, 300]]
    rect = [[100, 100], [160, 100], [160, 160], [100, 160]]
    mgg = _build([_poly("1", boundary, layer="CUT", inferred="cut"),
                  _poly("2", rect)], boundary)
    results = check_tool_radius_corner(mgg)
    assert all(r.passed for r in results)


def test_mfg003_skips_approximated_polyline():
    """Bulge-flattened polylines are skipped (their chords would false-positive)."""
    boundary = [[0, 0], [300, 0], [300, 300], [0, 300]]
    arrow = [[100, 100], [200, 100], [200, 200], [150, 130], [100, 200]]
    mgg = _build([_poly("1", boundary, layer="CUT", inferred="cut"),
                  _poly("2", arrow, approximated=True)], boundary)
    results = check_tool_radius_corner(mgg)
    assert all(r.passed for r in results)


# ---------------------------------------------------------------------------
# Classifier expansion: HARDWARE_HOLE + GROOVE
# ---------------------------------------------------------------------------


def _classify(entities, boundary):
    mgg = _build(entities, boundary)
    ann = FeatureClassifier().classify(mgg)
    return {tuple(a.node_id): a for a in ann.feature_annotations}, ann


def test_classifier_emits_hardware_hole():
    """A 30mm circle on a drill layer -> HARDWARE_HOLE (was UNKNOWN before)."""
    boundary = [[0, 0], [400, 0], [400, 400], [0, 400]]
    mgg = _build([_poly("1", boundary, layer="CUT", inferred="cut"),
                  _circle("2", 200, 200, 30.0)], boundary)
    ann = FeatureClassifier().classify(mgg)
    classes = {a.feature_class for a in ann.feature_annotations}
    assert "HARDWARE_HOLE" in classes


def test_classifier_emits_groove():
    """A long narrow closed pocket polyline -> GROOVE (aspect ratio >= 5)."""
    boundary = [[0, 0], [400, 0], [400, 400], [0, 400]]
    # 100mm x 8mm channel: aspect ratio 12.5.
    groove = [[50, 200], [150, 200], [150, 208], [50, 208]]
    mgg = _build([_poly("1", boundary, layer="CUT", inferred="cut"),
                  _poly("2", groove, layer="POCKET", inferred="pocket")], boundary)
    ann = FeatureClassifier().classify(mgg)
    classes = {a.feature_class for a in ann.feature_annotations}
    assert "GROOVE" in classes


def test_classifier_square_pocket_still_pocket_not_groove():
    """A square pocket stays POCKET (aspect ratio ~1, below groove threshold)."""
    boundary = [[0, 0], [400, 0], [400, 400], [0, 400]]
    square = [[100, 100], [140, 100], [140, 140], [100, 140]]
    mgg = _build([_poly("1", boundary, layer="CUT", inferred="cut"),
                  _poly("2", square, layer="POCKET", inferred="pocket")], boundary)
    ann = FeatureClassifier().classify(mgg)
    by_id = {a.node_id: a for a in ann.feature_annotations}
    pocket = by_id.get("geom-2")
    assert pocket is not None and pocket.feature_class == "POCKET"
