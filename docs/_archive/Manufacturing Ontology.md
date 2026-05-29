# Manufacturing Ontology Specification

Version: v0.1.0  
Domain: Panel Manufacturing (2.5D CNC)  

See also: [[What Is OMIM]], [[Manufacturing Geometry Graph (MGG) Specification]], [[Rule Engine and Standards]]

---

## Purpose

This document defines the complete manufacturing vocabulary for OMIM v0.1.0 (panel manufacturing scope). Every semantic label used anywhere in the system — feature classes, operation types, relationship types, constraint types — is defined here.

Rules for adding new terms:
1. Check existing terms for overlap first
2. Provide a source reference where possible (ISO, DIN, handbook)
3. Define the term unambiguously
4. Specify how it is detected/inferred
5. Specify confidence method

---

## Feature Taxonomy

### Class: HOLE_FEATURES

Holes are circular cutouts, either fully through the panel or blind (partial depth).

#### THROUGH_HOLE
- **Definition**: Circular cutout that passes completely through the panel thickness
- **Detection**: Circle entity with diameter within range, cutting layer
- **Diameter range**: 2mm – 60mm (general range; specific subtypes below)
- **Confidence method**: Geometric (diameter + layer), confidence: 0.6–0.9
- **Source**: General machining terminology; ANSI/ASME Y14.5

#### BLIND_HOLE
- **Definition**: Circular hole that does not pass completely through the panel
- **Detection**: Requires depth metadata; often inferred from context
- **Note**: Without explicit depth in DXF, blind/through distinction requires heuristic inference
- **Confidence method**: Layer convention + context, confidence: 0.5–0.8

#### COUNTERSINK
- **Definition**: Conical enlargement at the top of a hole to allow flush fastener seating
- **Detection**: Concentric circles (small + large), or layer named "V_SINK"
- **Source**: ISO 10642 — Hexagon socket countersunk head screws
- **Confidence method**: Concentric geometry pattern, confidence: 0.75–0.90

#### COUNTERBORE
- **Definition**: Cylindrical enlargement at the top of a hole (flat-bottomed)
- **Detection**: Concentric circles with specific diameter ratio
- **Source**: ISO 6194 — Counterbore dimensions
- **Confidence method**: Concentric pattern + diameter ratio, confidence: 0.70–0.85

#### SHELF_PIN_HOLE
- **Definition**: Small hole for adjustable shelf support pins; follows 32mm grid system
- **Diameter**: 5.0mm ± 0.2mm (standard), sometimes 3mm for light-duty pins
- **Detection**: 5mm circles, collinear, spaced 32mm ± 1mm apart (minimum 3 in a row)
- **Pattern**: European "Rasterbohrsystem" (32mm modular system)
- **Source**: Hettich shelf pin systems; Grass hardware standards; European 32mm system (DIN 68xxx furniture hardware)
- **Reference**: Blum catalog https://www.blum.com/; Hettich catalog https://www.hettich.com/
- **Confidence method**: Diameter match + 32mm spacing pattern, confidence: 0.85–0.95

#### HINGE_CUP_HOLE
- **Definition**: Large circular recess for concealed hinge cup (Blum/Grass-style hinges)
- **Diameter**: 35.0mm ± 0.5mm (standard), 26mm for mini hinges
- **Detection**: Circle with diameter 34–36mm, positioned near panel edge
- **Source**: Blum catalog (hinge mounting holes); DIN 68xxx furniture hardware
- **Reference**: Blum CLIP top BLUMOTION spec: https://www.blum.com/
- **Confidence method**: Diameter match + edge proximity, confidence: 0.88–0.96

#### CONFIRMAT_HOLE
- **Definition**: Stepped hole for Confirmat (Euro) screw fastener
- **Diameter**: Body: 7.0mm; Head: 10mm (stepped)
- **Detection**: 7mm circle or stepped geometry on joining faces
- **Source**: HAFELE Confirmat screw specifications; common European furniture joining hardware
- **Reference**: https://www.hafele.com/
- **Confidence method**: Diameter match, confidence: 0.80–0.92

#### DOWEL_HOLE
- **Definition**: Cylindrical hole for wooden dowel alignment/joining
- **Diameter**: 8mm (standard), 10mm (heavy duty), 6mm (light duty)
- **Detection**: 8mm or 10mm circles in pairs/groups near panel edges
- **Source**: ISO 10140 — Dowel pins; DIN 7 — Dowel pins
- **Confidence method**: Diameter range + position (near edge, in pairs), confidence: 0.70–0.85

