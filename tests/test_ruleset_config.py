"""Prove the YAML rule configuration is actually live (was previously ignored).

These tests write a custom data/rules YAML, point a RuleEngine at it, and assert
that (a) editing a threshold changes the verdict, and (b) disabling a rule stops
it running — neither of which was possible when the engine used only hardcoded
defaults.
"""

from __future__ import annotations

import textwrap

from omim.graph.builder import MGGBuilder
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry
from omim.validation.rule_engine import RuleEngine
from omim.validation.ruleset import load_ruleset


def _panel_with_hole_at(cx, cy, dia=5.0):
    panel = [[0, 0], [200, 0], [200, 200], [0, 200]]
    r = dia / 2.0
    ents = [
        RawEntity(
            entity_id="1", ezdxf_handle="h1", entity_type="LWPOLYLINE",
            layer="cut", inferred_layer_type="cut", coordinates=panel,
            is_closed=True, bounding_box=[0, 0, 200, 200], centroid=[100.0, 100.0],
            area_mm2=40000.0, perimeter_mm=800.0,
        ),
        RawEntity(
            entity_id="2", ezdxf_handle="h2", entity_type="CIRCLE",
            layer="drill", inferred_layer_type="drill", coordinates=[cx, cy, r],
            is_closed=True, bounding_box=[cx - r, cy - r, cx + r, cy + r],
            centroid=[cx, cy], area_mm2=3.14159 * r * r, perimeter_mm=2 * 3.14159 * r,
            diameter_mm=dia, radius_mm=r,
        ),
    ]
    raw = RawGeometry(
        source_file="t.dxf", source_file_hash="sha256:t", dxf_version="AC1027",
        entities=ents,
        panel_boundary=PanelBoundary(
            entity_id="1", coordinates=panel, bounding_box=[0, 0, 200, 200],
            area_mm2=40000.0, inferred=False,
        ),
        panel_boundary_inferred=False, entity_counts={},
    )
    return MGGBuilder().build(raw)


def _write_rules(tmp_path, min_edge_clearance_mm, mfg001_enabled=True):
    content = textwrap.dedent(f"""
    version: "test"
    rules:
      - rule_id: "MFG-001"
        name: "minimum_edge_clearance"
        severity: "ERROR"
        applies_to: ["CIRCLE"]
        parameters:
          min_edge_clearance_mm: {min_edge_clearance_mm}
        enabled: {str(mfg001_enabled).lower()}
    """)
    d = tmp_path / "rules"
    d.mkdir(parents=True)
    (d / "layer2.yaml").write_text(content, encoding="utf-8")
    return d


def test_loader_translates_yaml_param_name():
    """The YAML 'min_edge_clearance_mm' maps to the code kwarg 'min_distance_mm'."""
    # (uses the packaged data/rules via a direct load)
    from omim.config import get_settings

    cfgs = load_ruleset(get_settings().rules_dir)
    assert "MFG-001" in cfgs
    assert "min_distance_mm" in cfgs["MFG-001"].params  # translated, not raw name
    assert cfgs["MFG-001"].params["min_distance_mm"] == 8.0


def test_yaml_threshold_changes_verdict(tmp_path):
    """A hole 12mm from the edge passes at 8mm clearance but FAILS at 15mm.

    Proves the YAML threshold is actually applied (not the hardcoded 8mm default).
    """
    mgg = _panel_with_hole_at(12, 100)  # centroid 12mm from left edge

    # Default 8mm clearance -> 12mm is fine -> MFG-001 passes.
    rules_default = _write_rules(tmp_path / "a", 8.0)
    rep1 = RuleEngine(rules_dir=rules_default).validate(mgg, annotate_graph=False)
    mfg001_1 = [r for r in rep1.layer2_results if r.rule_id == "MFG-001"]
    assert mfg001_1 and all(r.passed for r in mfg001_1)

    # Stricter 15mm clearance -> 12mm now violates -> MFG-001 fails.
    rules_strict = _write_rules(tmp_path / "b", 15.0)
    rep2 = RuleEngine(rules_dir=rules_strict).validate(mgg, annotate_graph=False)
    mfg001_2 = [r for r in rep2.layer2_results if r.rule_id == "MFG-001"]
    assert mfg001_2 and any(not r.passed for r in mfg001_2)


def test_disabled_rule_does_not_run(tmp_path):
    """A rule marked enabled: false produces no results at all."""
    mgg = _panel_with_hole_at(2, 100)  # 2mm from edge -> would normally fail MFG-001
    rules = _write_rules(tmp_path / "c", 8.0, mfg001_enabled=False)
    rep = RuleEngine(rules_dir=rules).validate(mgg, annotate_graph=False)
    assert [r for r in rep.layer2_results if r.rule_id == "MFG-001"] == []
