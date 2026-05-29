# Manufacturing Standards Research Library

Version: v0.1.0  

See also: [[Rule Engine and Standards]], [[Manufacturing Ontology]], [[Research direction]]

---

## Purpose

This document is the curated research corpus for OMIM — the collection of standards, papers, tools, and references that the system is built upon. Every claim in OMIM should trace back to something in this library or be explicitly labeled as a heuristic.

---

## ISO Standards

### ISO 14649 / STEP-NC (Critical Positioning Reference)

**This standard must be understood before any reviewer conversation.**

- **ISO 14649:2003** — Data model for computerized numerical controllers — Part 1-11
- **Also known as**: STEP-NC (Numerical Control extension to STEP)
- **Also known as**: ISO 10303 AP238

**What STEP-NC models**: Machining features (pockets, holes, profiles), operations (drilling, milling, turning), tooling, workingsteps, process plans, tolerances. It is essentially a machine-readable manufacturing plan that includes both geometry AND semantic manufacturing intent.

**STEP-NC already does much of what OMIM does** — for CNC programs. The key differences:

| STEP-NC | OMIM |
|---------|------|
| Rich semantic format; requires CAM/CAD software to generate | Works from raw DXF (the format 99% of panel shops actually use) |
| Designed for NC program exchange | Designed for research inference + synthetic datasets |
| Requires explicit machining program | Infers from geometry alone |
| Industry standard (niche adoption) | Open research infrastructure (MIT/Apache) |
| No synthetic data generation | Core feature: benchmarkable synthetic generation |
| No ML integration path | Explicit GNN/ML research direction |

**OMIM's position**: STEP-NC is what you get when you have a full CAM system and a cooperative manufacturer. OMIM is what you build when you have raw DXF and need to understand what it means. The majority of small-to-medium panel manufacturers work in DXF + operator knowledge; STEP-NC adoption in that segment is minimal.

**References**:
- ISO 14649-1:2003: https://www.iso.org/standard/30990.html
- STEP-NC overview: Suh, S.H., et al. "STEP-Compliant CNC Technology." Springer, 2008.
- NC-STEP initiative: https://www.steptools.com/stix/
- Open source STEP-NC: https://github.com/steptools (STEPTools reference implementations)

---

### ISO 286: Geometrical Product Specifications — Fits and Tolerances
- **ISO 286-1:2010** — Linear sizes, Part 1: ISO code system for tolerances on cylindrical features
- **ISO 286-2:2010** — Part 2: Tables of standard tolerance grades and limit deviations for holes and shafts
- **Relevance**: Hole diameter tolerances; defines tolerance grades IT1–IT18; H-series (hole system) tolerances
- **Use in OMIM**: Baseline for acceptable diameter variation ranges in feature detection
- **Access**: https://www.iso.org/standard/45975.html (paid); summary tables widely available

### ISO 2768: General Tolerances
- **ISO 2768-1:1989** — Part 1: Tolerances for linear and angular dimensions without individual tolerance indications
- **ISO 2768-2:1989** — Part 2: Geometrical tolerances for features without individual tolerance indications
- **Classes**: f (fine), m (medium), c (coarse), v (very coarse)
- **Relevance**: Default machining tolerances when not specified; baseline for rule thresholds
- **Use in OMIM**: Default tolerance class "m" (medium) used for unspecified dimensions
- **Key values (class m)**: ±0.1mm for 0.5-6mm, ±0.2mm for 6-30mm, ±0.3mm for 30-120mm

### ISO 1101: Geometrical Tolerancing
- **ISO 1101:2017** — Geometrical product specifications — Geometrical tolerancing
- **Relevance**: Form tolerances (flatness, straightness, roundness) for CNC parts
- **Use in OMIM**: Validation context; circularity check basis

### ISO 6983: Numerical Control
- **ISO 6983-1:2009** — Automation systems — Numerical control — NC Part program format and definitions
- **Relevance**: G-code and M-code standards; assumed format for CNC output context
- **Use in OMIM**: Background reference for CNC operation semantics

