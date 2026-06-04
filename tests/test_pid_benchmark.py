"""Tests for the P&ID symbol-classification benchmark (real-annotation path).

Builds a small PID2Graph-style networkx graph whose nodes carry BOTH a human
symbol_class annotation and an ISA tag, and verifies the benchmark scores tag-
derived predictions against the independent annotations. This is the de-
circularized evaluation path: labels (annotation) and predictions (tag parse)
come from different sources.
"""

from __future__ import annotations

import networkx as nx

from omim.domains.pid.benchmark import evaluate_graphml, evaluate_symbol_classification


def _annotated_graph():
    g = nx.Graph()
    # Nodes carry the human-annotated symbol_class AND the tag (independent signals).
    nodes = [
        ("n1", "FT-101", "FLOWRATE_TRANSMIT"),
        ("n2", "PT-205", "PRESSURE_TRANSMIT"),
        ("n3", "LIC-300", "LEVEL_INDICATE_CONTROL"),
        ("n4", "TIC-12", "TEMPERATURE_INDICATE_CONTROL"),
        ("n5", "FIC-101", "FLOWRATE_INDICATE_CONTROL"),
    ]
    for nid, tag, sym in nodes:
        g.add_node(nid, tag=tag, symbol_class=sym)
    g.add_edge("n1", "n5")
    g.add_edge("n5", "n3")
    return g


def test_pid_benchmark_perfect_when_tags_match_annotations():
    g = _annotated_graph()
    res = evaluate_symbol_classification(g)
    assert res.n_scored == 5
    assert res.n_skipped == 0
    assert res.accuracy == 1.0
    assert res.macro_f1_present == 1.0
    assert res.passed is True
    # The two signals are independent sources.
    assert res.label_source == "human_annotation"
    assert res.prediction_source == "isa_5_1_tag_parse"


def test_pid_benchmark_penalises_mismatch():
    g = _annotated_graph()
    # Corrupt one annotation so the tag-derived prediction disagrees.
    g.nodes["n1"]["symbol_class"] = "PRESSURE_TRANSMIT"  # but tag is FT-101 (flow)
    res = evaluate_symbol_classification(g)
    assert res.n_scored == 5
    assert res.accuracy < 1.0


def test_pid_benchmark_skips_unlabelled_nodes():
    g = _annotated_graph()
    g.add_node("x", tag="FT-999")  # tag but no annotation -> skipped
    g.add_node("y", symbol_class="PRESSURE_TRANSMIT")  # annotation but no tag -> skipped
    res = evaluate_symbol_classification(g)
    assert res.n_scored == 5
    assert res.n_skipped == 2


def test_pid_benchmark_empty_graph():
    res = evaluate_symbol_classification(nx.Graph())
    assert res.n_scored == 0
    assert res.passed is False
    assert res.warnings


def test_pid_benchmark_from_graphml(tmp_path):
    g = _annotated_graph()
    path = tmp_path / "pid.graphml"
    nx.write_graphml(g, path)
    res = evaluate_graphml(str(path))
    assert res.n_scored == 5
    assert res.macro_f1_present == 1.0
