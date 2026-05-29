# Manufacturing Domain Lock — v0

**Status: LOCKED. No changes during hackathon implementation.**

Version: v0.1.0  
Section: 01_FOUNDATION  

See also: [[06_REAL_WORLD_GROUNDING/Cabinet_Standards]], [[06_REAL_WORLD_GROUNDING/Panel_Dimension_Standards]], [[04_ONTOLOGY/Feature_Taxonomy]]

---

## v0 Domain: Modular Cabinetry / Panel Furniture Manufacturing

OMIM v0 is hard-locked to this domain. Every rule, every feature type, every standard reference, and every test fixture must be consistent with this domain.

**Domain Summary**:
- **Products**: Flat-pack and modular furniture, kitchen cabinets, shelving units, office furniture panels
- **Manufacturing process**: 2.5D CNC routing + multi-spindle drilling on flat panel stock
- **Machine axis constraint**: 3-axis (X, Y, Z) only — no tilting head, no 5-axis
- **Geometry**: Rectangular panels with 2D features drilled/routed from the face
- **Distribution context**: European cabinet industry; hardware standards from Blum/Hettich/Häfele/Grass

---

## Panel Material Lock

| Material | Standard | Locked-In Properties |
|----------|----------|---------------------|
| MDF (Medium Density Fiberboard) | EN 622-5 | Homogeneous, no grain direction, fragile at thin walls |
| Particleboard (chipboard) | EN 309 / EN 312 | Lower strength than MDF, standard carcass material |
| Melamine-coated particleboard | EN 312 (P2, P3) | Decorative surface, requires edge banding post-cut |
| Plywood | EN 636 | Has grain direction — nesting must respect this |

**Default material assumption**: MDF at 18mm thickness when no metadata is present.

**Out of scope (v0)**: Solid wood, aluminium extrusions, plastic panels, glass, stone, composites with fiber reinforcement.

---

## Standard Panel Thickness Lock

From EN 309 particleboard and EN 622-5 MDF specifications:

```
9mm, 12mm, 15mm, 18mm, 22mm, 25mm
```

**Default**: 18mm  
**Rationale**: 18mm particleboard is the industry-standard carcass material for flat-pack furniture (IKEA system, Euro-style cabinets, kitchen units).

---

## CNC Machine Parameter Lock

| Parameter | Locked Value | Source |
|-----------|-------------|--------|
| Machine type | 3-axis CNC router + multi-spindle drill | Standard panel CNC |
| Maximum nesting area | 3600mm × 2100mm | Standard CNC nesting table (HOMAG, SCM, Biesse) |
| Minimum practical drill bit | 3mm diameter | Practical minimum for panel work |
| Standard routing tool | 6mm diameter end mill | Most common panel routing tool |
| Minimum corner radius | 3mm | = standard routing tool radius |
| Routing spindle | Single-pass at rated feed | No multi-pass modeling in v0 |

---

## Feature Size Lock

| Dimension | Minimum | Maximum | Source |
|-----------|---------|---------|--------|
| Hole diameter | 3mm | 100mm | Practical limits for 3-axis panel drilling |
| Pocket width | 7.2mm (= 6mm × 1.2) | Unlimited | Tool diameter × 1.2 clearance ratio |
| Internal corner radius | 3mm | Unlimited | Routing tool radius constraint |
| Edge clearance | 8mm | — | MFG-001; shop convention for MDF |
| Drill-to-drill wall | 3mm + radii | — | MFG-002; MDF structural |
| Blind feature depth | — | 75% of thickness | MFG-007; structural floor |

---

## European 32mm Modular System Lock

The **Rasterbohrsystem** (32mm modular grid) is a foundational constraint in European cabinet manufacturing. It defines:

- Shelf pin holes at **5mm diameter** in columns spaced **32mm apart**
- The 32mm grid is measured from the **back face** of the side panel
- First hole typically at **37mm from the top/bottom edge** (37 = 32 + 5mm half-hole alignment)
- Applies to: shelving units, kitchen wall units, bookcases, filing cabinets

**Hardware using 32mm system**: Blum shelf pin system, Hettich InnoFit shelf carriers, Grass shelf supports.

**OMIM Rule**: MFG-005 enforces 32mm spacing for detected SHELF_PIN_HOLE features (WARNING severity).

---

## Hardware System Lock

These hardware systems define the exact hole dimensions and positions that OMIM must recognize:

### Blum CLIP top Hinge System
- **Cup hole**: 35mm diameter, 13mm depth
- **Edge distance**: 22.5mm from panel edge to cup center (standard; 26mm for thick-door option)
- **OMIM Rule**: MFG-006 checks this positioning (WARNING severity)
- **Feature**: HINGE_CUP_HOLE

### HÄFELE / HETTICH Confirmat (Euro Screw) System
- **Body hole**: 7mm diameter
- **Head counterbore**: 10mm diameter (stepped)
- **OMIM Feature**: CONFIRMAT_HOLE (7mm diameter detection)

### DIN 7 Dowel Pins
- **Standard diameters**: 6mm, 8mm, 10mm, 12mm
- **OMIM primary**: 8mm and 10mm (most common for furniture joining)
- **OMIM Feature**: DOWEL_HOLE

### Lamello Bisco Groove System (v0.2)
- **Groove dimensions**: 3mm × 15mm
- **Not in v0 feature set** — represented as generic GROOVE

---

## Geometry Dimension Lock

| Panel Dimension | Minimum | Maximum | Typical |
|----------------|---------|---------|---------|
| Width | 50mm | 3600mm | 200–900mm |
| Height | 50mm | 2100mm | 300–1200mm |
| Thickness | 9mm | 25mm | 18mm |

**Performance guard**: Panel dimension checks are enforced by MFG-009.

---

## Why This Domain

Panel furniture manufacturing was chosen because:

1. **DXF is the universal format**: 99% of panel shops work in DXF. No STEP-NC, no rich CAM format.
2. **Hardware systems are standardized**: Blum, Hettich, Häfele publish exact dimensions. Rules are verifiable.
3. **32mm system is formal**: European shelf pin grid = deterministic, unambiguous rule source.
4. **Manageable complexity**: 2.5D profiles + drilling. No 5-axis, no sheet metal forming, no 3D solid machining.
5. **High commercial volume**: Flat-pack furniture is a multi-hundred-billion-dollar industry with unsolved AI problems.
6. **Open problem**: No comparable open research infrastructure exists for this domain.

---

## Domain Extension Path (Post-Hackathon)

The domain lock is for v0 only. Extension architecture is defined but NOT implemented:

| Domain | What Changes | Extension Mechanism |
|--------|-------------|---------------------|
| Waterjet / laser cutting | New rules (kerf compensation, no corner radius constraint) | New rule YAML + new feature types |
| 5-axis machining | 3D geometry, undercuts, draft angles | New node types in MGG, new parser |
| Sheet metal | Bending, forming, springback | New ontology YAML, new constraint types |
| Solid wood carpentry | Grain direction, joinery types | Material model extension |

To add a new domain: add ontology YAML + rule YAML + parser module. Do NOT touch core infrastructure.
