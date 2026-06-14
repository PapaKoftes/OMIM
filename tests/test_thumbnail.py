"""Tests for SVG panel thumbnails (visual human review) — synthetic only."""

from __future__ import annotations

import csv

import ezdxf

from omim.graph.builder import MGGBuilder
from omim.labeling import render_panel_svg
from omim.parser.dxf_parser import DXFParser


def _panel_mgg(tmp_path):
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (300, 0), (300, 400), (0, 400)], close=True,
                     dxfattribs={"layer": "CUT"})
    m.add_circle((50, 50), radius=2.5, dxfattribs={"layer": "DRILL"})
    m.add_circle((250, 350), radius=17.5, dxfattribs={"layer": "HINGE"})
    f = tmp_path / "p.dxf"
    doc.saveas(f)
    return MGGBuilder().build(DXFParser().parse(f).geometry)


def test_svg_is_wellformed(tmp_path):
    svg = render_panel_svg(_panel_mgg(tmp_path))
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # The panel outline (polygon) and the two circles render.
    assert "<polygon" in svg
    assert svg.count("<circle") == 2
    assert "viewBox" in svg


def test_svg_highlights_a_node(tmp_path):
    mgg = _panel_mgg(tmp_path)
    nid = next(n for n, d in mgg.geometry_nodes() if d.get("geometry_type") == "circle")
    svg = render_panel_svg(mgg, highlight_node_id=nid)
    # Highlight colour appears only when a node is highlighted.
    assert "#e67e22" in svg
    assert "#e67e22" not in render_panel_svg(mgg)


def test_svg_handles_empty():
    from omim.graph.mgg import ManufacturingGeometryGraph
    from omim.graph.models import GraphMetadata
    svg = render_panel_svg(ManufacturingGeometryGraph(GraphMetadata(graph_id="e")))
    assert svg.startswith("<svg")  # no crash on an empty panel


def test_build_dataset_writes_thumbnails(tmp_path):
    from omim.pipeline import DatasetBuilder

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    doc = ezdxf.new()
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True,
                     dxfattribs={"layer": "CUT"})
    m.add_circle((22.5, 100), radius=17.5, dxfattribs={"layer": "HINGE"})
    doc.saveas(corpus / "door.dxf")

    out = tmp_path / "ds"
    DatasetBuilder(accept_threshold=0.99).build(corpus, out)

    # Thumbnails dir populated, and the review sheet's "picture" column points at one.
    svgs = list((out / "thumbnails").glob("*.svg"))
    assert svgs
    rows = list(csv.DictReader((out / "review_sheet.csv").open(encoding="utf-8")))
    assert "picture" in rows[0]
    assert any(r["picture"].startswith("thumbnails/") for r in rows)
