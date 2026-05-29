# Trust & Authority Hierarchy

**Status: ENFORCED — This is an architectural invariant, not a suggestion.**

Version: v0.1.0  
Section: 01_FOUNDATION  

See also: [[05_VALIDATION/Rule_Engine]], [[08_PROVENANCE_AND_CONFIDENCE/Confidence_Model]]

---

## Purpose

Every system, module, and inference layer has a defined position in this hierarchy. Lower levels NEVER override higher levels. Period.

This hierarchy guards against:
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
- **What**: Raw output of Shapely and ezdxf computations. Positions, areas, distances, intersections.
- **ProvenanceRecord.inference_method**: `"deterministic"`
- **ProvenanceRecord.confidence**: Always `1.0`
- **Authority rule**: These values cannot be "wrong" from the system's perspective.

### Level 2: Topological Validity
- **What**: Topology checks — contour self-intersection, closure, connectivity.
- **ProvenanceRecord.inference_method**: `"deterministic"`
- **ProvenanceRecord.confidence**: Always `1.0`
- **Authority rule**: Topological facts are computed deterministically.

### Level 3: Standards and Rules
- **What**: Manufacturing rules drawn from ISO standards, DIN standards, hardware manufacturer specifications.
- **ProvenanceRecord.inference_method**: `"deterministic"`
- **ProvenanceRecord.confidence**: `1.0`
- **Critical constraint**: A rule from Level 3 CANNOT be weakened or invalidated by Level 4–6 outputs.

### Level 4: Deterministic Heuristics
- **What**: Pattern-matching logic rule-based but derived from engineering judgment, not a formal standard.
- **Confidence range**: 0.50 – 0.95 (never 1.0 unless backed by standards)
- **ProvenanceRecord.inference_method**: `"heuristic"`
- **Critical constraint**: Level 4 result CANNOT override a Level 3 rule violation.

### Level 5: Semantic Inference
- **What**: Feature classification layer synthesizing geometry, patterns, and context into manufacturing meaning.
- **Confidence range**: 0.30 – 0.99
- **ProvenanceRecord.inference_method**: `"heuristic"` (rules-based) or `"ml_gnn"` (GNN-based)
- **Multiple hypotheses required for confidence < 0.75**

### Level 6: ML Predictions
- **What**: Outputs from trained GNN or other ML models.
- **Confidence range**: 0.0 – 1.0 (raw softmax output; not calibrated by default)
- **Critical constraints**:
  1. ML CANNOT change geometry measurements
  2. ML CANNOT mark a validated-invalid panel as valid
  3. ML CANNOT assert a new manufacturing rule
  4. ML output MUST include confidence and evidence
  5. If ML and deterministic heuristic disagree: **report both, do not silently pick one**

---

## Conflict Resolution Protocol

```
Level 1 vs Level 2–6:    Level 1 wins. Always.
Level 2 vs Level 3–6:    Level 2 wins. Always.
Level 3 vs Level 4–6:    Level 3 wins. Always.
Level 4 vs Level 5–6:    Level 4 wins. Report both.
Level 5 vs Level 6:      Level 5 wins if confidence > 0.60, else report both.
Level 6 alone:           Only valid if no Level 4–5 result exists.
```

**Conflict flagging**: Any conflict between levels MUST be surfaced in the output with both values and their sources. Silent conflict resolution is forbidden.

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
    def execute_layer2(self, mgg):
        # No semantic_annotations parameter.
        # Validation CANNOT query the semantic layer.
        # Structural enforcement of Level 3 > Level 5.
        pass

# omim/semantic/inference_engine.py
class InferenceEngine:
    def infer(self, mgg, validation_report):
        # Receives ValidationReport as READ-ONLY.
        # CANNOT modify validation_report.overall_valid.
        assert not hasattr(validation_report, '__setattr__')

# omim/ml/models/gnn_classifier.py
class ManufacturingFeatureGNN:
    def predict(self, mgg, validation_report=None):
        # Returns additive GNNPrediction only.
        # Does NOT modify the MGG or validation report.
        return GNNPrediction(logits=..., proba=..., inference_method=InferenceMethod.ML_GNN)
```

---

## Authority Labels in ProvenanceRecord

```python
class InferenceMethod(str, Enum):
    DETERMINISTIC = "deterministic"    # Authority: Level 1-3
    HEURISTIC = "heuristic"            # Authority: Level 4
    SEMANTIC = "semantic"              # Authority: Level 5
    ML_GNN = "ml_gnn"                  # Authority: Level 6
    SYNTHETIC = "synthetic"            # Authority: Level 1 (ground truth)
    HUMAN_ANNOTATED = "human_annotated"  # Authority: Level 3-4 (expert)

AUTHORITY_LEVELS = {
    InferenceMethod.DETERMINISTIC: 1,
    InferenceMethod.SYNTHETIC: 1,
    InferenceMethod.HUMAN_ANNOTATED: 3,
    InferenceMethod.HEURISTIC: 4,
    InferenceMethod.SEMANTIC: 5,
    InferenceMethod.ML_GNN: 6,
}
```

**Invariants**:
- Any output with `authority_level > 4` MUST have confidence < 1.0
- Any output with `authority_level <= 3` MUST have confidence = 1.0

---

## Decision Table

| Scenario | Decision | Level Applied |
|---------|----------|--------------|
| Shapely says contour area = 0 | It's degenerate; rule GEO-003 fires | Level 1+2 |
| Rule MFG-001 says hole is 5mm from edge | Panel is invalid (ERROR) | Level 3 |
| ML says P(valid) = 0.85 despite MFG-001 failing | Panel is still INVALID | Level 3 overrides Level 6 |
| Heuristic says 5mm circle = SHELF_PIN_HOLE (0.88); ML says THROUGH_HOLE (0.73) | Label = SHELF_PIN_HOLE; conflict logged | Level 4 > Level 6 |
| Heuristic says UNKNOWN_FEATURE (0.35); ML says CONFIRMAT_HOLE (0.81) | Report both; flag for review | Conflict unresolved |
| Panel passes all rules; ML says anomaly_score = 0.92 | Anomaly score added to annotations; valid status unchanged | Level 3 ≠ Level 6 |
