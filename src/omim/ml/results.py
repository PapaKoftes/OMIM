"""Additive ML prediction result objects (Authority Hierarchy Level 6).

These are PURE pydantic / dataclass objects — no torch required to construct or
inspect them. Every ML output carries:

  * ``inference_method = InferenceMethod.ML_GNN`` (Level 6, lowest authority),
  * a ``confidence`` in [0, 1] (raw softmax, NOT calibrated),
  * ``evidence`` describing what drove the prediction,
  * a provenance record builder.

CRITICAL: predictions are *additive only*. They never mutate the MGG and never
override geometry / validation. A consumer is free to ignore them entirely.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from omim.provenance.models import (
    EvidenceItem,
    EvidenceType,
    InferenceMethod,
    ProvenanceRecord,
)

#: Canonical, ORDER-STABLE feature class list used as the GNN output space.
#: 13 classes, matching ``out_channels=13`` in ML_Integration.md. Index ==
#: class label index in the model's logits/softmax. Drawn from the ontology and
#: the synthetic generator's feature set, with SHELF_PIN_HOLE first (dominant
#: class — see class-imbalance handling).
FEATURE_CLASSES: list[str] = [
    "SHELF_PIN_HOLE",
    "HINGE_CUP_HOLE",
    "CONFIRMAT_HOLE",
    "DOWEL_HOLE",
    "THROUGH_HOLE",
    "BLIND_HOLE",
    "SYSTEM_HOLE",
    "POCKET",
    "GROOVE",
    "DADO",
    "RABBET",
    "PROFILE_CUT",
    "UNKNOWN_FEATURE",
]

NUM_FEATURE_CLASSES = len(FEATURE_CLASSES)
assert NUM_FEATURE_CLASSES == 13


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ml_provenance(
    *,
    confidence: float,
    module: str,
    evidence: list[EvidenceItem],
    source_entity_ids: list[str] | None = None,
    confidence_method: str = "softmax_probability",
) -> ProvenanceRecord:
    """Build a Level-6 (ML_GNN) provenance record. Confidence is clamped < 1.0.

    Level-6 outputs MUST have confidence < 1.0 (Authority_Hierarchy invariant:
    authority_level > 4 => confidence < 1.0). Raw softmax can theoretically hit
    1.0, so we clamp.
    """
    conf = max(0.0, min(float(confidence), 0.999))
    return ProvenanceRecord(
        record_id=str(uuid.uuid4()),
        timestamp=_now_iso(),
        generator="omim",
        generator_version="v0.1.0",
        pipeline_stage="ml",
        module=module,
        inference_method=InferenceMethod.ML_GNN,
        confidence=conf,
        confidence_method=confidence_method,
        evidence=evidence,
        source_entity_ids=source_entity_ids or [],
    )


class NodePrediction(BaseModel):
    """Per-node feature-class prediction from :class:`ManufacturingFeatureGNN`."""

    node_id: str
    feature_class: str
    confidence: float  # max softmax prob (raw, uncalibrated)
    proba: dict[str, float] = Field(default_factory=dict)  # full class distribution
    inference_method: InferenceMethod = InferenceMethod.ML_GNN

    def to_provenance(self) -> ProvenanceRecord:
        evidence = [
            EvidenceItem(
                evidence_type=EvidenceType.ML_EMBEDDING,
                description=f"GNN node classifier -> {self.feature_class}",
                value=self.feature_class,
                node_id=self.node_id,
                weight=self.confidence,
            )
        ]
        return _ml_provenance(
            confidence=self.confidence,
            module="omim.ml.models.ManufacturingFeatureGNN",
            evidence=evidence,
            source_entity_ids=[self.node_id],
        )


class FeatureClassificationPrediction(BaseModel):
    """Graph-wide result of node feature classification (additive overlay).

    This is what :meth:`ManufacturingFeatureGNN.predict` returns. It is an
    overlay: a consumer may attach these as alternative hypotheses, but they
    NEVER replace the deterministic / heuristic labels.
    """

    graph_id: str | None = None
    inference_method: InferenceMethod = InferenceMethod.ML_GNN
    model_id: str = "ManufacturingFeatureGNN"
    timestamp: str = Field(default_factory=_now_iso)
    node_predictions: list[NodePrediction] = Field(default_factory=list)
    ml_available: bool = True
    fallback: bool = False  # True when degraded (heuristics should be used)
    note: str = ""

    def mean_confidence(self) -> float:
        if not self.node_predictions:
            return 0.0
        return sum(p.confidence for p in self.node_predictions) / len(self.node_predictions)


class ManufacturabilityPrediction(BaseModel):
    """Graph-level binary manufacturability prediction (additive, advisory).

    CRITICAL: ``p_manufacturable`` NEVER overrides a deterministic validation
    verdict. If the rule engine says INVALID, the panel is INVALID regardless of
    this score (Authority_Hierarchy decision table).
    """

    graph_id: str | None = None
    inference_method: InferenceMethod = InferenceMethod.ML_GNN
    model_id: str = "ManufacturabilityGNN"
    timestamp: str = Field(default_factory=_now_iso)
    p_manufacturable: float = 0.0  # sigmoid output in [0, 1]
    predicted_manufacturable: bool = False
    confidence: float = 0.0  # distance of p from 0.5, mapped to [0, 1]
    ml_available: bool = True
    fallback: bool = False
    note: str = ""

    def to_provenance(self) -> ProvenanceRecord:
        evidence = [
            EvidenceItem(
                evidence_type=EvidenceType.ML_EMBEDDING,
                description=(
                    f"Graph-level GNN P(manufacturable)={self.p_manufacturable:.3f} "
                    "(ADVISORY — does not override deterministic validation)"
                ),
                value=round(self.p_manufacturable, 4),
            )
        ]
        return _ml_provenance(
            confidence=self.confidence,
            module="omim.ml.models.ManufacturabilityGNN",
            evidence=evidence,
            confidence_method="sigmoid_margin",
        )


class NodeAnomaly(BaseModel):
    """Per-node anomaly score from the VGAE."""

    node_id: str
    anomaly_score: float  # reconstruction error (higher = more anomalous)
    is_anomaly: bool = False


class AnomalyPrediction(BaseModel):
    """VGAE anomaly-detection result (additive, advisory).

    A high anomaly score does NOT make a valid panel invalid. Per the decision
    table: "Panel passes all rules; ML says anomaly_score = 0.92 -> Anomaly
    score added to annotations; valid status unchanged."
    """

    graph_id: str | None = None
    inference_method: InferenceMethod = InferenceMethod.ML_GNN
    model_id: str = "VariationalManufacturingEncoder"
    timestamp: str = Field(default_factory=_now_iso)
    node_anomalies: list[NodeAnomaly] = Field(default_factory=list)
    graph_anomaly_score: float = 0.0  # aggregate (mean node reconstruction error)
    threshold: float = 0.0
    ml_available: bool = True
    fallback: bool = False
    note: str = ""

    def to_provenance(self) -> ProvenanceRecord:
        n_anom = sum(1 for a in self.node_anomalies if a.is_anomaly)
        evidence = [
            EvidenceItem(
                evidence_type=EvidenceType.ML_EMBEDDING,
                description=(
                    f"VGAE anomaly scan: {n_anom} flagged node(s); "
                    f"graph_score={self.graph_anomaly_score:.3f} (ADVISORY)"
                ),
                value=round(self.graph_anomaly_score, 4),
            )
        ]
        # Confidence for an unsupervised anomaly signal is intentionally modest.
        conf = min(0.5 + self.graph_anomaly_score, 0.95)
        return _ml_provenance(
            confidence=conf,
            module="omim.ml.models.VariationalManufacturingEncoder",
            evidence=evidence,
            confidence_method="reconstruction_error",
        )


def unavailable_classification(
    graph_id: str | None, reason: str
) -> FeatureClassificationPrediction:
    """Build a graceful-degradation classification result (D-003)."""
    return FeatureClassificationPrediction(
        graph_id=graph_id,
        node_predictions=[],
        ml_available=False,
        fallback=True,
        note=f"ml_unavailable, falling back to heuristics: {reason}",
    )


def unavailable_manufacturability(
    graph_id: str | None, reason: str
) -> ManufacturabilityPrediction:
    """Build a graceful-degradation manufacturability result (D-003)."""
    return ManufacturabilityPrediction(
        graph_id=graph_id,
        p_manufacturable=0.0,
        predicted_manufacturable=False,
        confidence=0.0,
        ml_available=False,
        fallback=True,
        note=f"ml_unavailable, falling back to heuristics: {reason}",
    )


def unavailable_anomaly(graph_id: str | None, reason: str) -> AnomalyPrediction:
    """Build a graceful-degradation anomaly result (D-003)."""
    return AnomalyPrediction(
        graph_id=graph_id,
        node_anomalies=[],
        graph_anomaly_score=0.0,
        ml_available=False,
        fallback=True,
        note=f"ml_unavailable, falling back to heuristics: {reason}",
    )
