# External Baselines & Positioning

Version: v0.1.0  
Section: 01_FOUNDATION  

See also: [[01_FOUNDATION/Vision_and_Scope]], [[01_FOUNDATION/Research_Positioning]], [[06_REAL_WORLD_GROUNDING/Real_DXF_Corpus_Sources]], [[06_REAL_WORLD_GROUNDING/Hardware_System_References]], [[09_BENCHMARKS/Benchmark_Tasks]]

---

## Purpose

This document positions OMIM against the external systems, datasets, and standards a reviewer will reach for first. It exists to answer one question honestly: *"This already exists elsewhere — why does OMIM?"*

Every comparison below follows the claim discipline of [[01_FOUNDATION/Research_Positioning]]: no overclaiming, every "what OMIM adds" column is bounded to what the system actually does. OMIM is a **geometric manufacturability approximation and dataset-infrastructure layer for 2.5D DXF panels** — it is not a CAM system, not a B-Rep kernel, and not a physics simulator. Where a comparable does something OMIM does not, this document says so plainly.

---

## 1. Manufacturing-Understanding Baselines

These are the systems that overlap with OMIM's territory: feature recognition, geometry kernels, CAM operation models, and machining-semantics standards.

| System | What it does | Relationship to OMIM / what OMIM adds |
|--------|--------------|---------------------------------------|
| **Analysis Situs** (analysissitus.org) | Open-source CAD feature-recognition + topology-graph framework built on OpenCASCADE. Extracts features and adjacency graphs from B-Rep solids. **The strongest comparable** for OMIM's graph + feature-recognition direction. | Analysis Situs operates on **B-Rep solids (3D CAD kernels)**, where rich topology and machining semantics already exist. OMIM targets **2D/2.5D DXF panel workflows where no B-Rep / STEP semantics exist** — only raw geometry. OMIM adds: deterministic, source-cited manufacturability validation; complete provenance per label; confidence-bounded inference; and standards-grounded synthetic dataset generation. OMIM does **not** do general 3D B-Rep feature recognition. |
| **OpenCASCADE / OCCT** (opencascade.com) | Industrial B-Rep geometry kernel; topology, adjacency, STEP/IGES processing. | OMIM borrows *concepts* (topology, adjacency, the graph view of geometry) but deliberately operates on lightweight **Shapely 2D geometry**, not a full kernel. Scoped to panel CNC. Not a competitor to OCCT; a different altitude and domain. |
| **FreeCAD Path Workbench** (freecad.org) | Open-source CAM. Generates real toolpaths and references manufacturing operations: drilling, profile, pocket, etc. | Cross-reference target for OMIM's operation taxonomy. OMIM's `DRILLING / CNC_ROUTING / PROFILE_CUTTING / NESTING` (see [[09_BENCHMARKS/Benchmark_Tasks]] BENCH-003) map onto FreeCAD Path's drill / profile / pocket operations. OMIM **infers which operations a panel requires**; it does **not** generate the toolpaths FreeCAD Path produces. |
| **Fusion 360 CAM** (autodesk.com) | Industrial reference for expected CAM behaviour: toolpaths, feeds/speeds, simulation. | Reference point for *what correct CAM does*, not a thing OMIM reproduces. **OMIM is NOT a CAM system.** It performs geometric manufacturability *approximation* (does this geometry violate a programmed rule?), not toolpath generation, feeds/speeds, or cutting simulation. This boundary is explicit and non-negotiable. |
| **STEP-NC (ISO 14649)** | When present, carries full machining semantics: features, operations, tooling, workingsteps, process plans. | STEP-NC is the rich standard for *when the data exists*. OMIM targets the common case where **only raw DXF exists** and machining intent must be inferred, not read. This is already stated in [[01_FOUNDATION/Vision_and_Scope]] ("Relationship to STEP-NC / ISO 14649") — cross-reference, not contradiction. ISO 10303 AP238 is a future extension target, not v0 scope. |

### The CAM boundary, stated once and plainly

OMIM produces a *manufacturability judgement* and an *operation requirement set* from geometry. It does not produce G-code, toolpaths, feeds, speeds, or a cutting simulation. A passing OMIM validation means "this geometry satisfies the programmed rules derived from standards" — it does **not** mean "this part is certifiably machinable on a specific machine in a specific shop." (See the Deterministic Validation Disclaimer in [[01_FOUNDATION/Research_Positioning]].)

