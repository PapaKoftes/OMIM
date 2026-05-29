# Tooling Catalog References

Version: v0.1.0  
Section: 06_REAL_WORLD_GROUNDING  

See also: [[06_REAL_WORLD_GROUNDING/Cabinet_Standards]], [[04_ONTOLOGY/Constraint_Taxonomy]], [[05_VALIDATION/Manufacturability_Validation]]

---

## Purpose

Documents CNC tooling manufacturer specifications that define minimum feature sizes, tool diameters, and machining constraints. Validation rules MFG-003 (drill diameter range), MFG-004 (pocket width), and MFG-006 (hinge cup) reference these catalogs.

---

## Leuco (Leuco Ledermann GmbH & Co. KG)

**Country**: Germany  
**Specialization**: Routing tools, saw blades, drilling systems for panel processing  
**Catalog**: Leuco Tool Reference (leuco.com); annual print catalog; PDF download available  
**License**: Commercial catalog; not open access  
**Trust level in OMIM**: High — primary tooling supplier for European CNC cabinet shops  
**Domain relevance**: High — specifically designs for MDF, particleboard, melamine processing  

### Key Specifications Used in OMIM

```
Routing tools:
  Minimum diameter:    3.0mm (practical lower bound; specialized bit)
  Common diameters:    6mm, 8mm, 10mm, 12mm, 16mm, 20mm
  Maximum drilling:    40mm (above this: routing or boring operations)

Hinge cup boring bit:
  Standard diameter:   35mm ± 0.1mm
  Recommended speed:   3500–4000 RPM for MDF
  
Spiral compression bit (standard panel routing):
  Diameter range:      3mm–16mm standard catalog
  Recommended for:     MDF, particleboard, melamine
```

**OMIM constraint derived**: MFG-003 diameter bounds [3mm, 40mm]  
**Limitations**: Catalog values are for standard stock tools; custom tooling can go smaller  

---

## Leitz Werkzeugfabrik GmbH & Co. KG

**Country**: Germany  
**Specialization**: Precision routing tools, drilling bits, panel processing systems  
**Catalog**: Leitz Tooling Catalog (leitz.org); online catalog with parametric search  
**License**: Commercial catalog; freely viewable online  
**Trust level in OMIM**: High  
**Domain relevance**: High — comparable scope to Leuco  

### Key Specifications Used in OMIM

```
Panel routing bits:
  Minimum standard diameter:  3.175mm (1/8" inch shank = minimum common routing bit)
  Standard metric minimum:    3.0mm
  
Boring systems (for hinge cups):
  35mm boring bit:     ø35.0 ± 0.05mm; depth stop typically 12.5mm
  Multi-spindle drill: simultaneous boring for production lines

Pocket milling:
  Minimum recommended pocket width = 1.2 × tool_diameter
  (Leitz technical notes; also Sandvik Coromant general guidance)
```

**OMIM constraint derived**: MFG-004 pocket width ratio 1.2  

---

## Onsrud Cutter LP

**Country**: USA (Lake Geneva, WI)  
**Specialization**: Solid carbide router bits for composites, plastics, wood  
**Catalog**: Onsrud Cutter Catalog (onsrud.com); PDF available  
**License**: Commercial catalog; PDF freely downloadable  
**Trust level in OMIM**: High for general routing geometry; lower for MDF-specific claims  
**Domain relevance**: Medium — primarily North American market; specs broadly consistent with European tools  
**Limitations**: Inch-first documentation; metric conversion needed; some MDF-specific guidance differs from European practice  

### Key Specifications Used in OMIM

```
Down-cut spiral router:  common for melamine surfaces (prevents chip-out)
Up-cut spiral router:    chip evacuation for deep pockets
Compression spiral:      clean cuts on both faces (most common for cabinet panels)

Minimum shank diameter:  1/8" = 3.175mm; metric equivalent: 3mm used in OMIM
```

---

## CMT Utensili S.p.A.

**Country**: Italy  
**Specialization**: Router bits, saw blades, drill bits for woodworking  
**Catalog**: CMT Tools Catalog (cmtusa.com); available in print and PDF  
**License**: Commercial catalog; PDF freely available  
**Trust level in OMIM**: Medium-High  
**Domain relevance**: Medium — broad woodworking catalog; cabinet-specific sections less detailed than Leuco/Leitz  
**Limitations**: Some specifications are North American format  

### Key Specifications Used in OMIM

```
Spiral router bits: 3mm–25mm range
Straight bits: 3mm–50mm (larger diameters are routing, not drilling)
Hinge boring bit: ø35mm available; identical spec to Leuco/Leitz
```

---

## Amana Tool (Amana Tool Company)

**Country**: USA (Farmingdale, NY)  
**Specialization**: Router bits, CNC tooling  
**Catalog**: Amana Tool Catalog (amanatool.com); online and PDF  
**License**: Commercial; free online catalog  
**Trust level in OMIM**: Medium  
**Domain relevance**: Medium — good for general routing specs; less MDF/panel-specific than European makers  
**Limitations**: Primarily North American market; inch-based specifications primary  

---

## Tooling Constraints Summary for OMIM v0.1.0

These values synthesize across all catalog sources above:

```yaml
# Derived from tooling catalogs (Leuco, Leitz primary sources)
tooling_constraints:
  min_drill_diameter_mm: 3.0          # MFG-003 lower bound
  max_drill_diameter_mm: 40.0         # MFG-003 upper bound (above = routing)
  default_routing_tool_mm: 6.0        # Most common cabinet routing bit
  min_tool_radius_mm: 3.0             # Internal corner radius limit (6mm tool)
  min_pocket_width_ratio: 1.2         # MFG-004; tool must fit in pocket
  hinge_cup_diameter_mm: 35.0         # All major hinge cup boring bits
  hinge_cup_depth_mm: 12.5            # Standard depth stop
```

---

## Confidence Assessment

| Specification | Source(s) | Confidence |
|---------------|----------|-----------|
| 35mm hinge cup diameter | Blum + Leuco + Leitz + Hettich | Very high — industry universal |
| 6mm default routing diameter | Leuco + Leitz (catalog default) | High — dominant in cabinet routing |
| 3mm minimum drill diameter | Leuco + Leitz + Onsrud | High — practical lower bound |
| 40mm routing/drilling threshold | Leuco catalog | High — standard industry practice |
| 1.2× pocket width ratio | Leitz technical notes | Medium — widely cited, not in a published standard |

---

## Limitations

1. Tooling catalogs are commercial and can change annually. Values in OMIM are calibrated to circa 2022–2024 editions.
2. CNC-specific tooling varies by machine brand (Homag, SCM, Biesse, Felder). Catalog specs are for standalone tools, not machine-integrated tooling systems.
3. Custom tooling (special order, resharpened) can deviate from catalog minimums. OMIM uses standard catalog values.
4. Inch-based catalogs (Onsrud, Amana, CMT) are converted to metric. Minor rounding may apply.
