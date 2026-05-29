# Rule Engine & Standards Reference

Version: v0.1.0  

See also: [[Validation]], [[Manufacturing Ontology]], [[Standards and References]]

---

## Purpose

This document defines:
1. The rule schema (how rules are specified)
2. All manufacturing rules used in v0.1.0 with sources
3. Standards integration references
4. Rule versioning and governance

Every rule in OMIM must be traceable to a source. Custom heuristics are permitted only when no standard applies, and must be clearly labeled as such.

---

## Rule Type Classification

**Critical**: Many manufacturability rules are NOT universal. Real manufacturability depends on tooling, spindle, material, feeds/speeds, fixturing, machine rigidity, and shop conventions. A rule that holds for MDF on a 3-axis router does NOT necessarily hold for plywood on a high-speed machining center.

Every rule MUST declare its type. This determines how confidently it can be applied:

| Rule Type | Description | Confidence | Example |
|-----------|-------------|------------|---------|
| `geometric` | Geometric consistency; material/machine independent | `1.0` | Open contour, self-intersection |
| `standards_derived` | Directly traceable to an ISO/DIN standard | `0.95` | ISO 286 hole tolerance grades |
| `hardware_spec` | From a specific hardware manufacturer's catalog | `0.90` | Blum hinge cup: 22.5mm from edge |
| `shop_convention` | Widely used practice; not formally standardized | `0.75` | 8mm edge clearance default |
| `material_heuristic` | Applies to specific material class (MDF, plywood, etc.) | `0.70` | 3mm wall between MDF holes |
| `machine_heuristic` | Applies to specific machine configuration (tool diameter, RPM) | `0.65` | Pocket width = 1.2 × tool diameter |

Rules of type `shop_convention`, `material_heuristic`, or `machine_heuristic` MUST include:
- `domain_applicability`: what machine/material this applies to
- `confidence`: explicit value below 1.0 in the YAML
- `note`: documentation that this is not universal

```yaml
# Example: rule with explicit applicability constraints
rule_id: MFG-001
rule_type: shop_convention           # NOT a formal standard
domain_applicability:
  material: [MDF, particleboard, melamine_particleboard]
  machine_type: [3_axis_cnc_router]
  NOT_applicable_to: [solid_wood, plywood_grain_sensitive, high_speed_milling]
confidence: 0.75
source: "Common 3-axis panel CNC shop practice; not standardized"
note: "Heuristic. Real edge clearance depends on tool sharpness, spindle speed, material density, and fixturing. 8mm is conservative default for MDF."
```

This split prevents fake certainty. A failing MFG-001 on a solid oak panel is not the same as failing it on MDF.

---

## Rule Schema

Rules are stored in YAML and loaded at runtime. Each rule is self-describing.

```yaml
# Full rule schema
rule_id: string           # Required. Unique. Format: "GEO-NNN" or "MFG-NNN"
version: string           # Required. SemVer: "v0.1.0"
name: string              # Required. snake_case identifier
category: string          # "geometric" | "manufacturability" | "semantic_plausibility"
layer: integer            # 1 | 2 | 3 (validation layer)
description: string       # Required. Human-readable explanation
severity: string          # "ERROR" | "WARNING" | "INFO"

# Applicability
applies_to: list[string]  # Entity types or feature classes this rule applies to
domain: string            # "panel_cnc" | "all" | specific domain

# Rule logic
algorithm: string         # Description of the algorithm used
parameters:               # Named, overridable parameters
  key: value
  
# Sources (at least one required)
sources: list[string]     # Free-text citations
standards_refs: list      # Formal standard references
  - standard: string      # e.g., "ISO 2768-1:1989"
    clause: string        # e.g., "Table 1, class m"
    description: string
    
# Status
status: string            # "active" | "draft" | "deprecated"
expert_reviewed: boolean  # True if reviewed by domain expert
review_notes: string
added_in_version: string
```

---

## Layer 1 Rules (Geometric Validity)

