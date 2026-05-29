# Provenance & Uncertainty Specification

Version: v0.1.0  

See also: [[What Is OMIM]], [[Manufacturing Geometry Graph (MGG) Specification]], [[Validation]]

---

## Purpose

Scientific credibility requires that every output of OMIM can be traced back to its source. This document defines the provenance and uncertainty system — how OMIM records where every piece of information came from and how confident we are in it.

**Core principle**: No semantic label, no feature classification, no validation result, and no dataset sample should exist without a clear record of how it was produced.

This is not bureaucratic overhead. It is what separates research infrastructure from hallucination.

---

## What Provenance Records

Every provenance record answers the following questions:

1. **Who** generated this output? (System version, module name)
2. **When** was it generated? (ISO 8601 timestamp)
3. **From what** was it generated? (Source file, source entity IDs)
4. **How** was it generated? (Inference method: deterministic / heuristic / ML)
5. **How confident are we?** (Confidence score + confidence method)
6. **What evidence supports this?** (Evidence items with measurements)
7. **Which rules/ontology versions were in effect?** (Version references)
8. **Has an expert reviewed this?** (Review status)

---

## ProvenanceRecord Schema

```python
class ProvenanceRecord(BaseModel):
    """Attaches to every node, edge, and output artifact in OMIM."""
    
    record_id: str              # UUID (unique per record)
    timestamp: str              # ISO 8601 UTC: "2026-05-30T14:23:05Z"
    
    # System identity
    generator: str              # "omim" 
    generator_version: str      # "v0.1.0"
    pipeline_stage: str         # "parser" | "graph_builder" | "validation" | "semantic" | "synthetic"
    module: str                 # specific module, e.g., "omim.semantic.classifiers.hole_classifier"
    
    # Version references
    ontology_version: str       # "v0.1.0"
    ruleset_version: str        # "v0.1.0"
    
    # Inference method (determines how to interpret confidence)
    inference_method: InferenceMethod  # see below
    
    # Confidence
    confidence: float           # 0.0 - 1.0 (see semantics below)
    confidence_method: str      # how confidence was computed
    
    # Evidence
    evidence: list[EvidenceItem]  # supporting evidence for this output
    
    # Source tracing
    source_file: str | None     # path or URI of source DXF
    source_file_hash: str | None  # SHA256 hash of source file
    source_entity_ids: list[str]  # ezdxf entity handles that contributed
    parent_record_ids: list[str]  # provenance records this was derived from
    
    # Review
    review_status: ReviewStatus
    reviewer: str | None
    review_timestamp: str | None
    review_notes: str | None
    
    # Additional metadata
    extra: dict = {}            # pipeline-specific additional fields

class InferenceMethod(str, Enum):
    DETERMINISTIC = "deterministic"     # Computed from geometry with certainty
    HEURISTIC = "heuristic"             # Rule-based pattern matching (non-ML)
    ML_GNN = "ml_gnn"                   # Graph Neural Network inference
    ML_LLM = "ml_llm"                   # LLM-based inference (future)
    SYNTHETIC = "synthetic"             # Generated procedurally (ground truth)
    HUMAN_ANNOTATED = "human_annotated" # Expert-labeled

class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    AUTO_VALIDATED = "auto_validated"   # Passed automated tests
    EXPERT_REVIEWED = "expert_reviewed"
    FLAGGED = "flagged"                 # Needs human review
```

---

## Confidence Semantics

Confidence is a float in [0.0, 1.0] with the following semantics:

| Inference Method | Confidence Meaning |
|-----------------|-------------------|
| `deterministic` | Always 1.0 — geometry facts are certain |
| `heuristic` | Strength of pattern match (based on how many criteria satisfied) |
| `ml_gnn` | Softmax probability from GNN classifier |
| `ml_llm` | Not used in v0 |
| `synthetic` | Always 1.0 — ground truth is certain (it was injected) |
| `human_annotated` | Always 1.0 (if single annotator) or inter-annotator agreement |

### Confidence Computation for Heuristics

