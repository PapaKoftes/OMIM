# Constraint Taxonomy

Version: v0.1.0  
Section: 04_ONTOLOGY  

See also: [[05_VALIDATION/Manufacturability_Validation]], [[01_FOUNDATION/Manufacturing_Domain_Lock]]

---

## Purpose

Defines the constraint types used in OMIM v0.1.0 and their default values for the panel manufacturing domain.

---

## Constraint Definitions

| Constraint | Description | Unit | Source |
|-----------|-------------|------|--------|
| MIN_EDGE_CLEARANCE | Min distance from feature centroid to panel edge | mm | MFG-001; shop convention |
| MIN_FEATURE_SPACING | Min edge-to-edge distance between adjacent features | mm | MFG-002; material strength |
| MIN_DRILL_DIAMETER | Min manufacturable hole diameter | mm | Tooling limit |
| MAX_DRILL_DIAMETER | Max for drilling (route instead) | mm | Process limit |
| CORNER_RADIUS | Min internal corner radius (= tool_radius) | mm | CNC routing geometry |
| MIN_POCKET_WIDTH | Min milled pocket width (= 1.2 × tool_diameter) | mm | MFG-004; routing clearance |
| MAX_BLIND_DEPTH | Max blind feature depth as ratio of thickness | ratio | MFG-007; structural floor |
| PANEL_THICKNESS | Nominal panel thickness | mm | Material spec (EN 309) |
| TOOL_DIAMETER | Default routing tool diameter | mm | Tooling |
| DRILL_DIAMETER | Specific drill bit diameter | mm | Tooling |

---

## Default Values (Panel CNC, v0.1.0)

```yaml
# data/rules/default_constraints.yaml
constraints:
  min_edge_clearance_mm: 8.0         # MFG-001; shop convention for MDF
  min_drill_wall_mm: 3.0             # MFG-002; edge-to-edge between holes (absolute)
  min_drill_spacing_ratio: 1.5       # MFG-002 alternative; center_distance >= diameter * 1.5
  min_pocket_width_ratio: 1.2        # MFG-004; width >= tool_diameter * 1.2
  default_tool_diameter_mm: 6.0      # Standard routing tool
  min_tool_radius_mm: 3.0            # Corner radius limit for 6mm tool
  max_blind_depth_ratio: 0.75        # MFG-007; depth <= thickness * 0.75
  default_panel_thickness_mm: 18.0   # EN 309; standard particleboard
  min_hole_diameter_mm: 3.0          # MFG-011; practical minimum drill bit
  max_hole_diameter_mm: 40.0         # MFG-011; above this → routing, not drilling
  max_nesting_table_mm: [3600, 2100] # Standard CNC nesting table
  shelf_pin_spacing_mm: 32.0         # MFG-005; European 32mm system
  shelf_pin_tolerance_mm: 0.5        # MFG-005; grid tolerance
  hinge_cup_edge_distance_mm: 22.5   # MFG-006; Blum CLIP top standard
  hinge_cup_tolerance_mm: 1.0        # MFG-006; acceptable deviation
```

**Note on `min_drill_wall_mm` vs `min_drill_spacing_ratio`**: Two equivalent constraint formulations exist:
- `min_drill_wall_mm: 3.0` — absolute wall thickness (preferred for small holes)
- `min_drill_spacing_ratio: 1.5` — center_distance ≥ diameter × 1.5 (preferred for variable-diameter analysis)

For a 5mm hole: ratio gives wall ≥ 2.5mm; absolute gives wall ≥ 3.0mm. The absolute is stricter for small holes.  
For a 20mm hole: ratio gives wall ≥ 10mm; absolute gives wall ≥ 3.0mm. The ratio is stricter for large holes.

MFG-002 uses the absolute formulation (`min_drill_wall_mm`) as it is more conservative for the primary panel manufacturing use case (small drill holes). The ratio formulation is retained in constraints.yaml as a named alternative for systems that prefer it.

---

## Constraint Sources by Rule Type

| Rule Type | Confidence Ceiling | Example |
|-----------|------------------|---------|
| `geometric` | 1.0 | Open contour, self-intersection |
| `standards_derived` | 0.95 | ISO 286 hole tolerances |
| `hardware_spec` | 0.90 | Blum 22.5mm hinge cup distance |
| `shop_convention` | 0.75 | 8mm edge clearance |
| `material_heuristic` | 0.70 | 3mm wall between MDF holes |
| `machine_heuristic` | 0.65 | Pocket width = 1.2 × tool diameter |

---

## ConstraintNode in MGG

```python
class ConstraintNode(BaseModel):
    node_id: str
    node_type: Literal["constraint"] = "constraint"
    constraint_type: str            # from this taxonomy
    constraint_value: float
    constraint_unit: str            # "mm" | "ratio" | "degrees"
    is_violated: bool
    violation_severity: str | None  # "ERROR" | "WARNING"
    applies_to_node_ids: list[str]
    rule_id: str                    # which rule generated this
    provenance: ProvenanceRecord
```

**ConstraintNodes are added to the MGG only when a constraint is violated.** Non-violated constraints are not stored as graph nodes — they are implicit in the rule definitions.
