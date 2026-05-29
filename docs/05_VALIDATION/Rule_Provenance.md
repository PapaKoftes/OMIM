# Rule Provenance

Version: v0.1.0  
Section: 05_VALIDATION  

See also: [[05_VALIDATION/Geometric_Validation]], [[05_VALIDATION/Manufacturability_Validation]], [[08_PROVENANCE_AND_CONFIDENCE/Provenance_System]]

---

## Purpose

Documents the authoritative source for each validation rule. Rule provenance is distinct from data provenance — it records where the rule itself comes from, not where the geometry came from.

---

## Layer 1 Rule Sources

| Rule | Source Type | Citation | Trust Level |
|------|------------|---------|------------|
| GEO-001 Open Contour | Geometric mathematics | Euclidean geometry: closed contour iff start==end | Absolute |
| GEO-002 Self-Intersection | Computational geometry | Shapely `LinearRing.is_simple`; O'Rourke, *Computational Geometry in C* | Absolute |
| GEO-003 Degenerate Geometry | Geometric mathematics | Area/length = 0 is undefined geometry | Absolute |
| GEO-004 Coordinate Range | Domain constraint | CNC nesting table physical limits (3600×2100mm standard table) | High |
| GEO-005 Contour Orientation | Computational geometry | Outer contours CCW, inner contours CW (Shapely exterior.is_ccw) | High |
| GEO-006 Duplicate Geometry | DXF authoring practice | Common ezdxf authoring error; tolerance empirically set at 0.01mm | High |
| GEO-007 Geometry Within Panel Bounds | Geometric containment | Shapely `contains()`; features must be within declared panel boundary | Absolute |
| GEO-008 Zero-Area Contour | Geometric mathematics | Collinear polygon has zero area (Shapely); degenerate entity | Absolute |

---

## Layer 2 Rule Sources

| Rule | Source Type | Citation | Trust Level |
|------|------------|---------|------------|
| MFG-001 Edge Clearance | Shop convention | 8mm: empirical MDF tear-out threshold; confirmed in multiple CNC cabinet shops | Medium |
| MFG-002 Feature Spacing | Material heuristic | 3mm wall: MDF/particleboard minimum for structural integrity; absolute formulation preferred for small holes | Medium |
| MFG-003 Tool Radius Corner Feasibility | Machine heuristic | Internal corner radius ≥ tool_radius (3mm for 6mm tool); CNC routing geometry constraint | Low-Medium |
| MFG-004 Pocket Width | Machine heuristic | 1.2× tool diameter: 20% clearance for full-width cut; standard CNC router practice | Low-Medium |
| MFG-005 Shelf Pin Grid | Standards-derived | DIN 68xxx; European 32mm system (Rasterbohrsystem) since 1950s | High |
| MFG-006 Hinge Cup Distance | Hardware spec | Blum CLIP top hinge: 22.5mm from edge, 35mm cup; Blum motion technology catalog, item 70.1900.AC | High |
| MFG-007 Blind Depth | Material heuristic | 0.75×thickness: floor must be ≥ 0.25×thickness for structural integrity; shop practice | Low-Medium |
| MFG-008 Feature Density | Machine heuristic | 10 features/100cm² empirically derived from observed panel complexity limits | Low |
| MFG-009 Minimum Panel Dimensions | Domain constraint | 100×100mm: practical lower bound for CNC panel clamping (shop convention) | Medium |
| MFG-010 Confirmat Screw Pair Positioning | Hardware spec | Confirmat head is asymmetric; pairing requires 32mm system alignment; multi-panel assembly constraint | High |
| MFG-011 Drill Diameter Range | Tooling catalog | Min 3mm: practical drill bit lower bound. Max 40mm: above this use routing (Leuco drilling catalog rev. 2022) | High |
| MFG-012 No Feature on Sheet Edge | Domain constraint | Features at boundary = zero wall thickness; structural failure; shop convention | Medium |

**Rule Non-Universality**: Rules of type `shop_convention`, `material_heuristic`, and `machine_heuristic` are scoped to the declared `domain_applicability` and are NOT universal manufacturing rules. See each rule's YAML for its domain_applicability field.

---

## Rule Governance

### Adding a New Rule

1. Document the source (standard, catalog, shop practice, measurement)
2. Assign a `rule_type` from the taxonomy
3. Set `confidence_ceiling` per the rule type table
4. Add to appropriate YAML file
5. Register handler in `RuleEngine._rule_handlers`
6. Write acceptance test
7. Update this file with source citation

### Modifying an Existing Rule

Threshold changes require:
- Evidence that the new value is more accurate (measurement data or updated standard reference)
- Version bump in `ruleset_version`
- Migration note in Versioning_Policy.md

### Removing a Rule

Rules are not removed — they are set to `enabled: false`. This preserves the rule ID for historical results compatibility.

---

## Confidence Ceiling Reference

| Rule Type | Max Confidence | Rationale |
|-----------|--------------|---------|
| `geometric` | 1.0 | Mathematical fact; not empirical |
| `standards_derived` | 0.95 | ISO/DIN standards have edge cases |
| `hardware_spec` | 0.90 | Hardware specs are precise but application varies |
| `shop_convention` | 0.75 | Conventions vary across shops and regions |
| `material_heuristic` | 0.70 | Empirically derived; material variation |
| `machine_heuristic` | 0.65 | Machine-dependent; lowest confidence |

---

## RuleResult Provenance Record

Every `RuleResult` includes a `ProvenanceRecord` with:

```python
RuleResult.provenance = ProvenanceRecord(
    inference_method=InferenceMethod.DETERMINISTIC,   # all validation is deterministic
    confidence=rule.confidence_ceiling,               # from rule definition
    evidence=[EvidenceItem(
        evidence_type=EvidenceType.GEOMETRIC_MEASUREMENT,
        description=f"Measured: {measured_value} vs threshold: {threshold_value}",
        satisfied=result.passed
    )],
    source_entity_ids=[affected_node.entity_id for affected_node in affected_nodes],
    ruleset_version="0.1.0"
)
```

Validation confidence is always `InferenceMethod.DETERMINISTIC` — rule pass/fail is computed, not inferred.