```python
def compute_hole_classification_confidence(
    diameter_mm: float,
    expected_diameter_mm: float,
    diameter_tolerance_mm: float,
    context_match: bool,
    pattern_match: bool
) -> float:
    """
    Heuristic confidence for hole feature classification.
    
    Base confidence from diameter match:
      distance = abs(diameter_mm - expected_diameter_mm)
      diameter_score = max(0, 1 - distance / diameter_tolerance_mm)
    
    Context bonus:
      +0.05 if geometric context matches expected pattern
      +0.08 if part of confirmed group pattern (e.g., shelf pin row)
    
    Returns: min(1.0, diameter_score + context_bonus + pattern_bonus)
    """
```

### Mandatory Confidence Rules

1. `inference_method = "deterministic"` → confidence MUST be 1.0
2. `inference_method = "synthetic"` → confidence MUST be 1.0
3. `inference_method = "heuristic"` → confidence in [0.30, 0.99]
4. `inference_method = "ml_gnn"` → confidence is raw softmax output
5. Any output with `confidence < 0.3` must have `review_status = "flagged"`

---

## EvidenceItem Schema

```python
class EvidenceItem(BaseModel):
    """One piece of supporting evidence for a classification or inference."""
    
    evidence_type: EvidenceType
    description: str            # Human-readable explanation
    value: float | str | None   # Measured/observed value
    expected: float | str | None  # Expected value (for comparison)
    unit: str | None            # "mm" | "mm²" | "degrees" | etc.
    rule_id: str | None         # If this evidence comes from a rule evaluation
    node_id: str | None         # If this evidence refers to a specific node
    
    # Scoring contribution
    weight: float = 1.0         # How much this evidence contributes to confidence
    satisfied: bool             # Whether this evidence supports the classification

class EvidenceType(str, Enum):
    GEOMETRIC_MEASUREMENT = "geometric_measurement"   # Measured geometry (area, diameter, etc.)
    RULE_MATCH = "rule_match"                         # Rule was satisfied
    PATTERN_MATCH = "pattern_match"                   # Spatial pattern detected
    PROXIMITY = "proximity"                           # Spatial relationship
    LAYER_CONVENTION = "layer_convention"             # DXF layer name convention
    DIAMETER_MATCH = "diameter_match"                 # Diameter within expected range
    SPACING_MATCH = "spacing_match"                   # Spacing within expected range
    GROUP_DETECTION = "group_detection"               # Part of a detected feature group
    ML_EMBEDDING = "ml_embedding"                     # Neural network embedding similarity
```

### Evidence Example (SHELF_PIN_HOLE)

```json
{
  "evidence": [
    {
      "evidence_type": "diameter_match",
      "description": "Circle diameter 5.0mm matches SHELF_PIN_HOLE expected diameter 5.0mm",
      "value": 5.0,
      "expected": 5.0,
      "unit": "mm",
      "satisfied": true,
      "weight": 0.6
    },
    {
      "evidence_type": "spacing_match",
      "description": "Spacing to adjacent hole is 32.0mm, matching 32mm modular system",
      "value": 32.0,
      "expected": 32.0,
      "unit": "mm",
      "satisfied": true,
      "weight": 0.3
    },
    {
      "evidence_type": "group_detection",
      "description": "Part of a detected column of 4 collinear holes with 32mm spacing",
      "value": 4,
      "expected": null,
      "unit": "count",
      "satisfied": true,
      "weight": 0.1
    }
  ]
}
```

---

## Provenance Tracker

The `ProvenanceTracker` is a context manager that automatically captures metadata as the pipeline runs.

```python
# omim/provenance/tracker.py

class ProvenanceTracker:
    """
    Context manager that creates ProvenanceRecords for pipeline stages.
    
    Usage:
        with ProvenanceTracker(stage="semantic", module="hole_classifier") as tracker:
            result = classify_hole(circle)
            record = tracker.create_record(
                inference_method=InferenceMethod.HEURISTIC,
                confidence=result.confidence,
                evidence=result.evidence,
                source_entity_ids=[circle.entity_id]
            )
    """
    
    def __init__(self, 
                 stage: str,
                 module: str,
                 source_file: str | None = None,
                 source_file_hash: str | None = None,
                 ontology_version: str = "v0.1.0",
                 ruleset_version: str = "v0.1.0"):
        self.stage = stage
        self.module = module
        self.source_file = source_file
        self.source_file_hash = source_file_hash
        self.ontology_version = ontology_version
        self.ruleset_version = ruleset_version
        self._records: list[ProvenanceRecord] = []
    
    def create_record(
        self,
        inference_method: InferenceMethod,
        confidence: float,
        evidence: list[EvidenceItem],
        source_entity_ids: list[str] | None = None,
        parent_record_ids: list[str] | None = None,
        **extra
    ) -> ProvenanceRecord:
        """Create a ProvenanceRecord with current context."""
        record = ProvenanceRecord(
            record_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            generator="omim",
            generator_version=OMIM_VERSION,
            pipeline_stage=self.stage,
            module=self.module,
            ontology_version=self.ontology_version,
            ruleset_version=self.ruleset_version,
            inference_method=inference_method,
            confidence=confidence,
            confidence_method=self._infer_confidence_method(inference_method),
            evidence=evidence,
            source_file=self.source_file,
            source_file_hash=self.source_file_hash,
            source_entity_ids=source_entity_ids or [],
            parent_record_ids=parent_record_ids or [],
            review_status=ReviewStatus.UNREVIEWED,
        )
        record.extra = extra
        self._records.append(record)
        return record
    
    def get_records(self) -> list[ProvenanceRecord]:
        return self._records.copy()
```

