# Vision & Scope

Version: v0.1.0  
Section: 01_FOUNDATION  

See also: [[01_FOUNDATION/Authority_Hierarchy]], [[01_FOUNDATION/Non_Goals]], [[01_FOUNDATION/Manufacturing_Domain_Lock]], [[02_SCHEMA/MGG_Schema]]

---

## Mission Statement

OMIM — **Open Manufacturing Intelligence Middleware** — is an open-source, research-grade infrastructure layer for semantic manufacturing understanding.

Its thesis:

> Manufacturing AI currently lacks a robust semantic manufacturing representation layer with transparent provenance, deterministic validation, and benchmarkable synthetic manufacturing datasets. OMIM is that foundational infrastructure layer.

OMIM is NOT a product. It is NOT a chatbot, a CAM replacement, or an autonomous machining system. It is **research infrastructure** — the kind of foundational layer that future manufacturing AI systems can be built upon, evaluated against, and trained from.

---

## What OMIM Is

| OMIM Is | Description |
|---------|-------------|
| A manufacturing ontology | Formal, source-backed vocabulary for manufacturing concepts |
| A semantic representation layer | Graph-based canonical representation of manufacturing geometry and intent |
| A deterministic validation engine | Rule-based manufacturability checking with transparent provenance |
| A synthetic dataset infrastructure | Procedurally generated, labeled, benchmarkable manufacturing data |
| A benchmark suite | Standardized evaluation tasks for manufacturing AI systems |
| An open research standard | A peer-reviewable, extensible, collaborative infrastructure layer |

---

## Scientific Self-Description

The correct OMIM self-description in any presentation, paper, or README:

> OMIM is a **geometry-centric semantic inference infrastructure** for panel manufacturing. It transforms raw 2D DXF geometry into structured, provenance-tracked manufacturing feature graphs using deterministic rules derived from published standards and hardware catalogs.

This formulation:
- Names what OMIM actually does (inference from geometry)
- Names the constraint (geometry-centric — not full semantic ground truth)
- Names the domain (panel manufacturing)
- Names the mechanism (deterministic rules, published standards)

---

## What OMIM Is NOT

| OMIM Is NOT | Why This Matters |
|-------------|-----------------|
| A CAM system | OMIM does not generate G-code or toolpaths |
| A chatbot wrapper | There is no LLM at the center of this system |
| An autonomous machining AI | OMIM does not control machines or make manufacturing decisions |
| A universal CAD format converter | OMIM parses DXF for v0; other formats are extension points |
| A production-certified system | This is research infrastructure, not industrial software |
| A replacement for human machinists | OMIM is a reasoning aid, not a human replacement |
| "AI startup hype" | Every claim is backed by deterministic computation or sourced rules |

---

## Critical Scope Limitation: What DXF Actually Contains

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

---

## Relationship to STEP-NC / ISO 14649

Reviewers will ask: "STEP-NC already models machining features — why does OMIM exist?"

| Standard | What It Models | OMIM Relationship |
|----------|---------------|-------------------|
| **ISO 14649 / STEP-NC** | Machining features, operations, tooling, workingsteps, process plans | STEP-NC is the rich standard. OMIM is inference infrastructure for when STEP-NC data doesn't exist (which is most real-world DXF files). |
| **ISO 10303 AP238** | Full CNC process plan in STEP format | Future OMIM extension target; not v0 scope |
| **MTConnect** | Real-time machine data | Machine monitoring layer; orthogonal to OMIM |
| **OPC-UA Manufacturing** | Industrial equipment communication | System integration layer; post-hackathon |

**OMIM's position**: STEP-NC is what you get when you have a full CAM system and a cooperative manufacturer. OMIM is what you build when you have raw DXF and need to understand what it means. The majority of small-to-medium panel manufacturers work in DXF + operator knowledge; STEP-NC adoption in that segment is minimal.

---

## Long-Term Mission

The real long-term value:

1. **The manufacturing ontology** — a stable, peer-reviewable vocabulary for manufacturing features, operations, relationships, and constraints

2. **The graph representation** — the Manufacturing Geometry Graph (MGG) as a canonical, serializable, extensible representation layer that future systems can build on

3. **The synthetic dataset ecosystem** — a growing corpus of procedurally generated, labeled, benchmarkable manufacturing data

4. **The benchmark suite** — standardized evaluation tasks that allow fair comparison of manufacturing AI models

5. **The provenance infrastructure** — a system that makes every inference auditable, every label traceable, and every dataset sample reproducible

---

## Research Philosophy

### Deterministic-First Architecture

```
Geometric facts (Shapely/ezdxf)     ← ABSOLUTE AUTHORITY
         ↓
Deterministic manufacturing rules   ← HIGH AUTHORITY
         ↓
Heuristic pattern matching          ← MEDIUM AUTHORITY (annotated as such)
         ↓
Machine learning inference          ← LOWEST AUTHORITY (always confidence-bounded)
```

ML is secondary. It NEVER overrides geometry or deterministic rules.

### Scientific Credibility Requirements

OMIM must be:
- **Reviewable**: An expert machinist or manufacturing engineer must be able to read any rule, label, or inference and evaluate its validity
- **Reproducible**: Given the same input and seed, output is identical forever
- **Falsifiable**: Every claim has defined conditions under which it would be wrong
- **Provenance-aware**: Every output records how it was produced

---

## Scientific Positioning

OMIM positions itself in the gap between:

1. **CAD geometry research** (ABC Dataset, DeepCAD, Fusion360 Gallery) — geometric diversity but lacks manufacturing semantics
2. **CAM system logic** (FreeCAD, LinuxCNC, OpenCAMLib) — manufacturing rules but in opaque, non-ML-friendly form
3. **Manufacturing AI research** (feature recognition papers) — domain-specific and non-reproducible

| System/Dataset | What It Provides | What OMIM Adds |
|----------------|-----------------|----------------|
| ABC Dataset (Koch et al., CVPR 2019) | Large-scale CAD geometry | Manufacturing semantics, panel domain |
| DeepCAD (Wu et al., ICCV 2021) | CAD construction sequences | Manufacturing intent, validation |
| Fusion360 Gallery (Willis et al., TOG 2021) | CAD segmentation | Manufacturing feature ontology |
| FreeCAD / LinuxCNC | Rule logic | Externalized, versioned, citable rules |

---

## Open Source Philosophy

OMIM is intended to become an open, collaborative manufacturing intelligence research standard.

- Ontology changes require review (documented in [[01_FOUNDATION/Research_Positioning]])
- Rule additions require source citations
- Dataset releases require metadata completeness
- Contributions welcome under Apache 2.0 license