### GEO-001: Contour Closure
```yaml
rule_id: GEO-001
version: v0.1.0
name: contour_closure
category: geometric
layer: 1
description: "All closed cutting contours must be topologically closed with no open endpoints"
severity: ERROR
applies_to: [LWPOLYLINE, POLYLINE, contour_features]
algorithm: |
  check: distance(first_point, last_point) <= tolerance_mm
  for LWPOLYLINE: check is_closed flag OR endpoint distance
parameters:
  tolerance_mm: 0.01
sources:
  - "Fundamental CNC routing requirement: open contours produce undefined toolpaths"
  - "ezdxf documentation: LWPOLYLINE.is_closed property"
standards_refs:
  - standard: "ISO 6983-1:2009"
    description: "NC part program format; assumes closed contours for pocket operations"
status: active
expert_reviewed: false
added_in_version: v0.1.0
```

### GEO-002: No Self-Intersection
```yaml
rule_id: GEO-002
version: v0.1.0
name: no_self_intersection
category: geometric
layer: 1
description: "Closed contours must be simple polygons (no self-intersections)"
severity: ERROR
algorithm: "Shapely: not polygon.is_simple"
parameters: {}
sources:
  - "OGC Simple Feature Access specification §2.1.1.2"
  - "Shapely documentation: is_simple property"
  - "Self-intersecting toolpaths cause CNC controller errors"
standards_refs:
  - standard: "ISO 19125-1:2004"
    clause: "§6.1.2"
    description: "Simple feature: geometry with no anomalous geometric points (self-intersections)"
status: active
expert_reviewed: false
added_in_version: v0.1.0
```

### GEO-003: Positive Area
```yaml
rule_id: GEO-003
version: v0.1.0
name: positive_area
category: geometric
layer: 1
description: "All closed cutting contours must have positive area (degenerate geometry check)"
severity: ERROR
parameters:
  minimum_area_mm2: 0.01
sources:
  - "Shapely area property; degenerate polygons"
  - "Zero-area contours cannot be machined"
status: active
added_in_version: v0.1.0
```

### GEO-004: Valid Circle Radius
```yaml
rule_id: GEO-004
version: v0.1.0
name: valid_circle_radius
category: geometric
layer: 1
description: "All circles must have positive, non-zero radius"
severity: ERROR
applies_to: [CIRCLE]
parameters:
  minimum_radius_mm: 0.001
status: active
added_in_version: v0.1.0
```

### GEO-005: No Degenerate Arcs
```yaml
rule_id: GEO-005
version: v0.1.0
name: no_degenerate_arcs
category: geometric
layer: 1
description: "Arcs must have non-zero sweep angle and positive radius"
severity: ERROR
applies_to: [ARC]
parameters:
  minimum_sweep_degrees: 0.01
  minimum_radius_mm: 0.001
status: active
added_in_version: v0.1.0
```

### GEO-006: No Duplicate Entities
```yaml
rule_id: GEO-006
version: v0.1.0
name: no_duplicate_entities
category: geometric
layer: 1
description: "No two identical geometry entities at the same position on the same layer"
severity: WARNING
algorithm: "Compare (entity_type, layer, geometry_hash) tuples for duplicates"
parameters:
  position_tolerance_mm: 0.01
sources:
  - "Duplicate geometry on cutting layers causes double-cutting (tool wear, material damage)"
status: active
added_in_version: v0.1.0
```

---

## Layer 2 Rules (Manufacturing Feasibility)

### MFG-001: Minimum Edge Clearance
```yaml
rule_id: MFG-001
version: v0.1.0
name: minimum_edge_clearance
category: manufacturability
layer: 2
description: "Holes and features must maintain minimum distance from panel edge to prevent tearout and structural failure"
severity: ERROR
applies_to: [CIRCLE, pocket_features, milled_features]
algorithm: |
  For each feature:
    dist = shapely_panel_exterior.distance(feature_centroid_point)
    if dist < threshold_mm: FAIL
parameters:
  threshold_mm: 8.0
sources:
  - "Common CNC panel manufacturing practice"
  - "Wood composite structural requirements: tearout occurs when drilling too close to edge"
  - "Industry-standard minimum: most shops use 8-10mm for MDF/particleboard"
standards_refs:
  - standard: "DIN 68861-1"
    description: "Panel furniture surfaces; structural requirements indirectly imply edge distance"
adjustable: true
status: active
expert_reviewed: false
added_in_version: v0.1.0
```

