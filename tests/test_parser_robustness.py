"""Adversarial robustness tests for the DXF parser.

These synthesize real-world-messy DXF files with ezdxf (no fixtures ship in the
repo) and assert the parser survives them: it extracts geometry where it can,
emits a structured ParseWarning where it cannot, and NEVER crashes or silently
drops geometry. Where supported curves are produced (SPLINE / legacy POLYLINE /
LWPOLYLINE-with-bulge / ELLIPSE / exploded INSERT) we also build a full MGG from
the parse result to prove the geometry is consumable end-to-end.

Covers cases 1-12 from the hardening brief, mapped to Failure_Modes A/B.
"""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf

from omim.graph.builder import MGGBuilder
from omim.parser.dxf_parser import DXFParser
from omim.parser.models import ParserConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_doc(insunits: int = 4):
    doc = ezdxf.new("AC1024")
    doc.header["$INSUNITS"] = insunits
    return doc


def _save(doc, tmp_path: Path, name: str = "adv.dxf") -> Path:
    p = tmp_path / name
    doc.saveas(str(p))
    return p


def _parse_ok(path: Path, config: ParserConfig | None = None):
    result = DXFParser(config).parse(path)
    assert result.success, result.errors
    assert result.geometry is not None
    return result.geometry


def _warn_codes(geom) -> set[str]:
    return {w.warning_code for w in geom.warnings}


def _build_mgg(geom):
    """Build an MGG and assert it has at least the parsed entities as nodes."""
    mgg = MGGBuilder().build(geom)
    assert mgg.node_count >= len(geom.entities)
    return mgg


# ---------------------------------------------------------------------------
# Case 1: SPLINE -> approximated polyline, usable contour, is_approximated
# ---------------------------------------------------------------------------


def test_case01_spline_approximated_to_polyline(tmp_path):
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (300, 0), (300, 300), (0, 300)],
        close=True,
        dxfattribs={"layer": "CUT"},
    )
    # A wavy open spline + a closed spline blob.
    msp.add_spline(
        [(10, 10), (60, 80), (120, 20), (180, 90), (240, 30)],
        dxfattribs={"layer": "ENGRAVE"},
    )
    geom = _parse_ok(_save(doc, tmp_path))

    splines = [e for e in geom.entities if e.entity_type == "SPLINE"]
    assert len(splines) == 1
    s = splines[0]
    assert s.is_approximated is True
    # Flattened to many segments (default 50) -> a real polyline contour.
    assert isinstance(s.coordinates, list) and isinstance(s.coordinates[0], list)
    assert len(s.coordinates) >= 10
    assert s.perimeter_mm and s.perimeter_mm > 0
    assert s.bounding_box is not None
    # End-to-end: MGG consumes it.
    _build_mgg(geom)


def test_case01_spline_segment_count_config(tmp_path):
    """spline_approximation_segments in ParserConfig controls resolution."""
    doc = _new_doc()
    doc.modelspace().add_spline([(0, 0), (50, 50), (100, 0), (150, 50)])
    path = _save(doc, tmp_path)

    coarse = _parse_ok(path, ParserConfig(spline_approximation_segments=4))
    fine = _parse_ok(path, ParserConfig(spline_approximation_segments=100))
    n_coarse = len(coarse.entities[0].coordinates)
    n_fine = len(fine.entities[0].coordinates)
    assert n_fine > n_coarse


def test_curve_flattening_tolerance_controls_point_count(tmp_path):
    """curve_flattening_tolerance_mm bounds the spline approximation error: a
    coarser tolerance yields fewer points than a finer one. (Guards the
    performance fix — the old hardcoded 0.01mm exploded large curves into tens
    of thousands of points.)"""
    doc = _new_doc()
    # A large-extent wavy spline so the chord tolerance — not the segment
    # floor — drives the point count.
    doc.modelspace().add_spline(
        [(0, 0), (500, 400), (1000, -200), (1500, 600), (2000, 0)]
    )
    path = _save(doc, tmp_path)

    coarse = _parse_ok(path, ParserConfig(
        spline_approximation_segments=4, curve_flattening_tolerance_mm=2.0))
    fine = _parse_ok(path, ParserConfig(
        spline_approximation_segments=4, curve_flattening_tolerance_mm=0.01))
    n_coarse = len(coarse.entities[0].coordinates)
    n_fine = len(fine.entities[0].coordinates)
    assert n_fine > n_coarse
    assert n_coarse >= 4  # still a usable contour


