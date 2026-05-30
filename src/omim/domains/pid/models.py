"""P&ID validation report — aggregates the core RuleResult contract.

Reuses ``omim.validation.models.RuleResult`` (the domain-agnostic unit) so the
validation *contract* is shared with the panel domain; only the aggregation
framing (tag / connectivity / loop families instead of geometric layer1/layer2)
is P&ID-specific.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from omim.validation.models import RuleResult


class PIDValidationReport(BaseModel):
    """ISA-5.1 compliance report for a single P&ID graph."""

    graph_id: str
    ruleset_version: str = "v0.1.0"
    standard: str = "ANSI/ISA-5.1-2024"

    tag_results: list[RuleResult] = Field(default_factory=list)
    connectivity_results: list[RuleResult] = Field(default_factory=list)
    loop_results: list[RuleResult] = Field(default_factory=list)

    @property
    def all_results(self) -> list[RuleResult]:
        return self.tag_results + self.connectivity_results + self.loop_results

    @property
    def overall_valid(self) -> bool:
        return not any(
            (not r.passed) and r.severity == "ERROR" for r in self.all_results
        )

    @property
    def severity_summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.all_results:
            if not r.passed:
                out[r.severity] = out.get(r.severity, 0) + 1
        return out