### MFG-002: Minimum Drill-to-Drill Spacing
```yaml
rule_id: MFG-002
version: v0.1.0
name: minimum_drill_spacing
category: manufacturability
layer: 2
description: "Adjacent drill holes must have sufficient material remaining between them"
severity: ERROR
applies_to: [CIRCLE]
algorithm: |
  For each pair of circles (A, B):
    wall = distance(center_A, center_B) - radius_A - radius_B
    if wall < min_wall_mm: FAIL
parameters:
  min_wall_mm: 3.0
sources:
  - "Structural integrity requirement for MDF/particleboard panels"
  - "3mm minimum wall is conservative standard practice"
  - "Source: CNC router operator manuals; furniture manufacturing guidelines"
status: active
expert_reviewed: false
added_in_version: v0.1.0
```

### MFG-003: Tool Radius Corner Feasibility
```yaml
rule_id: MFG-003
version: v0.1.0
name: tool_radius_corner_feasibility
category: manufacturability
layer: 2
description: "Internal pocket corners cannot be sharper than the minimum tool radius — CNC cannot cut perfect 90° internal corners"
severity: ERROR
applies_to: [pocket_features, groove_features]
algorithm: |
  For each internal corner of each pocket contour:
    corner_radius = inscribed_circle_radius_at_corner(corner_vertex)
    if corner_radius < min_tool_radius_mm: FAIL
parameters:
  min_tool_radius_mm: 3.0  # assumes 6mm diameter router bit
sources:
  - "Fundamental CNC routing constraint: tool is circular, cannot cut sharper corners than its radius"
  - "Machinery's Handbook 30th ed., §Milling Cutters: tool path geometry"
  - "CAM principle: corner radius must be >= tool radius for any 2D pocket"
standards_refs:
  - standard: "ISO 1101:2017"
    description: "Geometrical tolerancing; corner form tolerances"
adjustable: true
status: active
expert_reviewed: false
added_in_version: v0.1.0
```

### MFG-004: Minimum Pocket Width
```yaml
rule_id: MFG-004
version: v0.1.0
name: minimum_pocket_width
category: manufacturability
layer: 2
description: "Pocket must be wide enough to allow routing passes (minimum 1.2x tool diameter)"
severity: ERROR
applies_to: [pocket_features, groove_features]
algorithm: |
  pocket_min_width = minimum_bounding_rectangle_shortest_side(pocket_contour)
  if pocket_min_width < tool_diameter * width_ratio: FAIL
parameters:
  tool_diameter_mm: 6.0
  width_ratio: 1.2
sources:
  - "CNC routing practice: 1.2x factor provides tool clearance for entry and chip evacuation"
  - "CAM toolpath minimum: pockets narrower than tool diameter cannot be routed"
status: active
added_in_version: v0.1.0
```

### MFG-005: Shelf Pin 32mm System Compliance
```yaml
rule_id: MFG-005
version: v0.1.0
name: shelf_pin_32mm_grid
category: manufacturability
layer: 2
description: "Detected shelf pin holes should conform to 32mm modular grid spacing"
severity: WARNING
applies_to: [SHELF_PIN_HOLE]
algorithm: |
  Group SHELF_PIN_HOLEs by column (same X within 1mm)
  For each group, check consecutive spacing = 32.0 ± tolerance_mm
parameters:
  expected_spacing_mm: 32.0
  tolerance_mm: 0.5
sources:
  - "European 32mm furniture system (Rasterbohrsystem)"
  - "Industry standard for adjustable shelving hardware"
  - "Hettich catalog §shelf carrier systems"
  - "Grass catalog §shelf pin systems"
  - "Blum shelf pin system: https://www.blum.com/"
standards_refs:
  - standard: "DIN 68xxx"
    description: "European furniture hardware standards; 32mm modular system"
status: active
expert_reviewed: false
added_in_version: v0.1.0
```