def test_circle_area_perimeter_exact_closed_form(tmp_path):
    """Circle area/perimeter are exact closed-form (pi*r^2, 2*pi*r), not a
    256-gon buffer approximation — faster and more accurate."""
    doc = _new_doc()
    doc.modelspace().add_circle(
        (100, 100), radius=10.0, dxfattribs={"layer": "DRILL"}
    )
    geom = _parse_ok(_save(doc, tmp_path))
    circ = next(e for e in geom.entities if e.entity_type == "CIRCLE")
    assert circ.area_mm2 == round(math.pi * 10.0 * 10.0, 4)
    assert circ.perimeter_mm == round(2 * math.pi * 10.0, 4)
    assert circ.diameter_mm == 20.0
    assert circ.radius_mm == 10.0
    assert circ.centroid == [100.0, 100.0]


# ---------------------------------------------------------------------------
# Case 2: Legacy POLYLINE (not LWPOLYLINE)
# ---------------------------------------------------------------------------


def test_case02_legacy_polyline(tmp_path):
    doc = _new_doc()
    msp = doc.modelspace()
    pl = msp.add_polyline2d(
        [(0, 0), (200, 0), (200, 150), (0, 150)],
        dxfattribs={"layer": "CUT"},
    )
    pl.close(True)
    geom = _parse_ok(_save(doc, tmp_path))

    polys = [e for e in geom.entities if e.entity_type == "POLYLINE"]
    assert len(polys) == 1
    p = polys[0]
    assert p.is_closed is True
    assert len(p.coordinates) == 4
    assert p.area_mm2 and math.isclose(p.area_mm2, 200 * 150, rel_tol=1e-3)
    # Closed POLYLINE becomes the detected panel boundary.
    assert geom.panel_boundary is not None
    assert geom.panel_boundary.inferred is False
    _build_mgg(geom)


def test_case02b_legacy_r12_accepted_with_warning(tmp_path):
    """Legacy R12 (AC1009) — a very common CAM/CNC interchange format — must be
    READ (ezdxf supports reading it), not rejected on a version gate. Real shops
    export R12; dropping it silently loses whole files."""
    import ezdxf as _ezdxf
    doc = _ezdxf.new("R12")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    pl = msp.add_polyline2d(
        [(0, 0), (300, 0), (300, 200), (0, 200)], dxfattribs={"layer": "CUT"},
    )
    pl.close(True)
    msp.add_circle((150, 100), radius=2.5, dxfattribs={"layer": "DRILL"})
    p = tmp_path / "legacy.dxf"
    doc.saveas(str(p))

    result = DXFParser().parse(p)
    assert result.success, result.errors  # accepted, not rejected
    assert result.geometry is not None
    assert "legacy_dxf_version" in _warn_codes(result.geometry)
    # Geometry is actually recovered (boundary + the hole).
    assert any(e.entity_type == "CIRCLE" for e in result.geometry.entities)
    assert result.geometry.panel_boundary is not None


# ---------------------------------------------------------------------------
# Case 2c: structurally-broken DXF salvaged via ezdxf.recover
# ---------------------------------------------------------------------------


