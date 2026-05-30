"""Tests for the P&ID domain adapter (ISA-5.1).

Proves the core (graph + provenance + RuleResult contract) is domain-agnostic:
these tests build a P&ID graph, ingest it into the core MGG via graphml, and run
ISA-5.1 rules — with zero panel-specific imports.
"""

from __future__ import annotations

import networkx as nx

from omim.domains.pid import (
    PIDValidationReport,
    ingest_graphml,
    ingest_nx_graph,
    parse_tag,
    validate_pid,
)

# ---------------------------------------------------------------------------
# ISA-5.1 tag grammar
# ---------------------------------------------------------------------------

class TestTagGrammar:
    def test_valid_tags(self):
        for tag, var, funcs in [
            ("FT-101", "F", ["T"]),
            ("TIC-205", "T", ["I", "C"]),
            ("PSV-310", "P", ["S", "V"]),
            ("LAH-120", "L", ["A", "H"]),
        ]:
            p = parse_tag(tag)
            assert p.valid, f"{tag} should be valid: {p.errors}"
            assert p.measured_variable == var
            assert p.function_letters == funcs
            assert p.loop_number == tag.split("-")[1]

    def test_symbol_class_derivation(self):
        assert parse_tag("FT-101").symbol_class.startswith("FLOW")
        assert "CONTROL" in parse_tag("TIC-205").symbol_class

    def test_invalid_tags(self):
        assert not parse_tag("XYZ").valid          # no loop number
        assert not parse_tag("9T-101").valid       # bad pattern
        assert not parse_tag("ÜT-101").valid       # non-letter
        # '2' is not a valid measured-variable letter
        assert not parse_tag("2-101").valid


# ---------------------------------------------------------------------------
# graphml -> MGG ingest (core reuse)
# ---------------------------------------------------------------------------

def _sample_pid_graph(valid=True) -> nx.Graph:
    g = nx.Graph()
    # a complete flow control loop 101: transmitter -> controller -> valve
    g.add_node("n1", tag="FT-101", symbol_class="FLOW_TRANSMITTER")
    g.add_node("n2", tag="FIC-101", symbol_class="FLOW_INDICATING_CONTROLLER")
    g.add_node("n3", tag="FV-101", symbol_class="FLOW_VALVE")
    g.add_edge("n1", "n2", relationship="SIGNALS")
    g.add_edge("n2", "n3", relationship="SIGNALS")
    if not valid:
        g.add_node("n4", tag="ZZZ", symbol_class="UNKNOWN")  # bad tag + isolated
    return g


class TestIngest:
    def test_ingest_builds_core_mgg(self):
        res = ingest_nx_graph(_sample_pid_graph(), source_file="t.graphml")
        assert res.component_count == 3
        assert res.connection_count == 2
        # nodes are core FeatureNodes with ISA symbol classes + HUMAN_ANNOTATED provenance
        node = res.mgg.get_node("n1")
        assert node["feature_class"] == "FLOW_TRANSMITTER"
        assert node["feature_label"] == "FT-101"
        assert node["provenance"]["inference_method"] == "human_annotated"
        assert node["provenance"]["confidence"] == 1.0

    def test_ingest_graphml_roundtrip(self, tmp_path):
        p = tmp_path / "pid.graphml"
        nx.write_graphml(_sample_pid_graph(), p)
        res = ingest_graphml(str(p))
        assert res.component_count == 3
        assert res.connection_count == 2


# ---------------------------------------------------------------------------
# ISA-5.1 validation rule families
# ---------------------------------------------------------------------------

class TestValidation:
    def test_clean_pid_passes(self):
        res = ingest_nx_graph(_sample_pid_graph(valid=True))
        report = validate_pid(res.mgg)
        assert isinstance(report, PIDValidationReport)
        assert report.overall_valid
        assert report.severity_summary == {}

    def test_bad_tag_and_isolated_are_caught(self):
        res = ingest_nx_graph(_sample_pid_graph(valid=False))
        report = validate_pid(res.mgg)
        assert not report.overall_valid  # ERRORs present
        failed = {r.rule_id for r in report.all_results if not r.passed}
        assert "PID-TAG-001" in failed       # ZZZ is not a valid ISA tag
        assert "PID-CONN-001" in failed       # n4 is isolated

    def test_loop_incompleteness_warns(self):
        # loop 200 has a controller but no transmitter/valve
        g = nx.Graph()
        g.add_node("c", tag="TIC-200", symbol_class="TEMP_CONTROLLER")
        g.add_node("x", tag="TI-200", symbol_class="TEMP_INDICATOR")
        g.add_edge("c", "x", relationship="SIGNALS")
        report = validate_pid(ingest_nx_graph(g).mgg)
        loop_fail = [r for r in report.loop_results if not r.passed]
        assert loop_fail and loop_fail[0].rule_id == "PID-LOOP-001"
        assert loop_fail[0].severity == "WARNING"

    def test_results_are_core_ruleresults(self):
        """The PID report reuses the domain-agnostic RuleResult contract."""
        from omim.validation.models import RuleResult
        report = validate_pid(ingest_nx_graph(_sample_pid_graph()).mgg)
        assert all(isinstance(r, RuleResult) for r in report.all_results)


class TestCoreIsDomainAgnostic:
    def test_pid_uses_core_graph_integrity(self):
        """check_graph_integrity (core) runs on a P&ID MGG without panel context."""
        from omim.integrity import check_graph_integrity
        res = ingest_nx_graph(_sample_pid_graph())
        violations = check_graph_integrity(res.mgg)
        # No dangling edges / self-loops / bad confidence in a clean ingest.
        assert not any("DANGLING" in v or "SELF_LOOP" in v for v in violations)
