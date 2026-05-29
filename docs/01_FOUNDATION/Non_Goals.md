# Non-Goals & Out-of-Scope Boundaries

Version: v0.1.0  
Section: 01_FOUNDATION  

See also: [[01_FOUNDATION/Vision_and_Scope]], [[01_FOUNDATION/Manufacturing_Domain_Lock]]

---

## Purpose

This document explicitly enumerates what OMIM is NOT trying to do. Non-goals are as important as goals — they prevent scope creep, prevent misleading claims, and keep the project focused.

**Rule**: Any feature request, design decision, or implementation that touches a non-goal item must be rejected or deferred to a post-v0 milestone.

---

## System Non-Goals (OMIM Is NOT)

| OMIM Is NOT | Why This Matters |
|-------------|-----------------|
| A CAM system | We do not generate G-code or toolpaths |
| A chatbot wrapper | There is no LLM at the center of this system |
| An autonomous machining AI | We do not control machines or make manufacturing decisions |
| A universal CAD format converter | We parse DXF for v0; other formats are extension points |
| A production-certified system | This is research infrastructure, not industrial software |
| A replacement for human machinists | It is a reasoning aid, not a human replacement |
| A simulation system | No physics simulation, no FEA, no toolpath simulation |
| A nesting optimizer | Nesting is recognized but not optimized in v0 |
| An ERP/MES system | No production scheduling, no inventory management |
| A real-time controller | No machine communication in v0 |

---

## Technical Non-Goals (v0 Only)

### What Validation Does NOT Cover

OMIM v0.1 validation is geometric manufacturability approximation. It explicitly does NOT validate:

| Not Validated | Why |
|-------------|-----|
| Fixturing adequacy | Requires machine knowledge, tooling, part weight |
| Tool deflection | Requires FEA / physics simulation |
| Machine rigidity | Machine-specific, dynamic analysis required |
| Material behavior | Chipload, tearout, moisture variation — material science |
| Operation ordering | Requires process planning domain knowledge |
| Feeds and speeds | Machine-specific; cannot infer from DXF |
| Coolant / chip evacuation | Machine and pocket-geometry dependent |
| Thermal effects | Requires heat transfer modeling |

A panel that passes OMIM validation may still fail to machine correctly in a specific shop with specific tooling. A panel that fails OMIM validation should be treated as a strong warning, not a certainty of failure.

---

## Manufacturing Domain Non-Goals (v0)

These domains are explicitly out of scope for v0 and must NOT be implemented:

| Out of Scope | Why |
|-------------|-----|
| 5-axis machining | Different constraint model entirely |
| Waterjet / laser / plasma cutting | Different physics, different rules |
| 3D printing / additive manufacturing | Fundamentally different domain |
| Robotic manufacturing | Requires motion planning, kinematics |
| Sheet metal forming | Bending, forming, punching — different ontology |
| G-code generation | Full CAM scope — separate product |
| Toolpath simulation | Physics simulation, out of budget |
| CAM toolpath optimization | Requires deep CAM knowledge |
| Multi-machine coordination | Scheduling problem, separate domain |
| Edge banding / post-processing | Post-routing operations; not representable in 2D DXF |
| STP/STEP/IGES format support | Additional parsers, not needed for v0 |
| Solid wood grain anisotropy | Material complexity beyond panel-grade composites |

---

## Architecture Non-Goals (v0)

### Prohibited During Hackathon
- Distributed systems or microservices
- Kubernetes, Docker Swarm, or container orchestration
- Cloud databases (SQLite, JSON files, or Parquet only)
- Authentication or authorization systems
- Real-time streaming pipelines
- Production deployment hardening
- Horizontal scaling infrastructure

### Prohibited Claims
- "OMIM validates real-world manufacturability" — it validates against programmed rules
- "OMIM can identify all manufacturing features" — only ontology v0.1.0 features are detectable
- "OMIM outputs can be used directly for CNC programming" — human review required
- "Synthetic data matches real manufacturing data distribution" — domain gap is expected
- "Models trained on synthetic data deploy to production" — research infrastructure only

---

## Ontology Non-Goals