def test_case02c_structural_error_recovered_with_warning(tmp_path, monkeypatch):
    """Real-world DXFs from assorted CAM/CAD exporters are frequently slightly
    malformed and make strict ezdxf.readfile raise DXFStructureError. ezdxf
    ships a tag-by-tag `recover` reader that salvages them. The parser must
    fall back to it (OMIM only reads) rather than dropping a valid file as
    corrupt. We force the strict path to fail and assert the recover fallback
    extracts geometry and flags it with `recovered_from_corruption`."""
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (300, 0), (300, 200), (0, 200)],
        close=True,
        dxfattribs={"layer": "CUT"},
    )
    msp.add_circle((150, 100), radius=2.5, dxfattribs={"layer": "DRILL"})
    path = _save(doc, tmp_path, name="recoverable.dxf")

    import omim.parser.dxf_parser as parser_mod

    def _boom(*_a, **_k):
        raise ezdxf.DXFStructureError("synthetic structural error")

    monkeypatch.setattr(parser_mod.ezdxf, "readfile", _boom)

    result = DXFParser().parse(path)
    assert result.success, result.errors  # salvaged, not declared corrupt
    assert result.geometry is not None
    assert "recovered_from_corruption" in _warn_codes(result.geometry)
    # Geometry is actually recovered through the fallback path.
    assert any(e.entity_type == "CIRCLE" for e in result.geometry.entities)


def test_case02d_unrecoverable_file_still_reports_corrupt(tmp_path, monkeypatch):
    """If recovery also fails, the parser must still return a clean
    DXF_CORRUPT result (never crash)."""
    path = tmp_path / "garbage.dxf"
    path.write_text("this is not a dxf file at all\n")

    import omim.parser.dxf_parser as parser_mod

    def _boom(*_a, **_k):
        raise ezdxf.DXFStructureError("synthetic structural error")

    # Strict read fails; recover also fails on genuine garbage.
    monkeypatch.setattr(parser_mod.ezdxf, "readfile", _boom)

    result = DXFParser().parse(path)
    assert not result.success
    assert result.errors and result.errors[0].error_code == "DXF_CORRUPT"


# ---------------------------------------------------------------------------
# Case 3: LWPOLYLINE with bulge (arc segments)
# ---------------------------------------------------------------------------


def test_case03_lwpolyline_with_bulge(tmp_path):
    doc = _new_doc()
    msp = doc.modelspace()
    # Rounded rectangle: bulge on first segment encodes an arc.
    msp.add_lwpolyline(
        [
            (0, 0, 0, 0, 0.5),  # bulge 0.5 -> arc to next vertex
            (100, 0, 0, 0, 0),
            (100, 80, 0, 0, 0),
            (0, 80, 0, 0, 0),
        ],
        format="xyseb",
        close=True,
        dxfattribs={"layer": "CUT"},
    )
    geom = _parse_ok(_save(doc, tmp_path))

    lw = [e for e in geom.entities if e.entity_type == "LWPOLYLINE"]
    assert len(lw) == 1
    e = lw[0]
    # Bulge must be flattened to a curve, not chorded: more than 4 vertices.
    assert len(e.coordinates) > 4, "bulge was not flattened"
    assert e.is_approximated is True
    assert e.is_closed is True
    assert e.area_mm2 and e.area_mm2 > 0
    _build_mgg(geom)


def test_case03_lwpolyline_no_bulge_not_approximated(tmp_path):
    """A plain LWPOLYLINE keeps exact vertices and is_approximated=False."""
    doc = _new_doc()
    doc.modelspace().add_lwpolyline(
        [(0, 0), (100, 0), (100, 100), (0, 100)],
        close=True,
        dxfattribs={"layer": "CUT"},
    )
    geom = _parse_ok(_save(doc, tmp_path))
    e = geom.entities[0]
    assert e.is_approximated is False
    assert len(e.coordinates) == 4


# ---------------------------------------------------------------------------
# Case 4: INSERT / block references -> explode to entities
# ---------------------------------------------------------------------------


def test_case04_insert_exploded(tmp_path):
    doc = _new_doc()
    blk = doc.blocks.new(name="HOLE")
    blk.add_circle((0, 0), 2.5)
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (400, 0), (400, 400), (0, 400)],
        close=True,
        dxfattribs={"layer": "BORDER"},
    )
    # Insert the block at three positions (translated to WCS on explode).
    for x in (100, 200, 300):
        msp.add_blockref("HOLE", (x, 200), dxfattribs={"layer": "DRILL"})
    geom = _parse_ok(_save(doc, tmp_path))

    circles = [e for e in geom.entities if e.entity_type == "CIRCLE"]
    assert len(circles) == 3, "INSERTs were not exploded to circles"
    # Circles must be at the insert WCS positions, not block origin.
    centers = sorted(round(c.coordinates[0]) for c in circles)
    assert centers == [100, 200, 300]
    # Inferred layer comes through (DRILL on the insert).
    assert all(c.inferred_layer_type == "drill" for c in circles)
    # Unique deterministic ids (no collisions despite shared block geometry).
    assert len({c.entity_id for c in circles}) == 3
    mgg = _build_mgg(geom)
    # 1 boundary + 3 holes.
    assert mgg.node_count == 4


