# Geometric Validation (Layer 1)

Version: v0.1.0  
Section: 05_VALIDATION  

See also: [[05_VALIDATION/Rule_Engine]], [[05_VALIDATION/Rule_Provenance]], [[03_INTERFACES/Validation_Interface]]

---

## Scope Disclaimer

**OMIM v0.1 validation is a geometric manufacturability approximation.** It is NOT production manufacturability authority.

Real manufacturability also depends on fixturing, tool deflection, machine rigidity, material behavior, operation ordering, feeds and speeds, and coolant/chip evacuation. **OMIM validates none of these.** The correct framing:

> "OMIM provides geometric manufacturability approximation for panel CNC workflows, checking programmed rules derived from industry standards and shop practices. It is not a simulation-based or physics-based manufacturability analysis."

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
```

**Layer 3** is NOT part of the validation engine. It lives in the Semantic Layer and is clearly labeled as probabilistic.

---

## Purpose

Layer 1 validates geometric integrity of the ManufacturingGeometryGraph. All Layer 1 rules are `rule_type: "geometric"` with `confidence_ceiling: 1.0`. These are mathematical facts, not heuristics.

**Layer 1 must pass before Layer 2 runs.**

---

## GEO-001: Open Contour Detection

```yaml
rule_id: "GEO-001"
name: "Open Contour Detection"
layer: 1
rule_type: "geometric"
severity: "ERROR"
applies_to: ["LWPOLYLINE", "ARC", "SPLINE"]
parameters:
  closure_tolerance_mm: 0.01
source: "Geometric mathematics"
confidence_ceiling: 1.0
```

**Logic**: For each LWPOLYLINE, check that the Euclidean distance between the first and last vertex is ≤ 0.01mm. Closed flag in DXF is insufficient — verify coordinate closure.

```python
def check_open_contour(rule, mgg, constraints):
    results = []
    for node in mgg.query().get_by_type(["LWPOLYLINE", "ARC", "SPLINE"]):
        coords = node.coordinates
        if len(coords) < 2:
            continue
        gap = distance(coords[0], coords[-1])
        if gap > rule.parameters["closure_tolerance_mm"]:
            results.append(RuleResult(
                rule_id="GEO-001",
                passed=False,
                severity="ERROR",
                message=f"Open contour: gap={gap:.4f}mm > {rule.parameters['closure_tolerance_mm']}mm",
                affected_node_ids=[node.node_id],
                measured_value=gap,
                threshold_value=rule.parameters["closure_tolerance_mm"]
            ))
    return results if results else [RuleResult(rule_id="GEO-001", passed=True, severity="PASS", ...)]
```

---

## GEO-002: Self-Intersection Detection

```yaml
rule_id: "GEO-002"
name: "Self-Intersection Detection"
layer: 1
rule_type: "geometric"
severity: "ERROR"
applies_to: ["LWPOLYLINE", "SPLINE"]
parameters: {}
source: "Shapely is_simple property"
confidence_ceiling: 1.0
```

**Logic**: Use `shapely.geometry.LinearRing(coords).is_simple`. A self-intersecting contour cannot be validly machined — the tool path is undefined.

```python
from shapely.geometry import LinearRing

def check_self_intersection(rule, mgg, constraints):
    for node in mgg.query().get_by_type(["LWPOLYLINE"]):
        ring = LinearRing(node.coordinates)
        if not ring.is_simple:
            # flag as ERROR
```

---

## GEO-003: Degenerate Geometry Detection

```yaml
rule_id: "GEO-003"
name: "Degenerate Geometry Detection"
layer: 1
rule_type: "geometric"
severity: "ERROR"
applies_to: ["CIRCLE", "LWPOLYLINE", "LINE", "ARC"]
parameters:
  min_radius_mm: 0.001
  min_length_mm: 0.001
source: "Geometric mathematics"
confidence_ceiling: 1.0
```

**Logic**: Circles with radius ≤ 0.001mm, lines with length ≤ 0.001mm, and polygons with area ≤ 0.001mm² are degenerate. These represent data errors or noise.

---

## GEO-004: Coordinate Range Validation

```yaml
rule_id: "GEO-004"
name: "Coordinate Range Validation"
layer: 1
rule_type: "geometric"
severity: "ERROR"
applies_to: ["CIRCLE", "LWPOLYLINE", "LINE", "ARC", "SPLINE"]
parameters:
  max_dimension_mm: 5000
  min_coordinate_mm: -100
source: "Domain constraint; nesting table limits"
confidence_ceiling: 1.0
```

**Logic**: All coordinates must fall within [-100mm, 5000mm] on both axes. Negative coordinates beyond -100mm indicate a misaligned DXF origin, not a valid manufacturing geometry. Upper bound matches maximum CNC table dimension.

---

## GEO-005: Contour Orientation

```yaml
rule_id: "GEO-005"
name: "Contour Orientation"
layer: 1
rule_type: "geometric"
severity: "WARNING"
applies_to: ["LWPOLYLINE", "closed_contours"]
parameters: {}
source: "CNC convention for climb vs. conventional milling direction"
confidence_ceiling: 1.0
```

**Logic**: Outer profile contours should be counter-clockwise (CCW); internal contours (holes, pockets) should be clockwise (CW). Use `Shapely: Polygon.exterior.is_ccw` for outer contours; check interior rings separately.

**Note**: Some CAD software exports reversed orientation. This is WARNING (not ERROR) because the parser can normalize orientation during import. A reversed-orientation contour is still geometrically valid — only the CNC direction convention is wrong.

```python
from shapely.geometry import Polygon