---

## 2. The OMIM Differentiator

The framing that separates OMIM from the CAD/CAM and CAD-dataset landscape:

> Most CAD datasets give you **Geometry + Labels**.
> OMIM gives you **Geometry + Validation + Constraints + Provenance + Manufacturing Intent + Graph representation**.

| Layer | Typical CAD dataset (ABC, DeepCAD, Fusion360 Gallery) | OMIM |
|-------|-------------------------------------------------------|------|
| Geometry | ✓ (often 3D B-Rep / point cloud) | ✓ (2.5D DXF panel geometry) |
| Feature labels | ✓ (segmentation / class labels) | ✓ (feature class per node) |
| Deterministic manufacturability validation | ✗ | ✓ (source-cited rule engine) |
| Manufacturing constraints (catalog/standard) | ✗ | ✓ (Blum/Hettich/Häfele, EN/DIN) |
| Provenance per label (how it was produced) | ✗ | ✓ (every label traceable) |
| Manufacturing intent (operations required) | ✗ | ✓ (inferred operation set) |
| Graph representation (MGG) | partial / format-specific | ✓ (canonical, serializable) |
| Confidence bound on every inference | ✗ | ✓ (confidence + evidence) |

```
   CAD dataset:   [ Geometry ] ── [ Labels ]

   OMIM:          [ Geometry ]
                       │
                       ├── [ Graph representation (MGG) ]
                       ├── [ Feature intent / operations ]
                       ├── [ Deterministic validation ] ←─ standards-cited rules
                       ├── [ Constraints ] ←─ catalog ground truth
                       ├── [ Confidence + evidence ]
                       └── [ Provenance ] ←─ every label traceable
```

**Honest bound**: OMIM does not claim its labels are more *accurate* than a hand-annotated CAD dataset. It claims they are *more complete in kind* — validated, constrained, provenance-tracked, and intent-bearing — within the narrow panel-manufacturing domain.

---

## 3. Dataset Ground-Truth Trust Hierarchy

OMIM's labels are only as trustworthy as the sources behind them. The trust hierarchy is explicit, and the highest tier is not heuristic — it is published manufacturer catalog and standards data.

| Tier | Sources | Trust | Role in OMIM |
|------|---------|-------|--------------|
| **Tier 1 (Extremely High)** | Blum, Hettich, Häfele catalogs; the European **32mm System** (System 32 / Rasterbohr) | Authoritative spec — exact, not inferred | **These catalog specs ARE the labels.** Encoded in `src/omim/corpus/catalog_ground_truth.py`. |
| **Tier 1 (High)** | DIN furniture standards (DIN 7, DIN 68863, DIN 68840/68871); EN panel standards (EN 309 particleboard, EN 622-5 MDF) | Published standard | Panel thicknesses, dowel geometry, grid pitch. Also encoded in `catalog_ground_truth.py`. |
| Tier 2 (High) | Empirical profile from an ingested real DXF corpus, validated against Tier 1 | Real geometry, conformance-checked | Pending a real corpus (see §4). |
| Tier 3 (Low) | Community / unvetted corpora | License + annotation review required | Reference only. |

The exact values live in `src/omim/corpus/catalog_ground_truth.py` and are documented in [[06_REAL_WORLD_GROUNDING/Hardware_System_References]]. Representative encoded ground truth:

| Feature | Diameter | Edge / grid | Source |
|---------|----------|-------------|--------|
| `HINGE_CUP_HOLE` | 35.0 mm ±0.5 | 22.5 mm setback | Blum CLIP top 70.1900.AC; Hettich Intermat; Grass Tiomos |
| `SHELF_PIN_HOLE` | 5.0 mm ±0.5 | 32 mm grid, 37 mm setback | Häfele System 32 / Rasterbohr; DIN 68840 |
| `CONFIRMAT_HOLE` | 7.0 mm ±0.2 | 8–15 mm setback | Häfele Confirmat; DIN 68871 |
| `DOWEL_HOLE` | 8.0 / 10.0 mm ±0.1 | joint position | DIN 7 Part 1; DIN 68863 |
| `CAM_HOLE` | 15.0 mm ±0.3 | — | Häfele Rafix cam fitting |

