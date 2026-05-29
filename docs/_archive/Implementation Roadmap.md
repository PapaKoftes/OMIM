# Implementation Roadmap

This document links the vision to the execution. For the time-boxed hackathon execution plan, see [[Execution Roadmap]]. For the full architectural vision, see [[Full System Architecture]].

---

## Phase Structure Overview

```
Phase 0 (Pre-Hackathon)   → Environment, schema drafts, DXF samples
Phase 1 (Hours 0-9)       → Ontology + DXF Parser
Phase 2 (Hours 9-17)      → MGG Builder + Validation Engine
Phase 3 (Hours 17-23)     → Provenance System + Semantic Layer
Phase 4 (Hours 23-29)     → Synthetic Dataset Generator + Benchmarks
Phase 5 (Hours 29-36)     → ML Integration + Demo
Phase 6 (Hours 36-40)     → Documentation + Dataset Release
```

---

## Implementation Principles

Every piece of code written during the hackathon must follow these rules:

### Rule 1: Schema First
Write the Pydantic model BEFORE writing the implementation.
If you cannot define the input/output types, you don't understand the subsystem yet.

### Rule 2: Accept Tests Before Code
Write acceptance tests BEFORE writing implementation.
Running `pytest` and seeing red is the starting condition; green is done.

### Rule 3: Commit at Every Checkpoint
```
git tag v0-skeleton
git tag v0-ontology
git tag v0-parser
git tag v0-graph
git tag v0-validation
git tag v0-provenance
git tag v0-semantic
git tag v0-synthetic
git tag v0-benchmarks
git tag v0-ml
git tag v0-demo
git tag v0.1.0-hackathon
```

### Rule 4: Every Module Stands Alone
At any checkpoint, the code up to that point should be independently useful.
A parser without a graph layer should still export `RawGeometry` objects.
A graph builder without ML should still serialize MGG to JSON.

### Rule 5: No Premature Abstraction
If you have one concrete use case, implement it directly.
Do not build extensibility mechanisms until you have two concrete use cases.

---

## Build Order (Critical Path)

```
[Pydantic schemas] → must be done first
        ↓
[Ontology YAML + loader] → vocabulary before everything
        ↓
[DXF Parser] → raw geometry extraction
        ↓
[MGG Builder] → geometry → graph
        ↓
[Provenance System] → cross-cutting (inject in parallel with below)
        ↓
[Validation Engine (Layer 1)] → geometry validity
        ↓
[Validation Engine (Layer 2)] → manufacturing rules
        ↓
[Semantic Layer] → feature classification
        ↓
[Synthetic Dataset Generator] → uses all above
        ↓
[Benchmark Suite] → consumes dataset
        ↓
[ML Integration] → optional, consumes dataset
        ↓
[Demo] → thin integration layer, uses all above
```

---

## Module-by-Module Implementation Guide

### Module 1: Schemas (First 30 Minutes)

Write these Pydantic models first, before any other code:

```python
# Priority order:
# 1. ProvenanceRecord (everything else embeds this)
# 2. EvidenceItem
# 3. RawGeometry / RawEntity
# 4. GeometryNode / FeatureNode / OperationNode
# 5. ManufacturingGeometryGraph (skeleton)
# 6. ValidationReport / RuleResult
# 7. SemanticAnnotation
# 8. DatasetSample
```

This step is fast (30 minutes) but is the most important investment. All subsequent modules are implementations of these contracts.

### Module 2: Ontology Loader

```python
# Minimal implementation:
from pathlib import Path
import yaml
from pydantic import BaseModel

class FeatureDefinition(BaseModel):
    id: str
    label: str
    category: str
    description: str
    sources: list[str]
    
class Ontology(BaseModel):
    version: str
    features: dict[str, FeatureDefinition]
    # ... operations, relationships, constraints
    
def load_ontology(ontology_dir: str) -> Ontology:
    features_raw = yaml.safe_load(open(f"{ontology_dir}/features.yaml"))
    # ... load and validate
    return Ontology(...)
```

### Module 3: DXF Parser