def test_case04_insert_skip_when_disabled(tmp_path):
    doc = _new_doc()
    blk = doc.blocks.new(name="HOLE")
    blk.add_circle((0, 0), 2.5)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True,
                       dxfattribs={"layer": "BORDER"})
    msp.add_blockref("HOLE", (50, 50))
    geom = _parse_ok(_save(doc, tmp_path),
                     ParserConfig(explode_inserts=False))
    assert not any(e.entity_type == "CIRCLE" for e in geom.entities)
    assert "insert_skipped" in _warn_codes(geom)


def test_case04_nested_insert(tmp_path):
    """Nested blocks explode recursively without crashing."""
    doc = _new_doc()
    inner = doc.blocks.new(name="INNER")
    inner.add_circle((0, 0), 2.5)
    outer = doc.blocks.new(name="OUTER")
    outer.add_blockref("INNER", (10, 0))
    outer.add_blockref("INNER", (-10, 0))
    msp = doc.modelspace()
    msp.add_blockref("OUTER", (100, 100))
    geom = _parse_ok(_save(doc, tmp_path))
    circles = [e for e in geom.entities if e.entity_type == "CIRCLE"]
    assert len(circles) == 2


# ---------------------------------------------------------------------------
# Case 5: ELLIPSE -> approximate, never crash
# ---------------------------------------------------------------------------


def test_case05_ellipse_approximated(tmp_path):
    doc = _new_doc()
    msp = doc.modelspace()
    # Full ellipse, major axis 40mm, ratio 0.5.
    msp.add_ellipse(
        center=(100, 100), major_axis=(40, 0), ratio=0.5,
        start_param=0, end_param=2 * math.pi,
        dxfattribs={"layer": "POCKET"},
    )
    geom = _parse_ok(_save(doc, tmp_path))
    ells = [e for e in geom.entities if e.entity_type == "ELLIPSE"]
    assert len(ells) == 1
    e = ells[0]
    assert e.is_approximated is True
    assert e.is_closed is True
    assert len(e.coordinates) >= 10
    assert e.area_mm2 and e.area_mm2 > 0
    _build_mgg(geom)


# ---------------------------------------------------------------------------
# Case 6: Annotation noise -> skipped gracefully; only-annotations -> A-006
# ---------------------------------------------------------------------------


def test_case06_annotations_skipped_with_geometry(tmp_path):
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True,
                       dxfattribs={"layer": "CUT"})
    msp.add_text("PART A", dxfattribs={"layer": "TEXT"})
    msp.add_mtext("Note: 18mm MDF", dxfattribs={"layer": "TEXT"})
    msp.add_leader([(10, 10), (40, 40)])
    geom = _parse_ok(_save(doc, tmp_path))
    # Geometry kept; annotations skipped with warnings; NOT flagged A-006.
    assert any(e.entity_type == "LWPOLYLINE" for e in geom.entities)
    assert "annotation_skipped" in _warn_codes(geom)
    assert "annotation_only" not in _warn_codes(geom)
    assert "empty_file" not in _warn_codes(geom)


def test_case06_annotation_only_file(tmp_path):
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_text("TITLE BLOCK", dxfattribs={"layer": "TEXT"})
    msp.add_mtext("revision A")
    geom = _parse_ok(_save(doc, tmp_path))
    assert "annotation_only" in _warn_codes(geom)
    assert not any(
        e.entity_type in {"LINE", "CIRCLE", "ARC", "LWPOLYLINE"}
        for e in geom.entities
    )


# ---------------------------------------------------------------------------
# Case 7: Chaotic layer names -> robust prefix match, unknown not crash
# ---------------------------------------------------------------------------