The v0.1.0 ontology intentionally does NOT cover:

- Assembly context (how panels connect to each other)
- Tolerance stack-up analysis
- Material grain direction effects
- Fixturing or workholding
- Economic cost modeling
- Time/cycle analysis
- Quality control inspection features

Adding these would require a fundamentally different data model than what DXF provides.

---

## ML Non-Goals

- OMIM does not train production-grade manufacturing AI models
- OMIM does not claim to replace domain expert judgment
- OMIM does not use LLMs for manufacturing reasoning (LLMs hallucinate manufacturing facts)
- OMIM does not train models on proprietary shop data without explicit permission

---

## Post-Hackathon Extension Points (Architecture Must Support, Not Implement)

The architecture must NOT hardcode furniture-only assumptions. Abstraction boundaries must be clean enough that a new domain can be added by:
1. Adding a new ontology YAML file
2. Adding new validator rules
3. Adding a new parser module

Without touching core infrastructure. These are extension points, not v0 deliverables.

---

## Anti-Perfectionism Triggers

These exist specifically to prevent rabbit holes that consume the hackathon window:

| Trigger | Required Action |
|---------|----------------|
| Stuck on ontology term naming > 20 minutes | Pick the ISO term or most common industry term; move on |
| Stuck on graph schema detail > 30 minutes | Default to NetworkX + JSON serialization; move on |
| Validation rule is ambiguous | Mark `confidence: heuristic`, document assumption, move on |
| ML not converging | Cut ML scope; mark as v0.2 extension; deliver deterministic pipeline |
| Parser fails on edge-case DXF | Log failure; skip file; move on |
| Demo UI looks bad | Ship CLI demo instead; move on |

**The single most important rule:**

> If improving this system does NOT unblock another system, STOP.

---

## Time Hard Limits Per Subsystem

Maximum time allocations. STOP when the subsystem meets acceptance tests, even if time remains.

| Subsystem | Max Hours | Hard Stop Condition |
|-----------|-----------|---------------------|
| Ontology finalization | 3h | Core panel features representable |
| DXF parser | 4h | 90%+ test DXFs parse correctly |
| MGG builder | 4h | Graph roundtrips correctly |
| Validation engine (Layer 1+2) | 4h | 10+ manufacturing violations detectable |
| Provenance system | 2h | Every label is traceable |
| Semantic layer | 4h | Common furniture features infer reasonably |
| Dataset generator | 4h | 1000+ valid samples generate |
| Benchmark suite | 2h | 4 benchmark task definitions complete |
| ML integration | 3h | Basic GNN trains without error |
| Documentation + packaging | 2h | README, examples, dataset README exist |

The project is still successful if the first five subsystems (Ontology, MGG, Parser, Validation, Provenance) are complete. The remaining subsystems are value-adds.

---

## Failure Recovery Protocol

If more than 2 hours are spent on a single unexpected problem:

1. **STOP** work on that subsystem
2. **Document** the blocker in `BLOCKERS.md`
3. **Reduce scope** to the minimum viable version of that subsystem
4. **Tag** the current state: `git tag v0-checkpoint-N`
5. **Move forward** to the next system

```python
# BLOCKERS.md template
## BLOCKER: [subsystem name]
**Date**: 2026-05-29
**Time spent**: 2h 15min
**Problem**: [what is broken]
**Attempted fixes**: [what was tried]
**Decision**: Reduce scope to [minimal version]
**Impact**: [what is deferred or degraded]
```

---

## Performance Guards

| Parameter | Limit | Rationale |
|-----------|-------|-----------|
| Maximum graph nodes per MGG | 10,000 | Memory + performance bound |
| Maximum graph edges per MGG | 50,000 | Memory + performance bound |
| Dataset sample generation timeout | 30 seconds per sample | Batch generation feasibility |
| Validation engine timeout | 10 seconds per part | Interactive use feasibility |
| Maximum synthetic dataset size (v0) | 50,000 samples | Storage and compute budget |

Exceeding these limits is a signal to reduce complexity, not to optimize. Profile only if the pipeline is unusably slow after meeting acceptance tests.
