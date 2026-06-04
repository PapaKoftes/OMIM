"""Tests for external-dataset adapters (ArchCAD-400K, MFCAD++).

The real datasets aren't bundled, so these use small synthetic stand-ins shaped
like the real records to verify the label-mapping + manifest logic.
"""

from __future__ import annotations

import json

from omim.datasets import archcad, mfcad

# ---------------------------------------------------------------------------
# ArchCAD-400K
# ---------------------------------------------------------------------------


def test_archcad_maps_holes_and_doors():
    record = {
        "id": "plan-1",
        "elements": [
            {"id": "e1", "label": "hole"},
            {"id": "e2", "label": "door"},
            {"id": "e3", "label": "wall"},     # no OMIM analogue
            {"id": "e4", "label": "window"},   # no OMIM analogue
        ],
    }
    s = archcad.convert_sample(record)
    assert s.source_dataset == "ArchCAD-400K"
    assert s.element_labels == {"e1": "THROUGH_HOLE", "e2": "DOOR"}
    assert set(s.unmapped_labels.values()) == {"wall", "window"}
    assert s.element_count == 4 and s.mapped_count == 2
    assert s.provenance["license"] == "CC0-1.0"


def test_archcad_load_jsonl(tmp_path):
    p = tmp_path / "archcad.jsonl"
    p.write_text(
        "\n".join(json.dumps(r) for r in [
            {"id": "a", "elements": [{"id": "1", "label": "hole"}]},
            {"id": "b", "elements": [{"id": "1", "label": "wall"}]},
        ]) + "\n",
        encoding="utf-8",
    )
    samples = archcad.load_jsonl(p)
    assert len(samples) == 2
    m = archcad.build_manifest(samples)
    assert m.dataset == "ArchCAD-400K"
    assert m.license == "CC0-1.0" and m.redistributable is True
    assert m.total_elements == 2 and m.mapped_elements == 1
    assert m.label_coverage == 0.5
    assert "THROUGH_HOLE" in m.omim_classes_seen
    assert "wall" in m.unmapped_source_labels


def test_archcad_map_label_unknown_is_none():
    assert archcad.map_label("staircase") is None
    assert archcad.map_label("hole") == "THROUGH_HOLE"


# ---------------------------------------------------------------------------
# MFCAD++
# ---------------------------------------------------------------------------


def test_mfcad_maps_machining_features():
    record = {
        "id": "model-1",
        "faces": [
            {"id": "f1", "label": "through_hole"},
            {"id": "f2", "label": "rectangular_pocket"},
            {"id": "f3", "label": "rectangular_through_slot"},
            {"id": "f4", "label": "chamfer"},   # no 2D analogue -> unmapped
        ],
    }
    s = mfcad.convert_sample(record)
    assert s.source_dataset == "MFCAD++"
    assert s.element_labels == {
        "f1": "THROUGH_HOLE", "f2": "POCKET", "f3": "GROOVE",
    }
    assert "chamfer" in s.unmapped_labels.values()
    assert s.provenance["license"] == "MIT"
    assert s.provenance["inference_method"] == "synthetic"


def test_mfcad_accepts_bare_label_list():
    record = {"id": "m", "faces": ["through_hole", "chamfer"]}
    s = mfcad.convert_sample(record)
    assert "THROUGH_HOLE" in s.element_labels.values()
    assert s.mapped_count == 1


def test_mfcad_load_json_and_manifest(tmp_path):
    p = tmp_path / "mfcad.json"
    p.write_text(json.dumps([
        {"id": "m1", "faces": [{"id": "f1", "label": "blind_hole"}]},
        {"id": "m2", "faces": [{"id": "f1", "label": "step"}]},  # unmapped
    ]), encoding="utf-8")
    samples = mfcad.load_json(p)
    m = mfcad.build_manifest(samples)
    assert m.dataset == "MFCAD++" and m.license == "MIT"
    assert m.total_elements == 2 and m.mapped_elements == 1
    assert "THROUGH_HOLE" in m.omim_classes_seen
    assert "step" in m.unmapped_source_labels


def test_mfcad_taxonomy_maps_to_real_omim_classes():
    """Every mapped target must be a class OMIM actually uses (no typos)."""
    from omim.semantic.classifier import FEATURE_CATEGORIES

    valid = set(FEATURE_CATEGORIES) | {"THROUGH_HOLE", "POCKET", "GROOVE",
                                       "INTERNAL_CUTOUT"}
    for omim_class in set(mfcad.MFCAD_TO_OMIM.values()):
        assert omim_class in valid, f"{omim_class} not a known OMIM class"