#### HARDWARE_HOLE
- **Definition**: Generic hole for hardware mounting (handles, locks, etc.)
- **Diameter**: 20–50mm range, specific to hardware type
- **Detection**: Large circles not matching other known patterns
- **Confidence method**: Size exclusion of other types, confidence: 0.50–0.70

---

### Class: MILLED_FEATURES

Milled features are produced by routing/milling operations rather than drilling.

#### POCKET
- **Definition**: Bounded, closed milled recess that does not pass through the panel
- **Detection**: Closed polyline/contour on pocket layer, or circle above certain threshold
- **Minimum dimensions**: Width ≥ tool_diameter × 1.2, depth < panel_thickness
- **Source**: CNC routing fundamentals; Machinery's Handbook §pocket milling
- **Confidence method**: Closed contour + layer classification, confidence: 0.75–0.90

#### THROUGH_POCKET
- **Definition**: Milled recess that passes completely through the panel (inner cutout)
- **Detection**: Closed internal contour on cut/through layer
- **Note**: Geometrically: closed contour fully inside panel boundary
- **Confidence method**: Contour nesting (inside panel boundary), confidence: 0.85–0.95

#### GROOVE
- **Definition**: Long, narrow linear or curved milled slot, usually for joinery or panel insertion
- **Typical dimensions**: Width 4–15mm, depth 6–12mm, length >> width
- **Detection**: Elongated parallel lines or thin closed polygon with high aspect ratio (length/width > 5)
- **Source**: Woodworking joinery terminology; DIN 68752 (tongue and groove boards)
- **Confidence method**: Aspect ratio + orientation, confidence: 0.75–0.90

#### DADO
- **Definition**: Groove cut perpendicular to the wood grain direction (across the panel)
- **Note**: In panel CNC work, "dado" and "groove" are often used interchangeably; distinguish by orientation
- **Detection**: Groove perpendicular to panel's primary dimension
- **Source**: Woodworking terminology; Cabinet making standards
- **Confidence method**: As GROOVE + orientation analysis, confidence: 0.65–0.85

#### RABBET (REBATE)
- **Definition**: L-shaped notch along the edge or end of a panel
- **Detection**: Open-sided rectangular recess along panel edge; contour touching panel boundary
- **Typical dimensions**: Depth × width: 9×12mm, 12×12mm (matches panel thickness)
- **Source**: Woodworking joinery terminology
- **Confidence method**: Open contour touching panel edge, confidence: 0.75–0.88

#### OPEN_SLOT
- **Definition**: Open-ended slot milled from the panel edge inward
- **Detection**: U-shaped or elongated open contour opening at panel boundary
- **Confidence method**: Open contour + alignment with panel edge, confidence: 0.78–0.90

---

### Class: PROFILE_FEATURES

#### PROFILE_CUT (OUTER_CONTOUR)
- **Definition**: The outer boundary cut that produces the final panel shape
- **Detection**: Outermost closed contour on cut layer
- **Note**: Every panel has exactly one profile cut
- **Confidence method**: Outermost geometry + layer, confidence: 0.95+

#### INTERNAL_CUTOUT
- **Definition**: Closed internal profile cut (creates a hole or window in the panel)
- **Detection**: Closed contour fully inside panel boundary, on cut layer
- **Confidence method**: Nested contour detection, confidence: 0.88–0.96

#### CHAMFER
- **Definition**: Angled cut removing a corner (45° standard)
- **Detection**: Diagonal line segment at corner intersection
- **Source**: ISO 286 — standard chamfer designations
- **Confidence method**: Corner angle analysis, confidence: 0.70–0.85

#### FILLET
- **Definition**: Rounded corner (concave arc at internal corner)
- **Detection**: Arc entity at internal corner with radius matching tool radius
- **Source**: ISO 2768 — general tolerances; design practice
- **Confidence method**: Arc at corner + radius match, confidence: 0.75–0.88

---

## Operation Taxonomy

### DRILLING
- **Definition**: Vertical hole-making operation using rotating drill bit
- **Applies to**: THROUGH_HOLE, BLIND_HOLE, COUNTERSINK, COUNTERBORE, SHELF_PIN_HOLE, HINGE_CUP_HOLE, CONFIRMAT_HOLE, DOWEL_HOLE
- **Parameters**: diameter, depth, RPM, feed rate, tooling type
- **Machine type**: Vertical CNC drill, multi-spindle drill, Drill + Router combo
- **Source**: Machining handbooks; ISO 15487 — Twist drills

