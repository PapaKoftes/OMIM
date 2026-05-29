# Hardware System References

Version: v0.1.0  
Section: 06_REAL_WORLD_GROUNDING  

See also: [[06_REAL_WORLD_GROUNDING/Cabinet_Standards]], [[04_ONTOLOGY/Feature_Taxonomy]], [[05_VALIDATION/Manufacturability_Validation]]

---

## Purpose

Documents hardware manufacturer specifications that define exact hole geometries. These are the ground truth for hinge cup, shelf pin, drawer slide, and fastener hole classifications. Each entry includes: manufacturer, specification, exact dimensions, OMIM feature type, and validation rule that uses it.

---

## Blum (Julius Blum GmbH)

**Country**: Austria  
**Domain relevance**: Dominant supplier of cabinet hinges, drawer systems, lift systems  
**Catalog**: Blum E-Catalog (catalog.blum.com); motion technology catalog PDF  
**Trust level in OMIM**: High — manufacturer specifications are exact, not heuristic  

### CLIP top Hinge (Item 70.1900.AC)

```
Cup hole diameter:    35mm ± 0.5mm
Cup hole depth:       12.5mm (blind)
Edge distance:        22.5mm ± 1.0mm (center of cup from panel edge)
Cup spacing (pair):   varies by door width (not constrained in OMIM)
Door thickness range: 16–23mm
```

**OMIM feature**: `HINGE_CUP_HOLE`  
**Validation rule**: MFG-006 (edge distance check)  
**Confidence ceiling**: 0.90 (hardware_spec)

### CLIP top BLUMOTION (Item 71B9550)

Same geometry as CLIP top — identical hole dimensions. Damping mechanism is internal.

### TANDEM Plus BLUMOTION Drawer System

```
Runner mounting hole: standard screw spacing
Side plate to panel:  varies by cabinet width
Bottom clearance:     4mm below drawer bottom
```

**OMIM v0 status**: Drawer runner mounting holes not modeled as distinct feature type in v0.1.0.

---

## Häfele GmbH & Co KG

**Country**: Germany  
**Domain relevance**: Comprehensive hardware catalog; fasteners, hinges, shelf systems, joinery  
**Catalog**: Häfele Furniture Hardware Catalog (hafele.com); annual print + online  
**Trust level in OMIM**: High  

### Confirmat Screw (Euro Screw)

```
Pilot hole diameter:  5.0mm ± 0.1mm
Main hole diameter:   7.0mm ± 0.2mm
Hole depth:           varies (50–70mm)
Spacing from edge:    typically 8–15mm
```

**OMIM feature**: `CONFIRMAT_HOLE`  
**Classification cue**: 7mm circle, often in pairs, near panel edges  
**Confidence ceiling**: 0.85 (hardware_spec — less unique diameter than hinge cup)

### System 32 / Rasterbohr System

```
Hole diameter:  5.0mm
Hole depth:     15mm (shelf pin stop depth)
Grid pitch:     32mm
Row setback:    37mm or 57mm from panel edge (manufacturer dependent)
```

**OMIM feature**: `SHELF_PIN_HOLE`  
**Validation rule**: MFG-005 (32mm grid check)

### Rafix Cam Fitting

```
Cam hole:    ø15.0mm × 12.5mm deep
Pin hole:    ø8.0mm × varies
```

**OMIM v0 status**: Not separately classified — may appear as THROUGH_HOLE or BLIND_HOLE.

---

## Hettich (Paul Hettich GmbH & Co. KG)

**Country**: Germany  
**Domain relevance**: Drawer systems (ArciTech, InnoTech), hinges (Intermat, Sensys), sliding systems  
**Catalog**: Hettich planning catalog; hettich.com technical specifications  
**Trust level in OMIM**: High  

### Intermat Hinge

```
Cup hole diameter:  35mm ± 0.5mm
Cup hole depth:     12.5mm
Edge distance:      22.5mm ± 1.0mm
```

**Note**: Same hole geometry as Blum CLIP top. Intermat and CLIP top are interchangeable at the geometry level — OMIM cannot distinguish them from hole dimensions alone.

### Sensys Hinge

```
Cup hole diameter:  35mm
Edge distance:      22.5mm
```

Identical geometry to other European hinges. This is industry-standard — all major European hinge manufacturers converged on the same cup dimensions.

---

## Grass (Grass GmbH)

**Country**: Austria  
**Domain relevance**: Drawer systems (Nova Pro, Vionaro), hinges (Tiomos)  
**Catalog**: Grass technical catalog (grassusa.com / grass.at)  
**Trust level in OMIM**: High  

### Tiomos Hinge

```
Cup hole diameter:  35mm (industry standard)
Edge distance:      22.5mm
```

Same cup geometry. OMIM cannot distinguish Tiomos from Blum CLIP top.

### Nova Pro Drawer

```
Runner body length: varies by cabinet depth (270–550mm)
Screw holes:        2mm × varies
Clearance:          standard 4mm bottom clearance
```

---

## DIN 7 Dowel Pins (DIN Standard, not a manufacturer)

**Standard**: DIN 7 Part 1 — Cylindrical pins  
**Source**: Beuth Verlag (DIN standard publisher)  
**Trust level**: High (ISO-family standard)  

```
Standard diameters:  6mm, 8mm, 10mm, 12mm
Furniture standard:  8mm diameter (most common), 10mm (heavy-duty)
Hole depth:         panel_thickness/2 per side (blind)
                    e.g., 17mm in 35mm combined thickness (2×18mm panels)
Tolerance class:    h8 (precision) or h11 (push fit)
```

**OMIM feature**: `DOWEL_HOLE`  
**Classification cue**: 8mm or 10mm circles at joint positions

---

## Lamello (Clamex, Bisco, Tenso)

**Country**: Switzerland  
**Domain relevance**: Plate joinery biscuits and clamping connectors  
**Trust level**: High  

### Clamex P Connector

```
Slot width:   varies (biscuit slot — open-ended geometry)
Not a circular hole — slot cut with biscuit joiner
```

**OMIM v0 status**: Biscuit slots appear as thin rectangular LWPOLYLINE cutouts. Not separately classified in v0.1.0.

---

## Summary: Hole Geometry Cross-Reference

| Feature | Diameter | Depth | Edge Distance | Manufacturer(s) |
|---------|----------|-------|--------------|----------------|
| HINGE_CUP_HOLE | 35mm ±0.5 | 12.5mm | 22.5mm ±1.0 | Blum, Hettich, Grass |
| SHELF_PIN_HOLE | 5mm ±0.5 | 15mm | 32mm grid | Any; system 32 |
| CONFIRMAT_HOLE | 7mm ±0.2 | varies | 8–15mm | Häfele (dominant) |
| DOWEL_HOLE | 8mm ±0.1 | 17mm | joint position | DIN 7 standard |
| DOWEL_HOLE (heavy) | 10mm ±0.1 | 17mm | joint position | DIN 7 standard |

All diameter values are the ground truth for feature classification in the Semantic Interface.