### MFG-006: Hinge Cup Edge Positioning
```yaml
rule_id: MFG-006
version: v0.1.0
name: hinge_cup_edge_distance
category: manufacturability
layer: 2
description: "Blum-style hinge cup holes should be positioned 22.5mm from panel edge (standard mounting)"
severity: WARNING
applies_to: [HINGE_CUP_HOLE]
algorithm: |
  distance_to_nearest_edge = min(feature_centroid to all panel edge segments)
  if |distance_to_nearest_edge - expected_distance_mm| > tolerance_mm: WARNING
parameters:
  expected_distance_mm: 22.5
  tolerance_mm: 1.0
sources:
  - "Blum CLIP top hinge mounting specification"
  - "Blum installation manual: https://www.blum.com/"
  - "Standard Eurohinges spec: 22.5mm from edge center"
standards_refs:
  - standard: "Blum Technical Documentation"
    description: "CLIP top BLUMOTION hinge mounting: 22.5mm bore center from edge"
status: active
expert_reviewed: false
added_in_version: v0.1.0
```

### MFG-007: Maximum Feature Depth
```yaml
rule_id: MFG-007
version: v0.1.0
name: max_blind_feature_depth
category: manufacturability
layer: 2
description: "Blind features must not exceed 75% of panel thickness to maintain structural floor"
severity: ERROR
applies_to: [BLIND_HOLE, pocket_features]
note: "Only evaluated when explicit depth metadata is available in DXF"
parameters:
  max_depth_ratio: 0.75
  default_panel_thickness_mm: 18.0
sources:
  - "Structural integrity requirement for wood composite panels"
  - "Insufficient floor thickness leads to surface breakthrough during machining"
  - "Industry practice: maintain minimum 4.5mm floor for 18mm panel"
status: active
added_in_version: v0.1.0
```

### MFG-008: Feature Density
```yaml
rule_id: MFG-008
version: v0.1.0
name: feature_density_check
category: manufacturability
layer: 2
description: "Panel hole coverage must not exceed threshold to maintain structural integrity"
severity: WARNING
algorithm: |
  total_hole_area = sum(π * r² for all circles)
  coverage_ratio = total_hole_area / panel_area
  if coverage_ratio > max_coverage_ratio: WARNING
parameters:
  max_coverage_ratio: 0.30
sources:
  - "Structural rule of thumb: MDF/particleboard panels lose structural integrity above ~30% hole coverage"
  - "Heuristic: no direct ISO standard; engineering judgment"
note: "Labeled as heuristic. Formal structural analysis is out of scope."
status: active
expert_reviewed: false
added_in_version: v0.1.0
```

### MFG-009: Minimum Panel Dimensions
```yaml
rule_id: MFG-009
version: v0.1.0
name: minimum_panel_dimensions
category: manufacturability
layer: 2
description: "Panel dimensions must be within processable range for CNC nesting workflow"
severity: WARNING
parameters:
  min_dimension_mm: 50.0
  max_dimension_mm: 3600.0
  min_area_mm2: 5000.0
sources:
  - "Practical CNC nesting table minimum: panels smaller than 50mm are typically manually processed"
  - "Maximum based on standard nesting table sizes (3600×2100mm common)"
status: active
added_in_version: v0.1.0
```

### MFG-010: Confirmat Screw Pair Positioning
```yaml
rule_id: MFG-010
version: v0.1.0
name: confirmat_pair_positioning
category: manufacturability
layer: 2
description: "Confirmat holes on joining panels should be in matching pairs at corresponding positions"
severity: INFO
applies_to: [CONFIRMAT_HOLE]
note: "Only applicable in multi-panel context; single-panel analysis cannot evaluate this"
sources:
  - "Confirmat screw joining technique requires matching holes on mating panels"
  - "HAFELE Confirmat screw system specifications: https://www.hafele.com/"
status: active
added_in_version: v0.1.0
```