### CNC_ROUTING
- **Definition**: 2.5D CNC milling/routing operation following a defined path
- **Applies to**: POCKET, GROOVE, DADO, RABBET, OPEN_SLOT, THROUGH_POCKET
- **Parameters**: path, depth, tool_diameter, RPM, feed rate, passes
- **Machine type**: CNC router (3-axis)
- **Source**: CNC routing fundamentals

### PROFILE_CUTTING
- **Definition**: Following the outer or inner profile contour to cut out the panel shape
- **Applies to**: PROFILE_CUT, INTERNAL_CUTOUT
- **Parameters**: contour, depth (through), tool_diameter, tabs/bridges
- **Machine type**: CNC router (3-axis)
- **Note**: Includes tab/bridge placement to prevent part movement during cut

### NESTING
- **Definition**: Placement optimization of multiple panel profiles onto a sheet to minimize waste
- **This is not a machining operation** — it is a pre-processing step
- **Applies to**: Entire panel set
- **Source**: Nesting theory; OpenNest; SVGnest; DeepNest
- **Reference**: OpenNest: https://github.com/AndrewCarterUK/simple-nesting; SVGnest: https://svgnest.com/

### EDGE_BANDING (OUT OF SCOPE v0)
- **Definition**: Applying thin material strips to exposed panel edges
- **Note**: Post-routing operation; not representable in DXF geometry; out of scope for v0

---

## Relationship Taxonomy

All relationships are directed (from source → target) and typed.

| Relationship | Direction | Description |
|-------------|-----------|-------------|
| CONTAINS | panel → feature | Panel contains this feature |
| DEPENDS_ON | operation_A → operation_B | Operation A must execute before B |
| CONFLICTS_WITH | feature_A ↔ feature_B | Features overlap or violate spacing |
| ADJACENT_TO | feature_A ↔ feature_B | Features are geometrically near each other |
| REQUIRES_TOOLING | feature → tool_spec | Feature requires specific tool |
| SAME_GROUP | feature_A ↔ feature_B | Features belong to same logical group |
| SAME_ROW | hole_A ↔ hole_B | Holes in same horizontal row |
| SAME_COLUMN | hole_A ↔ hole_B | Holes in same vertical column |
| ENABLES | feature_A → operation_B | Feature presence enables/suggests operation |
| PRODUCED_BY | feature → operation | Feature is produced by this operation |

---

## Constraint Taxonomy

| Constraint | Description | Value Type | Source |
|-----------|-------------|------------|--------|
| MIN_EDGE_CLEARANCE | Minimum distance from feature to panel edge | mm | Shop practice |
| MIN_FEATURE_SPACING | Minimum center-to-center distance between features | mm | Material strength |
| MIN_DRILL_DIAMETER | Minimum manufacturable hole diameter | mm | Tooling limit |
| MAX_DRILL_DIAMETER | Maximum for drilling operation (route instead) | mm | Process limit |
| CORNER_RADIUS | Minimum internal corner radius (= tool_radius) | mm | CNC routing geometry |
| MIN_POCKET_WIDTH | Minimum milled pocket width | mm | Tool diameter |
| MAX_BLIND_DEPTH | Maximum blind feature depth as ratio of thickness | ratio (0-1) | Structural |
| PANEL_THICKNESS | Nominal panel thickness (18mm default) | mm | Material spec |
| TOOL_DIAMETER | Default routing tool diameter | mm | Tooling |
| DRILL_DIAMETER | Specific drill bit diameter | mm | Tooling |

### Default Constraint Values (Panel CNC, v0.1.0)

```yaml
# data/rules/default_constraints.yaml
constraints:
  min_edge_clearance_mm: 8.0
  min_drill_spacing_ratio: 1.5  # center_distance >= diameter * 1.5
  min_pocket_width_ratio: 1.2   # width >= tool_diameter * 1.2
  default_tool_diameter_mm: 6.0
  min_tool_radius_mm: 3.0       # corner radius limit
  max_blind_depth_ratio: 0.75   # depth <= thickness * 0.75
  default_panel_thickness_mm: 18.0
  min_hole_diameter_mm: 3.0
  max_nesting_table_mm: [3600, 2100]
```