**The key statement**: because all major European hinge makers converged on the same 35mm cup geometry, OMIM cannot distinguish *brand* from geometry — but it can verify *conformance to the shared standard*. These catalog specs are the ground truth against which both ingested corpora and OMIM's own synthetic output are checked. (See [[01_FOUNDATION/Research_Positioning]] for what this does and does not let OMIM claim — rules are research-grade, not industrially certified.)

---

## 4. Real DXF Corpus Sources

No large, license-clear, domain-matched real DXF corpus of panel manufacturing files exists publicly — that gap is the primary justification for OMIM's synthetic-first approach (see [[06_REAL_WORLD_GROUNDING/Real_DXF_Corpus_Sources]]). The candidate real sources, with the Tier framing from `data/grounding/README.md`:

| Source | URL | Domain match | Tier | OMIM status |
|--------|-----|--------------|------|-------------|
| **OpenBuilds** | openbuilds.com | Medium (CNC router / panel; mixed materials) | Tier 3 → 2 | Reference; CC BY (verify per file); annotation needed |
| **WikiHouse** | wikihouse.cc | Medium-High (open-source CNC-cut plywood building parts) | Tier 3 → 2 | Reference; ingest target |
| **OpenDesk** | opendesk.cc | High (open-source CNC furniture, CC BY-SA) | Tier 3 → 2 | Reference; ingest target |
| Existing / company cabinet DXFs | private | Highest (real production panels) | Tier 2 | Highest relevance once ingested |

The ingestion + conformance path is implemented in `src/omim/corpus/` (`ingest.py`, `distribution_extractor.py`, `validator.py`, `reference_profile.py`) and documented step-by-step in `data/grounding/README.md`.

**What ships today**: only the **catalog-derived (Tier 1) profile** (`data/grounding/catalog_reference_profile.json`) — every number seeded from manufacturer catalogs and EN/DIN standards. No real corpus has been ingested in this environment (no network access at build time). A Tier 2 empirical profile *replaces, but never deletes,* Tier 1; Tier 1 always remains the conformance reference.

---

## 5. The Defining Baseline Question

This is the headline acceptance criterion for the whole grounding thesis:

> **"Can OMIM reproduce valid cabinet manufacturing geometry that conforms to Blum/Hettich specifications and passes all deterministic validation rules?"**

This is **now an executable test**, not a slogan: `tests/test_grounding_claim.py`. It ties the thesis together end-to-end:

```
Manufacturing Standards ──► Generator ──► Validator        (all deterministic rules pass)
                                       └─► Corpus catalog conformance  (Blum/Hettich/Häfele/System 32)
```

The test enforces three things on an all-valid generated dataset:
1. **Every** generated "valid" panel passes **all** deterministic rules — geometry from standards is *verified* valid by the rule engine, not merely labelled valid.
2. The generated corpus, ingested as if it were real, **conforms** to manufacturer catalog specs (hole diameters, edge setbacks, the 32mm grid) within catalog tolerance.
3. The named standard features are actually present (35mm hinge cups, 5mm shelf pins) — conformance is not vacuous.

**If these pass**, the synthetic generator is grounded in real manufacturing reality (manufacturer catalogs), not producing arbitrary CAD shapes. That is the bounded, honest version of the claim — and it is checkable by anyone who runs the test.

---

## Boundaries (Read Before Citing This Document)

Per [[01_FOUNDATION/Research_Positioning]], every claim here is bounded:

- OMIM is **geometric approximation**, not physics-based or CAM simulation.
- OMIM is **2.5D panel scope only** — not general 3D B-Rep, not 5-axis, not sheet metal (those are documented extension points, not current capability).
- Passing validation means **conformance to the programmed v0.1.0 ruleset derived from standards** — not certified machinability on any specific machine.
- Catalog conformance means **geometry matches published catalog nominals within tolerance** — it does not identify the brand, and the rules are research-grade, not industrially certified.
- Analysis Situs is the closest external feature-recognition baseline, but it operates on B-Rep/3D; OMIM and Analysis Situs are **not** drop-in comparable.