---

## Standards Integration Reference

### ISO Standards

| Standard | Title | Relevance to OMIM |
|----------|-------|-------------------|
| ISO 286-1:2010 | Geometrical Product Specifications — Linear sizes — Part 1: Tolerances | Hole tolerance grades |
| ISO 2768-1:1989 | General tolerances — Part 1: Tolerances for linear and angular dimensions | Default machining tolerances |
| ISO 2768-2:1989 | General tolerances — Part 2: Geometrical tolerances | Form and position tolerances |
| ISO 6983-1:2009 | Automation systems — Numerical control — NC Part program format | G-code format context |
| ISO 10303 (STEP) | Product data representation and exchange | Future format interoperability |
| ISO 1101:2017 | Geometrical tolerancing | Feature form tolerances |
| ISO 15487:2020 | Twist drills — Dimensions | Drill bit geometry |
| ISO 10642:2004 | Hexagon socket countersunk head screws | Countersink geometry |

### DIN Standards (Panel/Furniture Focus)

| Standard | Title | Relevance |
|----------|-------|-----------|
| DIN 68xxx series | Wood and panel materials | Panel dimensions, material grades |
| DIN 68861-1 | Coating materials for furniture | Panel surface requirements |
| DIN 7 | Dowel pins | Dowel pin dimensions |
| DIN 68752 | Tongue-and-groove boards | Groove/tongue geometry reference |

### Hardware Manufacturer Specifications

| Manufacturer | System | Relevance |
|-------------|--------|-----------|
| Blum | CLIP top / AVENTOS / TANDEM | Hinge cup holes (35mm), drawer systems |
| Hettich | Invis Mex / InnoFit | Shelf pins, drawer slides, hinge specifications |
| Grass | TIOMOS / Nova Pro | Hinge mounting, drawer systems |
| HAFELE | Confirmat screws / KD fittings | Confirmat holes, cam-lock fittings |
| Lamello | Bisco / P-System | Groove dimensions |
| FESTOOL | System accessories | Routing templates |

### Open Source References

| System | URL | Relevance |
|--------|-----|-----------|
| LinuxCNC | https://linuxcnc.org/ | G-code interpretation, CNC constraints |
| OpenCAMLib | https://github.com/aewallin/opencamlib | Open CAM algorithm reference |
| FreeCAD Path workbench | https://github.com/FreeCAD/FreeCAD | Open CAM toolpath logic |
| OpenSCAD | https://openscad.org/ | Programmatic CAD reference |
| CadQuery | https://cadquery.readthedocs.io/ | Programmatic CAD, used in synthetic gen |
| ezdxf | https://ezdxf.readthedocs.io/ | Primary DXF parsing library |

---

## Rule Governance

### Adding a New Rule
1. Assign next sequential rule_id in appropriate series (GEO-NNN or MFG-NNN)
2. Write YAML definition with all required fields
3. Add at least one source citation
4. Mark `expert_reviewed: false` until reviewed
5. Write unit test for the rule
6. Add to `panel_cnc_rules.yaml`
7. Bump ruleset minor version

### Modifying an Existing Rule
1. NEVER modify `rule_id` (would break provenance references)
2. Bump `version` field
3. Document change in `rules_changelog.md`
4. Re-run all validation tests after modification
5. Reset `expert_reviewed: false` if logic changed

### Rule Versioning
Ruleset version is independent of OMIM version.
Format: `v{major}.{minor}.{patch}`
- Major: breaking change to rule semantics or IDs
- Minor: new rules added
- Patch: parameter adjustments, description clarifications

### Rule Files
```
data/rules/
├── panel_cnc_rules.yaml     # Active rules (Layer 1 + Layer 2)
├── rules_changelog.md       # Change history
└── deprecated/              # Retired rules (kept for provenance)
```