### ISO 10303: STEP (Standard for Exchange of Product Data)
- **ISO 10303** — Product data representation and exchange
- **Relevance**: Future interoperability; current scope uses DXF, not STEP
- **Use in OMIM**: Future extension target for 3D geometry
- **Access**: OpenCascade implements STEP: https://www.opencascade.com/

### ISO 15487: Twist Drills
- **ISO 15487:2020** — Twist drills with cylindrical shank — Dimensions
- **Relevance**: Standard drill bit diameter sizes; informs which diameters are "standard"
- **Use in OMIM**: Standard drill diameters: 3mm, 4mm, 5mm, 6mm, 7mm, 8mm, 10mm, 12mm...

### ISO 10642: Countersunk Screws
- **ISO 10642:2004** — Hexagon socket countersunk head screws
- **Relevance**: Countersink geometry; head angles and dimensions
- **Use in OMIM**: COUNTERSINK feature parameters

---

## DIN Standards (German, widely adopted in European furniture industry)

### DIN Panel/Furniture Series
- **DIN 68xxx series** — Wood-based panel materials and furniture hardware
- **DIN 68861-1** — Furniture surface coatings; Panel surface requirements
- **DIN 68762:2002** — Wood-based panels; thickness tolerances
- **DIN 7** — Dowel pins; dimensions and tolerances
  - DIN 7 A: Short type; DIN 7 B: Long type
  - Standard diameters: 6, 8, 10, 12mm
- **DIN 68752** — Tongue and groove boards; groove geometry reference

### European Panel Standards (EN series)
- **EN 309:2005** — Particleboards — Definition and classification
  - Standard thicknesses: 9, 12, 15, 18, 22, 25mm
  - **This is the source for standard panel thicknesses in OMIM**
- **EN 312:2010** — Particleboards — Specifications (P1-P7 grades)
- **EN 622-5:2006** — Fibreboards — Specifications for MDF
- **EN 636:2012** — Plywood — Specifications
- **EN ISO 11093-9** — Testing of cores for paper rolls
- **Access**: CEN (European Committee for Standardization): https://standards.cen.eu/

---

## Hardware Manufacturer Technical References

### Blum GmbH (Hinge Systems)
- **CLIP top BLUMOTION hinge system**
  - Hinge cup hole: 35mm diameter, 13mm depth
  - Mounting hole: 22.5mm from panel edge (standard)
  - Installation PDF: https://www.blum.com/file-service/files/downloads/pdf/IFP_CLIP_top_BLUMOTION_en.pdf
- **TANDEM drawer system** — drawer slide holes
- **AVENTOS lift systems** — stay arm holes
- **Main catalog**: https://www.blum.com/
- **Technical support**: https://www.blum.com/us/en/planning/fitting-planning-tools/

### Hettich (Hardware)
- **InnoFit hinge system** — 26mm cup hole for mini hinges
- **Grass catalog** reference for shelf carrier systems
- **32mm grid shelf pin system specifications**
- **Catalog**: https://www.hettich.com/

### Grass GmbH (Movement Systems)
- **TIOMOS hinge system**
- **Nova Pro drawer system**
- **Technical downloads**: https://www.grass.eu/

### HAFELE (Fittings and Hardware)
- **Confirmat screw system**: 7mm body, 10mm head counterbore
- **KD fitting (cam-lock) systems**
- **Euro screw hole dimensions**: 5mm, 7mm, 10mm
- **Catalog**: https://www.hafele.com/

### Lamello (Joining Systems)
- **Bisco P-10 groove**: 3mm × 15mm slot
- **P-System groove**: 3mm × 15mm at 45° edge
- **Catalog**: https://www.lamello.com/

---

## Open Source Tools and Codebases

### DXF Processing
| Tool | URL | Use |
|------|-----|-----|
| ezdxf | https://ezdxf.readthedocs.io/ | Primary DXF library; Python |
| LibreCAD | https://librecad.org/ | Open source 2D CAD (DXF creation for testing) |
| QCAD | https://qcad.org/ | DXF editor with scripting |
| DXFlib (C++) | https://github.com/ribbon-studios/dxflib | Reference C++ DXF parser |

