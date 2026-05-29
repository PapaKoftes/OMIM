# Trust & Authority Hierarchy

**Status: ENFORCED — This is an architectural invariant, not a suggestion.**

See also: [[What Is OMIM]], [[Validation]], [[Provenence and Uncertainty]], [[ML Integration and research]]

---

## Purpose

This document defines the formal authority hierarchy for OMIM. Every system, module, and inference layer has a defined position in this hierarchy. Lower levels NEVER override higher levels. Period.

This hierarchy is the primary guard against:
- ML overriding geometric truth
- Heuristics pretending to be deterministic
- Confidence scores being mistaken for certainty
- Validation layers being bypassed

---

## The Hierarchy

```
╔══════════════════════════════════════════════════════════════════╗
║  LEVEL 1 — GEOMETRIC MATHEMATICS                                 ║
║  Source: Shapely computations on raw DXF coordinates             ║
║  Authority: ABSOLUTE                                             ║
║  Can be overridden by: NOTHING                                   ║
╠══════════════════════════════════════════════════════════════════╣
║  LEVEL 2 — TOPOLOGICAL VALIDITY                                  ║
║  Source: ezdxf entity structure + Shapely topology checks        ║
║  Authority: ABSOLUTE                                             ║
║  Can be overridden by: NOTHING                                   ║
╠══════════════════════════════════════════════════════════════════╣
║  LEVEL 3 — STANDARDS AND RULES                                   ║
║  Source: ISO/DIN standards; hardware catalogs; YAML rule files   ║
║  Authority: HIGH — deterministic, externalized                   ║
║  Can be overridden by: Level 1 and 2 only                        ║
╠══════════════════════════════════════════════════════════════════╣
║  LEVEL 4 — DETERMINISTIC HEURISTICS                              ║
║  Source: Pattern matching; diameter ranges; spacing logic        ║
║  Authority: MEDIUM — rule-based but not standards-backed         ║
║  Can be overridden by: Levels 1, 2, 3                            ║
╠══════════════════════════════════════════════════════════════════╣
║  LEVEL 5 — SEMANTIC INFERENCE                                    ║
║  Source: Feature classification; pattern recognition             ║
║  Authority: LOW — probabilistic, always confidence-bounded       ║
║  Can be overridden by: Levels 1–4                                ║
╠══════════════════════════════════════════════════════════════════╣
║  LEVEL 6 — ML PREDICTIONS                                        ║
║  Source: GNN / embedding models                                  ║
║  Authority: LOWEST — advisory, never factual                     ║
║  Can be overridden by: ALL other levels                          ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Level-by-Level Specification

### Level 1: Geometric Mathematics

**What it is**: The raw output of Shapely and ezdxf computations. Positions, areas, perimeters, distances, intersections.

**Examples**:
- `circle.area = π × r²` (this is always true)
- `distance(p1, p2) = sqrt((x2-x1)² + (y2-y1)²)` (always true)
- `polygon.is_valid` (Shapely computation, always deterministic)
- `polygon.intersection(other_polygon)` (geometric fact)

**Authority rule**: These values cannot be "wrong" from the system's perspective. If the DXF says the circle has radius 5.0mm, the area is 78.54mm². That is a geometric fact. Nothing downstream changes this.

**In code**: Produced by `omim/parser/` and geometry computations in `omim/graph/builder.py`.

**ProvenanceRecord.inference_method**: `"deterministic"`  
**ProvenanceRecord.confidence**: Always `1.0`

---

### Level 2: Topological Validity

**What it is**: Topology checks — does this contour self-intersect? Is it closed? Is it simple? Are entities connected?

**Examples**:
- Contour is closed (endpoint distance < tolerance)
- Polygon does not self-intersect
- No duplicate entities at same position
- All geometry lies within panel bounds

**Authority rule**: Topological facts are computed deterministically. An open contour IS open — the system does not "decide" whether to consider it open.

**In code**: Produced by `omim/validation/layer1_geometry.py`.

**ProvenanceRecord.inference_method**: `"deterministic"`  
**ProvenanceRecord.confidence**: Always `1.0`

---

### Level 3: Standards and Rules

**What it is**: Manufacturing rules drawn from ISO standards, DIN standards, hardware manufacturer specifications, and open-source CAM system logic.

**Examples**:
- MFG-001: Feature must be ≥ 8mm from panel edge (sourced from shop practice + DIN 68xxx)
- MFG-005: Shelf pins must be 32mm apart (sourced from European 32mm system + Blum/Hettich catalogs)
- MFG-007: Hinge cup 22.5mm from edge (sourced from Blum CLIP top spec)

**Authority rule**: Rules are deterministic when evaluated — given the same geometry and the same rule, the result is always the same. However, rules themselves may have domain-specific applicability (e.g., a furniture rule does not apply to aerospace). Rules are NEVER automatically extended beyond their stated domain.

**In code**: Produced by `omim/validation/layer2_manufacturability.py` + `omim/rules/`.

**ProvenanceRecord.inference_method**: `"deterministic"`  
**ProvenanceRecord.confidence**: `1.0`

**Critical constraint**: A rule from Level 3 CANNOT be weakened or invalidated by Level 4–6 outputs.

---

### Level 4: Deterministic Heuristics

**What it is**: Pattern-matching logic that is rule-based but where the rule is derived from engineering judgment, not a formal standard.

**Examples**:
- Diameter-based hole classification: "5mm circles are probably SHELF_PIN_HOLE"
- Layer name convention mapping: "DRILL layer → drill operations"
- Contour nesting detection: "inner contour inside outer = internal cutout"
- Column alignment detection: "holes within 1mm horizontal = same column"

**Authority rule**: Deterministic heuristics produce reproducible outputs (same input → same output), but they carry explicit uncertainty. A 5mm circle might be something other than a shelf pin hole — the heuristic does not claim certainty.

**Confidence range**: 0.50 – 0.95 (never 1.0 unless backed by standards)  
**ProvenanceRecord.inference_method**: `"heuristic"`

**Critical constraint**: A Level 4 heuristic result CANNOT override a Level 3 rule violation. A panel that fails MFG-001 is invalid regardless of what the semantic layer infers.

---

### Level 5: Semantic Inference

**What it is**: The feature classification layer that synthesizes geometry, patterns, and context into manufacturing meaning.

**Examples**:
- "This set of 4 collinear 5mm holes at 32mm spacing is a SHELF_PIN_ROW"
- "This 35mm circle 22mm from edge is a HINGE_CUP_HOLE, confidence: 0.92"
- "This elongated polygon is a GROOVE, confidence: 0.81"

**Authority rule**: Semantic inferences are hypotheses. They inform downstream reasoning but cannot override geometric facts or rule-based validations.

**Confidence range**: 0.30 – 0.99  
**ProvenanceRecord.inference_method**: `"heuristic"` (rules-based) or `"ml_gnn"` (GNN-based)

**Multiple hypotheses required for confidence < 0.75**: If confidence is below 0.75, the system MUST store at least 2 competing hypotheses with ranked probabilities.

---

### Level 6: ML Predictions

**What it is**: Outputs from trained GNN or other ML models.

**Examples**:
- GraphSAGE node classification: P(SHELF_PIN_HOLE) = 0.87, P(THROUGH_HOLE) = 0.10, ...
- VGAE anomaly score: 0.94 (high = anomalous)
- Graph-level manufacturability prediction: P(invalid) = 0.23

**Authority rule**: ML outputs are the weakest form of evidence in the system. They can reinforce Level 4-5 inferences when they agree, but they cannot overturn higher-level results.

**Confidence range**: 0.0 – 1.0 (raw softmax output; do not treat as calibrated probability without calibration step)  
**ProvenanceRecord.inference_method**: `"ml_gnn"`

**Critical constraints**:
1. ML CANNOT change geometry measurements
2. ML CANNOT mark a validated-invalid panel as valid
3. ML CANNOT assert a new manufacturing rule
4. ML output MUST include confidence and evidence; bare predictions are not allowed
5. If ML and deterministic heuristic disagree: **report both, surface to user, do not silently pick one**

---

## Conflict Resolution Protocol

When outputs from different levels conflict:

```
Level 1 vs Level 2–6:    Level 1 wins. Always.
Level 2 vs Level 3–6:    Level 2 wins. Always.
Level 3 vs Level 4–6:    Level 3 wins. Always.
Level 4 vs Level 5–6:    Level 4 wins. Report both.
Level 5 vs Level 6:      Level 5 wins if confidence > 0.60, else report both.
Level 6 alone:           Only valid if no Level 4–5 result exists.
```

**Conflict flagging**: Any conflict between Level 5 and Level 4 (or between Level 6 and Level 4–5) MUST be surfaced in the output with both values and their sources. Silent conflict resolution is forbidden.

```json
{
  "feature_class": "SHELF_PIN_HOLE",
  "confidence": 0.88,
  "inference_method": "heuristic",
  "ml_prediction": {
    "feature_class": "THROUGH_HOLE",
    "confidence": 0.73,
    "inference_method": "ml_gnn"
  },
  "conflict": true,
  "conflict_resolution": "heuristic_wins_confidence_threshold",
  "note": "Heuristic (Level 4) and GNN (Level 6) disagree. Heuristic reported as primary."
}
```

---

## Code Enforcement

The hierarchy is enforced structurally in code:

```python
# omim/validation/rule_engine.py

