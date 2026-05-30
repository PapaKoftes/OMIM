# External Annotated Datasets — Verified Survey

Version: v0.1.0
Section: 06_REAL_WORLD_GROUNDING

See also: [[06_REAL_WORLD_GROUNDING/Real_DXF_Corpus_Sources]], [[01_FOUNDATION/External_Baselines]], [[10_IMPLEMENTATION/Training_Readiness_And_Review]]

> Web-verified (URLs + licenses checked, not memory) survey answering: *do annotated
> datasets exist that OMIM can reuse, and which adjacent standardized fields are the
> best expansion targets?* Headline: **for OMIM's exact problem (2.5D DXF cabinet-panel
> feature recognition) no usable labeled dataset exists** — confirmed independently by
> three search streams. But there are strong **method** templates and **expansion** targets.

---

## 1. For OMIM's current domain (2.5D DXF panel features)

### Verdict: zero drop-in datasets. The intersection "furniture panel × machining feature" is empty.

- Furniture ML datasets label **functional parts** (door / shelf / leg), never the machined
  features (5 mm shelf-pin hole, 35 mm hinge cup, dowel, groove). Verified on PartNet's actual
  `StorageFurniture-level-3` leaf labels — it stops at `hinge`/`handle` as assembled parts.
- Machining-feature datasets label **holes/slots/pockets** but only on **generic 3D mechanical
  B-Rep parts**, not 2.5D furniture panels, and not DXF.
- This gap is the justification for OMIM's synthetic generator — there is no shortcut.

### (a) Closest by FEATURE TAXONOMY (3D machining features — reuse as taxonomy/pretraining, not DXF)
| Dataset | Size | Format | Labels | License | URL |
|---|---|---|---|---|---|
| **MFCAD++** ⭐ | 59,655 | B-Rep STEP | per-face, ~25 classes (holes/pockets/slots/chamfers/steps) | **CC BY** | https://pure.qub.ac.uk/en/datasets/mfcad-dataset-dataset-for-paper-hierarchical-cadnet-learning-from/ |
| MFCAD | ~15,488 | STEP | per-face, 16 classes (planar) | **MIT** | https://github.com/hducg/MFCAD |
| CADSynth | 100,000 | STEP + JSON + B-Rep graph | feature labels | verify | https://www.scidb.cn/en/detail?dataSetId=931c088fd44f4d3e82891a5180f10d90 |
| FeatureNet | 24,000 | STL/voxel | 1 class/model, 24 classes | GPL-3.0 | https://github.com/madlabub/Machining-feature-dataset |

**Use:** align OMIM's label schema to MFCAD++'s feature definitions (a credible published standard);
optional pretraining **only if** OMIM ever lifts to 3D. Not directly ingestible (3D STEP ≠ 2D DXF).

### (b) Closest by METHOD (2D vector CAD → semantic graph — reuse the architecture, not the data)
| Dataset | Task | Size | License | URL |
|---|---|---|---|---|
| **FloorPlanCAD** ⭐ | panoptic symbol spotting on vector primitives (30 classes) | ~15,663 | **CC BY-NC** | https://floorplancad.github.io/ |
| ArchCAD-400K | panoptic spotting, auto-annotated from CAD layer metadata (27 classes) | 413,062 chunks | "open" (verify) | https://archiai-lab.github.io/ArchCAD.github.io/ |
| ResPlan | vector + graph floor plans, open pipeline | 17,000 | **MIT** | https://github.com/m-agour/ResPlan |
| CubiCasa5K | polygon segmentation on plans (80+ classes) | 5,000 | CC BY-NC | https://github.com/CubiCasa/CubiCasa5k |
| SESYD | synthetic vector symbol spotting (ancestor of the task) | large | research | http://mathieu.delalandre.free.fr/projects/sesyd/ |

**FloorPlanCAD defines OMIM's exact task** (per-primitive class + instance grouping on vector CAD).
Data is buildings (unusable for panels) and NC-licensed, but the **task framing + GCN/GAT graph head
+ ArchCAD's "bootstrap labels from CAD layer/block metadata" trick** transfer directly. **ResPlan**
(MIT) is the most legally reusable vector→graph *pipeline* template.

