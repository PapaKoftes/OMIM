# Inference Transparency

Version: v0.1.0  
Section: 08_PROVENANCE_AND_CONFIDENCE  

See also: [[08_PROVENANCE_AND_CONFIDENCE/Provenance_System]], [[08_PROVENANCE_AND_CONFIDENCE/Confidence_Model]], [[01_FOUNDATION/Authority_Hierarchy]]

---

## Purpose

Defines how OMIM surfaces inference decisions to downstream systems. Transparency means: every output comes with a machine-readable explanation of how it was produced, and every conflict is surfaced rather than silently resolved.

---

## Conflict Surfacing

When two inference mechanisms produce different conclusions about the same geometry node, OMIM surfaces the conflict — it does not silently pick one:

```python
class InferenceConflict(BaseModel):
    node_id: str
    attribute: str           # which attribute has conflicting values
    claims: list[ConflictClaim]
    resolution: str | None   # how it was resolved, or None if unresolved
    resolution_method: str | None  # "authority_hierarchy" | "confidence_max" | "unresolved"

class ConflictClaim(BaseModel):
    source: str              # which stage/rule produced this claim
    value: str               # the claimed value
    confidence: float
    inference_method: str
    authority_level: int     # 1–6 from Trust Hierarchy
```

**Resolution by Trust Hierarchy**:
```python
def resolve_conflict(claims: list[ConflictClaim]) -> ConflictClaim:
    """Higher authority_level wins. If same level, higher confidence wins."""
    return max(claims, key=lambda c: (c.authority_level, c.confidence))
```

---

## Inference Chain

Every `FeatureAnnotation` includes a chain showing how the classification was reached:

```python
class InferenceChain(BaseModel):
    steps: list[InferenceStep]

class InferenceStep(BaseModel):
    step_number: int
    description: str         # Human-readable explanation
    evidence: EvidenceItem
    result: str              # What conclusion this step produced
    confidence_at_step: float
```

Example for HINGE_CUP_HOLE:
```python
InferenceChain(steps=[
    InferenceStep(
        step_number=1,
        description="Entity type check: CIRCLE",
        evidence=EvidenceItem(evidence_type=EvidenceType.GEOMETRIC_MEASUREMENT, ...),
        result="entity_is_circle=True",
        confidence_at_step=1.0
    ),
    InferenceStep(
        step_number=2,
        description="Diameter range check: 35mm ± 1mm",
        evidence=EvidenceItem(evidence_type=EvidenceType.RULE_MATCH, measured_value=35.1, ...),
        result="diameter_matches_hinge_cup=True",
        confidence_at_step=0.90
    ),
    InferenceStep(
        step_number=3,
        description="Edge distance check: 22.5mm ± 1mm",
        evidence=EvidenceItem(evidence_type=EvidenceType.RULE_MATCH, measured_value=22.3, ...),
        result="edge_distance_matches=True",
        confidence_at_step=0.90
    ),
])
```

---

## Audit Tooling

```python
def audit_provenance(mgg: ManufacturingGeometryGraph) -> AuditReport:
    """
    Comprehensive provenance audit.
    Returns AuditReport with all violations and statistics.
    """
    violations = []
    
    for node in mgg.query().get_all_nodes():
        v = validate_provenance_record(node.provenance)
        violations.extend(v)
    
    return AuditReport(
        total_nodes=mgg.metadata.node_count,
        nodes_with_provenance=sum(1 for n in mgg.query().get_all_nodes() if n.provenance),
        violations=violations,
        confidence_distribution=compute_confidence_distribution(mgg),
        method_distribution=compute_method_distribution(mgg)
    )

class AuditReport(BaseModel):
    total_nodes: int
    nodes_with_provenance: int
    violations: list[str]
    is_clean: bool = field(default_factory=lambda: len(violations) == 0)
    confidence_distribution: dict  # {method: [confidence values]}
    method_distribution: dict      # {method: count}
```

---

## Transparency in Dataset Export

The `provenance.json` per-sample file exposes inference transparency to dataset consumers:

```json
{
  "pipeline_stages": [
    {
      "stage": "semantic_annotation",
      "methods_used": ["rule_based"],
      "confidence_range": [0.65, 0.90],
      "unclassified_nodes": 2,
      "conflicts_surfaced": 1,
      "conflicts_resolved": 1
    }
  ],
  "inference_conflicts": [
    {
      "node_id": "node_abc123",
      "attribute": "feature_class",
      "claims": [
        {"source": "diameter_rule", "value": "DOWEL_HOLE", "confidence": 0.75},
        {"source": "layer_name_rule", "value": "THROUGH_HOLE", "confidence": 0.65}
      ],
      "resolution": "DOWEL_HOLE",
      "resolution_method": "confidence_max"
    }
  ]
}
```

---

## What OMIM Does NOT Hide

1. **Low-confidence classifications**: Always reported with their actual confidence, not rounded up
2. **Unclassified features**: Reported as `UNKNOWN_FEATURE` with `confidence=0.0`, not omitted
3. **Conflicting evidence**: InferenceConflicts always included in output, even when resolved
4. **System errors in rules**: `SYSTEM_ERROR` RuleResult included in ValidationReport, not swallowed
5. **Alternative hypotheses**: When confidence < 0.90, alternatives are listed

**Principle**: A researcher looking at OMIM output should be able to reconstruct every inference decision from the provenance records alone.