---

## Material Types

```yaml
# data/ontology/materials.yaml
materials:
  MDF:
    name: Medium Density Fiberboard
    standard: EN 622-5
    typical_thickness_mm: [9, 12, 15, 18, 22, 25]
    notes: "Homogeneous, no grain direction. Standard furniture/cabinet material."
    
  PARTICLEBOARD:
    name: Particleboard (chipboard)
    standard: EN 309 / EN 312
    typical_thickness_mm: [9, 12, 15, 18, 22, 25]
    notes: "Lower strength than MDF, standard furniture carcass material."
    
  PLYWOOD:
    name: Plywood
    standard: EN 636
    typical_thickness_mm: [6, 9, 12, 15, 18, 21, 24]
    notes: "Has grain direction. Higher strength-to-weight. Note for nesting."
    
  MELAMINE_COATED_PARTICLEBOARD:
    name: Melamine coated particleboard
    notes: "Decorative surface. Edge banding typically required post-cut."
    
  HDF:
    name: High Density Fiberboard
    standard: EN 622-5
    typical_thickness_mm: [2, 3, 4, 6]
    notes: "Thin panels, back panels, drawer bottoms."
```

---

## Ontology File Structure

```
data/ontology/
├── features.yaml         # All feature types defined above
├── operations.yaml       # All operation types
├── relationships.yaml    # All relationship types
├── constraints.yaml      # All constraint types + default values
├── materials.yaml        # Panel material definitions
└── VERSION               # "v0.1.0"
```

### features.yaml Schema

```yaml
version: "v0.1.0"
domain: "panel_manufacturing_2.5d"
features:
  - id: SHELF_PIN_HOLE
    label: "Shelf Pin Hole"
    category: HOLE_FEATURES
    description: "Small hole for adjustable shelf support pins, following 32mm modular system"
    detection:
      geometry_type: circle
      diameter_range_mm: [4.8, 5.2]
      pattern: "32mm_grid"
      min_count_for_pattern: 3
    confidence:
      single_hole: 0.75
      confirmed_pattern: 0.92
    inference_method: "heuristic_diameter_and_pattern"
    sources:
      - "European 32mm furniture system (Rasterbohrsystem)"
      - "Blum shelf pin system: https://www.blum.com/"
      - "DIN 68xxx furniture hardware series"
    operation: DRILLING
    parameters:
      diameter_mm: 5.0
      depth_mm: "12-15 (typically not through)"
      tolerance_mm: 0.1
```

---

## Ontology Loader (Python Interface)

```python
# omim/ontology/loader.py

class OntologyLoader:
    def load(self, ontology_dir: str) -> Ontology:
        """Load all YAML files into typed Ontology object."""
    
class Ontology:
    version: str
    features: dict[str, FeatureDefinition]
    operations: dict[str, OperationDefinition]
    relationships: dict[str, RelationshipDefinition]
    constraints: dict[str, ConstraintDefinition]
    materials: dict[str, MaterialDefinition]
    
    def get_feature(self, feature_id: str) -> FeatureDefinition: ...
    def get_features_by_category(self, category: str) -> list[FeatureDefinition]: ...
    def is_valid_feature_id(self, feature_id: str) -> bool: ...
    def get_operation_for_feature(self, feature_id: str) -> str: ...
```

---

## Implementation-Driven Ontology Rule

**The ontology must not become a research project in itself.**

The ontology adds a new term ONLY when one of the following is true:
1. A validation rule needs to reference it
2. A benchmark task needs to classify it
3. A synthetic generator needs to place it
4. A real DXF in the test corpus contains it

**Adding a term because it theoretically exists in manufacturing is insufficient justification.** The term must be needed by running code.

Current v0.1.0 ontology coverage is intentionally narrow:
- 14 feature types (panel CNC focus only)
- 4 operation types
- 10 relationship types

This is enough. The ontology is frozen at v0.1.0 for the hackathon. Refinement happens post-hackathon, driven by what the system actually needs during BENCH-001 evaluation.

---

## Versioning and Governance

- Version bump required when: feature ID renamed, definition fundamentally changed, detection criteria changed
- Minor version bump for: new features added, sources added, descriptions clarified
- Ontology is frozen during hackathon execution (changes after v0.1.0 finalized)
- Future changes tracked in `data/ontology/CHANGELOG.md`
