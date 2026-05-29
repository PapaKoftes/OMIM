# Failure Mode Specification v0.1

See also: [[Hard Limits and Constraints]], [[Trust and Authority Hierarchy]], [[Provenence and Uncertainty]], [[Validation]]

---

## Purpose

This document defines every known failure mode in OMIM, what happens when they occur, and how they are surfaced to the caller. 

**Hidden failures are the most dangerous kind.** This document ensures that no failure mode is silently swallowed.

Rule: Every module either returns a result (which may contain errors embedded in the result object) OR raises a typed exception. Silent exceptions and `pass` on exception blocks are forbidden in all core modules.

---

## Failure Categories

```
Category A: Input Failures         (bad DXF, unsupported format)
Category B: Geometry Failures      (malformed geometry, degenerate cases)
Category C: Validation Failures    (manufacturing rule violations)
Category D: Semantic Failures      (ambiguous classification, low confidence)
Category E: Synthetic Generation Failures  (placement failures, infeasible configs)
Category F: System Failures        (ML unavailable, rule load failure)
Category G: Schema Violations      (missing provenance, invalid fields)
```

---

## Category A: Input Failures

### A-001: DXF File Not Found
- **Trigger**: `parse_dxf("nonexistent.dxf")`
- **Behavior**: Raise `FileNotFoundError` with descriptive message
- **Do NOT**: Return empty `RawGeometry` silently
- **Recovery**: Caller must handle; cannot proceed without input

### A-002: DXF File Unreadable (Corrupt/Binary)
- **Trigger**: ezdxf raises `ezdxf.DXFStructureError`
- **Behavior**: Return `ParseResult` with `success=False`, `error_code="DXF_CORRUPT"`, `error_message=str(e)`
- **Do NOT**: Crash pipeline; do NOT return partial data
- **Logged**: `logger.error("DXF corrupt: {filepath}: {e}")`
- **Recovery**: Skip this file in batch processing; log path for investigation

### A-003: DXF Version Unsupported
- **Trigger**: DXF version < AC1015 (pre-2000) or unknown version string
- **Behavior**: Return `ParseResult` with `success=False`, `error_code="DXF_VERSION_UNSUPPORTED"`
- **Recovery**: Convert file using LibreCAD (external); retry

### A-004: DXF File Too Large
- **Trigger**: File size > 50MB
- **Behavior**: Return `ParseResult` with `success=False`, `error_code="DXF_TOO_LARGE"`
- **Recovery**: Split the DXF; scope not supported in v0

### A-005: Empty DXF (No Entities)
- **Trigger**: DXF file is valid but modelspace has zero entities
- **Behavior**: Return `RawGeometry` with empty `entities` list + `warning="empty_file"`
- **Do NOT**: Crash; empty files are valid inputs (produce empty MGG, empty validation)
- **Note**: This is NOT an error — valid dataset sample with no features

### A-006: DXF Has Only Annotations (No Cuttable Entities)
- **Trigger**: DXF contains only TEXT, DIMENSION, HATCH, INSERT — no LINE/CIRCLE/ARC/POLYLINE
- **Behavior**: Return `RawGeometry` with empty geometry + warning `"no_cuttable_entities"`
- **Note**: Likely a drawing file, not a CNC file

---

## Category B: Geometry Failures

### B-001: Open Contour (Expected Closed)
- **Trigger**: LWPOLYLINE on CUT layer with `is_closed=False` and endpoint gap > 0.01mm
- **Behavior**: Geometry node created with `is_closed=False`; Rule GEO-001 fires in Layer 1 validation
- **Authority**: Level 2 (topological) — this IS an error, no heuristic override
- **Dataset impact**: This sample is marked `is_valid=False` with violation `"GEO-001"`

### B-002: Self-Intersecting Contour
- **Trigger**: `Shapely.is_simple == False` for a closed contour
- **Behavior**: Geometry node created; GEO-002 fires; `is_valid=False`
- **Note**: Some DXF exports create self-intersecting spline approximations — log prominently