### CAD/CAM Systems
| Tool | URL | Use |
|------|-----|-----|
| FreeCAD | https://www.freecad.org/ | Open source 3D CAD; Path workbench for CAM |
| OpenCascade | https://www.opencascade.com/ | B-rep kernel; STEP support |
| CadQuery | https://cadquery.readthedocs.io/ | Pythonic CAD; used for synthetic generation |
| OpenSCAD | https://openscad.org/ | Programmatic CSG CAD |

### CNC/CAM Systems
| Tool | URL | Use |
|------|-----|-----|
| LinuxCNC | https://linuxcnc.org/ | Open source CNC controller + G-code reference |
| OpenCAMLib | https://github.com/aewallin/opencamlib | CAM algorithm library (C++/Python) |
| CAMotics | https://camotics.org/ | G-code simulation |
| bCNC | https://github.com/vlachoudis/bCNC | Python CNC controller |
| Flatcam | https://bitbucket.org/jpcgt/flatcam | PCB/panel CAM in Python |
| ncviewer | https://ncviewer.com/ | G-code/DXF viewer (web) |

### Geometry / Graph Libraries
| Tool | URL | Use |
|------|-----|-----|
| Shapely | https://shapely.readthedocs.io/ | 2D geometry operations |
| NetworkX | https://networkx.org/ | Graph data structures |
| scipy.spatial | https://docs.scipy.org/doc/scipy/reference/spatial.html | Spatial queries (KD-tree, Voronoi) |
| PyTorch Geometric | https://pytorch-geometric.readthedocs.io/ | GNN training |
| DGL | https://www.dgl.ai/ | Alternative GNN library |
| CGAL | https://www.cgal.org/ | Computational geometry algorithms (C++; reference) |

---

## Academic References

### Feature Recognition in CAD/CAM

| Paper | Citation | Key Contribution |
|-------|---------|----------------|
| Koch et al. 2019 | Koch, S., Matveev, A., et al. "ABC: A Big CAD Model Dataset For Geometric Deep Learning." CVPR 2019. | Large-scale CAD dataset; geometry diversity |
| Willis et al. 2021 | Willis, K.D., Pu, Y., et al. "Fusion 360 Gallery: A Dataset and Environment for Programmatic CAD Construction from Human Design Sequences." ACM TOG 2021. | CAD segmentation; feature labeling |
| Wu et al. 2021 | Wu, R., Xiao, C., Zheng, C. "DeepCAD: A Deep Generative Network for Computer-Aided Design Models." ICCV 2021. | Generative CAD; sequential construction |
| Shi et al. 2020 | Shi, P., Zhao, F., Chen, J. "Manufacturing Feature Recognition with Machine Learning: State of the Art and Future Challenges." Proc. Inst. Mech. Eng. B 2020. | Survey of ML for feature recognition |
| Sunil & Pande 2009 | Sunil, G., Pande, S.S. "Automatic Recognition of Machining Features Using Artificial Neural Network." Int. J. Mfg. Tech. 2009. | Early ML for feature recognition |
| Woo & Kang 2002 | Woo, Y., Kang, S. "Feature-based Design of Mold Base Parts Using Design by Analogy." CIRP Ann. 2002. | Manufacturing feature semantics |

### Graph Neural Networks

| Paper | Citation | Key Contribution |
|-------|---------|----------------|
| Hamilton et al. 2017 | Hamilton, W.L., Ying, R., Leskovec, J. "Inductive Representation Learning on Large Graphs." NeurIPS 2017. arXiv:1706.02216 | GraphSAGE: inductive GNN |
| Veličković et al. 2018 | Veličković, P., et al. "Graph Attention Networks." ICLR 2018. arXiv:1710.10903 | GAT: attention-based GNN |
| Kipf & Welling 2016 | Kipf, T.N., Welling, M. "Variational Graph Auto-Encoders." NIPS Workshop 2016. arXiv:1611.07308 | VGAE: generative graph models |
| Xu et al. 2019 | Xu, K., et al. "How Powerful are Graph Neural Networks?" ICLR 2019. arXiv:1810.00826 | GIN: expressiveness analysis |
| Scarselli et al. 2009 | Scarselli, F., et al. "The Graph Neural Network Model." IEEE Trans. Neural Networks 2009. | Original GNN formulation |

