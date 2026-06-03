"""P&ID symbol-classification benchmark on REAL annotated data (PID2Graph-style).

This is the de-circularization win the panel domain cannot have: the ground-truth
symbol classes are *human annotations* carried on the graphml nodes, while the
"model under test" predicts the symbol class independently from the ISA-5.1 tag
string (:func:`parse_tag`). Labels and predictions come from different sources, so
a good score is real evidence — not the panel domain's generate-from-catalog /
validate-against-catalog tautology.

Works on any networkx P&ID graph whose nodes carry both a tag and a
human-annotated symbol class. Reuses the existing numpy metric implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from omim.benchmarks.metrics import accuracy, macro_f1, macro_f1_present
from omim.domains.pid.ingest import FieldMap, _first_attr
from omim.domains.pid.isa_ontology import parse_tag


@dataclass
class PIDBenchmarkResult:
    """Result of the P&ID symbol-classification benchmark."""

    task_id: str = "BENCH-PID-001"
    name: str = "P&ID Symbol Classification (real annotated graph)"
    n_scored: int = 0
    n_skipped: int = 0
    accuracy: float = 0.0
    macro_f1: float = 0.0
    macro_f1_present: float = 0.0
    pass_threshold: float = 0.80
    passed: bool = False
    label_source: str = "human_annotation"
    prediction_source: str = "isa_5_1_tag_parse"
    warnings: list[str] = field(default_factory=list)


def evaluate_symbol_classification(
    g: nx.Graph,
    field_map: FieldMap | None = None,
    pass_threshold: float = 0.80,
) -> PIDBenchmarkResult:
    """Score ISA-5.1 tag-based symbol prediction against human-annotated classes.

    For each node carrying BOTH a human ``symbol_class`` annotation and a ``tag``,
    predict the class from the tag via :func:`parse_tag` and compare. Nodes
    missing either field are skipped (and counted).
    """
    fm = field_map or FieldMap()
    y_true: list[str] = []
    y_pred: list[str] = []
    skipped = 0

    for _nid, data in g.nodes(data=True):
        truth = _first_attr(data, fm.symbol_attrs)
        tag = _first_attr(data, fm.tag_attrs)
        if not truth or not tag:
            skipped += 1
            continue
        parsed = parse_tag(tag)
        pred = parsed.symbol_class if parsed.valid else "UNKNOWN_INSTRUMENT"
        y_true.append(truth)
        y_pred.append(pred)

    result = PIDBenchmarkResult(n_scored=len(y_true), n_skipped=skipped,
                               pass_threshold=pass_threshold)
    if not y_true:
        result.warnings.append("no nodes carried both a tag and a symbol_class label")
        return result

    result.accuracy = round(accuracy(y_true, y_pred), 4)
    result.macro_f1 = round(macro_f1(y_true, y_pred), 4)
    result.macro_f1_present = round(macro_f1_present(y_true, y_pred), 4)
    result.passed = result.macro_f1_present >= pass_threshold
    return result


def evaluate_graphml(
    path: str,
    field_map: FieldMap | None = None,
    pass_threshold: float = 0.80,
) -> PIDBenchmarkResult:
    """Convenience: load a `.graphml` P&ID and run the symbol-classification benchmark."""
    g = nx.read_graphml(path)
    return evaluate_symbol_classification(g, field_map=field_map, pass_threshold=pass_threshold)
