"""Tests for the carpenter-friendly CSV review sheet (the non-technical bridge).

Verifies the full hand-off loop: export a plain-English CSV -> a non-technical
reviewer fills two columns -> import folds their answers back as gold labels.
"""

from __future__ import annotations

import csv

from omim.graph.builder import MGGBuilder
from omim.labeling import (
    AutoLabeler,
    ReviewQueue,
    ReviewStatus,
    export_review_sheet,
    import_review_sheet,
    write_glossary,
)
from omim.labeling.review_sheet import plain_class
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry


def _door_mgg():
    b = [[0, 0], [400, 0], [400, 600], [0, 600]]
    panel = RawEntity(
        entity_id="P", ezdxf_handle="P", entity_type="LWPOLYLINE", layer="CUT",
        inferred_layer_type="cut", coordinates=b, is_closed=True,
        bounding_box=[0, 0, 400, 600], centroid=[200, 300], area_mm2=240000,
        perimeter_mm=2000,
    )
    cup = RawEntity(
        entity_id="h1", ezdxf_handle="h1", entity_type="CIRCLE", layer="HINGE",
        inferred_layer_type="drill", coordinates=[22.5, 100, 17.5], is_closed=True,
        bounding_box=[5, 82.5, 40, 117.5], centroid=[22.5, 100], area_mm2=962,
        perimeter_mm=110, diameter_mm=35.0, radius_mm=17.5,
    )
    raw = RawGeometry(
        source_file="door.dxf", source_file_hash="sha256:d", dxf_version="AC1027",
        entities=[panel, cup],
        panel_boundary=PanelBoundary(entity_id="P", coordinates=b,
                                     bounding_box=[0, 0, 400, 600], area_mm2=240000,
                                     inferred=False),
        panel_boundary_inferred=False, entity_counts={},
    )
    return MGGBuilder().build(raw)


def test_plain_class_is_human_readable():
    assert "hinge cup" in plain_class("HINGE_CUP_HOLE")
    assert plain_class("DOOR") == "door"
    # Unknown class degrades to a readable phrase, never blank.
    assert plain_class("SOME_NEW_THING") == "some new thing"


def test_export_sheet_is_plain_english(tmp_path):
    ls = AutoLabeler(accept_threshold=0.99).label_panel(_door_mgg())
    n = export_review_sheet([ls], tmp_path / "review_sheet.csv")
    assert n > 0
    rows = list(csv.DictReader((tmp_path / "review_sheet.csv").open(encoding="utf-8")))
    # The reviewer-facing columns exist and use words, not codes.
    assert "what OMIM thinks this is" in rows[0]
    assert "is it right? (yes/no)" in rows[0]
    assert any("hinge cup" in r["what OMIM thinks this is"] for r in rows)
    # Confidence is shown as a percentage.
    assert all(r["how sure (%)"].isdigit() for r in rows)


def test_glossary_written(tmp_path):
    write_glossary(tmp_path / "glossary.csv")
    rows = list(csv.DictReader((tmp_path / "glossary.csv").open(encoding="utf-8")))
    terms = {r["term"] for r in rows}
    assert "HINGE_CUP_HOLE" in terms


def test_full_carpenter_roundtrip(tmp_path):
    """Export -> carpenter answers yes/no in plain words -> gold labels."""
    ls = AutoLabeler(accept_threshold=0.99).label_panel(_door_mgg())
    sheet = tmp_path / "s.csv"
    export_review_sheet([ls], sheet)

    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    # Carpenter confirms the first, corrects the second with a PLAIN word.
    rows[0]["is it right? (yes/no)"] = "yes"
    rows[1]["is it right? (yes/no)"] = "no"
    rows[1]["if no, what is it?"] = "drawer front"
    with sheet.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    decisions = import_review_sheet(sheet)
    assert len(decisions) == 2
    updated = ReviewQueue(tmp_path / "q.jsonl").apply_decisions([ls], decisions=decisions)
    assert updated == 2

    by_id = {lab.label_id: lab for lab in ls.labels}
    confirmed = by_id[rows[0]["row_id"]]
    corrected = by_id[rows[1]["row_id"]]
    assert confirmed.review_status == ReviewStatus.HUMAN_CONFIRMED
    assert confirmed.is_gold
    # Plain "drawer front" mapped back to the machine class.
    assert corrected.review_status == ReviewStatus.HUMAN_CORRECTED
    assert corrected.final_value == "DRAWER_FRONT"
    assert corrected.is_gold


def test_marked_wrong_with_no_answer_is_rejected(tmp_path):
    ls = AutoLabeler(accept_threshold=0.99).label_panel(_door_mgg())
    sheet = tmp_path / "s.csv"
    export_review_sheet([ls], sheet)
    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    rows[0]["is it right? (yes/no)"] = "no"  # no replacement given
    with sheet.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    decisions = import_review_sheet(sheet)
    assert decisions[rows[0]["row_id"]]["decision"] == "reject"


def test_blank_rows_are_skipped(tmp_path):
    ls = AutoLabeler(accept_threshold=0.99).label_panel(_door_mgg())
    sheet = tmp_path / "s.csv"
    export_review_sheet([ls], sheet)
    # Don't fill anything in.
    assert import_review_sheet(sheet) == {}


def test_end_to_end_via_pipeline_and_apply(tmp_path):
    """build-dataset writes a CSV; apply_review_to_dataset folds answers back."""
    import ezdxf

    from omim.pipeline import DatasetBuilder, apply_review_to_dataset

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True,
                     dxfattribs={"layer": "CUT"})
    m.add_circle((22.5, 100), radius=17.5, dxfattribs={"layer": "HINGE"})
    doc.saveas(corpus / "door.dxf")

    out = tmp_path / "ds"
    # Force everything to review so the sheet is non-empty.
    DatasetBuilder(accept_threshold=0.99).build(corpus, out)
    sheet = out / "review_sheet.csv"
    assert sheet.exists()
    assert (out / "review_glossary.csv").exists()

    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    for r in rows:
        r["is it right? (yes/no)"] = "yes"
    with sheet.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    result = apply_review_to_dataset(out, sheet)
    assert result["labels_updated"] >= 1
    assert result["gold_labels_now"] >= 1
