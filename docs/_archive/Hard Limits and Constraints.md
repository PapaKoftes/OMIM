# Hard Limits & Constraints

These are inviolable boundaries. When in doubt, cut scope — do not compromise these rules.

See also: [[What Is OMIM]], [[Execution Roadmap]], [[Vision and Scope]]

---

## Scope Locks — What Is In Scope for the Hackathon

| Domain | Included |
|--------|----------|
| File format | DXF (2D entities only) |
| Manufacturing domain | Panel manufacturing (furniture/cabinet grade) |
| Machining type | 2.5D CNC routing/milling |
| Axis assumption | 3-axis (X, Y, Z) |
| Panel geometry | Rectangular panels with 2D features |
| Operations | Drilling, routing, nesting, contouring |
| Workflow | Nested CNC cutting from sheet stock |

---

## Scope Locks — What Is Out of Scope for the Hackathon

These MAY have extension points defined in architecture but MUST NOT be implemented:

| Out of Scope | Why |
|-------------|-----|
| 5-axis machining | Different constraint model entirely |
| Waterjet / laser / plasma | Different physics, different rules |
| 3D printing / additive | Fundamentally different domain |
| Robotic manufacturing | Requires motion planning, kinematics |
| G-code generation | Full CAM scope — separate product |
| Toolpath simulation | Physics simulation, out of budget |
| CAM toolpath optimization | Requires deep CAM knowledge |
| Multi-machine coordination | Scheduling problem, separate domain |
| ERP/MES integration | Enterprise integration, post-hackathon |
| Real CNC controller communication | Hardware interface, post-hackathon |
| Photorealistic rendering | No value for research infrastructure |
| Edge banding / post-processing operations | Post-processing, not primary manufacturing |
| STP/STEP/IGES format support | Additional parsers, not needed for v0 |

---

## Technical Hard Limits

### DXF Constraints
| Parameter | Limit | Source |
|-----------|-------|--------|
| DXF versions supported | AC1015 (R2000) through AC1032 (R2018) | ezdxf library support range |
| Geometry dimensionality | 2D entities only (Z ignored or forced = 0) | 2.5D workflow assumption |
| Supported entity types | LINE, CIRCLE, ARC, LWPOLYLINE, POLYLINE, SPLINE (approximated) | Core panel geometry primitives |
| Maximum panel dimensions | 3600mm × 2100mm | Standard CNC nesting table |
| Maximum file size | 50MB | Parser memory guard |

### Feature Size Constraints
| Parameter | Minimum | Source |
|-----------|---------|--------|
| Hole diameter | 3mm | Minimum practical drill bit for panel work |
| Pocket width | 6mm (= 2 × minimum tool radius) | Tool geometry constraint |
| Corner radius in pockets | ≥ tool_radius (typically 3mm) | Fundamental CNC routing constraint |
| Edge clearance for through-features | 8mm from panel edge | Common shop practice / DIN 68 panel work |
| Drill-to-drill spacing (wood) | 3mm + diameter | Structural integrity |
| Drill-to-drill spacing (MDF/composite) | 5mm + diameter | Material fragility |
| Minimum slot width | = tool_diameter | Cannot route narrower than tool |
| Minimum blind pocket depth | 3mm | Practical milling floor |
| Maximum blind feature depth | 0.75 × panel_thickness | Structural integrity |

### Standard Panel Thicknesses (Reference Values)
- 9mm, 12mm, 15mm, 18mm, 22mm, 25mm (EN 309 particleboard)
- 18mm is the default assumption unless DXF metadata specifies otherwise

### Performance Guards
| Parameter | Limit |
|-----------|-------|
| Maximum graph nodes per MGG | 10,000 |
| Maximum graph edges per MGG | 50,000 |
| Dataset sample generation timeout | 30 seconds per sample |
| Validation engine timeout | 10 seconds per part |
| Maximum synthetic dataset size (hackathon) | 50,000 samples |

---

## Architecture Hard Limits

### Prohibited During Hackathon
- No distributed systems
- No microservices or service mesh
- No Kubernetes, Docker Swarm, or container orchestration
- No cloud databases (SQLite, JSON files, or Parquet only)
- No authentication or authorization systems
- No real-time streaming pipelines
- No production deployment hardening
- No horizontal scaling infrastructure

### Required Architecture Invariants (Non-Negotiable)
1. **Determinism**: Same input + same seed → same output, always, forever
2. **ML subordination**: ML output NEVER overrides deterministic geometry facts
3. **Confidence requirement**: Every semantic label MUST carry confidence score and evidence list
4. **Rule traceability**: Every rule invocation MUST log rule ID + rule version + timestamp
5. **Provenance completeness**: Provenance MUST survive serialization round-trip (JSON → JSON identical)
6. **Separation of concerns**: Geometry validation layer has no knowledge of semantic layer
7. **No hidden state**: No global mutable state between pipeline stages

---

## Time Hard Limits

These are the maximum allocations. STOP when the subsystem meets acceptance tests, even if time remains.

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
| Demo integration | 2h | End-to-end pipeline works in browser/CLI |
| Documentation + packaging | 2h | README, examples, dataset README exist |
| **Total** | **~34h** | **Within 48-hour hackathon window** |

---

## Quality Hard Limits

These are the minimum quality gates. Nothing ships below these thresholds:

- No synthetic data sample without complete provenance metadata
- No semantic label without confidence score in [0.0, 1.0]
- No rule invocation without source citation or explicit justification
- No public claim not directly verifiable from system outputs
- No TODO/FIXME in core data schemas (implementation code is acceptable)
- No `assert False` or silent exception swallowing in validation pipeline

---

## Anti-Perfectionism Limits

These exist specifically to prevent rabbit holes:

| Trigger | Action |
|---------|--------|
| Stuck on ontology term naming > 20 minutes | Pick the ISO term or the most common industry term, move on |
| Stuck on graph schema detail > 30 minutes | Default to NetworkX + JSON serialization, move on |
| Validation rule is ambiguous | Mark as `confidence: heuristic`, document assumption, move on |
| ML not converging | Cut ML scope, mark as v0.2 extension, deliver deterministic pipeline |
| Parser fails on edge case DXF | Log failure, skip file, move on |
| Demo UI looks bad | Ship CLI demo instead, move on |

**The single most important rule:**

> If improving this system does NOT unblock another system, STOP.

---

## Failure Recovery Protocol

If more than 2 hours are spent on a single unexpected problem:

1. **STOP** work on that subsystem
2. **Document** the blocker in a `BLOCKERS.md` file
3. **Reduce scope** to minimum viable version of that subsystem
4. **Tag** the current state (`git tag v0-checkpoint-N`)
5. **Move forward** to the next system

The project is still successful if Systems 1–5 (Ontology, MGG, Parser, Validation, Provenance) are complete. Systems 6–9 are value-adds.

---

## Dependency Graph (Build Order)

```
[Ontology] ──────────────────────────────────────────────────────┐
                                                                   ↓
[DXF Parser] ─→ [MGG Builder] ─→ [Validation Engine] ─→ [Semantic Layer] ─→ [Dataset Generator] ─→ [Benchmark Suite] ─→ [ML]
                      ↑                    ↑                     ↑
               [Rule Engine]       [Provenance System]    [Confidence System]
```

**Critical path**: DXF Parser → MGG Builder → Validation Engine → Dataset Generator

Everything else is parallel or downstream.
