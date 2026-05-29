# Deterministic Validation Specification

Version: v0.1.0  

See also: [[Rule Engine and Standards]], [[Manufacturing Geometry Graph (MGG) Specification]], [[Provenence and Uncertainty]]

---

## Purpose

The validation engine provides deterministic, rule-based manufacturability checking. It is the authoritative layer for manufacturing feasibility — its results cannot be overridden by ML or semantic layers.

**Fundamental principle**: A part that fails Layer 1 or Layer 2 validation is not manufacturable, regardless of what the semantic layer infers.

---

## Scope Disclaimer (Read First)

**OMIM v0.1 validation is a geometric manufacturability approximation.** It is NOT production manufacturability authority.

Real manufacturability also depends on:
- **Fixturing**: Is the part held rigidly enough for the operation?
- **Tool deflection**: Will the tool flex under cutting forces?
- **Machine rigidity**: Does the machine have sufficient stiffness for this operation?
- **Material behavior**: Chipload, tearout, moisture content, density variation
- **Operation ordering**: Which features must be machined before which?
- **Feeds and speeds**: Is the programmed feed rate within machine capability?
- **Coolant/chip evacuation**: Can chips clear the pocket?

**OMIM validates none of these.** It validates geometry against programmed rules. The correct framing in any demo or paper:

> "OMIM provides geometric manufacturability approximation for panel CNC workflows, checking programmed rules derived from industry standards and shop practices. It is not a simulation-based or physics-based manufacturability analysis."

A panel that passes OMIM validation may still fail to machine correctly in a specific shop with specific tooling. A panel that fails OMIM validation should be treated as a strong warning, not a certainty of failure.

---

## Validation Architecture

```
ManufacturingGeometryGraph
         │
         ▼
┌─────────────────────────────────┐
│    Layer 1: Geometric Validity  │  ← Deterministic, always run first
│    (geometry self-consistency)  │
└──────────────┬──────────────────┘
               │ passes geometry checks
               ▼
┌─────────────────────────────────┐
│  Layer 2: Manufacturing Rules   │  ← Deterministic, rule-based
│  (manufacturability feasibility)│
└──────────────┬──────────────────┘
               │ results fed to
               ▼
┌─────────────────────────────────┐
│  Layer 3: Semantic Plausibility │  ← Probabilistic, advisory only
│  (in Semantic Layer, not here)  │
└─────────────────────────────────┘
               │
               ▼
         ValidationReport
```

**Layer 3** is NOT part of the validation engine. It lives in the Semantic Layer and is clearly labeled as probabilistic.

---

## Layer 1: Geometric Validity

These rules check that the geometry is self-consistent and topologically valid. They have nothing to do with manufacturing — they ensure the geometry itself makes sense.

### Layer 1 Rules

#### GEO-001: Contour Closure
```yaml
rule_id: GEO-001
version: "v0.1.0"
name: contour_closure
description: "All contours intended for cutting must be closed (no open endpoints)"
severity: ERROR
tolerance_mm: 0.01  # endpoints within this distance are considered coincident
algorithm: "Check all polylines: first point distance to last point <= tolerance"
applies_to: ["LWPOLYLINE", "POLYLINE"]
exception: "Open polylines on non-cutting layers (annotation, engrave) are allowed"
source: "Fundamental CNC requirement: open contours cannot be routed"
```

#### GEO-002: No Self-Intersection
```yaml
rule_id: GEO-002
version: "v0.1.0"
name: no_self_intersection
description: "Closed contours must not self-intersect"
severity: ERROR
algorithm: "Shapely: not polygon.is_valid or polygon.is_simple"
applies_to: ["closed_contours"]
source: "Shapely geometry validity; OGC Simple Feature Access specification"
```

#### GEO-003: Positive Area
```yaml
rule_id: GEO-003
version: "v0.1.0"
name: positive_area
description: "All closed contours must have positive non-zero area"
severity: ERROR
minimum_area_mm2: 0.01
applies_to: ["closed_contours"]
source: "Degenerate geometry check; Shapely area property"
```

#### GEO-004: Valid Circle Geometry
```yaml
rule_id: GEO-004
version: "v0.1.0"
name: valid_circle
description: "All circles must have positive radius"
severity: ERROR
applies_to: ["CIRCLE"]
```

#### GEO-005: Contour Orientation
```yaml
rule_id: GEO-005
version: "v0.1.0"
name: contour_orientation
description: "Outer profile contours should be counter-clockwise (CCW); internal contours clockwise (CW)"
severity: WARNING
algorithm: "Shapely: Polygon.exterior.is_ccw for outer; check interior rings"
note: "Some CAD software exports reversed orientation; normalize during parsing"
source: "CNC convention for climb vs. conventional milling direction"
```

