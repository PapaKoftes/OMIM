"""Provenance schema models — exact spec from 02_SCHEMA/Provenance_Schema.md."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class InferenceMethod(str, Enum):
    """Authority levels: DETERMINISTIC=L1-3, HEURISTIC=L4, SEMANTIC=L5, ML_GNN=L6."""

    DETERMINISTIC = "deterministic"
    HEURISTIC = "heuristic"
    SEMANTIC = "semantic"
    ML_GNN = "ml_gnn"
    ML_LLM = "ml_llm"
    SYNTHETIC = "synthetic"
    HUMAN_ANNOTATED = "human_annotated"


AUTHORITY_LEVELS = {
    InferenceMethod.DETERMINISTIC: 1,
    InferenceMethod.SYNTHETIC: 1,
    InferenceMethod.HUMAN_ANNOTATED: 3,
    InferenceMethod.HEURISTIC: 4,
    InferenceMethod.SEMANTIC: 5,
    InferenceMethod.ML_GNN: 6,
    InferenceMethod.ML_LLM: 6,
}


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    AUTO_VALIDATED = "auto_validated"
    EXPERT_REVIEWED = "expert_reviewed"
    FLAGGED = "flagged"


class EvidenceType(str, Enum):
    GEOMETRIC_MEASUREMENT = "geometric_measurement"
    RULE_MATCH = "rule_match"
    PATTERN_MATCH = "pattern_match"
    PROXIMITY = "proximity"
    LAYER_CONVENTION = "layer_convention"
    DIAMETER_MATCH = "diameter_match"
    SPACING_MATCH = "spacing_match"
    GROUP_DETECTION = "group_detection"
    ML_EMBEDDING = "ml_embedding"


class EvidenceItem(BaseModel):
    """A single piece of evidence supporting an inference decision."""

    evidence_type: EvidenceType
    description: str
    value: float | str | None = None
    expected: float | str | None = None
    unit: str | None = None  # "mm" | "mm2" | "degrees" | "count"
    rule_id: str | None = None
    node_id: str | None = None
    weight: float = 1.0
    satisfied: bool = True


class ProvenanceRecord(BaseModel):
    """Universal metadata attached to every node, edge, and output in OMIM.

    Spec: 02_SCHEMA/Provenance_Schema.md
    """

    record_id: str  # UUID
    timestamp: str = ""  # ISO 8601 UTC

    # System identity
    generator: str = "omim"
    generator_version: str = "v0.1.0"
    pipeline_stage: str = ""  # "parser" | "graph_builder" | "validation" | "semantic" | "synthetic"
    module: str = ""  # e.g., "omim.semantic.classifier"

    # Version references
    ontology_version: str = "v0.1.0"
    ruleset_version: str = "v0.1.0"

    # Inference method
    inference_method: InferenceMethod

    # Confidence
    confidence: float  # [0.0, 1.0]
    confidence_method: str = ""  # how confidence was computed

    # Evidence — REQUIRED, not Optional
    evidence: list[EvidenceItem] = Field(default_factory=list)

    # Source tracing
    source_file: str | None = None
    source_file_hash: str | None = None  # SHA256
    source_entity_ids: list[str] = Field(default_factory=list)
    parent_record_ids: list[str] = Field(default_factory=list)

    # Review
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    reviewer: str | None = None
    review_timestamp: str | None = None
    review_notes: str | None = None

    @model_validator(mode="after")
    def deterministic_confidence_must_be_one(self):
        if self.inference_method == InferenceMethod.DETERMINISTIC:
            if self.confidence != 1.0:
                raise ValueError(
                    f"Deterministic inference must have confidence=1.0, got {self.confidence}"
                )
        if self.inference_method == InferenceMethod.SYNTHETIC:
            if self.confidence != 1.0:
                raise ValueError(
                    f"Synthetic inference must have confidence=1.0, got {self.confidence}"
                )
        return self

    @model_validator(mode="after")
    def heuristic_confidence_bounds(self):
        if self.inference_method == InferenceMethod.HEURISTIC:
            if self.confidence >= 1.0:
                raise ValueError(
                    f"Heuristic inference must have confidence < 1.0, got {self.confidence}"
                )
        return self
