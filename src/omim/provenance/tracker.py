"""ProvenanceTracker — context manager that creates ProvenanceRecords.

Spec: 08_PROVENANCE_AND_CONFIDENCE/Provenance_System.md
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from omim.provenance.models import (
    EvidenceItem,
    InferenceMethod,
    ProvenanceRecord,
    ReviewStatus,
)

OMIM_VERSION = "v0.1.0"


class ProvenanceTracker:
    """Context manager that creates ProvenanceRecords for pipeline stages.

    Usage::

        with ProvenanceTracker(
            stage="semantic",
            module="omim.semantic.classifier",
            source_file="geometry.dxf",
            source_file_hash="sha256:abc123...",
        ) as tracker:
            record = tracker.create_record(
                inference_method=InferenceMethod.HEURISTIC,
                confidence=0.88,
                evidence=[...],
                source_entity_ids=["geom-123"],
            )
    """

    def __init__(
        self,
        stage: str,
        module: str = "",
        source_file: str | None = None,
        source_file_hash: str | None = None,
        ontology_version: str = "v0.1.0",
        ruleset_version: str = "v0.1.0",
    ) -> None:
        self.stage = stage
        self.module = module
        self.source_file = source_file
        self.source_file_hash = source_file_hash
        self.ontology_version = ontology_version
        self.ruleset_version = ruleset_version
        self._records: list[ProvenanceRecord] = []
        self._start_time: datetime | None = None
        self._duration_ms: float | None = None

    def __enter__(self) -> ProvenanceTracker:
        self._start_time = datetime.now(UTC)
        return self

    def __exit__(self, *args) -> None:
        if self._start_time:
            elapsed = datetime.now(UTC) - self._start_time
            self._duration_ms = elapsed.total_seconds() * 1000

    def create_record(
        self,
        inference_method: InferenceMethod,
        confidence: float,
        evidence: list[EvidenceItem] | None = None,
        source_entity_ids: list[str] | None = None,
        parent_record_ids: list[str] | None = None,
        confidence_method: str = "",
    ) -> ProvenanceRecord:
        if not confidence_method:
            confidence_method = self._infer_confidence_method(inference_method)

        record = ProvenanceRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            generator="omim",
            generator_version=OMIM_VERSION,
            pipeline_stage=self.stage,
            module=self.module,
            ontology_version=self.ontology_version,
            ruleset_version=self.ruleset_version,
            inference_method=inference_method,
            confidence=confidence,
            confidence_method=confidence_method,
            evidence=evidence or [],
            source_file=self.source_file,
            source_file_hash=self.source_file_hash,
            source_entity_ids=source_entity_ids or [],
            parent_record_ids=parent_record_ids or [],
            review_status=ReviewStatus.UNREVIEWED,
        )
        self._records.append(record)
        return record

    @staticmethod
    def _infer_confidence_method(inference_method: InferenceMethod) -> str:
        return {
            InferenceMethod.DETERMINISTIC: "geometric_computation",
            InferenceMethod.HEURISTIC: "diameter_pattern_matching",
            InferenceMethod.SEMANTIC: "feature_classification",
            InferenceMethod.ML_GNN: "softmax_probability",
            InferenceMethod.ML_LLM: "llm_advisory",
            InferenceMethod.SYNTHETIC: "generation_ground_truth",
            InferenceMethod.HUMAN_ANNOTATED: "expert_annotation",
        }.get(inference_method, "unknown")

    @property
    def records(self) -> list[ProvenanceRecord]:
        return list(self._records)

    def records_for_node(self, node_id: str) -> list[ProvenanceRecord]:
        return [
            r for r in self._records if node_id in r.source_entity_ids
        ]

    def get_summary(self) -> dict:
        return {
            "stage": self.stage,
            "total_records": len(self._records),
            "duration_ms": self._duration_ms,
            "methods_used": list({r.inference_method.value for r in self._records}),
            "confidence_range": (
                min(r.confidence for r in self._records),
                max(r.confidence for r in self._records),
            )
            if self._records
            else (None, None),
        }

    def to_dict(self) -> list[dict]:
        return [r.model_dump() for r in self._records]
