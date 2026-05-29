# Provenance Schema

**Schema Version: v0.1.0**

Version: v0.1.0  
Section: 02_SCHEMA  

See also: [[08_PROVENANCE_AND_CONFIDENCE/Provenance_System]], [[08_PROVENANCE_AND_CONFIDENCE/Confidence_Model]]

---

## Purpose

Defines the exact schema for ProvenanceRecord — the universal metadata object attached to every node, edge, and output in OMIM — and for `provenance.json` at the dataset sample level.

---

## ProvenanceRecord Schema

```python
class ProvenanceRecord(BaseModel):
    record_id: str              # UUID
    timestamp: str              # ISO 8601 UTC: "2026-05-30T14:23:05Z"
    
    # System identity
    generator: str              # "omim"
    generator_version: str      # "v0.1.0"
    pipeline_stage: str         # "parser" | "graph_builder" | "validation" | "semantic" | "synthetic"
    module: str                 # e.g., "omim.semantic.classifiers.hole_classifier"
    
    # Version references
    ontology_version: str       # "v0.1.0"
    ruleset_version: str        # "v0.1.0"
    
    # Inference method
    inference_method: InferenceMethod
    
    # Confidence
    confidence: float           # [0.0, 1.0]
    confidence_method: str      # how confidence was computed
    
    # Evidence
    evidence: list[EvidenceItem]  # REQUIRED — not Optional
    
    # Source tracing
    source_file: str | None
    source_file_hash: str | None  # SHA256
    source_entity_ids: list[str]
    parent_record_ids: list[str]
    
    # Review
    review_status: ReviewStatus
    reviewer: str | None
    review_timestamp: str | None
    review_notes: str | None

    @model_validator(mode="after")
    def deterministic_confidence_must_be_one(self):
        if self.inference_method == InferenceMethod.DETERMINISTIC:
            if self.confidence != 1.0:
                raise ValueError(f"Deterministic inference must have confidence=1.0, got {self.confidence}")
        return self


class InferenceMethod(str, Enum):
    DETERMINISTIC = "deterministic"
    HEURISTIC = "heuristic"
    ML_GNN = "ml_gnn"
    ML_LLM = "ml_llm"
    SYNTHETIC = "synthetic"
    HUMAN_ANNOTATED = "human_annotated"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    AUTO_VALIDATED = "auto_validated"
    EXPERT_REVIEWED = "expert_reviewed"
    FLAGGED = "flagged"
```

---

## EvidenceItem Schema

```python
class EvidenceItem(BaseModel):
    evidence_type: EvidenceType
    description: str
    value: float | str | None
    expected: float | str | None
    unit: str | None            # "mm" | "mm²" | "degrees" | "count"
    rule_id: str | None
    node_id: str | None
    weight: float = 1.0
    satisfied: bool


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
```

### Evidence Example (SHELF_PIN_HOLE classification)

```json
{
  "evidence": [
    {
      "evidence_type": "diameter_match",
      "description": "Circle diameter 5.0mm matches SHELF_PIN_HOLE expected diameter 5.0mm",
      "value": 5.0, "expected": 5.0, "unit": "mm",
      "satisfied": true, "weight": 0.6
    },
    {
      "evidence_type": "spacing_match",
      "description": "Spacing to adjacent hole is 32.0mm, matching 32mm modular system",
      "value": 32.0, "expected": 32.0, "unit": "mm",
      "satisfied": true, "weight": 0.3
    },
    {
      "evidence_type": "group_detection",
      "description": "Part of a detected column of 4 collinear holes with 32mm spacing",
      "value": 4, "unit": "count", "satisfied": true, "weight": 0.1
    }
  ]
}
```

---

## `provenance.json` (Per Sample)

```json
{
  "$schema": "omim-provenance-v0.1.0",
  "sample_id": "sample_00001",
  "schema_version": "v0.1.0",
  
  "pipeline_stages": [
    {
      "stage": "synthetic_generator",
      "record_id": "...",
      "timestamp": "2026-05-30T14:23:05Z",
      "generator": "omim",
      "generator_version": "v0.1.0",
      "ontology_version": "v0.1.0",
      "ruleset_version": "v0.1.0",
      "inference_method": "synthetic",
      "confidence": 1.0,
      "generation_seed": 1001,
      "generation_config": "default.yaml"
    },
    {
      "stage": "parser",
      "inference_method": "deterministic",
      "confidence": 1.0,
      "source_file": "geometry.dxf",
      "source_file_hash": "sha256:abc123..."
    },
    {
      "stage": "validation",
      "inference_method": "deterministic",
      "confidence": 1.0,
      "ruleset_version": "v0.1.0",
      "rules_evaluated": ["GEO-001", "GEO-002", "MFG-001", "MFG-002"]
    },
    {
      "stage": "semantic",
      "inference_method": "heuristic",
      "confidence": 0.88
    }
  ],
  
  "source_license": "Apache 2.0",
  "source_type": "synthetic_generated",
  "contains_external_data": false,
  "dataset_version": "omim-synthetic-v0.1.0"
}
```

---

## Mandatory Confidence Rules

| Inference Method | Confidence Constraint |
|-----------------|----------------------|
| `deterministic` | MUST be 1.0 — enforced by Pydantic model_validator |
| `synthetic` | MUST be 1.0 — ground truth is certain |
| `heuristic` | MUST be in [0.30, 0.99] — never 1.0 |
| `ml_gnn` | Any value in [0.0, 1.0] — raw softmax |
| `human_annotated` | 1.0 (single annotator) or inter-annotator agreement |

---

## Enforcement Mechanisms

### 1. Pydantic Validation (Construction Time)
```python
class SemanticAnnotation(BaseModel):
    confidence: float           # NOT Optional
    evidence: list[EvidenceItem]  # NOT Optional, NOT empty
    provenance: ProvenanceRecord  # NOT Optional

    @field_validator("evidence")
    def evidence_not_empty(cls, v):
        if len(v) == 0:
            raise ValueError("evidence list cannot be empty")
        return v
```

### 2. Dataset Write-Time Validation
Every sample validated with `validate_sample_schema()` before inclusion in any split.

### 3. Audit Function
```python
def audit_provenance(mgg: ManufacturingGeometryGraph) -> ProvenanceAuditReport:
    violations = []
    for node in mgg.query().get_all_nodes():
        if node.provenance is None:
            violations.append(ProvenanceViolation(node_id=node.node_id, issue="missing_provenance"))
        elif node.provenance.inference_method == InferenceMethod.DETERMINISTIC and node.provenance.confidence != 1.0:
            violations.append(ProvenanceViolation(node_id=node.node_id, issue="deterministic_confidence_mismatch"))
    return ProvenanceAuditReport(total_nodes=..., violations=violations, is_clean=len(violations)==0)
```

---

## Round-Trip Guarantee

```python
# Required acceptance test
record = create_provenance_record(...)
json_str = record.model_dump_json()
record2 = ProvenanceRecord.model_validate_json(json_str)
assert record == record2
```