```python
# Minimal implementation skeleton:
import ezdxf

def parse_dxf(filepath: str) -> RawGeometry:
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()
    
    entities = []
    for entity in msp:
        if entity.dxftype() == "CIRCLE":
            entities.append(extract_circle(entity))
        elif entity.dxftype() in ("LWPOLYLINE", "POLYLINE"):
            entities.append(extract_polyline(entity))
        elif entity.dxftype() == "ARC":
            entities.append(extract_arc(entity))
        elif entity.dxftype() == "LINE":
            entities.append(extract_line(entity))
        # Skip: TEXT, DIMENSION, HATCH, INSERT
    
    return RawGeometry(
        source_file=filepath,
        source_hash=compute_file_hash(filepath),
        units=detect_units(doc),
        entities=entities,
        ...
    )
```

### Module 4: MGG Builder (Core Logic)

```python
# Start with the simplest possible graph:
# 1. One GeometryNode per RawEntity
# 2. CONTAINS edges based on Shapely containment
# 3. ADJACENT_TO edges based on distance threshold

def build_mgg(geometry: RawGeometry, ontology: Ontology) -> ManufacturingGeometryGraph:
    mgg = ManufacturingGeometryGraph()
    
    # Pass 1: Create geometry nodes
    for entity in geometry.entities:
        node = entity_to_geometry_node(entity)
        mgg.add_geometry_node(node)
    
    # Pass 2: Detect spatial relationships
    nodes = mgg.query().get_geometry_nodes()
    for i, node_a in enumerate(nodes):
        for node_b in nodes[i+1:]:
            relationship = detect_relationship(node_a, node_b)
            if relationship:
                mgg.add_edge(relationship)
    
    return mgg
```

### Module 5: Validation Engine

```python
# Minimal implementation: hard-code 3 rules first, externalize to YAML after

def validate_layer1(mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
    results = []
    for node in mgg.query().get_geometry_nodes():
        if node.geometry_type == "polyline" and node.is_closed:
            # GEO-001: contour closure
            results.append(check_contour_closure(node))
    return results

def validate_layer2(mgg: ManufacturingGeometryGraph) -> list[RuleResult]:
    results = []
    circles = [n for n in mgg.query().get_geometry_nodes() if n.geometry_type == "circle"]
    
    # MFG-001: edge clearance
    panel_boundary = get_panel_boundary(mgg)
    for circle in circles:
        results.append(check_edge_clearance(circle, panel_boundary, threshold_mm=8.0))
    
    # MFG-002: drill spacing
    for i, c1 in enumerate(circles):
        for c2 in circles[i+1:]:
            results.append(check_drill_spacing(c1, c2, min_wall_mm=3.0))
    
    return results
```

### Module 6: Semantic Layer (Minimum Viable)

```python
# Minimum viable: hole diameter-based classification only

def classify_features(mgg: ManufacturingGeometryGraph, ontology: Ontology) -> list[SemanticAnnotation]:
    annotations = []
    
    for node in mgg.query().get_geometry_nodes():
        if node.geometry_type == "circle":
            feature_class, confidence = classify_hole_by_diameter(node.diameter_mm)
            annotation = SemanticAnnotation(
                node_id=node.node_id,
                feature_class=feature_class,
                confidence=confidence,
                inference_method="heuristic",
                ...
            )
            annotations.append(annotation)
    
    return annotations

def classify_hole_by_diameter(diameter_mm: float) -> tuple[str, float]:
    """Simple diameter-based hole classification."""
    if 4.8 <= diameter_mm <= 5.2:
        return "SHELF_PIN_HOLE", 0.88
    elif 34.0 <= diameter_mm <= 36.0:
        return "HINGE_CUP_HOLE", 0.92
    elif 6.5 <= diameter_mm <= 7.5:
        return "CONFIRMAT_HOLE", 0.84
    elif 7.5 <= diameter_mm <= 10.5:
        return "DOWEL_HOLE", 0.75
    else:
        return "THROUGH_HOLE", 0.65
```

