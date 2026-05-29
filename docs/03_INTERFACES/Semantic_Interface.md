# Semantic Interface Contract

Version: v0.1.0  
Section: 03_INTERFACES  

See also: [[04_ONTOLOGY/Feature_Taxonomy]], [[04_ONTOLOGY/Manufacturing_Ontology]], [[02_SCHEMA/Provenance_Schema]]

---

## Contract

```
Input:  ManufacturingGeometryGraph (read-only) + ValidationReport (read-only)
Output: SemanticAnnotations
```

The semantic layer classifies geometric features into manufacturing feature types. It reads the MGG and ValidationReport. It cannot mutate the MGG.

**Prerequisite**: `ValidationReport.layer1_passed == True` before semantic layer runs. The semantic layer does not run on geometrically invalid graphs.

---

## Input

```python
# ManufacturingGeometryGraph — read-only
# ValidationReport — read-only; must have overall_valid=True or layer1_passed=True
```

---

## Output: `SemanticAnnotations`

```python
class SemanticAnnotations(BaseModel):
    annotation_id: str
    graph_id: str
    timestamp: str
    ontology_version: str

    feature_annotations: list[FeatureAnnotation]
    operation_annotations: list[OperationAnnotation]
    
    coverage_ratio: float           # fraction of GeometryNodes annotated
    unclassified_node_ids: list[str]
    
    provenance: ProvenanceRecord    # inference_method: "rule_based" or "heuristic"
    annotation_time_ms: float
```

---

## FeatureAnnotation

```python
class FeatureAnnotation(BaseModel):
    node_id: str                    # GeometryNode.node_id
    feature_class: str              # from Feature_Taxonomy
    confidence: float               # 0.0–1.0; reflects inference method ceiling
    evidence: list[EvidenceItem]
    provenance: ProvenanceRecord
    alternative_classes: list[AlternativeHypothesis]  # if confidence < 0.9

class AlternativeHypothesis(BaseModel):
    feature_class: str
    confidence: float
    reason: str
```

---

## OperationAnnotation

```python
class OperationAnnotation(BaseModel):
    operation_type: str             # from Operation_Taxonomy
    applies_to_node_ids: list[str]
    confidence: float
    provenance: ProvenanceRecord
```

---

## Inference Engine Interface

```python
class SemanticInferenceEngine:
    def __init__(self, ontology: Ontology):
        self.ontology = ontology
    
    def classify(
        self,
        mgg: ManufacturingGeometryGraph,
        validation_report: ValidationReport
    ) -> SemanticAnnotations:
        """
        Run rule-based feature classification.
        Never modifies mgg.
        Returns SemanticAnnotations with full provenance.
        """
    
    def classify_node(
        self,
        node: GeometryNode,
        context: GraphContext
    ) -> FeatureAnnotation:
        """
        Classify a single node given its graph context.
        context includes: containing_panel, adjacent_nodes, same_row_nodes.
        """
    
    def infer_operations(
        self,
        annotations: list[FeatureAnnotation]
    ) -> list[OperationAnnotation]:
        """Derive operations from feature classes using FEATURE_TO_OPERATIONS mapping."""
```

---

## Classification Logic (Rule Priority Order)

Rules are evaluated in this order; first match wins:

| Priority | Rule | Feature | Confidence Ceiling |
|----------|------|---------|------------------|
| 1 | diameter == 35mm ± 1mm AND layer contains "HINGE" | HINGE_CUP_HOLE | 0.90 |
| 2 | diameter == 35mm ± 1mm AND edge distance ~22.5mm | HINGE_CUP_HOLE | 0.90 |
| 3 | diameter == 5mm ± 0.5mm AND part of 32mm grid pattern | SHELF_PIN_HOLE | 0.90 |
| 4 | diameter == 7mm ± 0.5mm AND layer contains "CONFIRMAT" | CONFIRMAT_HOLE | 0.85 |
| 5 | diameter in {8, 10} mm ± 0.2mm | DOWEL_HOLE | 0.75 |
| 6 | CIRCLE, entity_type CIRCLE, layer "DRILL" | THROUGH_HOLE | 0.80 |
| 7 | CIRCLE with no depth info, default classification | THROUGH_HOLE | 0.70 |
| 8 | Closed LWPOLYLINE, interior, no through-cut context | POCKET | 0.65 |
| 9 | Outermost closed contour | PROFILE_CUT | 0.95 |
| 10 | Interior closed contour (cutout) | INTERNAL_CUTOUT | 0.80 |
| 11 | No match | UNKNOWN_FEATURE | 0.0 |

---

## Confidence Ceiling by Inference Method

Per the Trust Hierarchy (Level 5), semantic inference has a confidence ceiling:

```python
SEMANTIC_CONFIDENCE_CEILINGS = {
    "hardware_spec": 0.90,      # Blum 35mm hinge cup — well-defined
    "standards_derived": 0.90,  # European 32mm system
    "shop_convention": 0.75,    # Layer naming conventions
    "material_heuristic": 0.70, # Diameter range matching
    "machine_heuristic": 0.65,  # Default classifications
}
```

Confidence above 0.90 requires `inference_method="deterministic"` — reserved for geometry-layer facts only.

---

## Module Isolation

```python
# CORRECT: Semantic layer reads MGG but does not modify it
def classify(self, mgg: ManufacturingGeometryGraph, ...) -> SemanticAnnotations:
    for node in mgg.query().get_geometry_nodes():
        annotation = self.classify_node(node, ...)
    # Returns annotations separately — never calls mgg.add_feature_node()

# FORBIDDEN: Semantic layer cannot mutate the graph
# mgg.add_feature_node(...)  # NEVER called from semantic layer
```

The caller (pipeline orchestrator) is responsible for merging annotations back into the MGG after the semantic layer completes.

---

## Failure Handling

| Failure | Behavior |
|---------|---------|
| Ontology file missing | Raise `OntologyLoadError` — fatal |
| Geometry node unclassifiable | `FeatureAnnotation(feature_class="UNKNOWN_FEATURE", confidence=0.0)` — non-fatal |
| ValidationReport.layer1_passed=False | Raise `SemanticPreconditionError` — fatal |
| Ontology version mismatch | Log warning; continue with loaded ontology |

---

## Acceptance Tests

```python
def test_hinge_cup_classified_correctly():
    """35mm circle at 22.5mm from edge → HINGE_CUP_HOLE with confidence >= 0.85."""

def test_shelf_pin_grid_detected():
    """Four 5mm circles at 32mm spacing → SHELF_PIN_HOLE with confidence >= 0.85."""

def test_unknown_feature_not_fatal():
    """Unclassifiable geometry → UNKNOWN_FEATURE annotation, not exception."""

def test_semantic_layer_does_not_mutate_mgg():
    """MGG node count before and after classify() is identical."""

def test_operation_inference_uses_mapping():
    """THROUGH_HOLE annotation → DRILLING operation via FEATURE_TO_OPERATIONS."""

def test_no_semantic_run_on_invalid_geometry():
    """layer1_passed=False raises SemanticPreconditionError."""
```
