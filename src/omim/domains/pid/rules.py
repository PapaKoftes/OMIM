"""P&ID deterministic rule families (ISA-5.1), reusing the core RuleResult.

Three families, mirroring the panel engine's YAML-defined + handler-dispatched
pattern (see 05_VALIDATION/Rule_Engine):

  PID-TAG-*   tag grammar         (string grammar — like panel diameter checks)
  PID-CONN-*  connectivity        (graph topology — NEW kind: dangling/isolated)
  PID-LOOP-*  control-loop checks (graph grouping — controller needs T + final element)

Every check returns a core ``omim.validation.models.RuleResult`` so the contract
is shared with the panel domain. Rules are deterministic (no randomness, sorted
iteration) and standards-cited.
"""

from __future__ import annotations

from omim.domains.pid.isa_ontology import (
    CONTROLLER_LETTER,
    FINAL_ELEMENT_LETTERS,
    TRANSMITTER_LETTER,
    parse_tag,
)
from omim.domains.pid.models import PIDValidationReport
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.validation.models import RuleResult

# Standards-cited rule metadata (the panel domain keeps this in YAML; kept inline
# here for the v0 stub — see data/pid/pid_rules.yaml for the externalized copy).
_ISA = "ANSI/ISA-5.1-2024"
_CEILING = 0.95  # standards_derived


def _result(rule_id, name, passed, severity, message, nodes=None, **kw) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_name=name,
        passed=passed,
        severity=severity if not passed else "PASS",
        message=message,
        affected_node_ids=sorted(nodes or []),
        confidence=_CEILING,
        **kw,
    )


def _components(mgg: ManufacturingGeometryGraph):
    """Yield (node_id, data) for component (feature) nodes, sorted for determinism."""
    return sorted(mgg.feature_nodes(), key=lambda nv: nv[0])


# ---------------------------------------------------------------------------
# PID-TAG: tag grammar
# ---------------------------------------------------------------------------

def check_tag_grammar(mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
    """PID-TAG-001: every tagged component carries a valid ISA-5.1 tag."""
    results: list[RuleResult] = []
    for nid, data in _components(mgg):
        tag = data.get("feature_label") or ""
        if not tag:
            continue  # untagged graphical element (e.g. a line) — not a tag violation
        parsed = parse_tag(tag)
        if not parsed.valid:
            results.append(_result(
                "PID-TAG-001", "Valid ISA-5.1 tag grammar", False, "ERROR",
                f"'{tag}' is not a valid ISA-5.1 tag: {'; '.join(parsed.errors or [])}",
                nodes=[nid],
            ))
    if not results:
        results.append(_result("PID-TAG-001", "Valid ISA-5.1 tag grammar", True, "PASS",
                               "all component tags conform to ISA-5.1"))
    return results


# ---------------------------------------------------------------------------
# PID-CONN: connectivity / topology
# ---------------------------------------------------------------------------

def check_connectivity(mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
    """PID-CONN-001: no isolated components (every component connects to >=1 other)."""
    g = mgg.graph
    results: list[RuleResult] = []
    isolated = [
        nid for nid, _ in _components(mgg)
        if (g.degree(nid) if nid in g else 0) == 0
    ]
    for nid in isolated:
        results.append(_result(
            "PID-CONN-001", "No isolated component", False, "ERROR",
            f"component '{nid}' has no connections (dangling/floating in the P&ID)",
            nodes=[nid],
        ))
    if not results:
        results.append(_result("PID-CONN-001", "No isolated component", True, "PASS",
                               "every component is connected"))
    return results


# ---------------------------------------------------------------------------
# PID-LOOP: control-loop completeness
# ---------------------------------------------------------------------------

def check_loop_completeness(mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
    """PID-LOOP-001: a loop containing a controller should also contain a
    measurement (transmitter/sensor) and a final control element (valve)."""
    # Group components by loop number (group_id), parsing functions from the tag.
    loops: dict[str, dict[str, set[str]]] = {}
    for nid, data in _components(mgg):
        loop = data.get("group_id")
        tag = data.get("feature_label") or ""
        if not loop or not tag:
            continue
        parsed = parse_tag(tag)
        if not parsed.valid:
            continue
        funcs = set(parsed.function_letters or [])
        entry = loops.setdefault(loop, {"controller": set(), "measure": set(), "final": set()})
        if CONTROLLER_LETTER in funcs:
            entry["controller"].add(nid)
        if TRANSMITTER_LETTER in funcs:
            entry["measure"].add(nid)
        if funcs & FINAL_ELEMENT_LETTERS:
            entry["final"].add(nid)

    results: list[RuleResult] = []
    for loop in sorted(loops):
        e = loops[loop]
        if e["controller"] and not (e["measure"] and e["final"]):
            missing = []
            if not e["measure"]:
                missing.append("measurement (transmitter)")
            if not e["final"]:
                missing.append("final control element (valve)")
            results.append(_result(
                "PID-LOOP-001", "Control loop completeness", False, "WARNING",
                f"loop {loop} has a controller but is missing: {', '.join(missing)}",
                nodes=sorted(e["controller"]),
            ))
    if not results:
        results.append(_result("PID-LOOP-001", "Control loop completeness", True, "PASS",
                               "all controller loops have measurement + final element"))
    return results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def validate_pid(mgg: ManufacturingGeometryGraph) -> PIDValidationReport:
    """Run all ISA-5.1 rule families; return a PIDValidationReport."""
    return PIDValidationReport(
        graph_id=mgg.metadata.graph_id,
        standard=_ISA,
        tag_results=check_tag_grammar(mgg),
        connectivity_results=check_connectivity(mgg),
        loop_results=check_loop_completeness(mgg),
    )