def check_contour_orientation(rule, mgg, constraints):
    for node in mgg.query().get_outer_contours():
        polygon = Polygon(node.coordinates)
        if not polygon.exterior.is_ccw:
            # flag as WARNING: outer contour is CW, expected CCW
    
    for node in mgg.query().get_interior_contours():
        polygon = Polygon(node.coordinates)
        if polygon.exterior.is_ccw:
            # flag as WARNING: interior contour is CCW, expected CW
```

---

## GEO-006: Duplicate Geometry Detection

```yaml
rule_id: "GEO-006"
name: "Duplicate Geometry Detection"
layer: 1
rule_type: "geometric"
severity: "WARNING"
applies_to: ["CIRCLE", "LWPOLYLINE"]
parameters:
  position_tolerance_mm: 0.1
  size_tolerance_ratio: 0.01
source: "DXF authoring error pattern"
confidence_ceiling: 1.0
```

**Logic**: Two circles are duplicates if their centers are within 0.1mm and radii within 1%. Two polylines are duplicates if their bounding boxes match within tolerance. Duplicates are WARNING (not ERROR) — they may represent intentional overlapping geometry in some workflows, but are almost always authoring errors.

```python
def check_duplicate_geometry(rule, mgg, constraints):
    circles = mgg.query().get_by_entity_type("CIRCLE")
    for i, a in enumerate(circles):
        for b in circles[i+1:]:
            dist = distance(a.centroid, b.centroid)
            radius_diff = abs(a.radius_mm - b.radius_mm) / max(a.radius_mm, b.radius_mm)
            if dist <= rule.parameters["position_tolerance_mm"] and radius_diff <= rule.parameters["size_tolerance_ratio"]:
                # flag as WARNING
```

**Source rationale**: Duplicate geometry on cutting layers causes double-cutting, which increases tool wear and can damage the workpiece. Almost always an authoring error (copy-paste without removing original).

---

## GEO-007: Geometry Within Panel Bounds

```yaml
rule_id: "GEO-007"
name: "Geometry Within Panel Bounds"
layer: 1
rule_type: "geometric"
severity: "ERROR"
applies_to: ["all geometry within a panel context"]
parameters: {}
source: "Physical requirement: cannot machine outside stock material"
confidence_ceiling: 1.0
```

**Logic**: All features must lie within or on the panel boundary. Use `shapely: panel_polygon.contains(feature_geometry) or panel_polygon.touches(feature_geometry)`. Features partially or fully outside the panel boundary cannot be machined.

```python
from shapely.geometry import Point, Polygon

def check_geometry_within_bounds(rule, mgg, constraints):
    panel_boundary = mgg.query().get_panel_boundary()
    panel_polygon = Polygon(panel_boundary.coordinates)
    
    for node in mgg.query().get_interior_nodes():
        if hasattr(node, 'radius_mm'):
            feature_geom = Point(node.centroid).buffer(node.radius_mm)
        else:
            feature_geom = Polygon(node.coordinates)
        
        if not panel_polygon.contains(feature_geom) and not panel_polygon.touches(feature_geom):
            # flag as ERROR: geometry extends outside panel boundary
```

---

## GEO-008: Zero-Area Closed Contour

```yaml
rule_id: "GEO-008"
name: "Zero-Area Closed Contour"
layer: 1
rule_type: "geometric"
severity: "ERROR"
applies_to: ["LWPOLYLINE"]
parameters:
  min_area_mm2: 1.0
source: "Geometric mathematics"
confidence_ceiling: 1.0
```

**Logic**: A closed LWPOLYLINE with area < 1mm² cannot represent a manufacturable feature. This catches collinear "closed" contours where all points fall on a line.

---

## Layer 1 Summary

| Rule | Name | Severity | Key Check |
|------|------|---------|-----------|
| GEO-001 | Open Contour Detection | ERROR | endpoint gap ≤ 0.01mm |
| GEO-002 | Self-Intersection Detection | ERROR | Shapely is_simple |
| GEO-003 | Degenerate Geometry | ERROR | min_radius=0.001mm, min_length=0.001mm |
| GEO-004 | Coordinate Range | ERROR | within [-100mm, 5000mm] |
| GEO-005 | Contour Orientation | WARNING | outer=CCW, inner=CW |
| GEO-006 | Duplicate Geometry | WARNING | position_tol=0.1mm |
| GEO-007 | Geometry Within Panel Bounds | ERROR | Shapely contains or touches |
| GEO-008 | Zero-Area Closed Contour | ERROR | area ≥ 1.0mm² |

**Pass condition**: `layer1_passed = True` when zero ERRORs in GEO-001 through GEO-008. Warnings do not block Layer 2.

---

## Dual Use in Dataset Generation

When generating synthetic datasets, Layer 1 serves two purposes:

1. **Quality gate**: Valid samples must pass all ERROR rules
2. **Label generator**: Invalid samples have known violations (injected, then verified by the engine)

The validation engine is **both** a quality control mechanism and a ground truth label source. The provenance system tracks which role it played for each record.