### B-003: Zero-Area Feature
- **Trigger**: Closed contour with `shapely.area < 0.01mm²`
- **Behavior**: GEO-003 fires; feature skipped for semantic inference
- **Recovery**: Likely a stray entity; parser logs warning

### B-004: Negative or Zero Radius Circle
- **Trigger**: ezdxf CIRCLE entity with `radius <= 0`
- **Behavior**: Entity skipped; parser logs warning `"degenerate_circle_skipped: {entity_handle}"`
- **Do NOT**: Include in MGG — degenerate geometry pollutes the graph

### B-005: Geometry Outside Panel Bounds
- **Trigger**: Feature centroid outside the detected panel boundary (GEO-007)
- **Behavior**: Rule fires; feature still included in MGG (may be intentional); sample marked invalid
- **Note**: Some DXFs have annotation geometry outside the panel — use layer filter before checking

### B-006: No Panel Boundary Detected
- **Trigger**: No closed contour on CUT layer that could serve as panel boundary
- **Behavior**: Parser infers panel bounds from bounding box of all entities; logs `"warning: no explicit panel boundary; using geometry bounding box + 10mm margin"`
- **Confidence impact**: All edge-clearance rules (Level 3) fall back to bounding-box inference; lower confidence on those results
- **`panel_boundary_inferred = true`** recorded in MGG metadata

### B-007: Coordinate System Mismatch
- **Trigger**: DXF header `$INSUNITS = 1` (inches) instead of 4 (mm)
- **Behavior**: Normalizer converts all coordinates to mm; logs `"units_converted: inches_to_mm"`
- **Provenance**: `"units_normalized_from": "inches"` stored in provenance

### B-008: Duplicate Entities
- **Trigger**: Two geometrically identical entities at same position on same layer
- **Behavior**: GEO-006 fires (WARNING); both entities retained; duplicate pair logged
- **Note**: Duplicates cause double-cutting on real machines — always surface, never silently deduplicate

---

## Category C: Validation Failures

### C-001: Rule Evaluation Exception
- **Trigger**: Code inside a rule check raises an unexpected exception
- **Behavior**: `RuleResult(rule_id=..., passed=False, severity="SYSTEM_ERROR", message=str(e))`
- **Do NOT**: Let one rule crash the whole validation run
- **Recovery**: Log traceback; continue evaluating remaining rules

### C-002: Rule YAML Not Found
- **Trigger**: `data/rules/panel_cnc_rules.yaml` missing at startup
- **Behavior**: Raise `RuleLoadError` at startup, before any parsing
- **Recovery**: Check file exists before running pipeline; this is a configuration error

### C-003: Unknown Rule ID in YAML
- **Trigger**: Rule YAML has `rule_id: MFG-999` but no implementation
- **Behavior**: `RuleEngine` raises `UnknownRuleError` at load time
- **Recovery**: Remove rule from YAML or implement it; no silent skip

### C-004: Rule Timeout
- **Trigger**: A rule takes > 10 seconds on a single part (performance guard)
- **Behavior**: Rule killed; `RuleResult(severity="SYSTEM_ERROR", message="timeout")`
- **Note**: If hitting this, the geometry likely has pathological complexity; log for investigation

### C-005: Validation Produces Non-Deterministic Result
- **Trigger**: Running validation twice on same MGG produces different results
- **Behavior**: This should be IMPOSSIBLE by design; if detected in testing, treat as a critical bug
- **Detection**: Reproducibility test in test suite (required acceptance test)

---

## Category D: Semantic Failures

### D-001: Classification Below Confidence Threshold
- **Trigger**: Best hypothesis confidence < 0.30 for a geometry node
- **Behavior**: `feature_class = "UNKNOWN_FEATURE"`, `confidence = max_hypothesis_confidence`, `review_status = "flagged"`
- **Do NOT**: Force-assign a feature class below threshold
- **Dataset impact**: Sample is valid as a data point; UNKNOWN_FEATURE is a valid label for benchmarking