#### GEO-006: No Duplicate Geometry
```yaml
rule_id: GEO-006
version: "v0.1.0"
name: no_duplicate_entities
description: "No two identical geometry entities at the same position"
severity: WARNING
algorithm: "Compare geometry hashes (centroid + area + perimeter)"
tolerance: 0.01  # mm
source: "Duplicate geometry causes double-cutting problems on CNC"
```

#### GEO-007: Geometry Within Panel Bounds
```yaml
rule_id: GEO-007
version: "v0.1.0"
name: geometry_within_panel_bounds
description: "All features must lie within or on the panel boundary"
severity: ERROR
algorithm: "Shapely: panel_polygon.contains(feature_geometry) or touches"
applies_to: ["all geometry within a panel context"]
source: "Physical requirement: can't machine outside the stock material"
```

---

## Layer 2: Manufacturing Feasibility Rules

These rules check whether the geometry is actually manufacturable given real-world tooling and process constraints.

### Layer 2 Rules

#### MFG-001: Minimum Edge Clearance
```yaml
rule_id: MFG-001
version: "v0.1.0"
name: minimum_edge_clearance
description: "Drill holes and features must be at minimum distance from panel edge to prevent tearout"
severity: ERROR
threshold_mm: 8.0  # conservative; can be reduced for specific materials
algorithm: |
  For each feature centroid:
    min_distance_to_panel_edge = min(distances to all panel boundary segments)
    if min_distance_to_panel_edge < threshold_mm: FAIL
  For holes: measure from circle center, not adjusted for radius
source: "Common panel CNC practice; ISO 2768 general tolerances; shop experience"
note: "8mm conservative; MDF can sometimes go to 6mm. Rule is adjustable via config."
adjustable: true
```

#### MFG-002: Minimum Drill Spacing
```yaml
rule_id: MFG-002
version: "v0.1.0"
name: minimum_drill_spacing
description: "Adjacent drill holes must have minimum material remaining between them to prevent panel failure"
severity: ERROR
formula: "center_distance >= (r1 + r2) + min_wall_mm"
min_wall_mm: 3.0  # minimum material between holes for MDF/particleboard
algorithm: |
  For each pair of circles:
    edge_to_edge_distance = center_distance - r1 - r2
    if edge_to_edge_distance < min_wall_mm: FAIL
source: "Structural integrity requirement; material strength considerations for MDF/particleboard"
note: "3mm is conservative for MDF; softwoods may need more. Wood composites are weakest at these locations."
```

#### MFG-003: Tool Radius Feasibility
```yaml
rule_id: MFG-003
version: "v0.1.0"
name: tool_radius_corner_feasibility
description: "Internal pocket corners must have radius >= minimum tool radius (can't cut sharper corners than the tool)"
severity: ERROR
default_min_tool_radius_mm: 3.0  # assumes 6mm diameter router bit minimum
algorithm: |
  For each pocket contour:
    find all concave (internal) corners
    measure actual corner radius
    if corner_radius < min_tool_radius_mm: FAIL
source: "Fundamental CNC routing constraint; tool geometry; CAM toolpath planning"
reference: "Machinery's Handbook, 30th ed., §CNC Milling Fundamentals"
```

#### MFG-004: Minimum Pocket Width
```yaml
rule_id: MFG-004
version: "v0.1.0"
name: minimum_pocket_width
description: "Pocket width must be at least 1.2x tool diameter to allow routing passes"
severity: ERROR
formula: "pocket_min_width >= tool_diameter * 1.2"
default_tool_diameter_mm: 6.0
algorithm: |
  For each pocket:
    min_width = minimum distance between parallel walls of pocket bounding box
    if min_width < tool_diameter * 1.2: FAIL
source: "CNC routing practice; insufficient clearance causes tool binding"
```

#### MFG-005: Shelf Pin 32mm System Compliance
```yaml
rule_id: MFG-005
version: "v0.1.0"
name: shelf_pin_32mm_system
description: "Shelf pin holes should follow 32mm modular grid spacing"
severity: WARNING  # advisory only; non-standard spacing is allowed but unusual
expected_spacing_mm: 32.0
tolerance_mm: 0.5
algorithm: |
  If detected SHELF_PIN_HOLE group:
    check spacing between consecutive holes in same column
    if |spacing - 32.0| > tolerance: WARNING
source: "European 32mm furniture system (Rasterbohrsystem); Hettich, Blum, Grass hardware systems"
reference: "Hettich catalog section §shelf pin systems"
```

#### MFG-006: Maximum Drill Depth vs Panel Thickness
```yaml
rule_id: MFG-006
version: "v0.1.0"
name: max_blind_drill_depth
description: "Blind hole depth must not exceed 75% of panel thickness (structural integrity)"
severity: ERROR
max_depth_ratio: 0.75
algorithm: |
  For blind holes with explicit depth:
    if depth > panel_thickness * max_depth_ratio: FAIL
note: "Without explicit depth metadata in DXF, this rule cannot be evaluated deterministically."
source: "Structural integrity; woodworking joinery practice"
```

