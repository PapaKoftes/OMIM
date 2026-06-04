"""Tests for the auto-label + review-queue layer."""

from __future__ import annotations

import json

from omim.graph.builder import MGGBuilder
from omim.labeling import AutoLabeler, LabelKind, ReviewQueue, ReviewStatus
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry


def _poly(eid, coords, layer="CUT", inferred="cut"):
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


def _circle(eid, cx, cy, dia, layer="DRILL", inferred="drill"):
    r = dia / 2.0
    return RawEntity(
        entity_id=eid, ezdxf_handle=f"h{eid}", entity_type="CIRCLE",
        layer=layer, inferred_layer_type=inferred, coordinates=[cx, cy, r],
        is_closed=True, bounding_box=[cx - r, cy - r, cx + r, cy + r],
        centroid=[cx, cy], area_mm2=3.14159 * r * r, perimeter_mm=2 * 3.14159 * r,
        diameter_mm=float(dia), radius_mm=float(r),
    )


def _door_mgg():
    boundary = [[0, 0], [400, 0], [400, 600], [0, 600]]
    ents = [
        _poly("P", boundary),
        _circle("hc1", 22.5, 100, 35.0, layer="HINGE"),
        _circle("hc2", 22.5, 500, 35.0, layer="HINGE"),
    ]
    raw = RawGeometry(
        source_file="door.dxf", source_file_hash="sha256:door", dxf_version="AC1027",
        entities=ents,
        panel_boundary=PanelBoundary(
            entity_id="P", coordinates=boundary, bounding_box=[0, 0, 400, 600],
            area_mm2=240000.0, inferred=False,
        ),
        panel_boundary_inferred=False, entity_counts={},
    )
    return MGGBuilder().build(raw)


def test_autolabeler_produces_feature_and_part_labels():
    ls = AutoLabeler().label_panel(_door_mgg())
    assert ls.by_kind(LabelKind.PART), "expected a part label"
    assert ls.by_kind(LabelKind.FEATURE), "expected feature labels"
    part = ls.by_kind(LabelKind.PART)[0]
    assert part.value == "DOOR"
    # High-confidence door -> auto accepted.
    assert part.review_status == ReviewStatus.AUTO_ACCEPTED


def test_low_confidence_goes_to_review():
    """Forcing a high accept threshold pushes labels into NEEDS_REVIEW."""
    ls = AutoLabeler(accept_threshold=0.99).label_panel(_door_mgg())
    assert ls.needs_review_count > 0


def test_review_queue_roundtrip(tmp_path):
    """Export -> simulate a human edit in the JSONL -> apply -> labels become gold."""
    labeler = AutoLabeler(accept_threshold=0.99)  # force everything to review
    ls = labeler.label_panel(_door_mgg())
    sets = [ls]

    q = ReviewQueue(tmp_path / "review.jsonl")
    n = q.export(sets)
    assert n == ls.needs_review_count > 0

    # Simulate a reviewer editing the JSONL: confirm the first, correct the second.
    rows = [json.loads(line) for line in (tmp_path / "review.jsonl").read_text().splitlines()]
    rows[0]["decision"] = "confirm"
    rows[1]["decision"] = "correct"
    rows[1]["corrected_value"] = "DOWEL_HOLE"
    rows[1]["note"] = "actually a dowel"
    (tmp_path / "review.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )

    updated = q.apply_decisions(sets)
    assert updated == 2

    by_id = {lab.label_id: lab for lab in ls.labels}
    confirmed = by_id[rows[0]["label"]["label_id"]]
    corrected = by_id[rows[1]["label"]["label_id"]]
    assert confirmed.review_status == ReviewStatus.HUMAN_CONFIRMED
    assert confirmed.is_gold
    assert corrected.review_status == ReviewStatus.HUMAN_CORRECTED
    assert corrected.final_value == "DOWEL_HOLE"
    assert corrected.is_gold


def test_unreviewed_rows_are_ignored(tmp_path):
    ls = AutoLabeler(accept_threshold=0.99).label_panel(_door_mgg())
    q = ReviewQueue(tmp_path / "r.jsonl")
    q.export([ls])
    # No decisions filled in -> nothing applied.
    assert q.apply_decisions([ls]) == 0
    assert ls.needs_review_count > 0


def test_reject_decision_marks_rejected(tmp_path):
    ls = AutoLabeler(accept_threshold=0.99).label_panel(_door_mgg())
    q = ReviewQueue(tmp_path / "r.jsonl")
    q.export([ls])
    rows = [json.loads(line) for line in (tmp_path / "r.jsonl").read_text().splitlines()]
    rows[0]["decision"] = "reject"
    (tmp_path / "r.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    q.apply_decisions([ls])
    by_id = {lab.label_id: lab for lab in ls.labels}
    assert by_id[rows[0]["label"]["label_id"]].review_status == ReviewStatus.REJECTED