---

## Provenance in the Pipeline

### Parser → ProvenanceRecord
```python
# For each parsed geometry entity
ProvenanceRecord(
    pipeline_stage="parser",
    inference_method=InferenceMethod.DETERMINISTIC,
    confidence=1.0,
    source_entity_ids=[ezdxf_entity.dxf.handle],
    evidence=[EvidenceItem(
        evidence_type=EvidenceType.GEOMETRIC_MEASUREMENT,
        description="Directly extracted from DXF entity",
        satisfied=True
    )]
)
```

### MGG Builder → ProvenanceRecord
```python
# For each spatial relationship inferred
ProvenanceRecord(
    pipeline_stage="graph_builder",
    inference_method=InferenceMethod.DETERMINISTIC,
    confidence=1.0,
    evidence=[EvidenceItem(
        evidence_type=EvidenceType.GEOMETRIC_MEASUREMENT,
        description=f"Spatial relationship detected: distance={dist:.2f}mm < threshold={threshold:.2f}mm"
    )]
)
```

### Validation → ProvenanceRecord
```python
# For each rule evaluation
ProvenanceRecord(
    pipeline_stage="validation",
    inference_method=InferenceMethod.DETERMINISTIC,
    confidence=1.0,
    evidence=[EvidenceItem(
        evidence_type=EvidenceType.RULE_MATCH,
        rule_id="MFG-001",
        description=f"Edge clearance {measured:.1f}mm vs threshold {threshold:.1f}mm",
        value=measured,
        expected=threshold,
        satisfied=(measured >= threshold)
    )]
)
```

### Semantic Layer → ProvenanceRecord
```python
# For each feature classification
ProvenanceRecord(
    pipeline_stage="semantic",
    inference_method=InferenceMethod.HEURISTIC,
    confidence=0.92,
    evidence=[
        EvidenceItem(type=EvidenceType.DIAMETER_MATCH, ...),
        EvidenceItem(type=EvidenceType.SPACING_MATCH, ...),
    ]
)
```

---

## Uncertainty Representation

### Multiple Hypotheses
When a feature could be one of several classes, ALL ranked hypotheses are stored:

```json
{
  "feature_class": "SHELF_PIN_HOLE",
  "confidence": 0.87,
  "hypotheses": [
    {"feature_class": "SHELF_PIN_HOLE", "confidence": 0.87},
    {"feature_class": "THROUGH_HOLE", "confidence": 0.10},
    {"feature_class": "DOWEL_HOLE", "confidence": 0.03}
  ]
}
```

The primary `feature_class` is always the highest-confidence hypothesis.

### Low Confidence Handling

```python
CONFIDENCE_THRESHOLDS = {
    "accept": 0.60,        # Feature class accepted as primary label
    "flag_for_review": 0.30,  # Accept but mark for human review
    "reject": 0.00,         # Below 0.30: label as UNKNOWN_FEATURE
}

def apply_confidence_threshold(annotation: SemanticAnnotation) -> SemanticAnnotation:
    if annotation.confidence >= CONFIDENCE_THRESHOLDS["accept"]:
        annotation.review_status = ReviewStatus.AUTO_VALIDATED
    elif annotation.confidence >= CONFIDENCE_THRESHOLDS["flag_for_review"]:
        annotation.feature_class = annotation.feature_class  # keep tentative label
        annotation.review_status = ReviewStatus.FLAGGED
    else:
        annotation.feature_class = "UNKNOWN_FEATURE"
        annotation.review_status = ReviewStatus.FLAGGED
    return annotation
```

