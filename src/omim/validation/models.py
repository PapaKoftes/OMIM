"""Validation result models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationResult(BaseModel):
    """A single rule evaluation result."""

    rule_id: str
    rule_name: str
    severity: Severity
    passed: bool
    message: str
    measured_value: float | None = None
    threshold_value: float | None = None
    applies_to_node_ids: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    """Aggregated validation report for an MGG."""

    graph_id: str
    total_rules_evaluated: int = 0
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    results: list[ValidationResult] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(
            not r.passed and r.severity == Severity.ERROR for r in self.results
        )

    @property
    def error_results(self) -> list[ValidationResult]:
        return [
            r for r in self.results if not r.passed and r.severity == Severity.ERROR
        ]

    @property
    def warning_results(self) -> list[ValidationResult]:
        return [
            r for r in self.results if not r.passed and r.severity == Severity.WARNING
        ]
