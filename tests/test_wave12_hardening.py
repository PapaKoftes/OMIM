"""Wave 12 hardening: verify the 6 adversarial-review fixes actually hold.

These tests target the SPECIFIC failures the review found, with geometry built
independently of the heuristics where possible:

1. Panel thickness comes from stock (layer/Z), NOT feature depth.
2. Assembly grouping is scoped by source file (no cross-cabinet merge).
3. Nest files are genuinely split into per-panel records.
4. Dataset mgg.json is byte-reproducible (pinned timestamp).
5. Assembly/project labels reach the review queue.
6. The tuner emits tolerances.
"""

from __future__ import annotations

import json

import ezdxf

from omim.graph.builder import MGGBuilder
from omim.identify import identify_assemblies
from omim.identify.models import PartIdentification
from omim.nesting import split_raw_geometry_by_panels
from omim.parser.depth import resolve_panel_thickness
from omim.parser.dxf_parser import DXFParser
from omim.pipeline import DatasetBuilder, tune_ruleset


def _rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


# ---------------------------------------------------------------------------
# Fix 1: thickness = stock, not feature depth
# ---------------------------------------------------------------------------


def test_thickness_is_stock_not_feature_depth(tmp_path):
    """A panel with a deep blind pocket but an 18mm layer tag reports thickness 18,
    NOT the pocket's depth."""
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline(_rect(0, 0, 600, 800), close=True, dxfattribs={"layer": "PANEL_18MM"})
    # A 6mm-deep pocket (feature depth 6) — must NOT become the panel thickness.
    m.add_lwpolyline(_rect(100, 100, 60, 60), close=True, dxfattribs={"layer": "POCKET_D6"})
    p = tmp_path / "panel.dxf"
    doc.saveas(p)

    mgg = MGGBuilder().build(DXFParser().parse(p).geometry)
    assert mgg.metadata.panel_thickness_mm == 18.0  # stock, from PANEL_18MM
    assert mgg.metadata.panel_thickness_source == "layer_name"
    # The pocket still has its own feature depth of 6 — distinct quantity.
    depths = [d.get("depth_mm") for _n, d in mgg.geometry_nodes() if d.get("depth_mm")]
    assert 6.0 in depths


def test_resolve_panel_thickness_prefers_z_extent():
    t, src = resolve_panel_thickness(layers=["CUT"], z_values=[0.0, 18.0])
    assert t == 18.0 and src == "z_extent"


def test_thickness_none_for_flat_2d():
    """A flat 2D file with no thickness convention -> thickness stays None."""
    t, src = resolve_panel_thickness(layers=["CUT", "DRILL"], z_values=[])
    assert t is None and src is None


# ---------------------------------------------------------------------------
# Fix 2: assembly grouping scoped by source file (no cross-cabinet merge)
# ---------------------------------------------------------------------------


def _part(pid, part_type, thickness, src):
    return (
        PartIdentification(panel_id=pid, part_type=part_type, confidence=0.8,
                           width_mm=600, height_mm=800, thickness_mm=thickness),
        src,
    )


def test_flat_pile_same_thickness_not_merged():
    """5 cabinets' worth of 18mm panels from DIFFERENT files must NOT merge into
    one giant assembly (the headline review failure)."""
    panels = []
    for cab in range(5):
        src = f"cabinet_{cab}.dxf"
        panels.append(_part(f"side_{cab}", "SIDE_PANEL", 18.0, src))
        panels.append(_part(f"top_{cab}", "SHELF", 18.0, src))
    asms = identify_assemblies(panels)
    # Each source file is its own scope -> at most one assembly per file, never
    # a single 10-panel blob.
    assert max(a.panel_count for a in asms) <= 2
    assert len(asms) >= 5


def test_same_file_panels_can_group():
    """Panels from the SAME file with shared thickness DO group into one assembly."""
    src = "cabinet.dxf"
    panels = [
        _part("side_l", "SIDE_PANEL", 18.0, src),
        _part("side_r", "SIDE_PANEL", 18.0, src),
        _part("top", "SHELF", 18.0, src),
    ]
    asms = identify_assemblies(panels)
    assert any(a.panel_count == 3 and a.assembly_type == "CARCASS" for a in asms)


# ---------------------------------------------------------------------------
# Fix 3: nests are genuinely split into per-panel records
# ---------------------------------------------------------------------------


