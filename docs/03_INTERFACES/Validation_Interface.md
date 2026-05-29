# Validation Interface Contract

Version: v0.1.0  
Section: 03_INTERFACES  

See also: [[02_SCHEMA/Validation_Report_Schema]], [[05_VALIDATION/Rule_Engine]]

---

## Contract

```
Input:  ManufacturingGeometryGraph (read-only)
Output: ValidationReport
```

**Critical**: The validation engine CANNOT query the semantic layer. It receives only the MGG. This is structural enforcement of the Trust Hierarchy (Level 3 > Level 5).

---

## Input

```python
# ManufacturingGeometryGraph (from MGG Builder)
# read-only access — validation never modifies the graph
```

---

## Output: `ValidationReport`

See [[02_SCHEMA/Validation_Report_Schema]] for the complete schema.

```python
class ValidationReport(BaseModel):
    report_id: str
    graph_id: str
    timestamp: str
    ruleset_version: str
    
    layer1_passed: bool
    layer2_passed: bool
    overall_valid: bool
    has_warnings: bool
    severity_summary: dict
    
    layer1_results: list[RuleResult]
    layer2_results: list[RuleResult]
    failed_node_ids: list[str]
    
    provenance: ProvenanceRecord  # inference_method MUST be "deterministic"
    validation_time_ms: float
```

---

## Rule Engine Interface

```python
class RuleEngine:
    def __init__(self, rules_dir: str):
        self.rules = self._load_rules(rules_dir)  # Raises RuleLoadError if rules missing
    
    def execute_layer1(self, mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
        """Run geometric validity rules (GEO-001 through GEO-006)."""
    
    def execute_layer2(self, mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
        """Run manufacturing feasibility rules (MFG-001 through MFG-010).
        
        Note: No semantic_annotations parameter.
        Validation CANNOT see feature classifications.
        """
    
    def build_report(self, mgg, layer1_results, layer2_results) -> ValidationReport:
        """Combine results into final ValidationReport."""
    
    def get_applicable_rules(self, feature_class: str) -> list[Rule]:
        """Get rules applicable to a specific feature type."""
```

---

## Determinism Guarantee

```python
def validate_mgg(mgg: ManufacturingGeometryGraph, ruleset_version: str) -> ValidationReport:
    """
    DETERMINISM INVARIANT: Same input → same output, always.
    
    Enforced by:
    - Sorting rule IDs before execution
    - Using tolerances, not exact equality
    - No random state in any rule evaluation
    """
```

---

## Failure Handling

| Failure | Behavior |
|---------|---------|
| Rules file missing at startup | Raise `RuleLoadError` — fatal |
| Unknown rule ID | Raise `UnknownRuleError` at load time — fatal |
| Rule evaluation exception | `RuleResult(severity="SYSTEM_ERROR", message=str(e))` — non-fatal |
| Rule timeout (>10s) | `RuleResult(severity="SYSTEM_ERROR", message="timeout")` — non-fatal |

No validation failure is silent. Every failed rule produces a structured `RuleResult`.

---

## Module Isolation (Enforced)

```python
# CORRECT: Layer 2 runs without semantic annotations
def execute_layer2(self, mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
    # No import of omim.semantic anywhere in this file
    # No access to feature_class on geometry nodes
    pass

# FORBIDDEN: This import would break the isolation invariant
# from omim.semantic.inference_engine import InferenceEngine  # NEVER
```

---

## Acceptance Tests

```python
def test_edge_clearance_violation_detected():
    """MFG-001: Circle at (3, 50) on 400×400 panel flagged as ERROR."""

def test_valid_panel_passes_all_rules():
    """Well-formed panel with correct spacing produces zero ERRORs."""

def test_validation_determinism():
    """Same MGG always produces identical ValidationReport."""

def test_open_contour_detected():
    """GEO-001: LWPOLYLINE with gap > 0.01mm at endpoints flagged as ERROR."""

def test_overlapping_holes_detected():
    """MFG-002: Two 10mm circles with centers 8mm apart → wall = 8-5-5 = -2mm → ERROR."""

def test_validation_report_serializes():
    """ValidationReport.model_dump_json() produces valid JSON."""
```
