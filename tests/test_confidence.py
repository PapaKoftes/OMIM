"""Graded-confidence tests for the semantic classifier.

These tests pin the FIX for the audit finding that the classifier assigned a
hardcoded confidence (e.g. 0.80) to ANY circle on a drill layer regardless of
diameter. Confidence is now a *reflection of match quality*:

  * an exact-diameter hole scores higher than an off-spec one,
  * a diameter outside the manufacturable drill window (50mm too big, 2mm too
    small) does NOT get a confident standard-feature label,
  * deterministic / boundary cases are unaffected.

Geometry is built directly from RawEntity (no DXF fixtures ship in the repo),
matching tests/test_acceptance.py.
"""

from __future__ import annotations

import pytest

from omim.graph.builder import MGGBuilder
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry
from omim.semantic.calibration import (
    CONFIDENCE_THRESHOLDS,
    compute_hole_classification_confidence,
)
from omim.semantic.classifier import FeatureClassifier

ACCEPT = CONFIDENCE_THRESHOLDS["accept"]  # 0.60


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _panel_entity(pts, bbox) -> RawEntity:
    return RawEntity(
        entity_id="1", ezdxf_handle="h1", entity_type="LWPOLYLINE",
        layer="cut", inferred_layer_type="cut", coordinates=pts,
        is_closed=True, bounding_box=bbox,
        centroid=[(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
        area_mm2=(bbox[2] - bbox[0]) * (bbox[3] - bbox[1]),
        perimeter_mm=2 * ((bbox[2] - bbox[0]) + (bbox[3] - bbox[1])),
    )


def _circle(eid, cx, cy, diameter, layer="drill", inferred="drill") -> RawEntity:
    r = diameter / 2.0
    return RawEntity(
        entity_id=eid, ezdxf_handle=f"h{eid}", entity_type="CIRCLE",
        layer=layer, inferred_layer_type=inferred,
        coordinates=[cx, cy, r], is_closed=True,
        bounding_box=[cx - r, cy - r, cx + r, cy + r], centroid=[cx, cy],
        area_mm2=3.14159 * r * r, perimeter_mm=2 * 3.14159 * r,
        diameter_mm=float(diameter), radius_mm=float(r),
    )


def _build(entities, bbox=(0, 0, 400, 400)):
    pts = [[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]]]
    raw = RawGeometry(
        source_file="t.dxf", source_file_hash="sha256:t", dxf_version="AC1027",
        entities=entities,
        panel_boundary=PanelBoundary(
            entity_id=entities[0].entity_id, coordinates=pts,
            bounding_box=list(bbox), area_mm2=1.0, inferred=False,
        ),
        panel_boundary_inferred=False, entity_counts={},
    )
    return MGGBuilder().build(raw)


def _annotate(entities, bbox=(0, 0, 400, 400)):
    """Classify and return a dict keyed by (cx, cy) -> FeatureAnnotation."""
    mgg = _build(entities, bbox)
    anns = FeatureClassifier().classify(mgg)
    centroid_of = {nid: data.get("centroid") for nid, data in mgg.geometry_nodes()}
    out = {}
    for a in anns.feature_annotations:
        c = centroid_of.get(a.node_id)
        key = (round(c[0], 1), round(c[1], 1)) if c else a.node_id
        out[key] = a
    return out


# ---------------------------------------------------------------------------
# Pure-function grading (the unit-level contract)
# ---------------------------------------------------------------------------


class TestGradedConfidenceFunction:
    def test_exact_match_beats_offspec(self):
        exact = compute_hole_classification_confidence(5.0, 5.0, 0.5, True, True, 0.95)
        offspec = compute_hole_classification_confidence(5.4, 5.0, 0.5, True, True, 0.95)
        assert exact > offspec
        assert exact == pytest.approx(0.95)

    def test_beyond_tolerance_is_low(self):
        # 7mm against a 5mm/0.5 expectation: distance 2 >> tol -> base 0.
        c = compute_hole_classification_confidence(7.0, 5.0, 0.5, False, False, 0.95)
        assert c == pytest.approx(0.0)

    def test_ceiling_is_respected(self):
        # Even an exact match cannot exceed the rule-type ceiling.
        c = compute_hole_classification_confidence(8.0, 8.0, 0.2, True, True, 0.70)
        assert c == pytest.approx(0.70)


# ---------------------------------------------------------------------------
# End-to-end classifier grading
# ---------------------------------------------------------------------------


class TestClassifierGrading:
    def test_5mm_beats_5_4mm_shelfpin(self):
        """A clean 5.0mm shelf-pin scores higher confidence than a 5.4mm hole."""
        # Two 32mm grid columns so both are confirmed-pattern shelf pins.
        good = [_panel_entity(
            [[0, 0], [400, 0], [400, 400], [0, 400]], [0, 0, 400, 400])]
        for i in range(4):
            good.append(_circle(f"g{i}", 37, 100 + i * 32, 5.0))
        ann_good = _annotate(good)
        c_good = ann_good[(37.0, 100.0)].confidence

        off = [_panel_entity(
            [[0, 0], [400, 0], [400, 400], [0, 400]], [0, 0, 400, 400])]
        for i in range(4):
            off.append(_circle(f"o{i}", 37, 100 + i * 32, 5.4))
        ann_off = _annotate(off)
        c_off = ann_off[(37.0, 100.0)].confidence

        assert c_good > c_off, (c_good, c_off)
        assert ann_good[(37.0, 100.0)].feature_class == "SHELF_PIN_HOLE"

    def test_50mm_circle_not_a_confident_through_hole(self):
        """A 50mm circle is too big to drill: it must NOT be a confident
        THROUGH_HOLE. With HARDWARE_HOLE detection (20-50mm), a large bore is now
        classified as a hardware mounting hole rather than left UNKNOWN — but it
        is still never a through hole."""
        ents = [
            _panel_entity([[0, 0], [400, 0], [400, 400], [0, 400]], [0, 0, 400, 400]),
            _circle("big", 200, 200, 50.0),
        ]
        ann = _annotate(ents)
        a = ann[(200.0, 200.0)]
        assert a.feature_class != "THROUGH_HOLE"
        assert a.feature_class in ("HARDWARE_HOLE", "UNKNOWN_FEATURE")

    def test_2mm_circle_not_a_confident_standard_feature(self):
        """A 2mm circle is below the drill window: not auto-validated as a hole."""
        ents = [
            _panel_entity([[0, 0], [400, 0], [400, 400], [0, 400]], [0, 0, 400, 400]),
            _circle("tiny", 200, 200, 2.0),
        ]
        ann = _annotate(ents)
        a = ann[(200.0, 200.0)]
        assert a.confidence < ACCEPT, a.confidence

    def test_exact_35mm_hinge_near_edge_scores_high(self):
        """An exact 35mm hole 22.5mm from the edge scores high (Blum pattern)."""
        # cx = 22.5 from left edge -> edge distance ~22.5mm triggers P2.
        ents = [
            _panel_entity([[0, 0], [400, 0], [400, 400], [0, 400]], [0, 0, 400, 400]),
            _circle("hc", 22.5, 200, 35.0, layer="DRILL"),
        ]
        ann = _annotate(ents)
        a = ann[(22.5, 200.0)]
        assert a.feature_class == "HINGE_CUP_HOLE"
        assert a.confidence >= 0.85

    def test_offspec_hinge_scores_lower_than_exact(self):
        """A 36mm hinge (off-spec) scores lower than an exact 35mm one."""
        exact = [
            _panel_entity([[0, 0], [400, 0], [400, 400], [0, 400]], [0, 0, 400, 400]),
            _circle("e", 22.5, 200, 35.0, layer="HINGE"),
        ]
        off = [
            _panel_entity([[0, 0], [400, 0], [400, 400], [0, 400]], [0, 0, 400, 400]),
            _circle("o", 22.5, 200, 35.8, layer="HINGE"),
        ]
        a_exact = _annotate(exact)[(22.5, 200.0)]
        a_off = _annotate(off)[(22.5, 200.0)]
        assert a_exact.feature_class == a_off.feature_class == "HINGE_CUP_HOLE"
        assert a_exact.confidence > a_off.confidence

    def test_legitimate_8mm_through_hole_still_accepted(self):
        """A 12mm generic drill circle (no special diameter) stays a confident
        THROUGH_HOLE -- grading must not over-reject normal holes."""
        ents = [
            _panel_entity([[0, 0], [400, 0], [400, 400], [0, 400]], [0, 0, 400, 400]),
            _circle("th", 200, 200, 12.0),
        ]
        ann = _annotate(ents)
        a = ann[(200.0, 200.0)]
        assert a.feature_class == "THROUGH_HOLE"
        assert a.confidence >= ACCEPT


# ---------------------------------------------------------------------------
# Deterministic / boundary cases unaffected
# ---------------------------------------------------------------------------


class TestDeterministicUnaffected:
    def test_outer_boundary_confidence_unchanged(self):
        """The outer boundary is deterministic PROFILE_CUT at 0.95 regardless."""
        ents = [_panel_entity(
            [[0, 0], [400, 0], [400, 400], [0, 400]], [0, 0, 400, 400])]
        mgg = _build(ents)
        anns = FeatureClassifier().classify(mgg)
        boundary = [
            a for a in anns.feature_annotations if a.feature_class == "PROFILE_CUT"
        ]
        assert boundary
        assert all(a.confidence == 0.95 for a in boundary)

    def test_internal_cutout_confidence_unchanged(self):
        """A closed interior contour on a cut layer stays INTERNAL_CUTOUT @0.80."""
        panel = _panel_entity(
            [[0, 0], [400, 0], [400, 400], [0, 400]], [0, 0, 400, 400])
        cutout = RawEntity(
            entity_id="cut1", ezdxf_handle="hc", entity_type="LWPOLYLINE",
            layer="cut", inferred_layer_type="cut",
            coordinates=[[100, 100], [150, 100], [150, 150], [100, 150]],
            is_closed=True, bounding_box=[100, 100, 150, 150],
            centroid=[125.0, 125.0], area_mm2=2500.0, perimeter_mm=200.0,
        )
        mgg = _build([panel, cutout])
        anns = FeatureClassifier().classify(mgg)
        cutouts = [
            a for a in anns.feature_annotations
            if a.feature_class == "INTERNAL_CUTOUT"
        ]
        assert cutouts
        assert all(a.confidence == 0.80 for a in cutouts)
