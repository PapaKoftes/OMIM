# Panel Dimension Standards

Version: v0.1.0  
Section: 06_REAL_WORLD_GROUNDING  

See also: [[06_REAL_WORLD_GROUNDING/Cabinet_Standards]], [[04_ONTOLOGY/Constraint_Taxonomy]], [[05_VALIDATION/Manufacturability_Validation]]

---

## Purpose

Documents standard panel dimensions for modular cabinetry. Defines the realistic geometry space for synthetic generation and the bounds checked by MFG-008 (panel dimension limits).

---

## Standard Sheet Material Sizes

### European Standard Sheet (Primary for OMIM)

```
Full sheet:         2800mm × 2070mm  (most common in European industry)
Alternative:        3050mm × 1220mm  (narrower format)
Alternative:        2440mm × 1220mm  (exported to North American market)
Thickness options:  as per EN 309 (see Cabinet_Standards.md)
```

### North American Standard Sheet

```
Full sheet:  2440mm × 1220mm  (= 8' × 4'; common in North America)
Half sheet:  1220mm × 1220mm
```

**OMIM v0 primary target**: European 2800×2070mm sheet sizes. North American sizes are within the validation range but are secondary.

---

## CNC Nesting Table Constraints (MFG-008)

The maximum panel set that fits on a CNC router bed:

```
Representative CNC tables:
  SCM Accord 25 FX:    3950 × 1600mm working area
  Homag BOF 211:       3800 × 1850mm working area
  Biesse Rover A:      3650 × 2100mm working area
  Felder Format-4:     2800 × 1300mm (smaller shop machine)

OMIM v0.1.0 MFG-008 limit: 3600 × 2100mm
  (conservative value that fits all listed machines)
```

---

## Standard Cabinet Component Dimensions

### Base Cabinets (Floor Units)

```
Height:      720mm body (+ 150mm legs + countertop = ~880–920mm total)
Depth:       560mm body (+ 20mm door = 580mm; + countertop overhang = ~600mm)
Width range: 150mm to 1200mm in 50mm or 100mm increments (depends on manufacturer)
Common widths: 300, 400, 450, 500, 600, 800, 900, 1000, 1200mm
```

### Wall Cabinets (Hanging Units)

```
Height range: 300mm to 900mm; most common: 600mm, 720mm
Depth:        280mm to 350mm
Width:        same as base cabinets
```

### Tall Cabinets (Full-Height)

```
Height: 1980mm, 2000mm, 2100mm, 2200mm (floor to ceiling options)
Depth:  560mm (same as base)
Width:  300mm to 600mm (structural constraint at larger widths)
```

### Wardrobe / Closet Units

```
Height: 2000mm, 2200mm, 2400mm
Depth:  400mm (reach-in) to 600mm (walk-in threshold)
Width:  up to 1200mm single panel; larger = multi-panel
```

---

## Panel Component Size Ranges

These define the realistic bounds for individual panel components in the OMIM synthetic generation system:

```yaml
# data/rules/default_constraints.yaml panel dimension section
panel_dimensions:
  # Single panel component (not full sheet)
  min_width_mm: 50.0      # Minimum panel width (narrow filler strips)
  max_width_mm: 1200.0    # Maximum single component width
  min_height_mm: 50.0     # Minimum panel height
  max_height_mm: 2400.0   # Maximum panel height (tall cabinet)
  
  # Synthetic generation targets (realistic distribution)
  typical_widths_mm:  [300, 400, 450, 500, 600]    # base cabinet widths
  typical_heights_mm: [720, 600, 300, 1980, 2100]  # height by component type
  
  # Full sheet limits (for MFG-008)
  max_nesting_table_mm: [3600, 2100]
```

---

## Standard Thickness Values (EN 309 + EN 622-5)

The complete list of acceptable panel thicknesses in OMIM validation:

```python
VALID_PANEL_THICKNESSES_MM = [
    6.0,   # thin back panels (HDF)
    8.0,   # drawer bottoms (thin)
    9.0,
    10.0,
    12.0,
    15.0,
    16.0,  # EU standard carcass (common)
    18.0,  # EU standard carcass (most common)
    19.0,  # NA equivalent to 18mm
    22.0,
    25.0,
    28.0,
    30.0,
    38.0,  # thick worktops
]

DEFAULT_PANEL_THICKNESS_MM = 18.0  # Used when thickness not specified
```

---

## Feature Count Expectations by Panel Type

Used for MFG-009 (feature density) calibration and synthetic generation distribution:

| Panel Type | Typical Hole Count | Typical Contours |
|-----------|------------------|-----------------|
| Side panel (600mm high base) | 8–24 holes (shelf pins) | 1 (outer profile) |
| Side panel (with hinge) | 10–28 holes | 1 |
| Shelf (600mm wide) | 0–4 holes | 1 |
| Door panel | 2 holes (hinge cups) | 1 |
| Bottom/top panel | 4–8 holes | 1 |
| Drawer front | 0–2 holes | 1 |
| Back panel | 0 holes | 1 |

Maximum realistic hole count for a standard cabinet panel: ~40 holes (dense shelf pin array in tall wardrobe side panel).

---

## Implications for Synthetic Generation

The synthetic generator in `07_SYNTHETIC_GENERATION/` uses these values to:

1. Sample panel dimensions from realistic distributions (not uniform random)
2. Constrain feature placement to valid positions (not too close to edges)
3. Generate hole counts consistent with panel type
4. Ensure generated geometry matches what CNC operators actually produce

See [[07_SYNTHETIC_GENERATION/Realism_Constraints]] for how these bounds are enforced during generation.