### Manufacturing AI Research

| Paper | Citation | Key Contribution |
|-------|---------|----------------|
| Cao et al. 2020 | Cao, X., et al. "Intelligent process planning and machining feature recognition with deep learning." IJAMT 2020. | Deep learning for machining features |
| Zhang et al. 2018 | Zhang, X., et al. "Graph convolution networks for manufacturing feature recognition." CAD 2022. | GNN applied to CAD features |
| Bougouffa & Hamdi 2018 | Bougouffa, S., Hamdi, M. "Ontology-based approach for knowledge representation in manufacturing process." 2018. | Manufacturing ontology design |

### Manufacturability Analysis

| Paper | Citation | Key Contribution |
|-------|---------|----------------|
| Boothroyd et al. | Boothroyd, G., Dewhurst, P., Knight, W.A. "Product Design for Manufacture and Assembly." CRC Press, 3rd ed. 2010. | DFM/DFA framework |
| Bralla 1999 | Bralla, J.G. "Design for Manufacturability Handbook." 2nd ed. McGraw-Hill 1999. | Comprehensive DFM reference |

---

## Machining Handbooks

| Reference | Relevance |
|-----------|-----------|
| Machinery's Handbook, 31st Ed. (2020) | CNC milling fundamentals, tool geometry, tolerances. Industry standard reference. |
| ANSI/ASME Y14.5-2018 | Dimensioning and tolerancing. GD&T standard. |
| SME Manufacturing Engineering Handbook | Comprehensive manufacturing process reference |
| CNC Machining Handbook - Allen & Moretti | CNC tooling and process parameters |

---

## Domain Expansion Strategy

This section documents the extension path toward additional manufacturing domains post-hackathon.

### 2.5D CNC → 5-Axis Machining
- New requirement: 3D geometry (surfaces, not just 2D contours)
- New ontology terms: undercuts, complex surfaces, draft angles
- New validation rules: reach envelopes, collision avoidance
- Key standards: ISO 10303 (STEP), DMIS
- Key tools: OpenCascade, FreeCAD 5-axis path

### 2.5D CNC → Waterjet / Laser Cutting
- Similar: Still 2D profile cutting
- Different: No tool radius constraint (laser/waterjet has negligible kerf)
- New: Kerf compensation, heat-affected zone (laser), standoff distance (waterjet)
- Key standards: OSHA 1910.212 (machine guarding); ISO 11553 (laser safety)
- Key ontology additions: KERF_COMPENSATION, HEAT_AFFECTED_ZONE

### Panel → Sheet Metal
- Similar: 2.5D cutting of flat stock
- Different: Bending, forming, punching, springback
- New ontology: BEND_LINE, PUNCH_HOLE, EMBOSS, HEM
- Key standards: DIN 6935 (bending), ISO 2768-1 (sheet metal tolerances)
- Key tools: FreeCAD Sheet Metal workbench

### Subtractive → 3D Printing / Additive
- Completely different paradigm
- Separate ontology required
- Key considerations: support structures, layer orientation, infill patterns
- Standards: ASTM F2792 (additive manufacturing terminology)

---

## Reference Management

All references in rule YAML files should use the citation key format:
- ISO standards: `ISO-<number>-<year>` (e.g., `ISO-286-1-2010`)
- DIN standards: `DIN-<number>-<year>` (e.g., `DIN-68762-2002`)
- Academic papers: `<FirstAuthorSurname>-<Year>` (e.g., `Hamilton-2017`)
- Manufacturer docs: `<Manufacturer>-<System>-<Year>` (e.g., `Blum-CLIPtop-2022`)

This enables systematic citation tracking and future expert review.
