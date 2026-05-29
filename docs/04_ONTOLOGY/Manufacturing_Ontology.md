# Manufacturing Ontology

Version: v0.1.0  
Domain: Panel Manufacturing (2.5D CNC)  
**Status: FROZEN for hackathon**

Section: 04_ONTOLOGY  

See also: [[04_ONTOLOGY/Feature_Taxonomy]], [[04_ONTOLOGY/Operation_Taxonomy]], [[04_ONTOLOGY/Constraint_Taxonomy]]

---

## Purpose

Defines the complete manufacturing vocabulary for OMIM v0.1.0. Every semantic label used anywhere in the system is defined here.

---

## Implementation-Driven Rule

**The ontology adds a new term ONLY when one of the following is true:**
1. A validation rule needs to reference it
2. A benchmark task needs to classify it
3. A synthetic generator needs to place it
4. A real DXF in the test corpus contains it

Adding a term because it theoretically exists in manufacturing is insufficient. The term must be needed by running code.

---

## Coverage Summary (v0.1.0)

| Category | Count | Locked for Hackathon |
|----------|-------|---------------------|
| Feature types | 14 | Yes |
| Operation types | 4 | Yes |
| Relationship types | 10 | Yes |
| Constraint types | 10 | Yes |
| Material types | 5 | Yes |

---

## File Structure

```
data/ontology/
├── features.yaml         # All feature types (see Feature_Taxonomy.md)
├── operations.yaml       # All operation types (see Operation_Taxonomy.md)
├── relationships.yaml    # All relationship types
├── constraints.yaml      # All constraint types + default values
├── materials.yaml        # Panel material definitions
└── VERSION               # "v0.1.0"
```

---

## YAML Feature Schema

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
      - "Blum shelf pin system"
      - "DIN 68xxx furniture hardware series"
    operation: DRILLING
    parameters:
      diameter_mm: 5.0
      depth_mm: "12-15 (typically not through)"
      tolerance_mm: 0.1
```

---

## Python Loader Interface

```python
# omim/ontology/loader.py

class OntologyLoader:
    def load(self, ontology_dir: str) -> Ontology: ...

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
    def get_rule_feature_references(self) -> dict[str, list[str]]:
        """
        Returns a mapping of rule_id → list of feature_class IDs that the rule
        applies to (from the rule's `applies_to` field in its YAML).

        Used by check_ontology_consistency() to verify that every feature class
        referenced in rule definitions exists in the loaded ontology.

        Example return value:
            {
                "MFG-005": ["SHELF_PIN_HOLE"],
                "MFG-006": ["HINGE_CUP_HOLE"],
                "MFG-010": ["CONFIRMAT_HOLE"],
                "MFG-011": ["THROUGH_HOLE", "SHELF_PIN_HOLE", "HINGE_CUP_HOLE", "DOWEL_HOLE"],
            }
        Only rules with feature-specific applicability are included.
        Rules with `applies_to: ["all"]` are not included.
        """
        ...
```

---

## Versioning and Governance

- Version bump required when: feature ID renamed, definition fundamentally changed, detection criteria changed
- Minor version bump for: new features added, sources added, descriptions clarified
- Ontology is **frozen** during hackathon execution
- Future changes tracked in `data/ontology/CHANGELOG.md`

---

## Relationship Types

| Relationship | Direction | Description |
|-------------|-----------|-------------|
| CONTAINS | panel → feature | Panel contains this feature |
| DEPENDS_ON | operation_A → operation_B | Op A must execute before B |
| CONFLICTS_WITH | feature_A ↔ feature_B | Features overlap or violate spacing |
| ADJACENT_TO | feature_A ↔ feature_B | Features geometrically near each other |
| REQUIRES_TOOLING | feature → tool_spec | Feature requires specific tool |
| SAME_GROUP | feature_A ↔ feature_B | Features belong to same logical group |
| SAME_ROW | hole_A ↔ hole_B | Holes in same horizontal row |
| SAME_COLUMN | hole_A ↔ hole_B | Holes in same vertical column |
| ENABLES | feature_A → operation_B | Feature presence enables/suggests operation |
| PRODUCED_BY | feature → operation | Feature is produced by this operation |

---

## Material Definitions

```yaml
materials:
  MDF:
    name: Medium Density Fiberboard
    standard: EN 622-5
    typical_thickness_mm: [9, 12, 15, 18, 22, 25]
    notes: "Homogeneous, no grain direction."
  PARTICLEBOARD:
    name: Particleboard
    standard: EN 309 / EN 312
    typical_thickness_mm: [9, 12, 15, 18, 22, 25]
  PLYWOOD:
    name: Plywood
    standard: EN 636
    typical_thickness_mm: [6, 9, 12, 15, 18, 21, 24]
    notes: "Has grain direction."
  MELAMINE_COATED_PARTICLEBOARD:
    name: Melamine coated particleboard
    notes: "Edge banding typically required post-cut."
  HDF:
    name: High Density Fiberboard
    standard: EN 622-5
    typical_thickness_mm: [2, 3, 4, 6]
    notes: "Thin back panels, drawer bottoms."
```
