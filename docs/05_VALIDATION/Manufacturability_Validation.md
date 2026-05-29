# Manufacturability Validation (Layer 2)

Version: v0.1.0  
Section: 05_VALIDATION  

See also: [[05_VALIDATION/Rule_Engine]], [[04_ONTOLOGY/Constraint_Taxonomy]], [[06_REAL_WORLD_GROUNDING/Cabinet_Standards]]

---

## Scope Disclaimer

**OMIM v0.1 validation is a geometric manufacturability approximation.** A panel that passes these rules may still fail to machine correctly in a specific shop with specific tooling. A panel that fails should be treated as a strong warning, not a certainty of failure.

---

## Rule Non-Universality

**Critical**: Many manufacturability rules are NOT universal. A rule that holds for MDF on a 3-axis router does NOT necessarily hold for plywood on a high-speed machining center.

Every rule declares its `rule_type` and `confidence_ceiling`. Rules of type `shop_convention`, `material_heuristic`, or `machine_heuristic` include explicit `domain_applicability` limiting where they apply:

```yaml
# Example
domain_applicability:
  material: [MDF, particleboard, melamine_particleboard]
  machine_type: [3_axis_cnc_router]
  NOT_applicable_to: [solid_wood, plywood_grain_sensitive, high_speed_milling]
```

---

## Purpose

Layer 2 validates manufacturing feasibility constraints against the MGG. Rules are `shop_convention`, `material_heuristic`, or `hardware_spec` type with confidence ceilings below 1.0. Layer 2 runs only after Layer 1 passes.

**Critical**: Layer 2 has NO access to semantic annotations. Rules operate on raw geometry (diameter, distance, position) only.

---

## MFG-001: Edge Clearance

```yaml
rule_id: "MFG-001"
name: "Minimum Edge Clearance"
layer: 2
rule_type: "shop_convention"
severity: "ERROR"
applies_to: ["CIRCLE", "LWPOLYLINE"]
parameters:
  min_edge_clearance_mm: 8.0
source: "Shop convention; MDF tear-out prevention"
confidence_ceiling: 0.75
```

**Logic**: The centroid of each non-boundary geometry node must be at least 8mm from the panel boundary edge. Measured as shortest distance from centroid to the nearest boundary edge.

```python
def check_edge_clearance(rule, mgg, constraints):
    panel_boundary = mgg.query().get_panel_boundary()
    min_clearance = rule.parameters["min_edge_clearance_mm"]
    
    for node in mgg.query().get_interior_nodes():
        dist = panel_boundary.exterior.distance(Point(node.centroid))
        if dist < min_clearance:
            # flag as ERROR with measured_value=dist, threshold=min_clearance
```

**Source rationale**: 8mm is standard for 18mm MDF particleboard. Too close to edge → fibre tear-out during routing, panel splitting at drill site.

---

## MFG-002: Feature Spacing (Wall Thickness)

```yaml
rule_id: "MFG-002"
name: "Minimum Feature Spacing"
layer: 2
rule_type: "material_heuristic"
severity: "ERROR"
applies_to: ["CIRCLE"]
parameters:
  min_drill_wall_mm: 3.0
source: "Material heuristic; MDF/particleboard fibre integrity"
confidence_ceiling: 0.70
```

**Logic**: For each pair of CIRCLE entities, the minimum wall thickness between them = center_distance - radius_A - radius_B. If this is < 3mm, the wall between holes is too thin to prevent splitting.

```python
def check_feature_spacing(rule, mgg, constraints):
    circles = mgg.query().get_by_entity_type("CIRCLE")
    min_wall = rule.parameters["min_drill_wall_mm"]
    
    for i, a in enumerate(circles):
        for b in circles[i+1:]:
            center_dist = distance(a.centroid, b.centroid)
            wall = center_dist - a.radius_mm - b.radius_mm
            if wall < min_wall:
                # flag as ERROR: wall={wall:.2f}mm < {min_wall}mm
```

