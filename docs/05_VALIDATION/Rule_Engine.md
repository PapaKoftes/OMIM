# Rule Engine

Version: v0.1.0  
Section: 05_VALIDATION  

See also: [[05_VALIDATION/Geometric_Validation]], [[05_VALIDATION/Manufacturability_Validation]], [[03_INTERFACES/Validation_Interface]]

---

## Purpose

The Rule Engine loads validation rules from YAML, executes them against the MGG in a deterministic order, and returns structured `RuleResult` objects. It is the sole execution context for all validation rules.

---

## Rule Loading

Rules are stored at `data/rules/` and loaded at engine startup:

```
data/rules/
├── layer1_geometric.yaml          # GEO-001 to GEO-008
├── layer2_manufacturability.yaml  # MFG-001 to MFG-012
├── default_constraints.yaml       # constraint default values
├── rules_changelog.md             # change history
└── deprecated/                    # retired rules (kept for provenance)
```

```python
class RuleEngine:
    def __init__(self, rules_dir: str = "data/rules/"):
        self.layer1_rules = self._load_rules(Path(rules_dir) / "layer1_geometric.yaml")
        self.layer2_rules = self._load_rules(Path(rules_dir) / "layer2_manufacturability.yaml")
        self.constraints = self._load_constraints(Path(rules_dir) / "default_constraints.yaml")
    
    def _load_rules(self, path: Path) -> list[Rule]:
        """Load and validate rules from YAML. Raises RuleLoadError if file missing or malformed."""
        if not path.exists():
            raise RuleLoadError(f"Rules file not found: {path}")
        data = yaml.safe_load(path.read_text())
        rules = [Rule(**r) for r in data["rules"]]
        self._validate_rule_ids(rules)
        return sorted(rules, key=lambda r: r.rule_id)  # deterministic execution order
```

---

## Rule YAML Schema

Full schema for each rule entry in YAML. All fields shown:

```yaml
rules:
  - rule_id: "MFG-001"                # Required. Unique. Format: "GEO-NNN" or "MFG-NNN"
    version: "v0.1.0"                  # Required. SemVer.
    name: "minimum_edge_clearance"     # Required. snake_case identifier.
    category: "manufacturability"      # "geometric" | "manufacturability"
    layer: 2                           # 1 | 2
    rule_type: "shop_convention"       # See Rule Type Classification
    severity: "ERROR"                  # "ERROR" | "WARNING" | "INFO"
    applies_to: ["CIRCLE", "pocket_features"]
    parameters:
      threshold_mm: 8.0
    description: "Holes must maintain minimum distance from panel edge to prevent tearout."
    
    # Domain applicability (required for shop_convention, material_heuristic, machine_heuristic)
    domain_applicability:
      material: [MDF, particleboard, melamine_particleboard]
      machine_type: [3_axis_cnc_router]
      NOT_applicable_to: [solid_wood, plywood_grain_sensitive, high_speed_milling]
    
    # Sources (at least one required)
    source: "Common CNC panel manufacturing practice"
    standards_refs:
      - standard: "DIN 68861-1"
        clause: ""
        description: "Panel furniture surfaces; structural requirements indirectly imply edge distance"
    
    # Configuration
    confidence_ceiling: 0.75
    adjustable: true    # parameter can be overridden in shop-specific config
    expert_reviewed: false
    
    # Governance
    status: "active"   # "active" | "draft" | "deprecated"
    added_in_version: "v0.1.0"
    enabled: true
```

---

## Rule Pydantic Model

```python
class Rule(BaseModel):
    rule_id: str
    version: str
    name: str
    category: str
    layer: Literal[1, 2]
    rule_type: Literal[
        "geometric",
        "standards_derived",
        "hardware_spec",
        "shop_convention",
        "material_heuristic",
        "machine_heuristic"
    ]
    severity: Literal["ERROR", "WARNING", "INFO"]
    applies_to: list[str]
    parameters: dict
    description: str
    source: str
    confidence_ceiling: float
    domain_applicability: dict | None = None   # material/machine constraints
    standards_refs: list[dict] | None = None   # formal standard citations
    adjustable: bool = False                   # parameter overridable in config
    expert_reviewed: bool = False
    status: Literal["active", "draft", "deprecated"] = "active"
    added_in_version: str = "v0.1.0"
    enabled: bool = True
```

---

## RuleResult

```python
class RuleResult(BaseModel):
    rule_id: str
    rule_name: str
    passed: bool
    severity: Literal["ERROR", "WARNING", "PASS", "SYSTEM_ERROR"]
    message: str
    affected_node_ids: list[str]
    measured_value: float | None    # e.g., actual distance measured
    threshold_value: float | None   # e.g., minimum required distance
    confidence: float
    provenance: ProvenanceRecord
```

---

## Execution Protocol

