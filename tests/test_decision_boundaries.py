"""Independent decision-boundary tests (de-circularization).

The headline grounding claim — "generate panels from the catalog, then validate
them against the same catalog" — is circular: it only proves the round-trip is
lossless, not that the rules/classifier decide correctly. These tests instead
build geometry BY HAND at deliberately chosen values straddling each decision
boundary (on-spec vs just-off-spec), with NO dependence on the synthetic
generator or the catalog constants, and assert the boundary lands where the
manufacturing standard says it should.

If a future edit silently moves a threshold, these tests fail — which a
generate-from-catalog/validate-against-catalog test never could.
"""

from __future__ import annotations

import pytest

from omim.graph.builder import MGGBuilder
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry
from omim.semantic.classifier import FeatureClassifier
from omim.validation.rule_engine import RuleEngine


def _build(circles=(), polys=(), panel=((0, 0), (600, 0), (600, 600), (0, 600))):
    panel = [list(p) for p in panel]
    pw = abs(panel[2][0] - panel[0][0])
    ph = abs(panel[2][1] - panel[0][1])
    ents = [RawEntity(
        entity_id="P", ezdxf_handle="P", entity_type="LWPOLYLINE",
        layer="CUT", inferred_layer_type="cut", coordinates=panel, is_closed=True,
        bounding_box=[panel[0][0], panel[0][1], panel[2][0], panel[2][1]],
        centroid=[(panel[0][0] + panel[2][0]) / 2, (panel[0][1] + panel[2][1]) / 2],
        area_mm2=pw * ph,
        perimeter_mm=2 * (pw + ph),
    )]
    for i, (cx, cy, dia, layer) in enumerate(circles):
        r = dia / 2.0
        ents.append(RawEntity(
            entity_id=f"c{i}", ezdxf_handle=f"c{i}", entity_type="CIRCLE",
            layer=layer, inferred_layer_type="drill", coordinates=[cx, cy, r],
            is_closed=True, bounding_box=[cx - r, cy - r, cx + r, cy + r],
            centroid=[cx, cy], area_mm2=3.14159 * r * r, perimeter_mm=2 * 3.14159 * r,
            diameter_mm=float(dia), radius_mm=float(r),
        ))
    raw = RawGeometry(
        source_file="t.dxf", source_file_hash="sha256:t", dxf_version="AC1027",
        entities=ents,
        panel_boundary=PanelBoundary(
            entity_id="P", coordinates=panel,
            bounding_box=[panel[0][0], panel[0][1], panel[2][0], panel[2][1]],
            area_mm2=ents[0].area_mm2, inferred=False,
        ),
        panel_boundary_inferred=False, entity_counts={},
    )
    return MGGBuilder().build(raw)


def _classify(mgg):
    ann = FeatureClassifier().classify(mgg)
    return {a.node_id: a for a in ann.feature_annotations}


# ---------------------------------------------------------------------------
# MFG-011 drill-diameter range: standard says [3.0, 40.0] mm.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dia,should_pass", [
    (2.9, False),   # just below the 3mm floor -> ERROR
    (3.1, True),    # just inside -> OK
    (39.5, True),   # just inside the 40mm ceiling -> OK
    (41.0, False),  # just above -> ERROR
])
def test_mfg011_drill_diameter_boundary(dia, should_pass):
    mgg = _build(circles=[(300, 300, dia, "DRILL")])
    rep = RuleEngine().validate(mgg, annotate_graph=False)
    mfg011 = [r for r in rep.layer2_results if r.rule_id == "MFG-011"]
    assert mfg011
    passed = all(r.passed for r in mfg011)
    assert passed == should_pass, f"dia={dia} expected pass={should_pass}"


# ---------------------------------------------------------------------------
# Hinge-cup classification: Blum standard is 35mm. A 35.0 hole near a 22.5mm
# edge is a HINGE_CUP_HOLE; a 30mm hole is NOT (independent of the generator).
# ---------------------------------------------------------------------------


def test_hinge_cup_diameter_boundary():
    # 35mm hole 22.5mm from the left edge -> HINGE_CUP_HOLE (Blum pattern).
    on_spec = _build(circles=[(22.5, 300, 35.0, "DRILL")])
    a = _classify(on_spec)["geom-c0"]
    assert a.feature_class == "HINGE_CUP_HOLE"

    # 30mm hole at the same position is off-spec -> must NOT be a hinge cup.
    off_spec = _build(circles=[(22.5, 300, 30.0, "DRILL")])
    b = _classify(off_spec)["geom-c0"]
    assert b.feature_class != "HINGE_CUP_HOLE"


# ---------------------------------------------------------------------------
# Shelf-pin: 5mm holes on a 32mm grid. Build the grid by hand (not via the
# generator) and confirm the 32mm spacing is recognised vs an off-grid spacing.
# ---------------------------------------------------------------------------


def test_shelf_pin_grid_boundary():
    # Three 5mm holes exactly 32mm apart -> recognised shelf-pin grid (MFG-005 OK).
    on_grid = _build(circles=[
        (100, 100, 5.0, "DRILL"), (100, 132, 5.0, "DRILL"), (100, 164, 5.0, "DRILL"),
    ])
    rep = RuleEngine().validate(on_grid, annotate_graph=False)
    mfg005 = [r for r in rep.layer2_results if r.rule_id == "MFG-005"]
    assert mfg005 and all(r.passed for r in mfg005), "32mm grid should pass MFG-005"

    # Same holes at 35mm spacing -> off the 32mm grid -> WARNING.
    off_grid = _build(circles=[
        (100, 100, 5.0, "DRILL"), (100, 135, 5.0, "DRILL"), (100, 170, 5.0, "DRILL"),
    ])
    rep2 = RuleEngine().validate(off_grid, annotate_graph=False)
    mfg005b = [r for r in rep2.layer2_results if r.rule_id == "MFG-005"]
    assert any(not r.passed for r in mfg005b), "35mm spacing should warn on MFG-005"


# ---------------------------------------------------------------------------
# Confirmat 7mm body: an exact 7mm hole classifies as CONFIRMAT_HOLE; a 5mm
# hole (shelf pin) does not. Independent of the generator's sampling.
# ---------------------------------------------------------------------------


def test_confirmat_vs_shelf_pin_diameter():
    confirmat = _build(circles=[(300, 300, 7.0, "DRILL")])
    a = _classify(confirmat)["geom-c0"]
    assert a.feature_class == "CONFIRMAT_HOLE"

    shelf = _build(circles=[(300, 300, 5.0, "DRILL")])
    b = _classify(shelf)["geom-c0"]
    assert b.feature_class != "CONFIRMAT_HOLE"
