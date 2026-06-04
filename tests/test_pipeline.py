"""End-to-end tests for the corpus -> labeled dataset pipeline."""

from __future__ import annotations

import json

import ezdxf

from omim.pipeline import CorpusLayout, DatasetBuilder, detect_layout


def _rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _write_door(path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(_rect(0, 0, 400, 600), close=True, dxfattribs={"layer": "CUT"})
    msp.add_circle((22.5, 100), radius=17.5, dxfattribs={"layer": "HINGE"})
    msp.add_circle((22.5, 500), radius=17.5, dxfattribs={"layer": "HINGE"})
    doc.saveas(path)


def _write_side(path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(_rect(0, 0, 600, 800), close=True, dxfattribs={"layer": "CUT"})
    for i in range(6):
        msp.add_circle((37, 100 + 32 * i), radius=2.5, dxfattribs={"layer": "DRILL"})
    doc.saveas(path)


def _make_project_corpus(root):
    """Two project folders, each with a door + a side panel."""
    for proj in ("cabinet_a", "cabinet_b"):
        d = root / proj
        d.mkdir(parents=True)
        _write_door(d / "door.dxf")
        _write_side(d / "side.dxf")


def test_detect_per_project_layout(tmp_path):
    _make_project_corpus(tmp_path)
    det = detect_layout(tmp_path)
    assert det.layout == CorpusLayout.PER_PROJECT_FOLDERS
    assert det.dxf_count == 4


def test_detect_flat_pile(tmp_path):
    _write_door(tmp_path / "a.dxf")
    _write_door(tmp_path / "b.dxf")
    det = detect_layout(tmp_path)
    assert det.layout == CorpusLayout.FLAT_PILE


def test_build_dataset_end_to_end(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _make_project_corpus(corpus)
    out = tmp_path / "dataset"

    summary = DatasetBuilder().build(corpus, out)

    assert summary.layout == CorpusLayout.PER_PROJECT_FOLDERS.value
    assert summary.dxf_files == 4
    assert summary.panels == 4
    assert summary.projects == 2
    assert summary.labels_total > 0

    # Per-panel samples written with mgg + labels.
    samples = list((out / "samples").iterdir())
    assert len(samples) == 4
    for s in samples:
        assert (s / "mgg.json").exists()
        assert (s / "labels.json").exists()

    # Project trees written, one per project.
    projects = list((out / "projects").glob("*.json"))
    assert len(projects) == 2

    # Manifest + review queue present.
    manifest = json.loads((out / "dataset_manifest.json").read_text())
    assert manifest["panels"] == 4
    assert (out / "review_queue.jsonl").exists()


def test_build_dataset_labels_doors_and_sides(tmp_path):
    corpus = tmp_path / "c"
    corpus.mkdir()
    proj = corpus / "cab"
    proj.mkdir()
    _write_door(proj / "door.dxf")
    _write_side(proj / "side.dxf")

    out = tmp_path / "ds"
    DatasetBuilder().build(corpus, out)

    # Collect all part labels across samples.
    part_values = set()
    for s in (out / "samples").iterdir():
        labels = json.loads((s / "labels.json").read_text())
        for lab in labels["labels"]:
            if lab["kind"] == "part":
                part_values.add(lab["value"])
    assert "DOOR" in part_values
    assert "SIDE_PANEL" in part_values


def test_bad_dxf_is_skipped_not_fatal(tmp_path):
    corpus = tmp_path / "c"
    corpus.mkdir()
    _write_door(corpus / "good.dxf")
    (corpus / "bad.dxf").write_text("not a real dxf", encoding="utf-8")

    out = tmp_path / "ds"
    summary = DatasetBuilder().build(corpus, out)
    # The good file is processed; the bad one is logged as a failure, not fatal.
    assert summary.panels == 1
    assert summary.failures