def test_case07_chaotic_layer_names(tmp_path):
    doc = _new_doc()
    msp = doc.modelspace()
    cases = {
        "cut": "cut",                 # lowercase -> cut
        "VONIT_DRILL_5MM": "drill",   # vendor prefix, but starts with V -> unknown
        "DRILL_5MM": "drill",         # real drill prefix
        "Bohrung": "unknown",         # German "drill" -> not in conventions
        "12345": "unknown",           # numeric
        "PoCkEt_A": "pocket",         # mixed case
        "Profile": "cut",
    }
    for layer in cases:
        if layer not in doc.layers:
            doc.layers.add(layer)
        msp.add_circle((10, 10), 2.0, dxfattribs={"layer": layer})
    geom = _parse_ok(_save(doc, tmp_path))

    by_layer = {e.layer: e.inferred_layer_type for e in geom.entities}
    assert by_layer["cut"] == "cut"
    assert by_layer["DRILL_5MM"] == "drill"
    assert by_layer["Bohrung"] == "unknown"
    assert by_layer["12345"] == "unknown"
    assert by_layer["PoCkEt_A"] == "pocket"
    assert by_layer["Profile"] == "cut"
    # VONIT_DRILL_5MM starts with 'V' so prefix-match yields unknown (documented
    # behaviour: prefix, not substring).
    assert by_layer["VONIT_DRILL_5MM"] == "unknown"


# ---------------------------------------------------------------------------
# Case 8: Inch units -> converted to mm with warning
# ---------------------------------------------------------------------------


def test_case08_inch_units_converted(tmp_path):
    doc = _new_doc(insunits=1)  # inches
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True,
                       dxfattribs={"layer": "CUT"})
    msp.add_circle((2, 2), 0.5, dxfattribs={"layer": "DRILL"})
    geom = _parse_ok(_save(doc, tmp_path))
    assert geom.units_original == "inches"
    assert geom.units_normalized_to == "mm"
    assert "units_converted" in _warn_codes(geom)
    circle = next(e for e in geom.entities if e.entity_type == "CIRCLE")
    assert math.isclose(circle.radius_mm, 12.7, abs_tol=0.01)  # 0.5in -> 12.7mm
    # 10in panel -> 254mm bbox.
    assert math.isclose(geom.panel_boundary.bounding_box[2], 254.0, abs_tol=0.1)


# ---------------------------------------------------------------------------
# Case 9: Non-zero Z / elevation -> flatten to XY, never crash
# ---------------------------------------------------------------------------


def test_case09_nonzero_z_flattened(tmp_path):
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_circle((50, 50, 12.0), 2.5, dxfattribs={"layer": "DRILL"})  # z=12
    msp.add_line((0, 0, 5), (100, 100, 5), dxfattribs={"layer": "CUT"})
    geom = _parse_ok(_save(doc, tmp_path))

    circle = next(e for e in geom.entities if e.entity_type == "CIRCLE")
    # Coordinates are flattened: [cx, cy, r] only, centroid is 2D.
    assert len(circle.coordinates) == 3
    assert circle.coordinates[:2] == [50.0, 50.0]
    assert len(circle.centroid) == 2
    line = next(e for e in geom.entities if e.entity_type == "LINE")
    assert all(len(pt) == 2 for pt in line.coordinates)
    _build_mgg(geom)


# ---------------------------------------------------------------------------
# Case 10: Paperspace content -> parse modelspace only, don't crash
# ---------------------------------------------------------------------------


def test_case10_paperspace_ignored(tmp_path):
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True,
                       dxfattribs={"layer": "CUT"})
    # Put a circle in paperspace; it must NOT appear in parsed entities.
    psp = doc.layout("Layout1")
    psp.add_circle((5, 5), 2.5)
    geom = _parse_ok(_save(doc, tmp_path))
    # Only the modelspace polyline parsed.
    assert len(geom.entities) == 1
    assert geom.entities[0].entity_type == "LWPOLYLINE"


# ---------------------------------------------------------------------------
# Case 11: Empty modelspace -> A-005 graceful
# ---------------------------------------------------------------------------