---

## MFG-003: Tool Radius Corner Feasibility

```yaml
rule_id: "MFG-003"
name: "Tool Radius Corner Feasibility"
layer: 2
rule_type: "machine_heuristic"
severity: "ERROR"
applies_to: ["pocket_features", "groove_features"]
parameters:
  min_tool_radius_mm: 3.0
source: "Fundamental CNC routing constraint; assumes 6mm diameter router bit minimum"
confidence_ceiling: 0.65
adjustable: true
standards_refs:
  - standard: "ISO 1101:2017"
    description: "Geometrical tolerancing; corner form tolerances"
```

**Logic**: Internal pocket corners cannot be sharper than the minimum tool radius. A CNC router cannot cut perfect 90° internal corners — the tool is circular. For each pocket contour, find all concave (internal) corners, measure actual corner radius, and flag if `corner_radius < min_tool_radius_mm`.

```python
def check_tool_radius_feasibility(rule, mgg, constraints):
    min_radius = rule.parameters["min_tool_radius_mm"]
    for node in mgg.query().get_interior_closed_contours():
        polygon = Polygon(node.coordinates)
        for corner_radius in compute_internal_corner_radii(polygon):
            if corner_radius < min_radius:
                # flag as ERROR: internal corner radius {corner_radius:.2f}mm < min_tool_radius {min_radius}mm
```

**Source rationale**: "Machinery's Handbook, 30th ed., §CNC Milling Fundamentals — tool path geometry." A 6mm router bit cannot machine any internal corner tighter than 3mm radius.

---

## MFG-004: Pocket Width

```yaml
rule_id: "MFG-004"
name: "Minimum Pocket Width"
layer: 2
rule_type: "machine_heuristic"
severity: "ERROR"
applies_to: ["LWPOLYLINE"]
parameters:
  default_tool_diameter_mm: 6.0
  min_pocket_width_ratio: 1.2
source: "CNC routing geometry; tool cannot fit in narrower pocket"
confidence_ceiling: 0.65
```

**Logic**: The minimum inscribed circle diameter of a pocket contour must be ≥ tool_diameter × 1.2. A 6mm tool cannot route a pocket narrower than 7.2mm — the tool cannot complete the pass.

```python
def check_pocket_width(rule, mgg, constraints):
    tool_d = rule.parameters["default_tool_diameter_mm"]
    min_width = tool_d * rule.parameters["min_pocket_width_ratio"]
    
    for node in mgg.query().get_interior_closed_contours():
        polygon = Polygon(node.coordinates)
        min_inscribed_diameter = compute_min_inscribed_diameter(polygon)
        if min_inscribed_diameter < min_width:
            # flag as ERROR
```

---

## MFG-005: Shelf Pin Grid Alignment

```yaml
rule_id: "MFG-005"
name: "Shelf Pin Hole Grid Alignment"
layer: 2
rule_type: "standards_derived"
severity: "WARNING"
applies_to: ["CIRCLE"]
parameters:
  shelf_pin_diameter_mm: 5.0
  shelf_pin_spacing_mm: 32.0
  shelf_pin_tolerance_mm: 0.5
  diameter_tolerance_mm: 0.5
source: "European 32mm system (Rasterbohrsystem); DIN 68xxx cabinet hardware"
confidence_ceiling: 0.90
```

**Logic**: CIRCLE entities with diameter = 5mm ± 0.5mm that form a collinear group (SAME_COLUMN or SAME_ROW edges) are checked for 32mm spacing. Deviation > 0.5mm from the 32mm grid → WARNING. Note: This rule CANNOT confirm they are shelf pin holes (no semantic access), only that small-diameter circles violate the expected 32mm system spacing.

---

## MFG-006: Hinge Cup Edge Distance

