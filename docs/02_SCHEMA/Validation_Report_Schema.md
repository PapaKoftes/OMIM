# Validation Report Schema

**Schema Version: v0.1.0**

Version: v0.1.0  
Section: 02_SCHEMA  

See also: [[05_VALIDATION/Rule_Engine]], [[05_VALIDATION/Geometric_Validation]], [[05_VALIDATION/Manufacturability_Validation]]

---

## Purpose

Defines the exact JSON schema for `validation.json` — the output of OMIM's deterministic validation engine for a single panel.

---

## Schema

```json
{
  "$schema": "omim-validation-v0.1.0",
  "report_id": "val_9f2a3...",
  "graph_id": "3f9a1b2c-...",
  "schema_version": "v0.1.0",
  "timestamp": "2026-05-30T14:23:06Z",
  "ruleset_version": "v0.1.0",
  
  "layer1_passed": true,
  "layer2_passed": true,
  "overall_valid": true,
  "has_warnings": false,
  
  "severity_summary": {
    "ERROR": 0,
    "WARNING": 0,
    "INFO": 0,
    "SYSTEM_ERROR": 0
  },
  
  "layer1_results": [
    {
      "rule_id": "GEO-001",
      "rule_version": "v0.1.0",
      "rule_name": "contour_closure",
      "passed": true,
      "severity": "ERROR",
      "message": "All contours are closed",
      "affected_node_ids": [],
      "evidence": {},
      "execution_time_ms": 0.8
    }
  ],
  
  "layer2_results": [
    {
      "rule_id": "MFG-001",
      "rule_version": "v0.1.0",
      "rule_name": "minimum_edge_clearance",
      "passed": false,
      "severity": "ERROR",
      "message": "Circle at (4.0, 50.0) is 4.0mm from panel edge (threshold: 8.0mm)",
      "affected_node_ids": ["circle_b7f1"],
      "evidence": {
        "measured_mm": 4.0,
        "threshold_mm": 8.0,
        "feature_centroid": [4.0, 50.0],
        "nearest_edge": "left"
      },
      "execution_time_ms": 2.1
    }
  ],
  
  "failed_node_ids": ["circle_b7f1"],
  "validation_time_ms": 15.3,
  
  "provenance": {
    "record_id": "...",
    "generator": "omim",
    "generator_version": "v0.1.0",
    "pipeline_stage": "validation",
    "inference_method": "deterministic",
    "confidence": 1.0,
    "ruleset_version": "v0.1.0",
    "timestamp": "2026-05-30T14:23:06Z"
  }
}
```

---

## Pydantic Models

```python
class ValidationReport(BaseModel):
    report_id: str
    graph_id: str
    timestamp: str              # ISO 8601
    ruleset_version: str
    
    layer1_passed: bool
    layer2_passed: bool
    overall_valid: bool         # True iff ALL ERROR rules pass
    has_warnings: bool
    severity_summary: dict      # {"ERROR": N, "WARNING": N, "INFO": N, "SYSTEM_ERROR": N}
    
    layer1_results: list[RuleResult]
    layer2_results: list[RuleResult]
    failed_node_ids: list[str]
    
    provenance: ProvenanceRecord  # inference_method MUST be "deterministic"
    validation_time_ms: float


class RuleResult(BaseModel):
    rule_id: str
    rule_version: str
    rule_name: str
    passed: bool
    severity: str               # "ERROR" | "WARNING" | "INFO" | "SYSTEM_ERROR"
    message: str
    affected_node_ids: list[str]
    evidence: dict              # rule-specific measurements
    execution_time_ms: float
```

---

## Required Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `$schema` | string | yes | Must be `"omim-validation-v0.1.0"` |
| `overall_valid` | boolean | yes | True iff zero ERROR results |
| `ruleset_version` | string | yes | Must match active ruleset |
| `layer1_results` | list | yes | One entry per Layer 1 rule evaluated |
| `layer2_results` | list | yes | One entry per Layer 2 rule evaluated |
| `provenance` | object | yes | `inference_method = "deterministic"`, `confidence = 1.0` |

---

## Invariants

1. `overall_valid = True` iff `severity_summary["ERROR"] == 0`
2. `layer1_passed = True` iff no Layer 1 rules have `passed=False` and `severity="ERROR"`
3. `layer2_passed = True` iff no Layer 2 rules have `passed=False` and `severity="ERROR"`
4. `provenance.confidence` MUST be 1.0 (validation is deterministic)
5. `failed_node_ids` = union of all `affected_node_ids` where `passed=False` and `severity="ERROR"`

---

## Determinism Guarantee

```python
def test_validation_determinism(mgg, ruleset_version):
    """Same input must always produce same output."""
    result1 = validate_mgg(mgg, ruleset_version)
    result2 = validate_mgg(mgg, ruleset_version)
    assert result1.model_dump_json() == result2.model_dump_json()
```

Randomness sources eliminated:
- Dictionary iteration order → always sort rule IDs before execution
- Float arithmetic → use tolerances, not exact equality
- File timestamps → excluded from determinism check
