"""Validation result models — matches 02_SCHEMA/Validation_Report_Schema.md
and 05_VALIDATION/Rule_Engine.md."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from omim.provenance.models import ProvenanceRecord


class Rule(BaseModel):
    """A validation rule loaded from YAML."""

    rule_id: str
    version: str = "v0.1.0"
    name: str
    category: str  # "geometric" | "manufacturability"
    layer: Literal[1, 2]
    rule_type: Literal[
        "geometric",
        "standards_derived",
        "hardware_spec",
        "shop_convention",
        "material_heuristic",
        "machine_heuristic",
    ]
    severity: Literal["ERROR", "WARNING", "INFO"]
    applies_to: list[str] = Field(default_factory=list)
    parameters: dict = Field(default_factory=dict)
    description: str = ""
    source: str = ""
    confidence_ceiling: float = 1.0
    domain_applicability: dict | None = None
    standards_refs: list[dict] | None = None
    adjustable: bool = False
    expert_reviewed: bool = False
    status: Literal["active", "draft", "deprecated"] = "active"
    added_in_version: str = "v0.1.0"
    enabled: bool = True


class RuleResult(BaseModel):
    """Result of evaluating a single rule."""

    rule_id: str
    rule_version: str = "v0.1.0"
    rule_name: str
    passed: bool
    severity: str  # "ERROR" | "WARNING" | "INFO" | "PASS" | "SYSTEM_ERROR"
    message: str
    affected_node_ids: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)  # rule-specific measurements
    execution_time_ms: float = 0.0
    measured_value: float | None = None
    threshold_value: float | None = None
    confidence: float = 1.0
    provenance: ProvenanceRecord | None = None


class ValidationReport(BaseModel):
    """Aggregated validation report per spec."""

    report_id: str
    graph_id: str
    timestamp: str = ""
    ruleset_version: str = "v0.1.0"

    layer1_passed: bool = True
    layer2_passed: bool = True
    overall_valid: bool = True  # True iff ALL ERROR rules pass
    has_warnings: bool = False
    severity_summary: dict = Field(
        default_factory=lambda: {"ERROR": 0, "WARNING": 0, "INFO": 0, "SYSTEM_ERROR": 0}
    )

    layer1_results: list[RuleResult] = Field(default_factory=list)
    layer2_results: list[RuleResult] = Field(default_factory=list)
    failed_node_ids: list[str] = Field(default_factory=list)

    provenance: ProvenanceRecord | None = None
    validation_time_ms: float = 0.0
