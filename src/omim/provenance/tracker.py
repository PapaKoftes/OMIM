"""Provenance tracker — records why each inference decision was made.

Every FeatureNode classification and every ConstraintNode violation carries
a provenance record explaining the rule, method, and inputs used.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class InferenceMethod(str, Enum):
    DETERMINISTIC = "deterministic"
    HEURISTIC = "heuristic"
    ML_GNN = "ml_gnn"
    LLM_ADVISORY = "llm_advisory"


class ProvenanceRecord(BaseModel):
    """Immutable record of an inference decision."""

    record_id: str
    timestamp: str = ""
    node_id: str  # The node this record explains
    method: InferenceMethod
    rule_id: str = ""  # e.g., "DIAMETER_LOOKUP" or "MFG-001"
    inputs: dict = Field(default_factory=dict)  # What data was used
    output: dict = Field(default_factory=dict)  # What was decided
    confidence: float = 0.0
    parent_record_id: str | None = None  # Chain of derivations

    def model_post_init(self, __context) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class ProvenanceTracker:
    """Collects provenance records for an MGG processing run."""

    def __init__(self) -> None:
        self._records: list[ProvenanceRecord] = []
        self._counter = 0

    def record(
        self,
        node_id: str,
        method: InferenceMethod,
        rule_id: str = "",
        inputs: dict | None = None,
        output: dict | None = None,
        confidence: float = 0.0,
        parent_record_id: str | None = None,
    ) -> ProvenanceRecord:
        self._counter += 1
        rec = ProvenanceRecord(
            record_id=f"prov-{self._counter:04d}",
            node_id=node_id,
            method=method,
            rule_id=rule_id,
            inputs=inputs or {},
            output=output or {},
            confidence=confidence,
            parent_record_id=parent_record_id,
        )
        self._records.append(rec)
        return rec

    @property
    def records(self) -> list[ProvenanceRecord]:
        return list(self._records)

    def records_for_node(self, node_id: str) -> list[ProvenanceRecord]:
        return [r for r in self._records if r.node_id == node_id]

    def to_dict(self) -> list[dict]:
        return [r.model_dump() for r in self._records]
