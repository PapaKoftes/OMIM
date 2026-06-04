"""Tests for part-type identification (omim.identify.parts).

Builds panels with distinctive feature signatures and asserts the part type.
Identification is read-only inference with confidence + provenance.
"""

from __future__ import annotations

from omim.graph.builder import MGGBuilder
from omim.identify import PART_TYPES, identify_part
from omim.identify.parts import identify_part as identify_part_fn
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry
from omim.semantic.classifier import FeatureClassifier


def _ent_poly(eid, coords, layer="CUT", inferred="cut"):
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    return RawEntity(
        entity_id=eid, ezdxf_handle=f"h{eid}", entity_type="LWPOLYLINE",
        layer=layer, inferred_layer_type=inferred, coordinates=coords, is_closed=True,
        bounding_box=[min(xs), min(ys), max(xs), max(ys)],
        centroid=[sum(xs) / len(xs), sum(ys) / len(ys)],
        area_mm2=abs((max(xs) - min(xs)) * (max(ys) - min(ys))),
        perimeter_mm=2 * ((max(xs) - min(xs)) + (max(ys) - min(ys))),
    )


def _ent_circle(eid, cx, cy, dia, layer="DRILL", inferred="drill"):
    r = dia / 2.0
    return RawEntity(
        entity_id=eid, ezdxf_handle=f"h{eid}", entity_type="CIRCLE",
        layer=layer, inferred_layer_type=inferred, coordinates=[cx, cy, r],
        is_closed=True, bounding_box=[cx - r, cy - r, cx + r, cy + r],
        centroid=[cx, cy], area_mm2=3.14159 * r * r, perimeter_mm=2 * 3.14159 * r,
        diameter_mm=float(dia), radius_mm=float(r),
    )


def _build(entities, w, h):
    boundary = [[0, 0], [w, 0], [w, h], [0, h]]
    panel = _ent_poly("P", boundary)
    raw = RawGeometry(
        source_file="t.dxf", source_file_hash="sha256:t", dxf_version="AC1027",
        entities=[panel, *entities],
        panel_boundary=PanelBoundary(
            entity_id="P", coordinates=boundary, bounding_box=[0, 0, w, h],
            area_mm2=w * h, inferred=False,
        ),
        panel_boundary_inferred=False, entity_counts={},
    )
    return MGGBuilder().build(raw)


def _identify(mgg):
    ann = FeatureClassifier().classify(mgg)
    return identify_part(mgg, ann)


def test_door_from_hinge_cups():
    """A 400x600 panel with two 35mm hinge cups near an edge -> DOOR."""
    holes = [
        _ent_circle("hc1", 22.5, 100, 35.0, layer="HINGE"),
        _ent_circle("hc2", 22.5, 500, 35.0, layer="HINGE"),
    ]
    mgg = _build(holes, 400, 600)
    pid = _identify(mgg)
    assert pid.part_type == "DOOR"
    assert pid.confidence >= 0.75
    assert pid.provenance["inference_method"] == "heuristic"


def test_side_panel_from_shelf_pin_column():
    """A tall panel with a 32mm shelf-pin column + confirmat edge holes -> SIDE_PANEL."""
    holes = [_ent_circle(f"sp{i}", 37, 100 + 32 * i, 5.0) for i in range(6)]
    holes.append(_ent_circle("cf1", 300, 50, 7.0))  # confirmat edge joinery
    mgg = _build(holes, 600, 800)
    pid = _identify(mgg)
    assert pid.part_type == "SIDE_PANEL"
    assert "shelf-pin" in pid.evidence[1]["reason"]


def test_unknown_when_no_signals():
    """A blank panel with no features -> UNKNOWN_PART (honest, not guessed)."""
    mgg = _build([], 300, 300)
    pid = _identify(mgg)
    assert pid.part_type == "UNKNOWN_PART"
    assert pid.confidence == 0.0


def test_part_type_is_in_taxonomy():
    mgg = _build([_ent_circle("hc", 22.5, 100, 35.0, layer="HINGE")], 400, 600)
    pid = _identify(mgg)
    assert pid.part_type in PART_TYPES


def test_alternatives_ranked_descending():
    """When multiple signals fire, alternatives are sorted by confidence."""
    # Shelf-pin column (SIDE) + a hardware hole (weak DRAWER_FRONT signal).
    holes = [_ent_circle(f"sp{i}", 37, 100 + 32 * i, 5.0) for i in range(6)]
    holes.append(_ent_circle("hw", 300, 400, 25.0, layer="CUT", inferred="cut"))
    mgg = _build(holes, 600, 800)
    pid = _identify(mgg)
    confs = [a["confidence"] for a in pid.alternatives]
    assert confs == sorted(confs, reverse=True)


def test_params_override_threshold():
    """Raising shelf_pin_min suppresses the SIDE_PANEL call (config-tunable)."""
    holes = [_ent_circle(f"sp{i}", 37, 100 + 32 * i, 5.0) for i in range(6)]
    mgg = _build(holes, 600, 800)
    ann = FeatureClassifier().classify(mgg)
    pid = identify_part_fn(mgg, ann, shelf_pin_min_for_side=99)
    assert pid.part_type != "SIDE_PANEL"