### Module 7: Synthetic Dataset Generator

```python
# Minimum viable: generate rectangular panels with random circles

import numpy as np
import ezdxf

def generate_simple_panel(seed: int, n_features: int = 5) -> PanelSpecification:
    rng = np.random.default_rng(seed)
    
    width = rng.uniform(300, 1200)
    height = rng.uniform(200, 800)
    
    features = []
    for i in range(n_features):
        feature_type = rng.choice(["SHELF_PIN_HOLE", "HINGE_CUP_HOLE", "THROUGH_HOLE"])
        diameter = get_standard_diameter(feature_type)
        
        # Place with edge clearance
        x = rng.uniform(20, width - 20)
        y = rng.uniform(20, height - 20)
        
        features.append(FeatureSpec(
            feature_type=feature_type,
            position_mm=[x, y],
            diameter_mm=diameter
        ))
    
    return PanelSpecification(width_mm=width, height_mm=height, features=features, seed=seed)
```

---

## Testing Strategy

### Mandatory Test Fixtures

These DXF files MUST exist in `data/test_dxfs/` before the hackathon starts. Create them manually in LibreCAD or FreeCAD in under 30 minutes each. They are the ground truth for all acceptance tests.

**Create or collect before Hour 0:**

```
data/test_dxfs/
├── valid/
│   ├── simple_panel_with_shelf_pins.dxf    # 600×400mm panel; 8× 5mm circles in 32mm column
│   ├── door_panel_with_hinges.dxf          # 200×700mm panel; 2× 35mm circles, 22.5mm from edge
│   ├── confirmat_panel.dxf                 # 400×400mm panel; 6× 7mm circles near edges
│   ├── panel_with_groove.dxf               # 800×400mm panel; 6mm groove 12mm from rear edge
│   └── complex_cabinet_side.dxf            # Full side panel: shelf pins + hinges + groove + Confirmats
├── invalid/
│   ├── hole_too_close_to_edge.dxf          # 5mm circle at (3, 50) — violates MFG-001
│   ├── holes_overlapping.dxf               # Two 10mm circles with centers 8mm apart — violates MFG-002
│   ├── open_contour.dxf                    # Panel outline with 1mm gap — violates GEO-001
│   └── pocket_too_narrow.dxf              # 5mm pocket with 6mm tool assumption — violates MFG-004
├── edge_cases/
│   ├── empty_panel.dxf                     # Valid outline, zero features — tests empty case
│   ├── units_in_inches.dxf                 # Same geometry, $INSUNITS=1 — tests unit normalization
│   └── malformed_no_closing_vertex.dxf     # LWPOLYLINE missing close flag — tests GEO-001 tolerance
└── expected_outputs/
    ├── simple_panel_with_shelf_pins.json   # Expected: 8× SHELF_PIN_HOLE, is_valid=true
    ├── door_panel_with_hinges.json         # Expected: 2× HINGE_CUP_HOLE, is_valid=true
    ├── hole_too_close_to_edge.json         # Expected: is_valid=false, MFG-001 fired
    └── ...
```

**Expected outputs format** (minimal — one file per fixture):

```json
{
  "fixture": "simple_panel_with_shelf_pins.dxf",
  "expected_is_valid": true,
  "expected_feature_classes": ["SHELF_PIN_HOLE", "PROFILE_CUT"],
  "expected_feature_count": 9,
  "expected_violations": [],
  "expected_warnings": []
}
```

**Fixture acceptance test rule**: Any change to the parser, graph builder, validation engine, or semantic layer that changes the output for any fixture without a deliberate version bump is a REGRESSION BUG.

```python
# tests/test_fixtures.py  — single most important test file
@pytest.mark.parametrize("fixture_name", [
    "simple_panel_with_shelf_pins",
    "door_panel_with_hinges",
    "hole_too_close_to_edge",
    "open_contour",
])
def test_fixture_expected_output(fixture_name):
    """Pipeline output must match expected output for all test fixtures."""
    dxf_path = f"data/test_dxfs/valid/{fixture_name}.dxf"
    expected = json.loads(open(f"data/test_dxfs/expected_outputs/{fixture_name}.json").read())
    
    result = analyze_dxf(dxf_path)
    
    assert result.validation.overall_valid == expected["expected_is_valid"]
    actual_classes = sorted(set(f.feature_class for f in result.annotations))
    assert actual_classes == sorted(set(expected["expected_feature_classes"]))
```