class RuleEngine:
    def execute_layer2(self, mgg, semantic_annotations=None):
        """
        Layer 2 validation runs INDEPENDENTLY of semantic annotations.
        
        The semantic_annotations parameter is deliberately absent —
        validation CANNOT query the semantic layer.
        This is structural enforcement of Level 3 > Level 5.
        """
        # No import of semantic module here.
        # No access to feature classifications.
        # Only geometry matters at this level.
```

```python
# omim/semantic/inference_engine.py

class InferenceEngine:
    def infer(self, mgg, validation_report):
        """
        Semantic inference receives validation results as READ-ONLY input.
        
        It CANNOT modify validation_report.
        It CANNOT change ValidationReport.overall_valid.
        It CAN use validation results as additional evidence for classification.
        """
        assert not hasattr(validation_report, '__setattr__'), "ValidationReport must be frozen"
```

```python
# omim/ml/models/gnn_classifier.py

class ManufacturingFeatureGNN:
    def predict(self, mgg, validation_report=None):
        """
        GNN returns logits ONLY.
        
        It does not modify the MGG.
        It does not modify the validation report.
        Its output is ADDED to the annotation layer, not used to replace it.
        """
        logits = self.forward(...)
        return GNNPrediction(
            logits=logits,
            proba=F.softmax(logits, dim=-1),
            inference_method=InferenceMethod.ML_GNN,
            # Note: no field to "override" anything. Output is additive only.
        )