#### MFG-007: Hinge Cup Edge Distance
```yaml
rule_id: MFG-007
version: "v0.1.0"
name: hinge_cup_edge_distance
description: "Hinge cup holes (35mm) must be at correct distance from panel edge (typically 22.5mm center)"
severity: WARNING
expected_edge_distance_mm: 22.5  # standard Blum mounting spec
tolerance_mm: 1.0
applies_to: "HINGE_CUP_HOLE features only"
source: "Blum CLIP top hinge installation instructions; standard Eurohinges specification"
reference: "https://www.blum.com/file-service/files/downloads/pdf/IFP_CLIP_top_BLUMOTION_en.pdf"
```

#### MFG-008: No Feature on Sheet Edge
```yaml
rule_id: MFG-008
version: "v0.1.0"
name: no_feature_on_sheet_edge
description: "Features must not be positioned exactly on the panel outer boundary (machining ambiguity)"
severity: ERROR
tolerance_mm: 0.1
algorithm: |
  Feature centroid must NOT lie on panel boundary polygon
  (within tolerance_mm of boundary)
source: "CNC machining practice; ambiguous cut direction at exact boundary"
```

#### MFG-009: Minimum Panel Area
```yaml
rule_id: MFG-009
version: "v0.1.0"
name: minimum_panel_area
description: "Panel must have minimum area to be structurally meaningful"
severity: WARNING
minimum_area_mm2: 10000  # 100mm × 100mm minimum
source: "Practical minimum for furniture panel; smaller pieces are typically scraps"
```

#### MFG-010: Feature Density Check
```yaml
rule_id: MFG-010
version: "v0.1.0"
name: feature_density
description: "Panel must not be so densely drilled that structural integrity is compromised"
severity: WARNING
max_hole_coverage_ratio: 0.30  # max 30% of panel area as holes
algorithm: |
  total_hole_area = sum of all circle areas
  coverage_ratio = total_hole_area / panel_area
  if coverage_ratio > max_hole_coverage_ratio: WARNING
source: "Structural integrity rule of thumb for MDF panels"
note: "Heuristic; formal structural analysis is out of scope"
```

---

## Validation Report Structure

```python
class ValidationReport(BaseModel):
    report_id: str
    graph_id: str
    timestamp: str                  # ISO 8601
    
    # Layer results
    layer1_passed: bool
    layer2_passed: bool
    layer1_results: list[RuleResult]
    layer2_results: list[RuleResult]
    
    # Summary
    overall_valid: bool             # True iff ALL ERROR rules pass
    has_warnings: bool
    severity_summary: dict          # {"ERROR": 2, "WARNING": 1, "INFO": 0}
    
    # Affected nodes
    failed_node_ids: list[str]      # geometry node IDs that caused failures
    
    # Provenance
    ruleset_version: str
    provenance: ProvenanceRecord
    
    # Timing
    validation_time_ms: float

class RuleResult(BaseModel):
    rule_id: str
    rule_version: str
    rule_name: str
    passed: bool
    severity: str                   # "ERROR" | "WARNING" | "INFO" | "SYSTEM_ERROR"
    message: str                    # Human-readable explanation
    affected_node_ids: list[str]    # Which nodes triggered this result
    evidence: dict                  # Measured values (e.g., {"measured_mm": 5.2, "threshold_mm": 8.0})
    execution_time_ms: float
```

---

## Rule Engine

Rules are loaded from YAML and executed against the MGG.

```python
# omim/validation/rule_engine.py

class RuleEngine:
    def __init__(self, rules_dir: str):
        self.rules = self._load_rules(rules_dir)
    
    def execute_layer1(self, mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
        """Run geometric validity rules."""
    
    def execute_layer2(self, mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
        """Run manufacturing feasibility rules."""
    
    def execute_single_rule(self, rule_id: str, mgg: ManufacturingGeometryGraph) -> RuleResult:
        """Execute a single rule by ID."""
    
    def get_applicable_rules(self, feature_class: str) -> list[Rule]:
        """Get rules applicable to a specific feature type."""
```

---

## Determinism Guarantee

The validation engine is deterministically tested:

```python
def test_validation_determinism(mgg, ruleset_version):
    """Same input must always produce same output."""
    result1 = validate_mgg(mgg, ruleset_version)
    result2 = validate_mgg(mgg, ruleset_version)
    assert result1.json() == result2.json()
```

Randomness sources to eliminate:
- Dictionary iteration order → always sort rule IDs before execution
- Float arithmetic → use tolerances, not exact equality
- File timestamps → exclude from determinism check (use content hashes)

---

## Validation Use in Dataset Generation

When generating synthetic datasets, the validation engine serves dual purposes:

1. **Quality gate**: Valid samples must pass all ERROR rules
2. **Label generator**: Invalid samples have known violations (injected, then verified by validation engine)

This means the validation engine is **both** a quality control mechanism and a ground truth label source. This dual use is intentional and the provenance system tracks which role it played.
