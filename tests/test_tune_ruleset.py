"""Tests for corpus-tuned identification ruleset (omim.pipeline.tune)."""

from __future__ import annotations

import ezdxf
import yaml

from omim.pipeline import tune_ruleset, write_tuned_ruleset


def _rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _write_panel_with_holes(path, hole_dia, n=8):
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(_rect(0, 0, 600, 800), close=True, dxfattribs={"layer": "CUT"})
    for i in range(n):
        msp.add_circle((37, 100 + 32 * i), radius=hole_dia / 2.0, dxfattribs={"layer": "DRILL"})
    doc.saveas(path)


def test_tune_measures_corpus_diameter(tmp_path):
    """A corpus of consistent 5.0mm holes tunes shelf_pin_diameter from the corpus."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for i in range(4):
        _write_panel_with_holes(corpus / f"p{i}.dxf", hole_dia=5.0, n=8)

    tuned = tune_ruleset(corpus, min_samples=5)
    assert tuned.corpus_files == 4
    # 32 holes at 5.0mm -> shelf-pin diameter measured from corpus, ~5.0.
    assert tuned.sources["shelf_pin_diameter_mm"] == "corpus_measured"
    assert abs(tuned.parameters["shelf_pin_diameter_mm"] - 5.0) < 0.5


def test_tune_keeps_default_when_sparse(tmp_path):
    """Too few samples -> the catalog default is kept and flagged."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _write_panel_with_holes(corpus / "p.dxf", hole_dia=35.0, n=1)  # 1 hinge-ish hole

    tuned = tune_ruleset(corpus, min_samples=5)
    assert tuned.sources["hinge_cup_diameter_mm"] == "catalog_default"
    assert tuned.parameters["hinge_cup_diameter_mm"] == 35.0


def test_tune_measures_shelf_pin_spacing(tmp_path):
    """Consistent 32mm spacing is recovered as the grid pitch."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for i in range(4):
        _write_panel_with_holes(corpus / f"p{i}.dxf", hole_dia=5.0, n=8)
    tuned = tune_ruleset(corpus, min_samples=5)
    assert abs(tuned.parameters["shelf_pin_spacing_mm"] - 32.0) <= 1.0


def test_write_tuned_ruleset_yaml(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for i in range(4):
        _write_panel_with_holes(corpus / f"p{i}.dxf", hole_dia=5.0, n=8)

    out = tmp_path / "tuned.yaml"
    write_tuned_ruleset(corpus, out, min_samples=5)
    assert out.exists()
    doc = yaml.safe_load(out.read_text())
    assert "parameters" in doc
    assert "tuning" in doc
    assert doc["tuning"]["corpus_files"] == 4
    assert "sources" in doc["tuning"]


def test_tune_empty_corpus_all_defaults(tmp_path):
    """An empty corpus yields all catalog defaults, no crash."""
    corpus = tmp_path / "empty"
    corpus.mkdir()
    tuned = tune_ruleset(corpus)
    assert all(v == "catalog_default" for v in tuned.sources.values())
    assert tuned.parameters["panel_thickness_mm"] == 18.0