### Minimum Test Suite

```python
# tests/test_parser.py
def test_parser_circle_extraction():
    """Parser extracts circles from DXF with correct center and radius."""

def test_parser_handles_malformed_dxf():
    """Parser returns structured error on malformed DXF, not exception."""

# tests/test_graph.py
def test_mgg_roundtrip():
    """MGG serializes to JSON and deserializes back identically."""

def test_mgg_builds_from_geometry():
    """MGG builder creates nodes for all geometry entities."""

# tests/test_validation.py
def test_edge_clearance_violation_detected():
    """MFG-001: Circle too close to edge is flagged as ERROR."""

def test_valid_panel_passes_validation():
    """Panel with all valid geometry produces zero ERROR results."""

def test_validation_determinism():
    """Same input produces identical ValidationReport."""

# tests/test_semantic.py
def test_shelf_pin_hole_classification():
    """5mm circles classified as SHELF_PIN_HOLE with confidence > 0.8."""

def test_hinge_cup_classification():
    """35mm circles classified as HINGE_CUP_HOLE with confidence > 0.85."""

# tests/test_provenance.py
def test_provenance_roundtrip():
    """ProvenanceRecord serializes and deserializes without data loss."""

def test_every_feature_has_provenance():
    """All FeatureNodes in annotated MGG have non-null provenance."""
```

---

## Versioning System

Everything in OMIM is versioned. This is not overhead — it is what makes the provenance system work and what allows datasets and models to be reproducibly referenced.

### Version Registry

| Artifact | Version in v0 | Format | Where Stored |
|----------|--------------|--------|-------------|
| Ontology | v0.1.0 | SemVer | `data/ontology/VERSION` |
| MGG Schema | v0.1.0 | SemVer | `$schema` field in mgg.json |
| Rule Set | v0.1.0 | SemVer | `data/rules/panel_cnc_rules.yaml` header |
| Labels Schema | v0.1.0 | SemVer | `$schema` field in labels.json |
| Provenance Schema | v0.1.0 | SemVer | `$schema` field in provenance.json |
| Validation Schema | v0.1.0 | SemVer | `$schema` field in validation.json |
| Synthetic Dataset | omim-synthetic-v0.1.0 | named + SemVer | `dataset_metadata.json` |
| OMIM codebase | v0.1.0 | SemVer + git tag | `pyproject.toml`, git tags |

### Semantic Versioning Rules

```
v{major}.{minor}.{patch}

major: Breaking change (schema field removed/renamed, rule ID changed, ontology term removed)
minor: Additive change (new field added, new rule added, new ontology term)
patch: Fix/clarification (description change, source citation added, bug fix that doesn't change output)
```

### Version Increment Rules

| What Changed | Version Impact | Example |
|-------------|--------------|---------|
| Feature class ID renamed | ontology: major | `v0.1.0 → v0.2.0` |
| New feature class added | ontology: minor | `v0.1.0 → v0.1.1` |
| Rule threshold changed | ruleset: minor | `v0.1.0 → v0.1.1` |
| New rule added | ruleset: minor | `v0.1.0 → v0.1.1` |
| labels.json field renamed | labels schema: major | `v0.1.0 → v0.2.0` |
| New optional labels.json field | labels schema: minor | `v0.1.0 → v0.1.1` |

### Version Compatibility

Components are compatible iff they share the same major version:
- `omim-labels-v0.1.0` is compatible with `omim-labels-v0.1.7` (same major = 0)
- `omim-labels-v0.1.0` is NOT compatible with `omim-labels-v0.2.0`