def test_case11_empty_modelspace(tmp_path):
    doc = _new_doc()
    geom = _parse_ok(_save(doc, tmp_path))
    assert geom.entities == []
    assert "empty_file" in _warn_codes(geom)
    assert geom.panel_boundary is None
    # An empty MGG still builds.
    mgg = MGGBuilder().build(geom)
    assert mgg.node_count == 0


# ---------------------------------------------------------------------------
# Case 12: Mixed-bag realistic file with several failure modes together
# ---------------------------------------------------------------------------


def test_case12_mixed_bag(tmp_path):
    doc = _new_doc()
    blk = doc.blocks.new(name="PIN")
    blk.add_circle((0, 0), 2.5)
    msp = doc.modelspace()

    # Outer cut contour (closed LWPOLYLINE) -> panel boundary.
    msp.add_lwpolyline(
        [(0, 0), (600, 0), (600, 400), (0, 400)],
        close=True, dxfattribs={"layer": "CUT"},
    )
    # Legacy polyline pocket.
    pl = msp.add_polyline2d([(50, 50), (150, 50), (150, 120), (50, 120)],
                            dxfattribs={"layer": "POCKET"})
    pl.close(True)
    # Bulged slot.
    msp.add_lwpolyline(
        [(300, 50, 0, 0, 1.0), (340, 50, 0, 0, 1.0)],
        format="xyseb", close=True, dxfattribs={"layer": "SLOT_A"},
    )
    # A decorative spline (engraving).
    msp.add_spline([(400, 300), (450, 350), (500, 300), (550, 350)],
                   dxfattribs={"layer": "ENGRAVE"})
    # An ellipse cutout.
    msp.add_ellipse((500, 100), (30, 0), 0.6, 0, 2 * math.pi,
                    dxfattribs={"layer": "POCKET"})
    # Shelf-pin holes via INSERT.
    for y in (200, 232, 264):
        msp.add_blockref("PIN", (100, y), dxfattribs={"layer": "DRILL"})
    # Annotation noise.
    msp.add_text("PANEL 600x400", dxfattribs={"layer": "TEXT"})
    msp.add_mtext("18mm MDF")
    # 3D line (non-zero Z).
    msp.add_line((10, 380, 4), (590, 380, 4), dxfattribs={"layer": "SCORE"})

    geom = _parse_ok(_save(doc, tmp_path))
    counts = geom.entity_counts
    assert counts.get("LWPOLYLINE", 0) >= 2   # cut contour + bulged slot
    assert counts.get("POLYLINE", 0) == 1
    assert counts.get("SPLINE", 0) == 1
    assert counts.get("ELLIPSE", 0) == 1
    assert counts.get("CIRCLE", 0) == 3       # 3 exploded INSERT pins
    assert counts.get("LINE", 0) == 1

    # Annotations skipped, real geometry kept (not flagged annotation_only).
    assert "annotation_skipped" in _warn_codes(geom)
    assert "annotation_only" not in _warn_codes(geom)

    # Panel boundary detected from the largest closed contour (the cut frame).
    assert geom.panel_boundary is not None
    assert geom.panel_boundary.inferred is False
    assert math.isclose(geom.panel_boundary.area_mm2, 600 * 400, rel_tol=1e-2)

    # Full end-to-end MGG build from the messy file.
    mgg = _build_mgg(geom)
    assert mgg.node_count == len(geom.entities)
    assert mgg.edge_count >= 0


# ---------------------------------------------------------------------------
# Extra robustness: a degenerate spline must not crash the whole parse
# ---------------------------------------------------------------------------


def test_degenerate_entities_do_not_crash(tmp_path):
    doc = _new_doc()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True,
                       dxfattribs={"layer": "CUT"})
    msp.add_circle((50, 50), 0.0, dxfattribs={"layer": "DRILL"})  # zero radius
    geom = _parse_ok(_save(doc, tmp_path))
    assert "degenerate_circle_skipped" in _warn_codes(geom)
    assert not any(
        e.entity_type == "CIRCLE" and e.radius_mm == 0 for e in geom.entities
    )
