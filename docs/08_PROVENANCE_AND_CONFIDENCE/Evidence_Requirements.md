# Evidence Requirements

Version: v0.1.0  
Section: 08_PROVENANCE_AND_CONFIDENCE  

See also: [[02_SCHEMA/Provenance_Schema]], [[08_PROVENANCE_AND_CONFIDENCE/Confidence_Model]]

---

## Purpose

Specifies the minimum evidence required for each inference method. A ProvenanceRecord is only valid if its evidence list satisfies these requirements.

---

## Evidence Item Types

```python
class EvidenceType(Enum):
    GEOMETRIC_MEASUREMENT = "geometric_measurement"   # Shapely/numerical computation
    RULE_MATCH = "rule_match"                         # Rule condition satisfied
    STANDARD_REFERENCE = "standard_reference"         # Cites a published standard
    HARDWARE_SPEC = "hardware_spec"                   # Cites hardware manufacturer spec
    HEURISTIC_MATCH = "heuristic_match"               # Empirical pattern match
    EXPERT_ANNOTATION = "expert_annotation"           # Human expert label
    TRAINING_DATA = "training_data"                   # ML model inference (post-v0)
```

---

## Required Evidence by Inference Method

### DETERMINISTIC

Minimum: **1 evidence item of type `GEOMETRIC_MEASUREMENT`**

```python
# Correct: geometric measurement evidence
evidence=[EvidenceItem(
    evidence_type=EvidenceType.GEOMETRIC_MEASUREMENT,
    description="Shapely containment check: entity centroid (50, 30) inside panel polygon",
    satisfied=True,
    measured_value=0.0,        # distance from centroid to boundary
    threshold_value=None
)]

# Forbidden: rule_match for deterministic method
evidence=[EvidenceItem(
    evidence_type=EvidenceType.RULE_MATCH,  # WRONG — deterministic facts are not rule matches
    ...
)]
```

---

### RULE_BASED

Minimum: **1 evidence item of type `RULE_MATCH`**  
Recommended: Include `STANDARD_REFERENCE` or `HARDWARE_SPEC` for traceability

```python
evidence=[
    EvidenceItem(
        evidence_type=EvidenceType.RULE_MATCH,
        description="MFG-006: diameter=35.1mm matches hinge cup range 35±1mm",
        satisfied=True,
        measured_value=35.1,
        threshold_value=35.0
    ),
    EvidenceItem(
        evidence_type=EvidenceType.HARDWARE_SPEC,
        description="Blum CLIP top (item 70.1900.AC): cup diameter=35mm",
        satisfied=True,
        source_reference="Blum motion technology catalog, item 70.1900.AC"
    )
]
```

---

### HEURISTIC

Minimum: **1 evidence item of type `HEURISTIC_MATCH`**

```python
evidence=[EvidenceItem(
    evidence_type=EvidenceType.HEURISTIC_MATCH,
    description="diameter=8.0mm matches DIN 7 dowel pin range {8mm ± 0.1mm}",
    satisfied=True,
    measured_value=8.0,
    threshold_value=8.0,
    source_reference="DIN 7 Part 1"
)]
```

---

### EXPERT_ANNOTATION

Minimum: **1 evidence item of type `EXPERT_ANNOTATION`** including annotator ID

```python
evidence=[EvidenceItem(
    evidence_type=EvidenceType.EXPERT_ANNOTATION,
    description="CNC operator confirmed SHELF_PIN_HOLE on panel review 2024-03-15",
    satisfied=True,
    annotator_id="operator_01",  # anonymized
    annotation_date="2024-03-15"
)]
```

---

## Evidence Item Schema

```python
class EvidenceItem(BaseModel):
    evidence_type: EvidenceType
    description: str            # Human-readable explanation of this evidence
    satisfied: bool             # Does this evidence support the claim?
    
    # Optional measurement details
    measured_value: float | None = None
    threshold_value: float | None = None
    
    # Optional source citation
    source_reference: str | None = None    # e.g., "DIN 7 Part 1" or catalog entry
    
    # Optional annotator (for EXPERT_ANNOTATION)
    annotator_id: str | None = None
    annotation_date: str | None = None
```

---

## Validation of Evidence Requirements

```python
def validate_evidence_requirements(record: ProvenanceRecord) -> list[str]:
    """Returns list of violations (empty = valid)."""
    violations = []
    
    if not record.evidence:
        violations.append(f"Record {record.record_id}: empty evidence list")
        return violations
    
    evidence_types = {e.evidence_type for e in record.evidence}
    
    if record.inference_method == InferenceMethod.DETERMINISTIC:
        if EvidenceType.GEOMETRIC_MEASUREMENT not in evidence_types:
            violations.append(
                f"DETERMINISTIC record missing GEOMETRIC_MEASUREMENT evidence"
            )
    
    elif record.inference_method == InferenceMethod.RULE_BASED:
        if EvidenceType.RULE_MATCH not in evidence_types:
            violations.append(
                f"RULE_BASED record missing RULE_MATCH evidence"
            )
    
    elif record.inference_method == InferenceMethod.HEURISTIC:
        if EvidenceType.HEURISTIC_MATCH not in evidence_types:
            violations.append(
                f"HEURISTIC record missing HEURISTIC_MATCH evidence"
            )
    
    return violations
```

---

## Prohibited Evidence Patterns

```python
# FORBIDDEN: Empty description
EvidenceItem(evidence_type=EvidenceType.RULE_MATCH, description="", satisfied=True)

# FORBIDDEN: satisfied=True when measurement fails threshold
EvidenceItem(
    evidence_type=EvidenceType.GEOMETRIC_MEASUREMENT,
    description="edge clearance check",
    satisfied=True,   # WRONG if measured_value < threshold_value
    measured_value=5.0,
    threshold_value=8.0
)

# FORBIDDEN: Using TRAINING_DATA in v0 (ML inference not implemented)
EvidenceItem(evidence_type=EvidenceType.TRAINING_DATA, ...)  # v0 only
```