```

---

## Authority Hierarchy in Practice (Decision Table)

| Scenario | Decision | Level Applied |
|---------|----------|--------------|
| Shapely says contour area = 0 | It's degenerate; rule GEO-003 fires | Level 1+2 |
| Rule MFG-001 says hole is 5mm from edge | Panel is invalid (ERROR) | Level 3 |
| ML says P(valid) = 0.85 despite MFG-001 failing | ML prediction ignored for validity; panel is still INVALID | Level 3 overrides Level 6 |
| Heuristic says 5mm circle = SHELF_PIN_HOLE (0.88); ML says THROUGH_HOLE (0.73) | Label = SHELF_PIN_HOLE; conflict logged | Level 4 > Level 6 |
| Heuristic says UNKNOWN_FEATURE (0.35); ML says CONFIRMAT_HOLE (0.81) | Report both; flag for review | Conflict unresolved below threshold |
| Panel passes all rules; ML says anomaly_score = 0.92 | Anomaly score added to annotations; valid status unchanged | Level 3 ≠ Level 6; coexist |

---

## Authority Labels in ProvenanceRecord

Every ProvenanceRecord carries an `authority_level` field (added to v0.1.0 schema):

```python
class InferenceMethod(str, Enum):
    DETERMINISTIC = "deterministic"   # Authority: Level 1-3
    HEURISTIC = "heuristic"           # Authority: Level 4
    SEMANTIC = "semantic"             # Authority: Level 5
    ML_GNN = "ml_gnn"                 # Authority: Level 6
    ML_LLM = "ml_llm"                 # Authority: Level 6
    SYNTHETIC = "synthetic"           # Authority: Level 1 (ground truth)
    HUMAN_ANNOTATED = "human_annotated"  # Authority: Level 3-4 (expert)

AUTHORITY_LEVELS = {
    InferenceMethod.DETERMINISTIC: 1,
    InferenceMethod.SYNTHETIC: 1,
    InferenceMethod.HUMAN_ANNOTATED: 3,
    InferenceMethod.HEURISTIC: 4,
    InferenceMethod.SEMANTIC: 5,
    InferenceMethod.ML_GNN: 6,
    InferenceMethod.ML_LLM: 6,
}
```

Any output with `authority_level > 4` MUST have confidence < 1.0.  
Any output with `authority_level <= 3` MUST have confidence = 1.0.
