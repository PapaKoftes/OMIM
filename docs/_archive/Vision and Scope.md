# Vision and Scope

See also: [[What Is OMIM]], [[Hard Limits and Constraints]], [[Full System Architecture]]

---

## Mission Statement

OMIM — **Open Manufacturing Intelligence Middleware** — is an open-source, research-grade infrastructure layer for semantic manufacturing understanding.

Its thesis:

> Manufacturing AI currently lacks a robust semantic manufacturing representation layer with transparent provenance, deterministic validation, and benchmarkable synthetic manufacturing datasets. OMIM is that foundational infrastructure layer.

OMIM is NOT a product. It is NOT a chatbot, a CAM replacement, or an autonomous machining system. It is a **research infrastructure** — the kind of foundational layer that future manufacturing AI systems can be built upon, evaluated against, and trained from.

---

## What OMIM Is

| OMIM Is | Description |
|---------|-------------|
| A manufacturing ontology | A formal, source-backed vocabulary for manufacturing concepts |
| A semantic representation layer | A graph-based canonical representation of manufacturing geometry and intent |
| A deterministic validation engine | Rule-based manufacturability checking with transparent provenance |
| A synthetic dataset infrastructure | Procedurally generated, labeled, benchmarkable manufacturing data |
| A benchmark suite | Standardized evaluation tasks for manufacturing AI systems |
| An open research standard | A peer-reviewable, extensible, collaborative infrastructure layer |

---

## What OMIM Is NOT

| OMIM Is NOT | Why This Matters |
|-------------|-----------------|
| A CAM system | We do not generate G-code or toolpaths |
| A chatbot wrapper | There is no LLM at the center of this system |
| An autonomous machining AI | We do not control machines or make manufacturing decisions |
| A universal CAD format converter | We parse DXF for v0; other formats are extension points |
| A production-certified system | This is research infrastructure, not industrial software |
| A replacement for human machinists | It is a reasoning aid, not a human replacement |
| "AI startup hype" | Every claim is backed by deterministic computation or sourced rules |

---

## Long-Term Mission

The real long-term value of OMIM is not the hackathon demo.

The real value is:

1. **The manufacturing ontology** — a stable, peer-reviewable vocabulary for manufacturing features, operations, relationships, and constraints

2. **The graph representation** — the Manufacturing Geometry Graph (MGG) as a canonical, serializable, extensible representation layer that future systems can build on

3. **The synthetic dataset ecosystem** — a growing corpus of procedurally generated, labeled, benchmarkable manufacturing data that manufacturing AI researchers can use

4. **The benchmark suite** — standardized evaluation tasks that allow fair comparison of manufacturing AI models

5. **The provenance infrastructure** — a system that makes every inference auditable, every label traceable, and every dataset sample reproducible

Together, these constitute the kind of foundational infrastructure that allows the field of manufacturing AI to mature beyond bespoke, opaque, unverifiable systems.

---

## Critical Scope Limitation: What DXF Actually Contains

This is a non-negotiable epistemic constraint on OMIM's claims.

**DXF is a geometry exchange format.** It reliably contains:
- 2D/3D geometric entities (lines, circles, arcs, polylines)
- Layer names (by convention; not standardized)
- Block references (reusable geometry)
- Basic annotations (text, dimensions — informational only)

**DXF does NOT reliably contain:**
- Feature intent (why was this hole drilled?)
- Tolerances (what precision is required?)
- Machining history (what operations were already applied?)
- Operation semantics (is this a drill pass or a boring pass?)
- Material specification (what is this made of?)
- Assembly context (what does this panel join to?)
- Setup information (how is the part fixtured?)

**Consequence for OMIM**: Everything above the geometry layer is *inference*, not *reading*. OMIM infers manufacturing intent from geometry patterns — it does not decode manufacturing truth from the file. This must be stated explicitly in any presentation or publication.

**Correct positioning**: OMIM is a **geometry-centric semantic inference infrastructure**. Not "full manufacturing understanding from DXF."

### Relationship to STEP-NC and Richer Standards

The research community has explored richer manufacturing data models. OMIM must be positioned relative to these explicitly or reviewers will ask:

| Standard | What It Models | OMIM Relationship |
|----------|---------------|-------------------|
| **ISO 14649 / STEP-NC** | Machining features, operations, tooling, workingsteps, process plans | STEP-NC is the rich standard. OMIM is inference infrastructure for when STEP-NC data doesn't exist (which is most real-world DXF files). |
| **ISO 10303 AP238** | Full CNC process plan in STEP format | Future OMIM extension target; not v0 scope |
| **MTConnect** | Real-time machine data | Machine monitoring layer; orthogonal to OMIM |
| **OPC-UA Manufacturing** | Industrial equipment communication | System integration layer; post-hackathon |

**OMIM does NOT replace STEP-NC.** OMIM is what you build when you have raw geometry (DXF) and need to infer manufacturing meaning without a rich process plan. It fills the gap between raw CAD geometry and the semantic richness of STEP-NC — using inference rather than explicit encoding.