### D-002: All Hypotheses Equally Uncertain
- **Trigger**: Top-2 hypotheses have confidence within 0.05 of each other
- **Behavior**: Store both hypotheses; set `ambiguous = true`; do not pick one
- **Provenance**: `inference_notes = "ambiguous: {class_a}={conf_a:.2f} vs {class_b}={conf_b:.2f}"`

### D-003: ML Model Not Available
- **Trigger**: `torch` not installed OR model checkpoint file not found
- **Behavior**: Log `"ML unavailable; using heuristics only"`; fall back to Level 4 heuristics
- **Do NOT**: Raise exception; do NOT block pipeline
- **Provenance**: `"ml_fallback": true` in pipeline provenance

### D-004: ML NaN Output
- **Trigger**: GNN produces NaN values in logits/probabilities
- **Behavior**: Discard ML prediction; use heuristic result; log error with node IDs
- **Note**: Likely caused by zero-norm feature vectors or disconnected graph components; investigate

### D-005: Ontology Term Not Found
- **Trigger**: Feature classification returns an ID not in loaded ontology
- **Behavior**: Replace with `"UNKNOWN_FEATURE"`; log `"ontology_miss: {feature_id}"`
- **Recovery**: Add term to ontology YAML; or fix classification bug

---

## Category E: Synthetic Generation Failures

### E-001: Feature Cannot Be Placed (Spacing Violation)
- **Trigger**: Feature sampler cannot find a valid position for a feature after 100 attempts
- **Behavior**: Skip this feature; reduce `n_features` for this sample by 1; log `"placement_failed: {feature_type}"`
- **Do NOT**: Force-place a feature that violates constraints
- **Impact**: Sample has fewer features than requested; still valid if passes validation

### E-002: Requested Panel Too Small for Feature Density
- **Trigger**: `panel_area < n_features × min_feature_footprint`
- **Behavior**: Reduce feature count to fit available area; log `"density_reduced: {original} → {actual}"`
- **Recovery**: Increase panel size range in config OR reduce feature density

### E-003: Violation Injection Cannot Find Target
- **Trigger**: `inject_violations()` cannot find a valid feature to violate (e.g., all features already too close to edge)
- **Behavior**: Skip that violation type; try next violation type; log `"violation_injection_skipped: {violation_type}"`
- **Impact**: Invalid sample may have fewer injected violations than requested; still valid as invalid sample

### E-004: DXF Write Failure
- **Trigger**: ezdxf cannot write DXF (disk full, permissions, etc.)
- **Behavior**: Raise `DXFWriteError`; do NOT write partial files; clean up temp files
- **Recovery**: Check disk space; check permissions

### E-005: Generated DXF Fails Own Validation
- **Trigger**: A synthetically generated "valid" panel fails Layer 1 or Layer 2 validation
- **Behavior**: CRITICAL — this should not happen by design. Log as a generation bug. Do NOT include in dataset. Increment `generation_errors` counter.
- **Recovery**: Investigate generation logic; likely a floating-point tolerance issue in placement

### E-006: Reproducibility Check Failure
- **Trigger**: Regenerating from same seed produces different DXF
- **Behavior**: CRITICAL — treat as a bug; do NOT release this dataset version
- **Recovery**: Check for non-seeded RNG calls; check for OS-dependent behavior in floating point

---

## Category F: System Failures

### F-001: Ontology YAML Malformed
- **Trigger**: `yaml.safe_load()` fails on ontology file
- **Behavior**: Raise `OntologyLoadError` at startup
- **Recovery**: Validate YAML syntax; this is a configuration error

### F-002: Ontology Version Mismatch
- **Trigger**: Stored sample has `ontology_version: "v0.2.0"` but loaded ontology is `v0.1.0`
- **Behavior**: Log warning; refuse to evaluate the sample
- **Recovery**: Use correct ontology version for the dataset version

### F-003: Rule Version Mismatch
- **Trigger**: Stored sample has `ruleset_version: "v0.2.0"` but loaded ruleset is `v0.1.0`
- **Behavior**: Log warning; refuse to validate the sample (result would be incomparable)
- **Recovery**: Use correct ruleset version

