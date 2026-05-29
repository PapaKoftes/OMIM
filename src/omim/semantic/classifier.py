"""Deterministic + heuristic feature classifier.

Authority hierarchy: Geometry Truth > Validation Truth > Semantic Truth > AI Truth
This classifier is the SEMANTIC layer — it NEVER overrides geometry or validation.
"""

from __future__ import annotations

import logging

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.graph.models import EdgeType, FeatureNode
from omim.ontology.loader import ManufacturingOntology
from omim.semantic.models import ClassificationResult, FeatureHypothesis

logger = logging.getLogger(__name__)

# Deterministic rules: diameter ranges (mm) → feature class
DIAMETER_RULES: list[tuple[float, float, str, float]] = [
    # (min_d, max_d, feature_class, confidence)
    (4.8, 5.2, "SHELF_PIN_HOLE", 0.95),
    (7.8, 8.2, "DOWEL_HOLE", 0.90),
    (14.5, 15.5, "EURO_SCREW_HOLE", 0.85),
    (19.5, 20.5, "SYSTEM_HOLE_20MM", 0.80),
    (25.0, 26.0, "CABLE_GROMMET_HOLE", 0.70),
    (34.5, 35.5, "HINGE_CUP_HOLE", 0.95),
]


class FeatureClassifier:
    """Classify geometry nodes into manufacturing features."""

    def __init__(self, ontology: ManufacturingOntology | None = None) -> None:
        self.ontology = ontology

    def classify(
        self, mgg: ManufacturingGeometryGraph
    ) -> list[ClassificationResult]:
        """Run classification on all geometry nodes, attach FeatureNodes to the MGG."""
        results = []

        for nid, data in mgg.geometry_nodes():
            if data.get("is_outer_boundary"):
                continue

            cr = self._classify_node(nid, data)
            results.append(cr)

            if cr.best_hypothesis:
                # Create FeatureNode and attach it
                feat_id = f"feat-{nid}"
                feat = FeatureNode(
                    node_id=feat_id,
                    feature_class=cr.best_hypothesis.feature_class,
                    confidence=cr.best_hypothesis.confidence,
                    inference_method=cr.best_hypothesis.method,
                    diameter_mm=data.get("diameter_mm"),
                    position_mm=data.get("centroid"),
                    hypotheses=[h.model_dump() for h in cr.all_hypotheses],
                    geometry_node_ids=[nid],
                )
                mgg.add_feature_node(feat)
                mgg.add_edge(nid, feat_id, EdgeType.COMPOSES)

        logger.info("Classified %d geometry nodes", len(results))
        return results

    def _classify_node(
        self, node_id: str, data: dict
    ) -> ClassificationResult:
        geom_type = data.get("geometry_type", "")
        hypotheses: list[FeatureHypothesis] = []

        if geom_type == "circle":
            d = data.get("diameter_mm")
            if d is not None:
                hypotheses = self._diameter_lookup(d)

        if not hypotheses:
            # Fallback: generic classification based on layer
            layer_type = data.get("inferred_layer_type", "unknown")
            if layer_type == "drill":
                hypotheses.append(FeatureHypothesis(
                    feature_class="GENERIC_DRILL_HOLE",
                    confidence=0.3,
                    method="heuristic",
                    reasoning=f"On drill layer, diameter unknown or unmatched",
                ))
            elif layer_type in ("cut", "border"):
                hypotheses.append(FeatureHypothesis(
                    feature_class="CONTOUR_CUT",
                    confidence=0.5,
                    method="heuristic",
                    reasoning="On cut/border layer",
                ))
            elif layer_type == "pocket":
                hypotheses.append(FeatureHypothesis(
                    feature_class="POCKET_ROUT",
                    confidence=0.5,
                    method="heuristic",
                    reasoning="On pocket layer",
                ))

        best = max(hypotheses, key=lambda h: h.confidence) if hypotheses else None

        return ClassificationResult(
            geometry_node_id=node_id,
            best_hypothesis=best,
            all_hypotheses=hypotheses,
        )

    def _diameter_lookup(self, diameter_mm: float) -> list[FeatureHypothesis]:
        matches = []
        for min_d, max_d, feat_class, conf in DIAMETER_RULES:
            if min_d <= diameter_mm <= max_d:
                matches.append(FeatureHypothesis(
                    feature_class=feat_class,
                    confidence=conf,
                    method="deterministic",
                    reasoning=f"Diameter {diameter_mm:.1f} mm matches {feat_class} range [{min_d}-{max_d}]",
                ))
        return matches
