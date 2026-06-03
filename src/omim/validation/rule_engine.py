"""Validation rule engine — runs Layer 1 (geometric) and Layer 2 (manufacturing)
rules against an MGG, producing a ValidationReport per spec."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.graph.models import ConstraintNode, EdgeType
from omim.provenance.models import InferenceMethod, ProvenanceRecord
from omim.validation.geometric_rules import GEOMETRIC_HANDLERS
from omim.validation.manufacturing_rules import MANUFACTURING_HANDLERS
from omim.validation.models import RuleResult, ValidationReport
from omim.validation.ruleset import RuleConfig, load_ruleset

logger = logging.getLogger(__name__)


class RuleEngine:
    """Run Layer 1 (GEO-001..GEO-008) and Layer 2 (MFG-001..MFG-012) rules,
    returning a ValidationReport and optionally annotating the MGG.

    Rule thresholds are data-driven: when *rules_dir* is given (or the packaged
    ``data/rules`` directory exists), each rule's parameters/enabled flag are
    loaded from YAML and passed to the rule function. Without a config, rules run
    with their hardcoded defaults (unchanged behaviour).
    """

    def __init__(self, rules_dir: str | Path | None = None) -> None:
        # Handler registry mapping rule_id -> function
        self._handlers: dict[str, object] = {}
        self._handlers.update(GEOMETRIC_HANDLERS)
        self._handlers.update(MANUFACTURING_HANDLERS)

        # Load YAML rule configuration (thresholds + enabled). Default to the
        # packaged data/rules dir; fall back silently to hardcoded defaults.
        if rules_dir is None:
            try:
                from omim.config import get_settings
                candidate = get_settings().rules_dir
                rules_dir = candidate if Path(candidate).is_dir() else None
            except Exception:  # noqa: BLE001 — config is optional
                rules_dir = None
        self._rule_configs: dict[str, RuleConfig] = (
            load_ruleset(rules_dir) if rules_dir is not None else {}
        )

    # ------------------------------------------------------------------
    # Layer execution
    # ------------------------------------------------------------------

    def _run_handlers(
        self,
        mgg: ManufacturingGeometryGraph,
        handlers: dict[str, object],
    ) -> list[RuleResult]:
        """Run each handler sorted by rule_id, timing the whole rule once.

        The per-rule ``execution_time_ms`` is measured here, at the engine level,
        and stamped onto every RuleResult the handler returns. This fixes a
        long-standing bug where each rule recomputed ``elapsed`` inside individual
        violation branches, so a multi-violation rule reported a different,
        cumulative time per finding instead of the rule's true wall-clock cost.
        """
        results: list[RuleResult] = []
        for rule_id in sorted(handlers.keys()):
            config = self._rule_configs.get(rule_id)
            if config is not None and not config.enabled:
                logger.debug("Rule %s disabled in config; skipping", rule_id)
                continue
            handler = handlers[rule_id]
            params = config.params if config is not None else {}
            t0 = time.perf_counter()
            try:
                rule_results = handler(mgg, **params)
                elapsed = (time.perf_counter() - t0) * 1000
                for r in rule_results:
                    r.execution_time_ms = elapsed
                results.extend(rule_results)
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                logger.exception("Rule %s raised an exception", rule_id)
                results.append(RuleResult(
                    rule_id=rule_id,
                    rule_name=rule_id,
                    passed=False,
                    severity="SYSTEM_ERROR",
                    message=f"Rule {rule_id} raised an exception: {exc}",
                    execution_time_ms=elapsed,
                ))
        return results

    def execute_layer1(self, mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
        """Run GEO-001 to GEO-008 sorted by rule_id."""
        return self._run_handlers(mgg, GEOMETRIC_HANDLERS)

    def execute_layer2(self, mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
        """Run MFG-001 to MFG-012 sorted by rule_id. NO access to semantic layer."""
        return self._run_handlers(mgg, MANUFACTURING_HANDLERS)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def validate(
        self,
        mgg: ManufacturingGeometryGraph,
        *,
        annotate_graph: bool = True,
    ) -> ValidationReport:
        """Execute all validation rules.

        1. Run Layer 1 (geometric)
        2. If Layer 1 has ERRORs, skip Layer 2
        3. Build ValidationReport with layer1_passed, layer2_passed,
           overall_valid, severity_summary, failed_node_ids
        4. If annotate_graph, add ConstraintNode + APPLIES_TO edges for failures
        """
        t0 = time.perf_counter()

        # --- Layer 1 ---
        layer1_results = self.execute_layer1(mgg)
        layer1_has_errors = any(
            r.severity == "ERROR" and not r.passed for r in layer1_results
        )
        layer1_passed = not layer1_has_errors

        # --- Layer 2 (only if Layer 1 passes) ---
        layer2_results: list[RuleResult] = []
        if layer1_passed:
            layer2_results = self.execute_layer2(mgg)

        layer2_has_errors = any(
            r.severity == "ERROR" and not r.passed for r in layer2_results
        )
        layer2_passed = not layer2_has_errors

        # --- Build severity summary ---
        all_results = layer1_results + layer2_results
        severity_summary = {"ERROR": 0, "WARNING": 0, "INFO": 0, "SYSTEM_ERROR": 0}
        for r in all_results:
            if not r.passed and r.severity in severity_summary:
                severity_summary[r.severity] += 1

        # --- overall_valid: True iff ALL ERROR rules pass ---
        overall_valid = severity_summary["ERROR"] == 0 and severity_summary["SYSTEM_ERROR"] == 0

        # --- has_warnings ---
        has_warnings = severity_summary["WARNING"] > 0

        # --- failed_node_ids ---
        failed_node_ids: list[str] = []
        seen: set[str] = set()
        for r in all_results:
            if not r.passed:
                for nid in r.affected_node_ids:
                    if nid not in seen:
                        failed_node_ids.append(nid)
                        seen.add(nid)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # --- Provenance ---
        report_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        provenance = ProvenanceRecord(
            record_id=str(uuid.uuid4()),
            timestamp=now,
            generator="omim",
            generator_version="v0.1.0",
            pipeline_stage="validation",
            module="omim.validation.rule_engine",
            inference_method=InferenceMethod.DETERMINISTIC,
            confidence=1.0,
            confidence_method="deterministic_rule_evaluation",
        )

        report = ValidationReport(
            report_id=report_id,
            graph_id=mgg.metadata.graph_id,
            timestamp=now,
            ruleset_version="v0.1.0",
            layer1_passed=layer1_passed,
            layer2_passed=layer2_passed,
            overall_valid=overall_valid,
            has_warnings=has_warnings,
            severity_summary=severity_summary,
            layer1_results=layer1_results,
            layer2_results=layer2_results,
            failed_node_ids=failed_node_ids,
            provenance=provenance,
            validation_time_ms=elapsed_ms,
        )

        # --- Annotate graph ---
        if annotate_graph:
            self._annotate_mgg(mgg, all_results)

        logger.info(
            "Validation complete: layer1=%s, layer2=%s, overall=%s, "
            "errors=%d, warnings=%d, time=%.1fms",
            layer1_passed,
            layer2_passed,
            overall_valid,
            severity_summary["ERROR"],
            severity_summary["WARNING"],
            elapsed_ms,
        )

        return report

    # ------------------------------------------------------------------
    # Graph annotation
    # ------------------------------------------------------------------

    def _annotate_mgg(
        self,
        mgg: ManufacturingGeometryGraph,
        results: list[RuleResult],
    ) -> None:
        """Inject ConstraintNode + APPLIES_TO edges for failed results."""
        constraint_idx = 0
        for result in results:
            if result.passed:
                continue

            constraint_id = f"constraint-{result.rule_id}-{constraint_idx}"
            constraint_idx += 1

            node = ConstraintNode(
                node_id=constraint_id,
                constraint_type=result.rule_id,
                rule_id=result.rule_id,
                is_violated=True,
                violation_severity=result.severity,
                message=result.message,
                applies_to_node_ids=result.affected_node_ids,
            )
            mgg.add_constraint_node(node)

            # Link each affected node to the constraint via APPLIES_TO
            for affected_id in result.affected_node_ids:
                if mgg.has_node(affected_id):
                    mgg.add_edge(
                        constraint_id,
                        affected_id,
                        EdgeType.APPLIES_TO,
                    )
