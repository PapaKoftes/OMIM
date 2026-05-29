# Realism Constraints

Version: v0.1.0  
Section: 07_SYNTHETIC_GENERATION  

See also: [[06_REAL_WORLD_GROUNDING/Cabinet_Standards]], [[06_REAL_WORLD_GROUNDING/Hardware_System_References]], [[07_SYNTHETIC_GENERATION/Constraint_Grammar]]

---

## Purpose

Documents how synthetic generation is grounded in real-world manufacturing practice. Each realism constraint traces to a source in 06_REAL_WORLD_GROUNDING. This file bridges the abstract constraint grammar to physical reality.

---

## What Makes Synthetic Data "Realistic"

Realistic synthetic data means: a CNC operator seeing the generated DXF would recognize it as a plausible cabinet panel, not as random geometry.

Failures of realism (and their consequences for ML models):
- Random hole sizes → model learns to reject anything unusual, missing domain patterns
- Uniform dimension distribution → model overtunes to rare dimensions
- Missing hardware-specific holes → model never learns hinge cup or shelf pin patterns
- No edge clearance respect → model sees edge violations as normal

---

## Realism Constraint R-001: Hinge Cup Geometry

**Source**: [[06_REAL_WORLD_GROUNDING/Hardware_System_References]] — Blum CLIP top  
**Constraint**: HINGE_CUP_HOLE must always have diameter = 35mm ± 0.5mm  
**Why**: No manufacturer produces a non-35mm hinge cup hole. Random diameters here would produce impossible hardware configurations.

```python
# Correct: fixed hardware geometry
hinge_cup_radius = 17.5  # always; never sampled

# Forbidden: random hinge cup size
hinge_cup_radius = rng.uniform(15, 20)  # NEVER
```

---

## Realism Constraint R-002: Shelf Pin Grid

**Source**: [[06_REAL_WORLD_GROUNDING/Cabinet_Standards]] — European 32mm system  
**Constraint**: SHELF_PIN_HOLE groups must form 32mm-spaced collinear arrays  
**Why**: A real side panel has shelf pins on a grid, not scattered. Scattered 5mm holes are not a real manufacturing pattern.

```python
# Correct: grid-aligned generation
positions = [37.0 + i * 32.0 for i in range(count)]

# Forbidden: random shelf pin positions
positions = [rng.uniform(37, height-37) for _ in range(count)]  # NEVER
```

---

## Realism Constraint R-003: Panel Thickness

**Source**: [[06_REAL_WORLD_GROUNDING/Cabinet_Standards]] — EN 309  
**Constraint**: Panel thickness must be one of the EN 309 standard values  
**Why**: Random thicknesses don't correspond to any purchasable sheet material.

```python
VALID_THICKNESSES = [12.0, 15.0, 16.0, 18.0, 22.0, 25.0]
thickness = rng.choice(VALID_THICKNESSES, p=[0.05, 0.10, 0.15, 0.55, 0.10, 0.05])
```

---

## Realism Constraint R-004: Panel Type Coherence

**Source**: [[06_REAL_WORLD_GROUNDING/Panel_Dimension_Standards]] — component roles  
**Constraint**: Feature sets must be consistent with the panel's declared type  
**Why**: Door panels don't have shelf pin holes; back panels don't have hinge cups.

```python
PANEL_TYPE_ALLOWED_FEATURES = {
    "side_panel": ["SHELF_PIN_HOLE", "HINGE_CUP_HOLE", "DOWEL_HOLE", "CONFIRMAT_HOLE", "THROUGH_HOLE"],
    "door":       ["HINGE_CUP_HOLE", "THROUGH_HOLE"],
    "shelf":      ["THROUGH_HOLE", "DOWEL_HOLE"],
    "back_panel": ["THROUGH_HOLE"],
    "bottom_top": ["DOWEL_HOLE", "CONFIRMAT_HOLE", "THROUGH_HOLE"],
    "generic":    ["ALL"],
}
```

---

## Realism Constraint R-005: Dimension Realism

**Source**: [[06_REAL_WORLD_GROUNDING/Panel_Dimension_Standards]] — standard cabinet dimensions  
**Constraint**: Panel dimensions follow realistic cabinet component size distributions  
**Why**: Uniform random dimensions would generate 137mm × 1847mm panels that correspond to no real furniture component.

```python
# Side panels: realistic height = typical cabinet body heights
SIDE_PANEL_HEIGHTS = [720, 600, 900, 1980, 2100]
# Doors: realistic heights match opening heights
DOOR_HEIGHTS = [715, 595, 895, 1975, 2095]  # = cabinet height minus reveals
```

---

## Realism Constraint R-006: Tool Diameter Alignment

**Source**: [[06_REAL_WORLD_GROUNDING/Tooling_Catalog_References]] — Leuco/Leitz standard diameters  
**Constraint**: Routing contour sizes should be multiples of common tool diameters (6mm, 8mm, 10mm)  
**Why**: Pocket widths that are non-multiples of tool diameters don't correspond to clean routing passes.

This is a **soft constraint** — realistic but not strictly required for valid geometry. Applied probabilistically:

```python
if rng.random() < 0.70:  # 70% of pockets use tool-diameter-aligned widths
    pocket_width = rng.choice([7.2, 8.0, 9.6, 12.0, 14.4]) # multiples of 6mm tool
```

---

## Realism Constraint R-007: Edge Clearance Distribution

**Source**: [[06_REAL_WORLD_GROUNDING/Manufacturing_Conventions]] — shop practice  
**Constraint**: Valid samples must have edge clearance drawn from realistic distribution  
**Why**: Real panels don't have holes exactly at 8.0001mm from the edge every time.

```python
# Valid samples: edge clearance drawn from realistic distribution
edge_clearance = rng.normal(loc=20.0, scale=8.0)  # mean 20mm, std 8mm
edge_clearance = max(8.5, edge_clearance)  # clip to generation margin
```

---

## Realism Constraint R-008: Confirmat Hole Pairing

**Source**: [[06_REAL_WORLD_GROUNDING/Hardware_System_References]] — Häfele Confirmat  
**Constraint**: Confirmat holes should appear in pairs at joint positions  
**Why**: Confirmat screws connect two panels; they appear in pairs near edges.

```python
# Generate Confirmat holes in pairs
if panel_type in ("bottom_top", "generic"):
    pair_positions = rng.integers(2, 4)  # 1-3 pairs per joint edge
    for _ in range(pair_positions):
        x = rng.uniform(15.0, panel.width - 15.0)
        y_offset = rng.choice([8.0, 9.0, 10.0])  # edge of panel being joined
        # Two 7mm circles: one through + one pilot at same x, different y
```

---

## Realism Check: Manual Validation Protocol

Before each major version of the synthetic dataset, a manufacturing domain expert should review:

1. 20 random valid samples: "Do these look like real cabinet panels?"
2. 10 random invalid samples: "Are these violations plausible real-world errors?"
3. Feature distribution histogram: "Does the relative frequency match industry?"

Results of this review are recorded in [[09_BENCHMARKS/Benchmark_Reproducibility]].