### (c) Real UNLABELED cabinet DXFs (right format, no labels — hold-out only)
| Source | Format | Size | License | Note |
|---|---|---|---|---|
| AtFAB | **DXF** | ~13 designs | CC non-commercial | real tab/slot joinery; email-gated |
| OpenDesk | **DXF** + PDF | few dozen | ambiguous/mixed | license risk; GitHub mirrors exist |
| WikiHouse | DWG/IFC | handful | CC-BY-SA | architectural scale, not cabinet panels |

**Use:** a small real-world **parser sanity-check + hand-labeled hold-out** (Phase 2 of the watertight
plan), never a training corpus. You must annotate them yourself.

---

## 2. Best EXPANSION targets (other standardized fields OMIM's thesis fits)

OMIM = *standards-as-deterministic-rules + graph + provenance + validator-gated synthetic data.*
Ranked by fit (standardized **and** has permissive data **and** rules are machine-checkable **and**
real whitespace):

| Rank | Field | Standard | Public annotated dataset | License | Fit |
|---|---|---|---|---|---|
| **1** | **P&ID digitization** | **ANSI/ISA-5.1-2024** | **PID2Graph** (real, full-graph: symbols+connections) | **CC BY-SA 4.0** | **HIGH** |
| **2** | **Sheet-metal bending DFM** | DFM bend rules (K-factor, bend radius) | **BenDFM** (20k, validator-labeled, folded+flat) | verify | **MED-HIGH** |
| 3 | BIM/IFC compliance | **ISO 16739 + IDS** (computer-interpretable) | IFC samples; fragmented benchmarks | open/varies | HIGH method |
| — | GD&T from drawings | ASME Y14.5 / ISO 286 | ~1,367 drawings (likely in-house) | unconfirmed | MED (OCR problem) |
| — | PCB design rules | IPC-2221 / IPC-A-600 | DeepPCB, FICS-PCB (defect/visual) | mixed (some NC-ND) | TRAP (DRC commoditized) |
| — | Welding symbols | AWS A2.4 / ISO 2553 | none found | — | TRAP (no data) |
| — | GIS/cadastral | INSPIRE / parcel fabric | abundant | open | TRAP (commercial-owned) |

Load-bearing URLs: PID2Graph https://zenodo.org/records/14803338 (paper https://arxiv.org/abs/2411.13929) ·
BenDFM https://arxiv.org/abs/2603.13102 · buildingSMART IDS https://github.com/buildingSMART/IDS ·
DeepPCB https://github.com/tangsanli5201/DeepPCB · FICS-PCB https://physicaldb.ece.ufl.edu

### Why P&ID is the standout
A P&ID **is** a graph; ISA-5.1 is a precise, enumerated symbol/tag grammar (deterministic rules);
tag syntax + loop completeness are graph constraints (validation); synthetic generation is already
field practice (Digitize-PID); and **a real-world, graph-annotated, permissively-licensed dataset
already exists** (PID2Graph). Almost nothing in OMIM's architecture needs reshaping to fit it.

### Why BenDFM is the sleeper
It is **literally validator-gated synthetic CAD data** (manufacturable vs not), pairs folded + unfolded
geometry, and its authors **independently conclude graph representations win** — an external empirical
endorsement of OMIM's representation choice. Borrow its DFM-labeling methodology.

---

## 3. What this means for OMIM (honest)

1. **Current domain:** no dataset rescues you. The synthetic generator + a small hand-labeled
   AtFAB/OpenDesk hold-out + MFCAD++ as a taxonomy reference is the correct, evidence-backed plan.
2. **Method credibility:** cite FloorPlanCAD/MFCAD++ as proof the approach (learn features from CAD
   geometry; panoptic spotting on vector primitives) is established and works — OMIM is panel-domain
   instance of a proven paradigm, not a novel gamble.
3. **Expansion:** **P&ID (ISA-5.1 + PID2Graph)** is the single best second domain — graph-native,
   formally standardized, real permissive data. **Sheet-metal DFM (BenDFM)** is the best methodology
   match. Both are far stronger bets than chasing 3D B-Rep (covered in [[01_FOUNDATION/External_Baselines]]).

### Licensing caution (verify before any commercial use)
CC BY-NC (FloorPlanCAD, CubiCasa, FICS-PCB, AtFAB), redistribution-locked (RPLAN, R2V rasters),
and source-platform terms on scraped CAD (ABC/DeepCAD/MCB via Onshape/TraceParts) all constrain reuse.
The permissive ones worth leaning on: **MFCAD++ (CC BY), MFCAD (MIT), ResPlan (MIT), PID2Graph (CC BY-SA).**
