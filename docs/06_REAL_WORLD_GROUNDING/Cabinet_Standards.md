# Cabinet Standards

Version: v0.1.0  
Section: 06_REAL_WORLD_GROUNDING  

See also: [[06_REAL_WORLD_GROUNDING/Hardware_System_References]], [[06_REAL_WORLD_GROUNDING/Panel_Dimension_Standards]], [[04_ONTOLOGY/Constraint_Taxonomy]]

---

## Purpose

Documents the industry standards that define correct cabinet manufacturing geometry. These standards are the ground truth for validation rules and synthetic generation constraints. Every constraint in OMIM must trace to a source here.

---

## European Panel Furniture Standards

### EN 309 — Particleboard

- **Full title**: Particleboards — Definition and classification
- **Relevant to OMIM**: Standard thickness values for particleboard and chipboard panels
- **Standard thicknesses**: 8, 9, 10, 12, 15, 16, 18, 19, 22, 25, 28, 30, 38mm
- **Typical cabinet use**: 16mm and 18mm shelves, 18mm and 19mm carcasses
- **Trust level in OMIM**: High — ISO-family European standard

### EN 622-5 — MDF (Medium Density Fibreboard)

- **Full title**: Fibreboards — Specifications — Part 5: Requirements for dry process boards (MDF)
- **Relevant to OMIM**: Standard MDF thickness values; fiber density affecting drill/route parameters
- **Standard thicknesses**: 3, 4, 6, 8, 9, 10, 12, 15, 16, 18, 19, 22, 25, 30mm
- **Fiber density**: 700–800 kg/m³ (standard MDF); affects minimum wall thickness requirements
- **Trust level in OMIM**: High

### EN 635 — Plywood Classification

- **Full title**: Plywood — Classification and terminology
- **Relevant to OMIM**: Plywood thickness steps; grain direction affects routing geometry
- **Standard thicknesses**: 4, 6, 9, 12, 15, 18, 21, 24mm
- **Trust level in OMIM**: Medium (less common in flat-panel furniture)

---

## DIN Standards (German Institute for Standardization)

### DIN 68xxx Series — Wood and Panel Furniture

| Standard | Subject | OMIM Relevance |
|----------|---------|---------------|
| DIN 68705 | Particleboard grades | Material classification |
| DIN 68863 | Dowel holes for furniture | 8mm/10mm dowel, 34mm deep |
| DIN 68871 | Confirmat screws | 7mm hole, 5mm pilot |
| DIN 68840 | Shelf support systems | 5mm hole, 32mm spacing |

### DIN 7 — Pins and Dowels

- **DIN 7 Part 1**: Cylindrical pins; defines nominal diameters
- **Cabinet relevance**: 8mm and 10mm diameter dowel pins for furniture joints
- **OMIM usage**: DOWEL_HOLE feature classification uses DIN 7 diameter ranges
- **Tolerance class**: h8 (precision fit), h11 (push fit)

---

## European 32mm System (Rasterbohrsystem)

The European cabinet construction standard used by virtually all flat-pack furniture manufacturers.

### Definition

A modular drilling grid where hardware holes are positioned at multiples of 32mm from the panel edge.

### Specifications

```
Grid unit:         32mm
Shelf pin diameter: 5mm (standard)
Shelf pin depth:   15mm (blind hole)
Row offset from edge: typically 37mm (= 32 + 5mm setback)
Second row from edge: 69mm (= 37 + 32mm)
Standard bit:      5mm diameter, 35mm stop collar

System column spacing: typically 96mm (= 3 × 32mm)
```

### Compliance Criterion (MFG-005)

Holes at 5mm diameter ± 0.5mm in collinear groups must have center-to-center spacing within 0.5mm of 32mm multiples.

### Sources

- Häfele Furniture Hardware Catalog (annual; "System 32" section)
- Grass Technical Manual — Drawer Systems
- Blum Technical Manual — Hinge and Drawer Systems
- Hettich Catalog — Sliding Fittings and Hinge Systems

---

## KCMA A161.1 — North American Cabinet Standard

- **Full title**: American National Standard for Kitchen and Vanity Cabinets
- **Relevant to OMIM**: Alternative construction geometry for North American market
- **Key dimensions**: Face-frame construction (25.4mm = 1" grid); different edge clearances
- **OMIM v0 position**: Not primary target — OMIM v0 targets European construction. North American DXF sources use different conventions.
- **Trust level**: Medium (well-defined but not OMIM's primary domain)

---

## ISO Standards

### ISO 286 — Limits and Fits

- Dimensional tolerances for manufactured holes
- **OMIM use**: Constrains acceptable deviation in hole diameter during validation
- Cabinet application: IT7 tolerance class for most furniture joints

### ISO 2768 — General Tolerances

- General dimensional tolerances for machined parts
- **OMIM use**: GEO-003 degenerate geometry threshold references ISO 2768-m (medium)
- Minimum linear dimension: 0.1mm resolution for general machining

### ISO 14649 / STEP-NC

- **Relationship to OMIM**: STEP-NC is the standard for CNC semantic geometry. OMIM targets raw DXF workflows where STEP-NC is not available.
- **When STEP-NC is available**: OMIM is not needed — the CNC system has full semantic information
- See [[01_FOUNDATION/Vision_and_Scope]] STEP-NC positioning table

---

## Panel Construction Conventions

### European Cabinet Construction (Dominant in OMIM domain)

- **Carcass material**: 18mm particleboard or MDF
- **Back panel**: 3mm or 6mm HDF (hardboard/MDF)
- **Drawer bottom**: 6mm MDF
- **Connection method**: 8mm dowels, Confirmat screws, cam-and-pin fittings
- **Edge banding**: 0.4–2mm PVC or ABS (not visible in DXF 2D geometry)

### Standard Cabinet Depths

- Base cabinet (floor): 580mm (body) + 20mm door = 600mm total
- Wall cabinet: 330mm or 350mm depth
- Wardrobe/tall cabinet: 580mm depth

### Standard Hardware Integration Points

| Hardware | Required Hole | Distance From Edge |
|---------|--------------|-------------------|
| Blum CLIP top hinge | ø35mm × 12.5mm deep | 22.5mm ±1mm |
| European shelf pin | ø5mm × 15mm deep | 32mm grid |
| Confirmat screw (HÄFELE) | ø7mm through + ø5mm pilot | varies |
| Cam fitting (rafix) | ø15mm × 12.5mm | varies by size |
| DIN 7 dowel (8mm) | ø8mm × 17mm | joint position |