Every output artifact MUST store the version of every component used:
```python
OMIM_VERSION = "v0.1.0"
ONTOLOGY_VERSION = "v0.1.0"  # loaded from data/ontology/VERSION
RULESET_VERSION = "v0.1.0"   # loaded from data/rules/panel_cnc_rules.yaml
LABELS_SCHEMA_VERSION = "v0.1.0"  # hardcoded in canonical schema
```

### Version Freeze for Hackathon

All versions are frozen at `v0.1.0` for the hackathon. No version increments during the 48-hour window. After the hackathon, post-hackathon work starts from `v0.2.0-dev`.

---

## Vertical Slice Priority Control

**This is the most important execution rule.** The project dies if horizontal layers are built before the vertical slice works end-to-end.

### What Is a Vertical Slice?

A vertical slice is a complete, working end-to-end path through the system — even if it handles only the simplest possible case.

**Minimum viable vertical slice** (target: Hour 13):
```
One DXF with one circle
  → Parse: extract one CIRCLE entity
  → MGG: one GeometryNode
  → Validate: MFG-001 fires (or passes)
  → Semantic: classify the circle (SHELF_PIN_HOLE or THROUGH_HOLE)
  → Export: labels.json with one feature
  → Test: pytest green
```

Once this works, EXPAND. Never build an entire horizontal layer that can't be tested end-to-end.

### Forbidden Build Patterns

```
FORBIDDEN: Complete entire parser before touching graph layer
FORBIDDEN: Complete entire validation engine before touching semantic layer
FORBIDDEN: Build perfect ontology YAML before writing first parser line
FORBIDDEN: Design full dataset schema before any data generates
FORBIDDEN: Write all unit tests before writing any implementation
```

### Allowed Build Pattern

```
Step 1: Stub all schemas (30 min) → can import without error
Step 2: Vertical slice for simplest case (4 hours) → end-to-end works on 1 DXF
Step 3: Expand parser (2 hours) → 10+ entity types
Step 4: Expand validation (2 hours) → 10+ rules
Step 5: Expand semantic layer (2 hours) → 6+ feature types
Step 6: Synthetic generation (4 hours) → 1000+ samples
Step 7: Everything else builds on this working pipeline
```

### The One Rule

> **If you cannot run the full pipeline end-to-end, you are not done with the current phase.**

No "I'll connect it later." No "the interface works in theory." Working = `python -m omim.cli input.dxf` produces output files.

---

## Open Source Integration: Use vs Build

| Component | Use Existing | Build New |
|-----------|-------------|-----------|
| DXF parsing | **ezdxf** — do not rewrite | — |
| 2D geometry ops | **Shapely** — do not rewrite | — |
| Graph data structure | **NetworkX** — do not rewrite | MGG wrapper class |
| GNN training | **PyTorch Geometric** — do not rewrite | Feature extractor, model arch |
| API framework | **FastAPI** — do not rewrite | Route handlers |
| DXF test files | **FreeCAD samples, GrabCAD** | 3-5 hand-crafted test panels |
| Manufacturing semantics | — | Ontology YAML (this is novel) |
| Manufacturability rules | Reference LinuxCNC/OpenCAMLib logic | Rule YAML + engine (this is novel) |
| Provenance system | — | Build (novel; no existing standard) |
| Dataset schema | — | Build (novel; nothing comparable exists) |
| Benchmarks | — | Build (novel; defining the tasks) |

**Core insight**: Everything below the semantic layer (parsing, geometry, graphs) is solved. Everything above the geometry layer (manufacturing meaning, rules, provenance, benchmarks) is what OMIM contributes. Build only the novel parts.

---

## Post-Hackathon Milestones

| Milestone | Target Date | Description |
|-----------|-------------|-------------|
| v0.1.0-hackathon | 2026-05-31 | Hackathon submission |
| v0.2.0 | ~4 weeks post | 10k+ synthetic samples; improved ML |
| v0.3.0 | ~8 weeks post | Expert review of ontology; real DXF testing |
| v0.4.0 | ~12 weeks post | HuggingFace dataset release |
| v1.0.0 | ~6 months post | Publication-ready benchmark; paper submission |