def _nest_dxf(path, n_panels=3):
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline(_rect(0, 0, 1300, 400), close=True, dxfattribs={"layer": "SHEET"})
    for i in range(n_panels):
        x = 20 + i * 420
        m.add_lwpolyline(_rect(x, 20, 400, 360), close=True, dxfattribs={"layer": "CUT"})
        m.add_circle((x + 200, 200), radius=2.5, dxfattribs={"layer": "DRILL"})
    doc.saveas(path)


def test_split_nest_into_panels(tmp_path):
    p = tmp_path / "nest.dxf"
    _nest_dxf(p, n_panels=3)
    raw = DXFParser().parse(p).geometry
    subs = split_raw_geometry_by_panels(raw)
    assert len(subs) == 3  # 3 panels, not 1 sheet
    # Each sub-geometry has its own boundary + the hole that fell inside it.
    for sub in subs:
        assert sub.panel_boundary is not None
        assert any(e.entity_type == "CIRCLE" for e in sub.entities)


def test_single_panel_not_split(tmp_path):
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline(_rect(0, 0, 400, 600), close=True, dxfattribs={"layer": "CUT"})
    p = tmp_path / "single.dxf"
    doc.saveas(p)
    raw = DXFParser().parse(p).geometry
    subs = split_raw_geometry_by_panels(raw)
    assert len(subs) == 1


def test_pipeline_counts_nest_panels(tmp_path):
    """build-dataset on a 3-panel nest file yields 3 panel records, not 1."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    _nest_dxf(corpus / "sheet.dxf", n_panels=3)
    summary = DatasetBuilder().build(corpus, tmp_path / "ds")
    assert summary.panels == 3


# ---------------------------------------------------------------------------
# Fix 4: dataset is byte-reproducible
# ---------------------------------------------------------------------------


def test_dataset_mgg_is_reproducible(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline(_rect(0, 0, 400, 600), close=True, dxfattribs={"layer": "CUT"})
    m.add_circle((200, 300), radius=2.5, dxfattribs={"layer": "DRILL"})
    doc.saveas(corpus / "p.dxf")

    DatasetBuilder().build(corpus, tmp_path / "ds1")
    DatasetBuilder().build(corpus, tmp_path / "ds2")

    f1 = next((tmp_path / "ds1" / "samples").rglob("mgg.json"))
    f2 = next((tmp_path / "ds2" / "samples").rglob("mgg.json"))
    assert f1.read_text() == f2.read_text(), "mgg.json must be byte-identical across runs"


# ---------------------------------------------------------------------------
# Fix 5: assembly/project labels reach the review queue
# ---------------------------------------------------------------------------


def test_project_labels_in_review_dataset(tmp_path):
    corpus = tmp_path / "corpus"
    proj = corpus / "cab"
    proj.mkdir(parents=True)
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline(_rect(0, 0, 400, 600), close=True, dxfattribs={"layer": "CUT"})
    m.add_circle((22.5, 100), radius=17.5, dxfattribs={"layer": "HINGE"})
    doc.saveas(proj / "door.dxf")

    out = tmp_path / "ds"
    DatasetBuilder().build(corpus, out)

    queue = (out / "review_queue.jsonl").read_text().splitlines()
    kinds = {json.loads(line)["label"]["kind"] for line in queue if line.strip()}
    # The project-level label is heuristic and must be reviewable.
    assert "project" in kinds


# ---------------------------------------------------------------------------
# Fix 6: tuner emits tolerances
# ---------------------------------------------------------------------------


def test_tuner_emits_tolerances(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for i in range(4):
        doc = ezdxf.new()
        m = doc.modelspace()
        m.add_lwpolyline(_rect(0, 0, 600, 800), close=True, dxfattribs={"layer": "CUT"})
        for j in range(8):
            m.add_circle((37, 100 + 32 * j), radius=2.5, dxfattribs={"layer": "DRILL"})
        doc.saveas(corpus / f"p{i}.dxf")

    tuned = tune_ruleset(corpus, min_samples=5)
    # A tolerance param is emitted alongside the diameter (the docstring claim).
    assert "shelf_pin_tolerance_mm" in tuned.parameters
    assert tuned.parameters["shelf_pin_tolerance_mm"] >= 0.2
