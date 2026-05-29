# Provenance System

Version: v0.1.0  
Section: 08_PROVENANCE_AND_CONFIDENCE  

See also: [[02_SCHEMA/Provenance_Schema]], [[08_PROVENANCE_AND_CONFIDENCE/Confidence_Model]], [[08_PROVENANCE_AND_CONFIDENCE/Inference_Transparency]]

---

## Purpose

Documents the ProvenanceTracker implementation that records how every decision in the OMIM pipeline was made. Provenance is not optional — every node and annotation in the system carries a ProvenanceRecord.

---

## ProvenanceTracker

```python
class ProvenanceTracker:
    """
    Context manager that creates ProvenanceRecords for pipeline stages.
    
    Usage:
        with ProvenanceTracker(
            stage="semantic",
            module="omim.semantic.classifiers.hole_classifier",
            source_file="geometry.dxf",
            source_file_hash="sha256:abc123..."
        ) as tracker:
            record = tracker.create_record(
                inference_method=InferenceMethod.HEURISTIC,
                confidence=result.confidence,
                evidence=result.evidence,
                source_entity_ids=[circle.entity_id]
            )
    """
    
    def __init__(
        self,
        stage: str,
        module: str = "",
        source_file: str | None = None,
        source_file_hash: str | None = None,
        ontology_version: str = "v0.1.0",
        ruleset_version: str = "v0.1.0"
    ):
        self.stage = stage
        self.module = module
        self.source_file = source_file
        self.source_file_hash = source_file_hash
        self.ontology_version = ontology_version
        self.ruleset_version = ruleset_version
        self._records: list[ProvenanceRecord] = []
        self._start_time = None
    
    def __enter__(self) -> "ProvenanceTracker":
        self._start_time = datetime.utcnow()
        return self
    
    def __exit__(self, *args):
        self._duration_ms = (datetime.utcnow() - self._start_time).total_seconds() * 1000
    
    def create_record(
        self,
        inference_method: InferenceMethod,
        confidence: float,
        evidence: list[EvidenceItem],
        source_entity_ids: list[str] | None = None,
        parent_record_ids: list[str] | None = None,
        **extra
    ) -> ProvenanceRecord:
        record = ProvenanceRecord(
            record_id=str(uuid4()),
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
            extra=extra
        )
        self._records.append(record)
        return record
    
    def _infer_confidence_method(self, inference_method: InferenceMethod) -> str:
        return {
            InferenceMethod.DETERMINISTIC: "geometric_computation",
            InferenceMethod.HEURISTIC: "diameter_pattern_matching",
            InferenceMethod.ML_GNN: "softmax_probability",
            InferenceMethod.SYNTHETIC: "generation_ground_truth",
            InferenceMethod.HUMAN_ANNOTATED: "expert_annotation",
        }.get(inference_method, "unknown")
    
    def get_all_records(self) -> list[ProvenanceRecord]:
        return list(self._records)
    
    def get_summary(self) -> dict:
        return {
            "stage": self.stage,
            "total_records": len(self._records),
            "duration_ms": getattr(self, "_duration_ms", None),
            "methods_used": list({r.inference_method for r in self._records}),
            "confidence_range": (
                min(r.confidence for r in self._records),
                max(r.confidence for r in self._records)
            ) if self._records else (None, None)
        }
```

---

## Pipeline-Stage Provenance Records

### Parser Stage

```python
with ProvenanceTracker(stage="parsing") as tracker:
    for entity in raw_entities:
        provenance = tracker.create_record(
            inference_method=InferenceMethod.DETERMINISTIC,
            confidence=1.0,
            evidence=[EvidenceItem(
                evidence_type=EvidenceType.GEOMETRIC_MEASUREMENT,
                description=f"ezdxf extracted {entity.entity_type} from layer {entity.layer}",
                satisfied=True
            )],
            source_entity_ids=[entity.entity_id]
        )
```

### MGG Build Stage

```python
with ProvenanceTracker(stage="mgg_build") as tracker:
    # Spatial containment (deterministic Shapely)
    contains_provenance = tracker.create_record(
        inference_method=InferenceMethod.DETERMINISTIC,
        confidence=1.0,
        evidence=[EvidenceItem(
            evidence_type=EvidenceType.GEOMETRIC_MEASUREMENT,
            description=f"Shapely containment: {entity.entity_id} inside panel boundary",
            satisfied=True
        )],
        source_entity_ids=[entity.entity_id, panel_node.node_id]
    )
```

### Validation Stage

```python
# Validation is always DETERMINISTIC — rule pass/fail is computed
validation_provenance = tracker.create_record(
    inference_method=InferenceMethod.DETERMINISTIC,
    confidence=rule.confidence_ceiling,
    evidence=[EvidenceItem(
        evidence_type=EvidenceType.GEOMETRIC_MEASUREMENT,
        description=f"{rule.rule_id}: measured={measured_value}, threshold={threshold_value}",
        satisfied=result.passed
    )],
    source_entity_ids=affected_node_ids
)
```

### Semantic Annotation Stage

```python
# Semantic inference is HEURISTIC — never DETERMINISTIC
semantic_provenance = tracker.create_record(
    inference_method=InferenceMethod.HEURISTIC,
    confidence=annotation.confidence,  # bounded by semantic confidence ceilings
    evidence=annotation.evidence,
    source_entity_ids=[node.node_id]
)
```

---

## Provenance for the Full Sample (provenance.json)

The per-sample provenance file aggregates stage summaries:

```python
def build_sample_provenance(
    parser_tracker: ProvenanceTracker,
    mgg_tracker: ProvenanceTracker,
    validation_tracker: ProvenanceTracker,
    semantic_tracker: ProvenanceTracker,
    mgg: ManufacturingGeometryGraph
) -> dict:
    return {
        "schema_version": "0.1.0",
        "sample_id": mgg.metadata.graph_id,
        "pipeline_stages": [
            parser_tracker.get_summary(),
            mgg_tracker.get_summary(),
            validation_tracker.get_summary(),
            semantic_tracker.get_summary(),
        ],
        "source_file_hash": mgg.metadata.source_file_hash,
        "is_synthetic": mgg.metadata.is_synthetic,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
```

---

## Audit Function

```python
def audit_provenance(mgg: ManufacturingGeometryGraph) -> list[str]:
    """
    Check all provenance records in the MGG for consistency.
    Returns list of violations (empty = all good).
    """
    violations = []
    
    for node in mgg.query().get_all_nodes():
        p = node.provenance
        if p is None:
            violations.append(f"Node {node.node_id} has no provenance")
            continue
        
        # Deterministic method must have confidence == 1.0
        if p.inference_method == InferenceMethod.DETERMINISTIC and p.confidence != 1.0:
            violations.append(
                f"Node {node.node_id}: DETERMINISTIC method but confidence={p.confidence} != 1.0"
            )
        
        # Every record must have at least one evidence item
        if not p.evidence:
            violations.append(f"Node {node.node_id}: empty evidence list")
    
    return violations
```
