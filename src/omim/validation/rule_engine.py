"""Validation rule engine — runs all rules against an MGG."""

from __future__ import annotations

import logging

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.graph.models import ConstraintNode, EdgeType
from omim.validation.geometric_rules import GEOMETRIC_RULES
from omim.validation.manufacturing_rules import MANUFACTURING_RULES
from omim.validation.models import Severity, ValidationReport, ValidationResult

logger = logging.getLogger(__name__)


class RuleEngine:
    """Run geometric and manufacturing rules, returning a ValidationReport
    and optionally annotating the MGG with ConstraintNode violations."""

    def validate(
        self,
        mgg: ManufacturingGeometryGraph,
        *,
        annotate_graph: bool = True,
    ) -> ValidationReport:
        """Execute all registered rules.

        If *annotate_graph* is True, failed rules create ConstraintNode
        entries connected via VIOLATES edges.
        """
        all_results: list[ValidationResult] = []

        # Run geometric rules
        for rule_fn in GEOMETRIC_RULES:
            try:
                results = rule_fn(mgg)
                all_results.extend(results)
            except Exception:
                logger.exception("Rule %s raised an exception", rule_fn.__name__)

        # Run manufacturing rules
        for rule_fn in MANUFACTURING_RULES:
            try:
                results = rule_fn(mgg)
                all_results.extend(results)
            except Exception:
                logger.exception("Rule %s raised an exception", rule_fn.__name__)

        # Build report
        passed = sum(1 for r in all_results if r.passed)
        failed = sum(1 for r in all_results if not r.passed and r.severity == Severity.ERROR)
        warnings = sum(1 for r in all_results if not r.passed and r.severity == Severity.WARNING)

        report = ValidationReport(
            graph_id=mgg.metadata.graph_id,
            total_rules_evaluated=len(all_results),
            passed=passed,
            failed=failed,
            warnings=warnings,
            results=all_results,
        )

        # Annotate the graph
        if annotate_graph:
            self._annotate_mgg(mgg, all_results)

        logger.info(
            "Validation complete: %d passed, %d errors, %d warnings",
            passed,
            failed,
            warnings,
        )

        return report

    def _annotate_mgg(
        self,
        mgg: ManufacturingGeometryGraph,
        results: list[ValidationResult],
    ) -> None:
        """Inject ConstraintNode + VIOLATES edges for failed results."""
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
                severity=result.severity.value,
                message=result.message,
                measured_value=result.measured_value,
                threshold_value=result.threshold_value,
                applies_to_node_ids=result.applies_to_node_ids,
            )
            mgg.add_constraint_node(node)

            # Link each affected node to the constraint
            for affected_id in result.applies_to_node_ids:
                if mgg.has_node(affected_id):
                    mgg.add_edge(
                        affected_id,
                        constraint_id,
                        EdgeType.VIOLATES,
                    )
