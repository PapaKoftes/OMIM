# Real DXF Corpus Sources

Version: v0.1.0  
Section: 06_REAL_WORLD_GROUNDING  

See also: [[07_SYNTHETIC_GENERATION/Realism_Constraints]], [[09_BENCHMARKS/Train_Test_Policy]]

---

## Purpose

Documents sources of real manufacturing DXF files that can ground OMIM's synthetic generation and provide validation against real-world geometry. Each source is assessed for license, trust level, domain relevance, and limitations.

**OMIM v0 synthetic generation is the primary training data source.** Real DXF corpora serve as:
1. Validation benchmarks (held-out test sets)
2. Realism calibration for the synthetic generator
3. Expert annotation targets (BENCH-002, BENCH-004)

---

## OpenBuilds Community

**URL**: openbuilds.com  
**Type**: Community design sharing platform  
**License**: Mixed — Creative Commons (CC BY, CC BY-SA) for most user-submitted designs; verify per-file  
**Domain relevance**: Medium — CNC router projects; includes wood panel work but also metal, plastics  
**Trust level**: Medium — community-submitted; quality varies; no expert validation  
**Format availability**: DXF, SVG, Fusion 360  

**Strengths**:
- Large volume of real CNC-cut designs
- Many panel/wood projects
- Some cabinet-adjacent designs (shelving, furniture)

**Limitations**:
- Not specifically furniture/cabinet oriented
- Mixed materials (aluminum, acrylic alongside wood)
- Layer naming inconsistent — many files have no layer structure
- No ground-truth labels; annotation required

**OMIM use**: Visual reference for synthetic generation realism calibration. NOT used as training data without expert annotation and license verification.

---

## GrabCAD Community Library

**URL**: grabcad.com/library  
**Type**: Engineer/designer sharing platform  
**License**: GrabCAD Community License — free to use for non-commercial purposes; commercial use requires explicit permission  
**Domain relevance**: Low-Medium — primarily mechanical engineering (STEP/IGES), not furniture DXF  
**Trust level**: Medium — professional community; better quality than OpenBuilds  
**Format availability**: STEP, IGES, Fusion 360, CATIA, SolidWorks; DXF available for some 2D drawings  

**Limitations**:
- Primarily mechanical engineering focus; furniture DXF rare
- DXF files tend to be 2D technical drawings, not CNC manufacturing files
- GrabCAD license is restrictive for ML training datasets
- Not recommended as primary source for OMIM

**OMIM use**: Do not use as training data source in v0.1.0 due to license restrictions and domain mismatch.

---

## FreeCAD Sample Files

**URL**: freecad.org / FreeCAD GitHub repositories  
**Type**: Open-source CAD software sample files and tutorials  
**License**: LGPL (FreeCAD itself); sample files typically CC0 or CC BY  
**Domain relevance**: Low-Medium — FreeCAD covers all CAD domains; panel furniture samples exist but are not the primary focus  
**Trust level**: Medium — created by FreeCAD contributors; geometry correctness depends on contributor  
**Format availability**: FCStd (native), STEP, DXF export  

**Strengths**:
- Open licenses (CC0 / CC BY) compatible with ML dataset use
- Well-structured geometry (CAD tool ensures closure, unit consistency)
- DXF export from FreeCAD models produces clean, valid geometry

**Limitations**:
- Small volume of panel-furniture-specific files
- FreeCAD DXF export may include annotations, construction geometry
- Tutorial files may oversimplify real manufacturing geometry

**OMIM use**: Acceptable as supplementary test fixtures. DXF exports from FreeCAD models known to be geometrically valid — useful for testing the happy path.

---

## ABC Dataset (PointCloud / CAD Dataset)

**URL**: deep-geometry.com/abc-dataset (McNeel/Shapenet associated)  
**Type**: Large-scale CAD model dataset from Onshape  
**License**: Permissive research license; see dataset paper  
**Domain relevance**: Low — primarily mechanical parts, not panel furniture  
**Trust level**: High for geometry correctness (professional CAD models)  
**Format availability**: STEP, OBJ, NURBS; no direct DXF  