### F-004: Pydantic Validation Failure on Output
- **Trigger**: A module produces a Python object that fails Pydantic model validation
- **Behavior**: Raise the Pydantic `ValidationError` immediately; do NOT return invalid objects
- **Note**: This is a code bug, not a data issue. Fix the module.

---

## Category G: Schema Violations

### G-001: Missing Provenance on Feature Node
- **Trigger**: `FeatureNode.provenance is None`
- **Behavior**: Pydantic model validation rejects this; module must attach provenance before returning
- **Recovery**: This is a code bug; the module that created the node forgot to attach provenance

### G-002: Confidence Outside [0.0, 1.0]
- **Trigger**: Confidence value is negative or > 1.0
- **Behavior**: Pydantic validator clamps and logs warning
- **Note**: Softmax outputs are always in [0,1]; raw logits are not — ensure softmax is applied before storing confidence

### G-003: deterministic inference_method with confidence != 1.0
- **Trigger**: `inference_method="deterministic"` but `confidence=0.85`
- **Behavior**: Pydantic validator raises error
- **Rule**: Deterministic outputs are certain by definition. If it's not certain, it's not deterministic.

### G-004: Incomplete Sample (Missing Files)
- **Trigger**: Dataset sample directory missing one or more required files
- **Behavior**: `validate_sample_schema()` returns errors; sample excluded from benchmark splits
- **Recovery**: Regenerate the sample

---

## Failure Escalation Policy

Not all failures are equal. The following escalation rules apply:

| Failure Type | During Generation | During Inference | During Benchmarking |
|-------------|-------------------|-----------------|-------------------|
| A-001 to A-004 | Skip file, log, continue | Return error to caller | Fail loudly |
| B-001 to B-005 | Label as invalid, continue | Flag in output | Include as negative examples |
| C-001 | Log, continue other rules | Report SYSTEM_ERROR in result | Report as benchmark error |
| C-002, C-003 | STOP — fatal config error | STOP | STOP |
| D-001, D-002 | Label UNKNOWN, continue | Flag for review | Include as ambiguous class |
| D-003 | Log, use heuristics | Log, use heuristics | Acceptable |
| E-005, E-006 | STOP — generation bug | N/A | N/A |
| F-001 to F-004 | STOP — config/code bug | STOP | STOP |

---

## Surfacing Failures to Users

All public-facing functions return structured results, not bare exceptions:

```python
class PipelineResult(BaseModel):
    success: bool
    errors: list[PipelineError]       # hard failures that stopped processing
    warnings: list[PipelineWarning]   # soft issues that were handled
    result: AnalysisResult | None     # None if success=False
    
class PipelineError(BaseModel):
    error_code: str       # e.g., "DXF_CORRUPT"
    category: str         # "A" through "G"
    message: str
    affected_file: str | None
    affected_node_id: str | None
    recoverable: bool
    
class PipelineWarning(BaseModel):
    warning_code: str     # e.g., "no_cuttable_entities"
    message: str
    affected_entity_id: str | None
```

---

## Failure Handling Anti-Patterns (Forbidden)

```python
# FORBIDDEN — Silent exception swallowing
try:
    result = classify_feature(node)
except Exception:
    pass  # NEVER DO THIS

# FORBIDDEN — Bare exception catch without logging
try:
    result = run_rule(mgg)
except Exception as e:
    return None  # NEVER DO THIS

# FORBIDDEN — Fabricating values to hide failure
def compute_area(polygon):
    try:
        return shapely_area(polygon)
    except:
        return 1.0  # NEVER MAKE UP VALUES

# FORBIDDEN — Confidence 1.0 on non-deterministic output
SemanticAnnotation(confidence=1.0, inference_method="heuristic")  # INVALID

# FORBIDDEN — Proceeding with incomplete provenance
node = FeatureNode(feature_class="SHELF_PIN_HOLE", provenance=None)  # PYDANTIC REJECTS
```