```yaml
rule_id: "MFG-006"
name: "Hinge Cup Edge Distance"
layer: 2
rule_type: "hardware_spec"
severity: "WARNING"
applies_to: ["CIRCLE"]
parameters:
  hinge_cup_diameter_mm: 35.0
  hinge_cup_edge_distance_mm: 22.5
  hinge_cup_tolerance_mm: 1.0
  diameter_tolerance_mm: 1.0
source: "Blum CLIP top standard; Blum motion technology catalog"
confidence_ceiling: 0.90
```

**Logic**: CIRCLE entities with diameter = 35mm ± 1mm are checked for edge distance = 22.5mm ± 1.0mm. This is the Blum CLIP top hinge cup standard. Deviation outside tolerance → WARNING. Note: Rule cannot confirm this is a hinge cup (no semantic access) but 35mm circles near panel edges are almost always hinge cups in cabinet manufacturing.

---

## MFG-007: Blind Feature Depth

```yaml
rule_id: "MFG-007"
name: "Maximum Blind Feature Depth"
layer: 2
rule_type: "material_heuristic"
severity: "WARNING"
applies_to: ["LWPOLYLINE"]
parameters:
  max_blind_depth_ratio: 0.75
  default_panel_thickness_mm: 18.0
source: "CNC routing practice; structural floor thickness"
confidence_ceiling: 0.70
```

**Note**: DXF geometry is 2D. Depth information is not directly available. This rule applies when depth metadata is embedded in the layer name or as an attribute. If no depth information is present, rule is skipped (returns PASS with note "depth_unknown").

---

## MFG-008: Feature Density

```yaml
rule_id: "MFG-008"
name: "Feature Density Check"
layer: 2
rule_type: "material_heuristic"
severity: "WARNING"
applies_to: ["panel_level"]
parameters:
  max_hole_coverage_ratio: 0.30
source: "Structural rule of thumb; MDF/particleboard panels lose structural integrity above ~30% hole coverage"
confidence_ceiling: 0.70
```

**Logic**: Total hole area as a fraction of panel area must not exceed 30%. Computed as: `coverage_ratio = sum(π × r²) / panel_area`. If `coverage_ratio > 0.30`: WARNING.

**Note**: Labeled as heuristic. Formal structural analysis is out of scope for OMIM.

---

## MFG-009: Minimum Panel Dimensions

```yaml
rule_id: "MFG-009"
name: "Minimum Panel Dimensions"
layer: 2
rule_type: "shop_convention"
severity: "WARNING"
applies_to: ["panel_boundary"]
parameters:
  min_dimension_mm: 50.0
  max_dimension_mm: 3600.0
  min_area_mm2: 5000.0
source: "Practical CNC nesting table minimum; standard nesting table sizes"
confidence_ceiling: 0.75
```

**Logic**: Panel must be within processable range. Panels smaller than 50mm in any dimension are typically manually processed (not CNC). Maximum 3600mm matches standard nesting table. Minimum area 5000mm² (≈70×70mm) filters out sub-component details.

---

## MFG-010: Confirmat Screw Pair Positioning

```yaml
rule_id: "MFG-010"
name: "Confirmat Screw Pair Positioning"
layer: 2
rule_type: "hardware_spec"
severity: "INFO"
applies_to: ["CONFIRMAT_HOLE"]
parameters: {}
source: "Confirmat screw joining technique; HAFELE Confirmat specifications"
confidence_ceiling: 0.90
note: "Only applicable in multi-panel context; single-panel analysis cannot evaluate this"
```

**Logic**: Confirmat holes on joining panels should be in matching pairs at corresponding positions. In single-panel analysis this rule is informational only — it cannot be verified without the mating panel. Returns INFO result noting that pair verification requires multi-panel context.

**Source**: HAFELE Confirmat screw system: matching holes on mating panels must be precisely aligned for the screw to engage both panels correctly.

---

## MFG-011: Drill Diameter Range