**Limitations**:
- No panel furniture content — entirely wrong domain for OMIM
- 3D solid models, not 2D panel manufacturing DXF
- Would require significant processing to extract 2D cross-sections
- License restricts commercial use

**OMIM use**: Not applicable for v0. Included here as a known large-scale CAD dataset that is out-of-domain for OMIM's specific target.

---

## DeepCAD Dataset

**Paper**: DeepCAD: A Deep Generative Network for Computer-Aided Design Models (Wu et al., 2021)  
**Type**: CAD operation sequence dataset from Onshape  
**License**: Research use; see paper for data access  
**Domain relevance**: Low — general CAD (predominantly mechanical)  
**Trust level**: High for geometry validity  
**Format availability**: JSON operation sequences, not DXF  

**Limitations**:
- Parametric CAD operation sequences, not manufacturing DXF
- No 2D panel manufacturing content
- Requires conversion pipeline to produce anything DXF-compatible
- Domain mismatch: mechanical CAD, not furniture/panel

**OMIM use**: Not applicable for v0. Cited as known large-scale CAD ML dataset; confirms absence of panel manufacturing datasets (OMIM's gap).

---

## Fusion 360 Gallery Dataset

**Paper**: Reconstruction of Editable Parametric models from Point Clouds (Willis et al., 2021)  
**URL**: autodeskresearch.com (dataset access via Autodesk Research)  
**Type**: Parametric CAD models from Autodesk Fusion 360 Gallery  
**License**: Autodesk Research dataset license; research use  
**Domain relevance**: Low — mixed CAD models; some furniture items but not manufacturing-focused  
**Trust level**: High (professional Fusion 360 models)  
**Format availability**: STEP, F3D (native); no DXF  

**Limitations**:
- No direct DXF output; conversion required
- Mixed domain (consumer products, mechanical, furniture)
- License restricts commercial and training use without explicit agreement
- Panel manufacturing DXF conventions not preserved in 3D-to-2D conversion

**OMIM use**: Not recommended for v0. Confirms gap in publicly available, license-clear, domain-specific panel manufacturing DXF corpora.

---

## LinuxCNC Sample Files

**URL**: linuxcnc.org; LinuxCNC GitHub repository  
**Type**: CNC machine configuration examples and test G-code files  
**License**: GPLv2 (software); sample files vary  
**Domain relevance**: Medium — real CNC files, but G-code not DXF; different domain  
**Trust level**: High for CNC correctness  

**Limitations**:
- G-code format, not DXF — OMIM does not parse G-code
- Configuration examples, not design files
- Panel manufacturing examples are rare in LinuxCNC samples

**OMIM use**: Not directly usable. LinuxCNC's CNC ecosystem is relevant as grounding for what the downstream CNC programs look like, but the files are not OMIM input format.

---

## Summary: Corpus Suitability Table

| Source | License | Domain Match | Volume | OMIM Status |
|--------|---------|-------------|--------|------------|
| OpenBuilds | CC BY (verify) | Medium | Large | Reference only; annotation needed |
| GrabCAD | Restrictive | Low | Large | Do not use |
| FreeCAD samples | CC0/CC BY | Low-Medium | Small | Test fixtures acceptable |
| ABC Dataset | Research | Low | Very Large | Out of domain |
| DeepCAD | Research | Low | Large | Out of domain |
| Fusion360 Gallery | Autodesk Research | Low-Medium | Large | Do not use without agreement |
| LinuxCNC | GPL | Low | Small | Wrong format |

---

## Open Source Tool Reference

Tools used in or directly relevant to the OMIM implementation:

### DXF Processing
| Tool | URL | Role in OMIM |
|------|-----|-------------|
| ezdxf | https://ezdxf.readthedocs.io/ | Primary DXF parsing library |
| LibreCAD | https://librecad.org/ | DXF creation for test fixtures |
| QCAD | https://qcad.org/ | DXF inspection and validation |

### CAD/CAM Systems
| Tool | URL | Role |
|------|-----|------|
| FreeCAD | https://www.freecad.org/ | Open-source 3D CAD; test DXF export source |
| CadQuery | https://cadquery.readthedocs.io/ | Pythonic parametric CAD; used in synthetic DXF generation |
| OpenSCAD | https://openscad.org/ | Programmatic CSG CAD; reference implementation |
| OpenCascade | https://www.opencascade.com/ | B-rep geometry kernel; STEP processing |

### CNC Systems (Context References)
| Tool | URL | Role |
|------|-----|------|
| LinuxCNC | https://linuxcnc.org/ | G-code interpretation reference; CNC constraints |
| OpenCAMLib | https://github.com/aewallin/opencamlib | Open CAM algorithm library (C++/Python) |
| CAMotics | https://camotics.org/ | G-code simulation for validation context |
| FreeCAD Path workbench | https://github.com/FreeCAD/FreeCAD | Open CAM toolpath reference implementation |

### Geometry and Graph Libraries
| Tool | URL | Role in OMIM |
|------|-----|-------------|
| Shapely | https://shapely.readthedocs.io/ | All 2D geometry operations (CONTAINS, area, etc.) |
| NetworkX | https://networkx.org/ | MGG graph data structure |
| scipy.spatial | scipy.org | Spatial queries (KD-tree for proximity detection) |
| PyTorch Geometric | pytorch-geometric.readthedocs.io | GNN training on MGG |
| DGL | dgl.ai | Alternative GNN library |

---

## Domain Expansion Strategy

Architecture must be clean enough to support these domains without touching core infrastructure:

### 2.5D CNC → 5-Axis Machining
- **New requirement**: 3D geometry (surfaces, not just 2D contours)
- **New ontology terms**: undercuts, complex surfaces, draft angles
- **New validation rules**: reach envelopes, collision avoidance
- **Key standards**: ISO 10303 (STEP), DMIS
- **Key tools**: OpenCascade, FreeCAD 5-axis path workbench

### 2.5D CNC → Waterjet / Laser Cutting
- **Similar**: Still 2D profile cutting from flat stock
- **Different**: No tool radius constraint; kerf compensation required; heat-affected zone (laser)
- **New ontology**: KERF_COMPENSATION, HEAT_AFFECTED_ZONE
- **Key standards**: OSHA 1910.212 (machine guarding); ISO 11553 (laser safety)

### Panel Furniture → Sheet Metal
- **Similar**: 2.5D cutting of flat stock from sheets
- **Different**: Bending, forming, punching, springback — completely different constraint model
- **New ontology**: BEND_LINE, PUNCH_HOLE, EMBOSS, HEM
- **Key standards**: DIN 6935 (bending); ISO 2768-1 (sheet metal tolerances)
- **Key tools**: FreeCAD Sheet Metal workbench

### Subtractive → Additive Manufacturing
- **Completely different paradigm** — separate ontology required
- **Key considerations**: support structures, layer orientation, infill patterns
- **Standards**: ASTM F2792 (additive manufacturing terminology)

**Extension rule**: Each new domain requires (1) a new ontology YAML file, (2) new validator rules, (3) a new parser module. Core infrastructure (MGG, provenance, export, benchmarks) must require zero changes.

---

## Reference Citation Key Format

All references in rule YAML files use a standardized key format:

```
ISO standards:       ISO-<number>-<year>       e.g., ISO-286-1-2010
DIN standards:       DIN-<number>-<year>       e.g., DIN-68762-2002
Academic papers:     <AuthorSurname>-<Year>    e.g., Hamilton-2017
Manufacturer docs:   <Manufacturer>-<System>-<Year>  e.g., Blum-CLIPtop-2022
```

This enables systematic citation tracking and future expert review of rule sources.

---

## Implication: Why Synthetic Data is Primary

The absence of any large, license-clear, domain-matched real DXF corpus is the primary justification for OMIM's synthetic generation approach. No existing dataset provides:
- 2D panel manufacturing DXF files
- Ground-truth feature labels
- Permissive license for ML dataset publication

This gap is explicitly noted in [[01_FOUNDATION/Research_Positioning]] and is the primary OMIM contribution claim.
