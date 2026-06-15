"""The calibration data-gate, mechanised: gold labels -> fitted calibrator.

Covers calibrator persistence and the end-to-end build -> review -> calibrate
loop. Uses synthetic geometry + a simulated human review (no external data).
"""

from __future__ import annotations

import csv
import json

import ezdxf

from omim.pipeline import DatasetBuilder, apply_review_to_dataset, calibrate_from_dataset
from omim.semantic.calibration import IsotonicCalibrator


def test_calibrator_save_load_roundtrip(tmp_path):
    pairs = [(0.9, i % 2 == 0) for i in range(40)] + [(0.6, i % 10 < 6) for i in range(40)]
    cal = IsotonicCalibrator().fit(pairs)
    path = tmp_path / "cal.json"
    cal.save(path)
    loaded = IsotonicCalibrator.load(path)
    assert loaded.fitted == cal.fitted
    for c in (0.3, 0.6, 0.9, 1.0):
        assert loaded.calibrate(c) == cal.calibrate(c)


def test_identity_calibrator_when_no_gold(tmp_path):
    """No gold labels -> a safe identity calibrator is still written."""
    corpus = tmp_path / "c"
    corpus.mkdir()
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True,
                     dxfattribs={"layer": "CUT"})
    m.add_circle((22.5, 100), radius=17.5, dxfattribs={"layer": "HINGE"})
    doc.saveas(corpus / "door.dxf")
    out = tmp_path / "ds"
    DatasetBuilder().build(corpus, out)

    res = calibrate_from_dataset(out, out / "calibrator.json")
    assert res["gold_pairs"] == 0
    assert (out / "calibrator.json").exists()
    data = json.loads((out / "calibrator.json").read_text())
    assert data["fitted"] is False  # identity until gold exists


def test_calibrate_from_reviewed_dataset(tmp_path):
    """Build -> simulate a human confirming everything -> calibrate yields gold pairs."""
    corpus = tmp_path / "c"
    corpus.mkdir()
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True,
                     dxfattribs={"layer": "CUT"})
    m.add_circle((22.5, 100), radius=17.5, dxfattribs={"layer": "HINGE"})
    m.add_circle((200, 300), radius=2.5, dxfattribs={"layer": "DRILL"})
    doc.saveas(corpus / "door.dxf")

    out = tmp_path / "ds"
    DatasetBuilder(accept_threshold=0.99).build(corpus, out)  # force review

    # Simulate the carpenter confirming every row.
    sheet = out / "review_sheet.csv"
    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    assert rows
    for r in rows:
        r["is it right? (yes/no)"] = "yes"
    with sheet.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    apply_review_to_dataset(out, sheet)
    res = calibrate_from_dataset(out, out / "calibrator.json")
    assert res["gold_pairs"] >= 1  # human review produced real (conf, correct) pairs
    assert (out / "calibrator.json").exists()