---

## Provenance in Dataset Samples

Every synthetic dataset sample carries a complete provenance chain:

```json
{
  "sample_id": "sample_00001",
  "provenance": {
    "record_id": "...",
    "generator": "omim",
    "generator_version": "v0.1.0",
    "inference_method": "synthetic",
    "confidence": 1.0,
    "ontology_version": "v0.1.0",
    "ruleset_version": "v0.1.0",
    "pipeline_stages": ["synthetic_generator", "parser", "graph_builder", "validation", "semantic"],
    "generation_seed": 42,
    "generation_config": "default.yaml",
    "timestamp": "2026-05-30T14:23:05Z"
  }
}
```

---

## Provenance Enforcement

Provenance is not optional. The system actively enforces it through three mechanisms:

### Mechanism 1: Pydantic Validation at Model Level

```python
class FeatureNode(BaseModel):
    provenance: ProvenanceRecord  # NOT Optional[ProvenanceRecord]
    # Pydantic will reject any FeatureNode without provenance at construction time
    
class SemanticAnnotation(BaseModel):
    confidence: float             # NOT Optional[float]
    evidence: list[EvidenceItem]  # NOT Optional — must have at least one item
    provenance: ProvenanceRecord  # NOT Optional
    
    @field_validator("confidence")
    def confidence_in_range(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence {v} outside [0.0, 1.0]")
        return v
    
    @field_validator("evidence")
    def evidence_not_empty(cls, v):
        if len(v) == 0:
            raise ValueError("evidence list cannot be empty — provide at least one EvidenceItem")
        return v

class ProvenanceRecord(BaseModel):
    @model_validator(mode="after")
    def deterministic_confidence_must_be_one(self):
        if self.inference_method == InferenceMethod.DETERMINISTIC:
            if self.confidence != 1.0:
                raise ValueError(f"Deterministic inference must have confidence=1.0, got {self.confidence}")
        return self
```

### Mechanism 2: Dataset Schema Validation

The `validate_sample_schema()` function (defined in [[Canonical Sample Schema]]) is run on EVERY sample before it is added to any dataset split. Samples with provenance violations are rejected.

```python
# In dataset_builder.py — enforced, not optional:
errors = validate_sample_schema(sample_dir)
if errors:
    logger.error(f"Sample {sample_id} rejected: {errors}")
    failed_samples.append(sample_id)
    continue  # do NOT include in dataset
# Only include valid, complete samples in splits
```

### Mechanism 3: Audit Query

At any time, the entire MGG can be audited for provenance completeness:

```python
def audit_provenance(mgg: ManufacturingGeometryGraph) -> ProvenanceAuditReport:
    """
    Check that every node in the MGG has complete, valid provenance.
    Returns list of nodes missing or having invalid provenance.
    """
    violations = []
    for node in mgg.query().get_all_nodes():
        if node.provenance is None:
            violations.append(ProvenanceViolation(node_id=node.node_id, issue="missing_provenance"))
        elif node.provenance.inference_method == InferenceMethod.DETERMINISTIC and node.provenance.confidence != 1.0:
            violations.append(ProvenanceViolation(node_id=node.node_id, issue="deterministic_confidence_mismatch"))
    
    return ProvenanceAuditReport(
        total_nodes=len(list(mgg.query().get_all_nodes())),
        violations=violations,
        is_clean=len(violations) == 0
    )
```

This audit runs automatically as part of the test suite (`test_provenance.py`).

---

## What Provenance Does NOT Cover

- Physical machine logs (out of scope)
- Human design intent (inferred, not recorded)
- Material properties (modeled as assumptions, not measurements)
- Tool wear state (not modeled in v0)

These are documented limitations, not omissions.

---

## Serialization

ProvenanceRecord serializes to/from JSON with full fidelity. All fields are JSON-serializable (strings, numbers, lists, dicts).

```python
# Round-trip test (required acceptance test)
record = create_provenance_record(...)
json_str = record.model_dump_json()
record2 = ProvenanceRecord.model_validate_json(json_str)
assert record == record2  # All fields must be equal
```
