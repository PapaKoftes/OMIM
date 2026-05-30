"""Deterministic + heuristic feature classifier.

Authority hierarchy: Geometry Truth > Validation Truth > Semantic Truth > AI Truth
This classifier is the SEMANTIC layer -- it NEVER overrides geometry or validation.
It does NOT mutate the MGG. It returns SemanticAnnotations separately.

Classification rules are evaluated in priority order (first match wins).
See 03_INTERFACES/Semantic_Interface.md for the full rule table.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.ontology.loader import Ontology
from omim.semantic.models import (
    AlternativeHypothesis,
    FeatureAnnotation,
    OperationAnnotation,
    SemanticAnnotations,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Confidence ceilings by inference method (per Trust Hierarchy Level 5)
# ---------------------------------------------------------------------------

SEMANTIC_CONFIDENCE_CEILINGS = {
    "hardware_spec": 0.90,  # Blum 35mm hinge cup -- well-defined
    "standards_derived": 0.90,  # European 32mm system
    "shop_convention": 0.75,  # Layer naming conventions
    "material_heuristic": 0.70,  # Diameter range matching
    "machine_heuristic": 0.65,  # Default classifications
}

# ---------------------------------------------------------------------------
# Feature-to-Operation deterministic mapping
# (from 04_ONTOLOGY/Operation_Taxonomy.md)
# ---------------------------------------------------------------------------

FEATURE_TO_OPERATIONS: dict[str, list[str]] = {
    "THROUGH_HOLE": ["DRILLING"],
    "BLIND_HOLE": ["DRILLING"],
    "COUNTERSINK": ["DRILLING"],
    "COUNTERBORE": ["DRILLING"],
    "SHELF_PIN_HOLE": ["DRILLING"],
    "HINGE_CUP_HOLE": ["DRILLING"],
    "CONFIRMAT_HOLE": ["DRILLING"],
    "DOWEL_HOLE": ["DRILLING"],
    "HARDWARE_HOLE": ["DRILLING"],
    "GROOVE": ["CNC_ROUTING"],
    "POCKET": ["CNC_ROUTING"],
    "THROUGH_POCKET": ["CNC_ROUTING"],
    "RABBET": ["CNC_ROUTING"],
    "OPEN_SLOT": ["CNC_ROUTING"],
    "DADO": ["CNC_ROUTING"],
    "PROFILE_CUT": ["PROFILE_CUTTING"],
    "INTERNAL_CUTOUT": ["PROFILE_CUTTING"],
}

# ---------------------------------------------------------------------------
# Feature categories
# ---------------------------------------------------------------------------

FEATURE_CATEGORIES: dict[str, str] = {
    "THROUGH_HOLE": "HOLE_FEATURES",
    "BLIND_HOLE": "HOLE_FEATURES",
    "COUNTERSINK": "HOLE_FEATURES",
    "COUNTERBORE": "HOLE_FEATURES",
    "SHELF_PIN_HOLE": "HOLE_FEATURES",
    "HINGE_CUP_HOLE": "HOLE_FEATURES",
    "CONFIRMAT_HOLE": "HOLE_FEATURES",
    "DOWEL_HOLE": "HOLE_FEATURES",
    "HARDWARE_HOLE": "HOLE_FEATURES",
    "POCKET": "MILLED_FEATURES",
    "THROUGH_POCKET": "MILLED_FEATURES",
    "GROOVE": "MILLED_FEATURES",
    "DADO": "MILLED_FEATURES",
    "RABBET": "MILLED_FEATURES",
    "OPEN_SLOT": "MILLED_FEATURES",
    "PROFILE_CUT": "PROFILE_FEATURES",
    "INTERNAL_CUTOUT": "PROFILE_FEATURES",
    "CHAMFER": "PROFILE_FEATURES",
    "FILLET": "PROFILE_FEATURES",
    "UNKNOWN_FEATURE": "",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_close(value: float, target: float, tolerance: float) -> bool:
    """Check if *value* is within *tolerance* of *target*."""
    return abs(value - target) <= tolerance


def _layer_contains(layer: str, keyword: str) -> bool:
    """Case-insensitive check whether *layer* name contains *keyword*."""
    return keyword.upper() in (layer or "").upper()


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class SemanticPreconditionError(Exception):
    """Raised when the semantic layer cannot run (e.g. Layer 1 not passed)."""


class FeatureClassifier:
    """Classify geometry nodes into manufacturing features.

    The classifier reads the MGG but NEVER mutates it.
    It returns a ``SemanticAnnotations`` object containing all annotations.
    """

    def __init__(self, ontology: Ontology | None = None) -> None:
        self.ontology = ontology

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(
        self,
        mgg: ManufacturingGeometryGraph,
        *,
        validation_report: dict | None = None,
    ) -> SemanticAnnotations:
        """Run rule-based feature classification on all geometry nodes.

        Never modifies *mgg*. Returns ``SemanticAnnotations`` with full
        provenance.

        Parameters
        ----------
        mgg:
            The Manufacturing Geometry Graph (read-only).
        validation_report:
            Optional validation report dict. If provided and
            ``layer1_passed`` is ``False``, raises
            ``SemanticPreconditionError``.
        """
        # Pre-condition: Layer 1 must have passed
        if validation_report is not None:
            l1_passed = validation_report.get(
                "layer1_passed",
                validation_report.get("overall_valid", True),
            )
            if not l1_passed:
                raise SemanticPreconditionError(
                    "Semantic layer requires layer1_passed=True. "
                    "Geometric validation did not pass."
                )

        start = time.perf_counter()

        feature_annotations: list[FeatureAnnotation] = []
        unclassified: list[str] = []
        total_nodes = 0

        for nid, data in mgg.geometry_nodes():
            total_nodes += 1

            # Outer boundary nodes are not features to classify
            if data.get("is_outer_boundary"):
                annotation = FeatureAnnotation(
                    node_id=nid,
                    feature_class="PROFILE_CUT",
                    confidence=0.95,
                    evidence=[{
                        "type": "boundary_flag",
                        "detail": "is_outer_boundary=True",
                    }],
                    provenance={
                        "inference_method": "deterministic",
                        "pipeline_stage": "semantic_classification",
                        "rule": "P9: Outermost closed contour",
                    },
                )
                feature_annotations.append(annotation)
                continue

            annotation = self._classify_node(nid, data, mgg)
            feature_annotations.append(annotation)

            if annotation.feature_class == "UNKNOWN_FEATURE":
                unclassified.append(nid)

        # Derive operations from features
        operation_annotations = self.infer_operations(feature_annotations)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        classified_count = total_nodes - len(unclassified)
        coverage = classified_count / total_nodes if total_nodes > 0 else 0.0

        ontology_version = "v0.1.0"
        if self.ontology is not None:
            ontology_version = self.ontology.version

        result = SemanticAnnotations(
            annotation_id=f"sa-{uuid.uuid4().hex[:12]}",
            graph_id=mgg.metadata.graph_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            ontology_version=ontology_version,
            feature_annotations=feature_annotations,
            operation_annotations=operation_annotations,
            coverage_ratio=coverage,
            unclassified_node_ids=unclassified,
            annotation_time_ms=elapsed_ms,
        )

        logger.info(
            "Classified %d/%d geometry nodes (%.0f%% coverage) in %.1fms",
            classified_count,
            total_nodes,
            coverage * 100,
            elapsed_ms,
        )
        return result

    def infer_operations(
        self,
        annotations: list[FeatureAnnotation],
    ) -> list[OperationAnnotation]:
        """Derive operations from feature classes using FEATURE_TO_OPERATIONS mapping."""
        # Group node IDs by operation type
        ops_map: dict[str, list[str]] = {}
        confidence_map: dict[str, list[float]] = {}

        for ann in annotations:
            op_types = FEATURE_TO_OPERATIONS.get(ann.feature_class, [])
            for op_type in op_types:
                ops_map.setdefault(op_type, []).append(ann.node_id)
                confidence_map.setdefault(op_type, []).append(ann.confidence)

        operation_annotations: list[OperationAnnotation] = []
        for op_type, node_ids in ops_map.items():
            confs = confidence_map[op_type]
            avg_conf = sum(confs) / len(confs) if confs else 1.0
            operation_annotations.append(
                OperationAnnotation(
                    operation_type=op_type,
                    applies_to_node_ids=node_ids,
                    confidence=min(avg_conf, 1.0),
                    provenance={
                        "inference_method": "rule_based",
                        "pipeline_stage": "semantic_classification",
                        "mapping": "FEATURE_TO_OPERATIONS",
                    },
                )
            )

        return operation_annotations

    # ------------------------------------------------------------------
    # Node-level classification (priority-ordered rules, first match wins)
    # ------------------------------------------------------------------

    def _classify_node(
        self,
        node_id: str,
        data: dict,
        mgg: ManufacturingGeometryGraph,
    ) -> FeatureAnnotation:
        """Classify a single geometry node using the priority rule table.

        Rules are evaluated in priority order; first match wins.
        """
        geom_type = data.get("geometry_type", "")
        layer = data.get("layer", "")
        diameter = data.get("diameter_mm")
        entity_type = data.get("entity_type", geom_type).upper() if data.get("entity_type") else geom_type.upper()
        is_closed = data.get("is_closed", False)
        inferred_layer_type = data.get("inferred_layer_type", "unknown")

        # Compute edge distance if panel boundary available
        edge_distance = self._compute_edge_distance(data, mgg)

        # ---------------------------------------------------------------
        # Priority 1: diameter == 35mm +/- 1mm AND layer contains "HINGE"
        # ---------------------------------------------------------------
        if diameter is not None and _is_close(diameter, 35.0, 1.0) and _layer_contains(layer, "HINGE"):
            return self._make_annotation(
                node_id=node_id,
                feature_class="HINGE_CUP_HOLE",
                confidence=0.90,
                evidence=[{
                    "type": "diameter_match",
                    "diameter_mm": diameter,
                    "target_mm": 35.0,
                    "tolerance_mm": 1.0,
                }, {
                    "type": "layer_keyword",
                    "layer": layer,
                    "keyword": "HINGE",
                }],
                inference_method="hardware_spec",
                rule="P1: 35mm + HINGE layer",
            )

        # ---------------------------------------------------------------
        # Priority 2: diameter == 35mm +/- 1mm AND edge distance ~22.5mm
        # ---------------------------------------------------------------
        if (
            diameter is not None
            and _is_close(diameter, 35.0, 1.0)
            and edge_distance is not None
            and _is_close(edge_distance, 22.5, 2.0)
        ):
            return self._make_annotation(
                node_id=node_id,
                feature_class="HINGE_CUP_HOLE",
                confidence=0.90,
                evidence=[{
                    "type": "diameter_match",
                    "diameter_mm": diameter,
                    "target_mm": 35.0,
                    "tolerance_mm": 1.0,
                }, {
                    "type": "edge_distance",
                    "edge_distance_mm": edge_distance,
                    "target_mm": 22.5,
                }],
                inference_method="hardware_spec",
                rule="P2: 35mm + 22.5mm edge distance",
            )

        # ---------------------------------------------------------------
        # Priority 3: diameter == 5mm +/- 0.5mm AND part of 32mm grid
        # ---------------------------------------------------------------
        if diameter is not None and _is_close(diameter, 5.0, 0.5):
            is_grid = self._check_32mm_grid(node_id, data, mgg)
            if is_grid:
                return self._make_annotation(
                    node_id=node_id,
                    feature_class="SHELF_PIN_HOLE",
                    confidence=0.90,
                    evidence=[{
                        "type": "diameter_match",
                        "diameter_mm": diameter,
                        "target_mm": 5.0,
                        "tolerance_mm": 0.5,
                    }, {
                        "type": "pattern_match",
                        "pattern": "32mm_grid",
                    }],
                    inference_method="standards_derived",
                    rule="P3: 5mm + 32mm grid pattern",
                )

        # ---------------------------------------------------------------
        # Priority 4: diameter == 7mm +/- 0.5mm AND layer contains "CONFIRMAT"
        # ---------------------------------------------------------------
        if diameter is not None and _is_close(diameter, 7.0, 0.5) and _layer_contains(layer, "CONFIRMAT"):
            return self._make_annotation(
                node_id=node_id,
                feature_class="CONFIRMAT_HOLE",
                confidence=0.85,
                evidence=[{
                    "type": "diameter_match",
                    "diameter_mm": diameter,
                    "target_mm": 7.0,
                    "tolerance_mm": 0.5,
                }, {
                    "type": "layer_keyword",
                    "layer": layer,
                    "keyword": "CONFIRMAT",
                }],
                inference_method="hardware_spec",
                rule="P4: 7mm + CONFIRMAT layer",
            )

        # ---------------------------------------------------------------
        # Priority 5: diameter in {8, 10} mm +/- 0.2mm
        # ---------------------------------------------------------------
        if diameter is not None:
            for target in (8.0, 10.0):
                if _is_close(diameter, target, 0.2):
                    alternatives = []
                    # Confidence 0.75 is at the threshold; provide alternatives
                    alternatives.append(AlternativeHypothesis(
                        feature_class="THROUGH_HOLE",
                        confidence=0.50,
                        reason=f"Could be a generic through hole at {diameter:.1f}mm",
                    ))
                    return self._make_annotation(
                        node_id=node_id,
                        feature_class="DOWEL_HOLE",
                        confidence=0.75,
                        evidence=[{
                            "type": "diameter_match",
                            "diameter_mm": diameter,
                            "target_mm": target,
                            "tolerance_mm": 0.2,
                        }],
                        inference_method="material_heuristic",
                        rule=f"P5: {target}mm dowel diameter",
                        alternatives=alternatives,
                    )

        # ---------------------------------------------------------------
        # Priority 6: CIRCLE on DRILL layer
        # ---------------------------------------------------------------
        if geom_type == "circle" and (
            inferred_layer_type == "drill" or _layer_contains(layer, "DRILL")
        ):
            return self._make_annotation(
                node_id=node_id,
                feature_class="THROUGH_HOLE",
                confidence=0.80,
                evidence=[{
                    "type": "entity_type",
                    "entity_type": "CIRCLE",
                }, {
                    "type": "layer_match",
                    "layer": layer,
                    "inferred_type": "drill",
                }],
                inference_method="shop_convention",
                rule="P6: CIRCLE on DRILL layer",
            )

        # ---------------------------------------------------------------
        # Priority 7: CIRCLE with no depth info, default
        # ---------------------------------------------------------------
        if geom_type == "circle":
            alternatives = [
                AlternativeHypothesis(
                    feature_class="BLIND_HOLE",
                    confidence=0.40,
                    reason="Could be blind hole if depth metadata is available",
                ),
            ]
            # 5mm circles that did not match grid pattern
            if diameter is not None and _is_close(diameter, 5.0, 0.5):
                alternatives.append(AlternativeHypothesis(
                    feature_class="SHELF_PIN_HOLE",
                    confidence=0.60,
                    reason="5mm diameter matches shelf pin but no 32mm grid detected",
                ))
            # 7mm circles that did not match confirmat layer
            if diameter is not None and _is_close(diameter, 7.0, 0.5):
                alternatives.append(AlternativeHypothesis(
                    feature_class="CONFIRMAT_HOLE",
                    confidence=0.55,
                    reason="7mm body diameter matches confirmat but no layer confirmation",
                ))
            return self._make_annotation(
                node_id=node_id,
                feature_class="THROUGH_HOLE",
                confidence=0.70,
                evidence=[{
                    "type": "entity_type",
                    "entity_type": "CIRCLE",
                }, {
                    "type": "default_classification",
                    "detail": "Circle with no depth info or specific layer",
                }],
                inference_method="material_heuristic",
                rule="P7: CIRCLE default",
                alternatives=alternatives,
            )

        # ---------------------------------------------------------------
        # Priority 8: Closed LWPOLYLINE, interior, pocket layer
        # ---------------------------------------------------------------
        if (
            geom_type in ("polyline", "lwpolyline")
            and is_closed
            and not data.get("is_outer_boundary")
            and (inferred_layer_type == "pocket" or _layer_contains(layer, "POCKET"))
        ):
            alternatives = [
                AlternativeHypothesis(
                    feature_class="INTERNAL_CUTOUT",
                    confidence=0.45,
                    reason="Could be an internal cutout if it passes through the panel",
                ),
            ]
            return self._make_annotation(
                node_id=node_id,
                feature_class="POCKET",
                confidence=0.65,
                evidence=[{
                    "type": "geometry_type",
                    "geometry_type": geom_type,
                    "is_closed": True,
                }, {
                    "type": "layer_match",
                    "layer": layer,
                    "inferred_type": "pocket",
                }],
                inference_method="machine_heuristic",
                rule="P8: Closed LWPOLYLINE on pocket layer",
                alternatives=alternatives,
            )

        # ---------------------------------------------------------------
        # Priority 9: Outermost closed contour (already handled for
        # is_outer_boundary above, but catch contours on cut/border layer)
        # ---------------------------------------------------------------
        if (
            geom_type in ("polyline", "lwpolyline", "contour")
            and is_closed
            and inferred_layer_type in ("cut", "border")
            and not data.get("is_outer_boundary")
        ):
            # Check if this is likely an outer contour by area
            area = data.get("area_mm2")
            # Heuristic: large closed contours on cut layers are profile cuts
            # But without containment analysis, we fall through to P10
            pass

        # ---------------------------------------------------------------
        # Priority 10: Interior closed contour (cutout)
        # ---------------------------------------------------------------
        if (
            geom_type in ("polyline", "lwpolyline", "contour")
            and is_closed
            and not data.get("is_outer_boundary")
            and inferred_layer_type in ("cut", "border")
        ):
            return self._make_annotation(
                node_id=node_id,
                feature_class="INTERNAL_CUTOUT",
                confidence=0.80,
                evidence=[{
                    "type": "geometry_type",
                    "geometry_type": geom_type,
                    "is_closed": True,
                }, {
                    "type": "containment",
                    "detail": "Interior closed contour on cut/border layer",
                }],
                inference_method="shop_convention",
                rule="P10: Interior closed contour (cutout)",
            )

        # ---------------------------------------------------------------
        # Priority 11: No match -> UNKNOWN_FEATURE
        # ---------------------------------------------------------------
        return self._make_annotation(
            node_id=node_id,
            feature_class="UNKNOWN_FEATURE",
            confidence=0.0,
            evidence=[{
                "type": "no_match",
                "detail": f"No classification rule matched for geometry_type={geom_type}, layer={layer}",
            }],
            inference_method="none",
            rule="P11: No match",
        )

    # ------------------------------------------------------------------
    # Annotation builder
    # ------------------------------------------------------------------

    @staticmethod
    def _make_annotation(
        *,
        node_id: str,
        feature_class: str,
        confidence: float,
        evidence: list[dict],
        inference_method: str,
        rule: str,
        alternatives: list[AlternativeHypothesis] | None = None,
    ) -> FeatureAnnotation:
        """Build a ``FeatureAnnotation`` with provenance."""
        # Below confidence 0.75: alternative hypotheses MUST be provided
        if alternatives is None:
            alternatives = []
        if confidence < 0.75 and not alternatives:
            alternatives.append(
                AlternativeHypothesis(
                    feature_class="UNKNOWN_FEATURE",
                    confidence=0.0,
                    reason="Low confidence; no specific alternative identified",
                )
            )

        return FeatureAnnotation(
            node_id=node_id,
            feature_class=feature_class,
            confidence=confidence,
            evidence=evidence,
            provenance={
                "inference_method": inference_method,
                "pipeline_stage": "semantic_classification",
                "rule": rule,
            },
            alternative_classes=alternatives,
        )

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_edge_distance(
        data: dict,
        mgg: ManufacturingGeometryGraph,
    ) -> float | None:
        """Compute shortest distance from a node's centroid to the panel boundary.

        Returns ``None`` if boundary or centroid information is unavailable.
        """
        centroid = data.get("centroid")
        if centroid is None:
            return None

        # Try to find the panel boundary node
        for _nid, bdata in mgg.geometry_nodes():
            if bdata.get("is_outer_boundary"):
                # Use panel bbox as a rough approximation
                bbox = bdata.get("bounding_box")
                if bbox and len(bbox) == 4:
                    xmin, ymin, xmax, ymax = bbox
                    cx, cy = centroid[0], centroid[1]
                    # Distance to nearest edge
                    dist_left = cx - xmin
                    dist_right = xmax - cx
                    dist_bottom = cy - ymin
                    dist_top = ymax - cy
                    return min(dist_left, dist_right, dist_bottom, dist_top)
        return None

    @staticmethod
    def _check_32mm_grid(
        node_id: str,
        data: dict,
        mgg: ManufacturingGeometryGraph,
    ) -> bool:
        """Check if a node is part of a 32mm grid pattern with peer circles.

        Looks for at least 2 other circles of similar diameter whose
        center-to-center distance is a multiple of 32mm (+/- 1mm).
        """
        centroid = data.get("centroid")
        diameter = data.get("diameter_mm")
        if centroid is None or diameter is None:
            return False

        cx, cy = centroid[0], centroid[1]
        grid_peers = 0

        for peer_id, peer_data in mgg.geometry_nodes():
            if peer_id == node_id:
                continue
            peer_d = peer_data.get("diameter_mm")
            peer_c = peer_data.get("centroid")
            if peer_d is None or peer_c is None:
                continue
            # Similar diameter
            if not _is_close(peer_d, diameter, 0.5):
                continue
            # Check distance is a multiple of 32mm
            dx = peer_c[0] - cx
            dy = peer_c[1] - cy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < 1.0:
                continue
            remainder = dist % 32.0
            if remainder < 1.0 or remainder > 31.0:
                grid_peers += 1

        # Need at least 2 peers (3 total holes) for a confirmed pattern
        return grid_peers >= 2