```yaml
rule_id: "MFG-011"
name: "Drill Diameter Range"
layer: 2
rule_type: "shop_convention"
severity: "ERROR"
applies_to: ["CIRCLE"]
parameters:
  min_hole_diameter_mm: 3.0
  max_hole_diameter_mm: 40.0
source: "Tooling catalog limits; Leuco/Leitz drill specifications"
confidence_ceiling: 0.75
```

**Logic**: Circle diameter must be within [3.0mm, 40.0mm]. Holes smaller than 3mm require specialized micro-drill tooling not in scope for panel CNC. Holes larger than 40mm require routing operations, not drilling — they would be classified as pockets, not drilled holes.

---

## MFG-012: No Feature on Sheet Edge

```yaml
rule_id: "MFG-012"
name: "No Feature on Sheet Edge"
layer: 2
rule_type: "shop_convention"
severity: "ERROR"
applies_to: ["CIRCLE", "LWPOLYLINE"]
parameters:
  tolerance_mm: 0.1
source: "CNC machining practice; ambiguous cut direction at exact boundary"
confidence_ceiling: 0.75
```

**Logic**: Feature centroid must NOT lie on the panel boundary polygon (within 0.1mm tolerance). A feature positioned exactly on the boundary creates machining ambiguity — the CNC controller cannot determine whether to cut inside or outside the boundary.

```python
def check_no_feature_on_edge(rule, mgg, constraints):
    panel_boundary = mgg.query().get_panel_boundary()
    boundary_line = panel_boundary.exterior
    tolerance = rule.parameters["tolerance_mm"]
    
    for node in mgg.query().get_interior_nodes():
        centroid_pt = Point(node.centroid)
        dist_to_boundary = boundary_line.distance(centroid_pt)
        if dist_to_boundary <= tolerance:
            # flag as ERROR: feature centroid is on panel boundary
```

---

## Layer 2 Summary

| Rule | Name | Severity | Confidence | Key Threshold |
|------|------|---------|-----------|--------------|
| MFG-001 | Edge Clearance | ERROR | 0.75 | ≥ 8mm from edge |
| MFG-002 | Feature Spacing | ERROR | 0.70 | ≥ 3mm wall between holes |
| MFG-003 | Tool Radius Corner | ERROR | 0.65 | corner_r ≥ 3mm |
| MFG-004 | Pocket Width | ERROR | 0.65 | width ≥ 1.2 × tool_dia |
| MFG-005 | Shelf Pin 32mm Grid | WARNING | 0.90 | spacing = 32mm ±0.5mm |
| MFG-006 | Hinge Cup Edge Distance | WARNING | 0.90 | 22.5mm edge ±1.0mm |
| MFG-007 | Blind Feature Depth | WARNING | 0.70 | depth ≤ 0.75 × thickness |
| MFG-008 | Feature Density | WARNING | 0.70 | coverage ≤ 30% |
| MFG-009 | Minimum Panel Dimensions | WARNING | 0.75 | 50mm–3600mm |
| MFG-010 | Confirmat Pair Positioning | INFO | 0.90 | multi-panel context only |
| MFG-011 | Drill Diameter Range | ERROR | 0.75 | diameter 3–40mm |
| MFG-012 | No Feature on Sheet Edge | ERROR | 0.75 | centroid not on boundary |

**Pass condition**: `layer2_passed = True` when zero ERRORs in MFG-001 through MFG-012. Warnings and INFO are recorded but do not set layer2_passed=False.

**overall_valid**: `layer1_passed AND layer2_passed`

---

## Dual Use in Dataset Generation

When generating synthetic datasets, Layer 2 serves two purposes:

1. **Quality gate**: Valid samples must pass all ERROR rules
2. **Label generator**: Invalid samples have known violations (injected by the generator, then verified by this engine)

The provenance system records `pipeline_stage: "validation"` and `inference_method: "deterministic"` for all rule results.