This positioning avoids the reviewer objection: *"STEP-NC already models machining features, so why does OMIM exist?"*  
Answer: **Because 99% of panel manufacturing shops work in DXF and have never heard of STEP-NC.**

---

## Research Philosophy

### Deterministic-First Architecture

The system is built on a strict hierarchy of authority:

```
Geometric facts (Shapely/ezdxf)     ← ABSOLUTE AUTHORITY
         ↓
Deterministic manufacturing rules   ← HIGH AUTHORITY
         ↓
Heuristic pattern matching          ← MEDIUM AUTHORITY (annotated as such)
         ↓
Machine learning inference          ← LOWEST AUTHORITY (always confidence-bounded)
```

ML is secondary. It NEVER overrides geometry or deterministic rules. It only:
- Infers semantic hypotheses when heuristics are ambiguous
- Ranks competing interpretations
- Estimates confidence for soft classifications

### Scientific Credibility

OMIM must be:
- **Reviewable**: An expert machinist or manufacturing engineer must be able to read any rule, label, or inference and evaluate its validity
- **Reproducible**: Given the same input and seed, output is identical forever
- **Falsifiable**: Every claim has defined conditions under which it would be wrong
- **Provenance-aware**: Every output records how it was produced

### Standards-Based Rules

Manufacturing rules come from:
- ISO standards (ISO 286, ISO 2768, ISO 10303)
- DIN standards (DIN 68xxx panel woodworking)
- Published machining handbooks (Machinery's Handbook, etc.)
- Open-source CAM system logic (LinuxCNC, OpenCAMLib)
- Academic manufacturing research (CIRP, IJAMT, CAD journal)

Custom heuristics are a last resort and must be documented as such.

---

## Domain Scope

### v0 (Hackathon Scope)

| Parameter | Value |
|-----------|-------|
| File format | DXF (2D) |
| Manufacturing domain | Panel manufacturing (furniture/cabinet) |
| Machining type | 2.5D CNC routing + drilling |
| Material | Wood-based panels (MDF, particleboard, plywood) |
| Standard panel sizes | Up to 3600mm × 2100mm |
| Standard thicknesses | 9–25mm (18mm default) |
| Feature set | See [[Manufacturing Ontology]] |

### Future Extension (Architecture Must Support, Not Implement)

| Domain | Notes |
|--------|-------|
| 5-axis machining | Requires different constraint model, 3D geometry |
| Waterjet cutting | 2D profiles, different material model |
| Laser cutting | Similar to waterjet, speed/focus parameters |
| 3D printing / additive | Completely different ontology |
| Sheet metal | Bending, forming, different feature set |
| Robotic manufacturing | Motion planning, kinematics out of scope |

The architecture must NOT hardcode furniture-only assumptions. Abstraction boundaries must be clean enough that a new domain can be added by:
1. Adding a new ontology YAML file
2. Adding new validator rules
3. Adding a new parser module

Without touching core infrastructure.

---

## Scientific Positioning

OMIM positions itself in the gap between:

1. **CAD geometry research** (ABC Dataset, DeepCAD, Fusion360 Gallery) — which provides geometric diversity but lacks manufacturing semantics

2. **CAM system logic** (FreeCAD, LinuxCNC, OpenCAMLib) — which contains manufacturing rules but in opaque, non-ML-friendly form

3. **Manufacturing AI research** (feature recognition papers, machining optimization) — which tends to be domain-specific and non-reproducible

OMIM bridges this gap by providing:
- Semantic annotation atop CAD geometry
- Transparent, externalized manufacturing rules
- Reproducible, benchmarkable datasets
- An open representation layer other systems can build on

### Relevant Prior Work

| System/Dataset | What It Provides | What OMIM Adds |
|----------------|-----------------|----------------|
| ABC Dataset (Koch et al., CVPR 2019) | Large-scale CAD geometry | Manufacturing semantics, panel domain |
| DeepCAD (Wu et al., ICCV 2021) | CAD construction sequences | Manufacturing intent, validation |
| Fusion360 Gallery (Willis et al., TOG 2021) | CAD segmentation | Manufacturing feature ontology |
| MachiningFeatureDataset | Machining feature labels | Provenance, panel focus, synthetic gen |
| FreeCAD / LinuxCNC | Rule logic | Externalized, versioned, citable rules |

---

## Open Source Philosophy

OMIM is intended to become an open, collaborative manufacturing intelligence research standard.

The infrastructure itself being public is the point. The future commercial value in the manufacturing space lies in:
- Industrial deployment integrations
- Machine-specific optimization (proprietary knowledge)
- Production heuristics (proprietary data)
- Operational expertise (human knowledge)

None of those are things OMIM tries to capture. OMIM captures the open layer: the representation, the ontology, the rules, the benchmarks.

### Governance Philosophy
- Ontology changes require review (documented in [[Research direction]])
- Rule additions require source citations
- Dataset releases require metadata completeness
- Contributions welcome under open source license (Apache 2.0 proposed)