```python
def execute_layer1(self, mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
    results = []
    for rule in self.layer1_rules:  # already sorted by rule_id
        if not rule.enabled:
            continue
        try:
            result = self._execute_rule(rule, mgg)
            results.append(result)
        except Exception as e:
            results.append(RuleResult(
                rule_id=rule.rule_id,
                severity="SYSTEM_ERROR",
                message=str(e),
                passed=False,
                affected_node_ids=[]
            ))
    return results

def _execute_rule(self, rule: Rule, mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
    """Dispatch to rule-specific implementation."""
    handler = self._rule_handlers[rule.rule_id]
    return handler(rule, mgg, self.constraints)

def execute_single_rule(self, rule_id: str, mgg: ManufacturingGeometryGraph) -> RuleResult:
    """Execute a single rule by ID. Used for targeted re-validation and testing."""
    if rule_id not in self._rule_handlers:
        raise UnknownRuleError(f"No handler registered for rule_id: {rule_id}")
    rule = next((r for r in self.layer1_rules + self.layer2_rules if r.rule_id == rule_id), None)
    if rule is None:
        raise UnknownRuleError(f"Rule {rule_id} not found in loaded rules")
    return self._execute_rule(rule, mgg)

def get_applicable_rules(self, feature_class: str) -> list[Rule]:
    """Get rules applicable to a specific feature type or entity class."""
    return [r for r in self.layer1_rules + self.layer2_rules
            if feature_class in r.applies_to or "all" in r.applies_to]
```

---

## Determinism Enforcement

```python
# Rule execution order: alphabetical by rule_id (GEO-001 before GEO-002, etc.)
rules = sorted(rules, key=lambda r: r.rule_id)

# Tolerance-based comparison (never exact float equality)
def check_distance(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) <= tolerance

# No random state — no uuid4() calls, no datetime.now() in rule evaluation
# Rule IDs in results are deterministic strings from YAML, not generated
```

---

## Failure Codes

| Code | Condition | Fatal? |
|------|-----------|--------|
| `RuleLoadError` | YAML file missing or malformed | Yes — engine cannot start |
| `UnknownRuleError` | Rule ID not in handler registry | Yes — at load time |
| `SYSTEM_ERROR` result | Exception during rule execution | No — recorded in results |
| Timeout (>10s per rule) | Rule exceeds wall-clock budget | No — recorded as SYSTEM_ERROR |

---

## Handler Registration

Each rule ID maps to a Python function:

```python
self._rule_handlers = {
    # Layer 1: Geometric Validity
    "GEO-001": check_open_contour,
    "GEO-002": check_self_intersection,
    "GEO-003": check_degenerate_geometry,
    "GEO-004": check_coordinate_range,
    "GEO-005": check_contour_orientation,
    "GEO-006": check_duplicate_geometry,
    "GEO-007": check_geometry_within_bounds,
    "GEO-008": check_zero_area,
    # Layer 2: Manufacturing Feasibility
    "MFG-001": check_edge_clearance,
    "MFG-002": check_feature_spacing,
    "MFG-003": check_tool_radius_feasibility,
    "MFG-004": check_pocket_width,
    "MFG-005": check_shelf_pin_grid,
    "MFG-006": check_hinge_cup_distance,
    "MFG-007": check_blind_depth,
    "MFG-008": check_feature_density,
    "MFG-009": check_panel_dimensions,
    "MFG-010": check_confirmat_pair_positioning,
    "MFG-011": check_drill_diameter_range,
    "MFG-012": check_no_feature_on_edge,
}
```

Any `rule_id` not in `_rule_handlers` raises `UnknownRuleError` at load time.

---

## Rule Governance

### Adding a New Rule
1. Assign next sequential rule_id in appropriate series (GEO-NNN or MFG-NNN)
2. Write YAML definition with all required fields
3. Add at least one `source` citation; add `standards_refs` if a formal standard applies
4. Mark `expert_reviewed: false` until reviewed by a domain expert
5. Write a unit test for the rule
6. Register handler in `_rule_handlers`
7. Bump ruleset minor version

### Modifying an Existing Rule
1. NEVER modify `rule_id` — this would break provenance references
2. Bump `version` field
3. Document change in `rules_changelog.md`
4. Re-run all validation tests after modification
5. Reset `expert_reviewed: false` if logic changed

### Rule Versioning
Ruleset version is independent of OMIM version. Format: `v{major}.{minor}.{patch}`
- Major: breaking change to rule semantics or IDs
- Minor: new rules added
- Patch: parameter adjustments, description clarifications

### Rule Type Classification

| Rule Type | Confidence | Example |
|-----------|-----------|---------|
| `geometric` | 1.0 | Open contour, self-intersection |
| `standards_derived` | 0.95 | ISO 286 hole tolerance grades |
| `hardware_spec` | 0.90 | Blum hinge cup: 22.5mm from edge |
| `shop_convention` | 0.75 | 8mm edge clearance default |
| `material_heuristic` | 0.70 | 3mm wall between MDF holes |
| `machine_heuristic` | 0.65 | Pocket width = 1.2 × tool diameter |
