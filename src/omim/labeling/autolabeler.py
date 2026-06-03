"""AutoLabeler — turn a built MGG into a confidence-scored, reviewable LabelSet.

Runs the feature classifier and the part identifier, converts each result into a
:class:`Label`, and assigns a review status by confidence band:

  * confidence >= accept_threshold        -> AUTO_ACCEPTED   (silver, trusted)
  * reject_threshold <= conf < accept     -> NEEDS_REVIEW    (human queue)
  * confidence < reject_threshold          -> NEEDS_REVIEW    (low-conf, still queued)

Assembly/project labels are added at the corpus level (see omim.pipeline), since
they span multiple panels; this class handles the per-panel feature + part labels.
"""

from __future__ import annotations

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.identify.parts import identify_part
from omim.labeling.models import Label, LabelKind, LabelSet, ReviewStatus
from omim.semantic.classifier import FeatureClassifier


class AutoLabeler:
    """Produce a reviewable LabelSet for a single panel MGG."""

    def __init__(
        self,
        accept_threshold: float = 0.75,
        reject_threshold: float = 0.30,
        classifier: FeatureClassifier | None = None,
    ) -> None:
        self.accept_threshold = accept_threshold
        self.reject_threshold = reject_threshold
        self._classifier = classifier or FeatureClassifier()

    def _status(self, confidence: float) -> ReviewStatus:
        if confidence >= self.accept_threshold:
            return ReviewStatus.AUTO_ACCEPTED
        return ReviewStatus.NEEDS_REVIEW

    def label_panel(self, mgg: ManufacturingGeometryGraph) -> LabelSet:
        graph_id = mgg.metadata.graph_id
        source_file = mgg.metadata.source_file
        labels: list[Label] = []

        # --- Feature labels (per geometry node) ---
        annotations = self._classifier.classify(mgg)
        for fa in annotations.feature_annotations:
            labels.append(Label(
                label_id=f"{graph_id}:feat:{fa.node_id}",
                kind=LabelKind.FEATURE,
                target_id=fa.node_id,
                value=fa.feature_class,
                confidence=fa.confidence,
                source_layer="omim.semantic.classifier",
                evidence=fa.evidence,
                alternatives=[a.model_dump() for a in fa.alternative_classes],
                review_status=self._status(fa.confidence),
            ))

        # --- Part label (per panel) ---
        part = identify_part(mgg, annotations)
        labels.append(Label(
            label_id=f"{graph_id}:part",
            kind=LabelKind.PART,
            target_id=graph_id,
            value=part.part_type,
            confidence=part.confidence,
            source_layer="omim.identify.parts",
            evidence=part.evidence,
            alternatives=part.alternatives,
            review_status=self._status(part.confidence),
        ))

        return LabelSet(
            set_id=f"labelset:{graph_id}",
            source_file=source_file,
            graph_id=graph_id,
            labels=labels,
        )
