# P&ID Expansion Scope — ISA-5.1 → OMIM

Version: v0.1.0 (proposal)
Section: 10_IMPLEMENTATION

See also: [[06_REAL_WORLD_GROUNDING/External_Datasets_Survey]], [[02_SCHEMA/MGG_Schema]], [[05_VALIDATION/Rule_Engine]], [[01_FOUNDATION/Authority_Hierarchy]]

> Scope for extending OMIM from cabinet panels to **Piping & Instrumentation Diagrams**.
> The thesis port: *standards-as-deterministic-rules + typed graph + provenance +
> validator-gated synthetic data* applies almost unchanged — and unlike furniture,
> **P&ID has a real, permissively-licensed, graph-annotated dataset (PID2Graph,
> CC BY-SA), so you can train and validate against real ground truth on day one.**

---

## 0. Why P&ID is the right second domain (the data argument)

The panel domain's fatal gap was: **no real labeled data** → synthetic circularity → can't
prove generalization. P&ID inverts every one of those:

| Problem in panels | P&ID status |
|---|---|
| No real labeled dataset | **PID2Graph**: real P&IDs, full-graph (symbols + connections), `.graphml`, CC BY-SA |
| Standard cited but not machine-checkable end-to-end | **ANSI/ISA-5.1-2024** tag grammar + loop topology are *formally* checkable |
| Graph was inferred from spatial heuristics | A P&ID **is** a graph natively (connectivity is explicit, not guessed) |
| Synthetic = circular | Synthetic is field-standard (Digitize-PID) **and** can be checked against real PID2Graph |

So the GNN-vs-rules gate (the thing we could only run on synthetic noise for panels) can be
run on **real, third-party, labeled graphs** here. This is the domain where OMIM's claims
become verifiable, not just internally consistent.

---

## 1. Concept mapping (panel → P&ID)

| OMIM panel concept | P&ID equivalent | Notes |
|---|---|---|
| DXF entity (circle, polyline) | Vector primitive / symbol glyph / line segment | raw geometry layer |
| GeometryNode | **PrimitiveNode** (unchanged schema) | the raw drawn thing |
| FeatureNode (SHELF_PIN_HOLE…) | **ComponentNode** (instrument / equipment / valve / line) | "feature_class" → ISA symbol class |
| OperationNode (DRILLING…) | **FunctionNode / Loop** (control loop, ISA tag function) | the *intent* layer |
| ConstraintNode (MFG-001 violation) | **ComplianceNode** (tag-syntax / loop / connectivity violation) | same role |
| RelationshipEdge: ADJACENT_TO / CONTAINS (spatial) | **CONNECTED_TO / SIGNALS / MEMBER_OF_LOOP** (topological) | ← biggest shift: edges are *connections*, not proximity |
| Panel boundary | Drawing sheet / process unit boundary | container |
| MFG rules (geometric) | ISA-5.1 tag + topology rules | deterministic, standards-cited |

**The one conceptual inversion:** in panels, edges are *derived* from geometry (spatial
adjacency); in P&ID, **edges are first-class data** (a pipe explicitly connects pump→valve→tank).
Topology carries the meaning. OMIM's MGG is already a `networkx.MultiDiGraph` with typed,
provenance-tracked edges, so this is a re-weighting of existing machinery, not a rewrite.

---

## 2. PID2Graph → MGG ingest (this is nearly free)

PID2Graph ships `.graphml`. OMIM's MGG is a NetworkX MultiDiGraph. **`networkx.read_graphml()`
loads it directly** — so the panel "DXF parser" stage is replaced by a thin graphml→MGG adapter
that maps PID2Graph node/edge attributes onto `ComponentNode` / `RelationshipEdge`, attaching a
`ProvenanceRecord(inference_method=HUMAN_ANNOTATED, confidence=1.0)` (the labels are real,
expert/auto-annotated ground truth — Authority Level 3).

```
PID2Graph .graphml ──nx.read_graphml──> typed MGG (ComponentNodes + CONNECTED_TO edges)
                                          + provenance(HUMAN_ANNOTATED)
```

No perception needed for v1 — you start from the annotated graph. (Perception, i.e.
image/vector → graph, is the hard, crowded part and is explicitly deferred; see §6.)

---

## 3. ISA-5.1 → rule engine (the deterministic core ports directly)

OMIM's rule engine already loads YAML rules with `rule_id / severity / source / confidence_ceiling`
and dispatches to handlers. P&ID rules slot into the same structure — three new families:

### 3a. Tag-grammar rules (string grammar — like MFG diameter checks but on identifiers)
ISA-5.1 instrument tags: `[first-letter = measured variable][succeeding = functions]-[loop no.]`.
Examples: `FT-101` = Flow Transmitter; `TIC-205` = Temperature Indicating Controller; `PSV-310`
= Pressure Safety Valve.

```yaml
- rule_id: "PID-TAG-001"
  name: "Valid ISA-5.1 tag grammar"
  category: "standards"
  rule_type: "standards_derived"          # confidence_ceiling 0.95
  severity: "ERROR"
  source: "ANSI/ISA-5.1-2024 §tag identification"
  parameters: { first_letter_set: [A,B,C,D,E,F,...], function_letter_set: [I,R,C,T,V,...] }
```
Deterministic regex/grammar validation — identical pattern to the panel rule handlers.

### 3b. Connectivity rules (graph topology — NEW rule kind)
- `PID-CONN-001` (ERROR): no dangling line endpoints (every line connects two components).
- `PID-CONN-002` (ERROR): every instrument bubble connects to a process line or another instrument.
- `PID-CONN-003` (WARNING): in-line elements (valves) must lie on a process line, not float.

### 3c. Control-loop rules (graph-path topology — NEW rule kind)
- `PID-LOOP-001` (WARNING): a control loop with a controller (`*C*`) should have a measurement
  (transmitter `*T`) and a final control element (valve) reachable in the loop graph.
- `PID-LOOP-002` (INFO): loop-number consistency across members sharing a loop tag.

These are **graph-reachability checks** on the MGG — a new handler style alongside the existing
geometric ones, but the engine, severities, provenance, and report schema are unchanged.

---

## 4. What carries over vs. what's new

### Carries over unchanged (≈70% of the codebase — the domain-agnostic core)
- **Graph schema**: `Geometry/Feature/Operation/Constraint` nodes + `RelationshipEdge` + `GraphMetadata` (rename, don't redesign).
- **ProvenanceRecord + authority hierarchy** — fully generic; `HUMAN_ANNOTATED`/`DETERMINISTIC`/`HEURISTIC`/`ML_GNN` all already exist.
- **Rule engine**: YAML-loaded rules, handler registry, layered execution, deterministic ordering, `RuleResult` + `ValidationReport`.
- **Validator-as-gatekeeper** synthetic pipeline, `check_graph_integrity`, dataset export (5-file canonical), benchmark harness (BENCH-style tasks), confidence model, CLI/API skeleton, ML layer (GraphSAGE/feature extraction → just a different node-feature vector).

### New (the domain adapter — `omim.domains.pid`)
- graphml→MGG ingest adapter (thin).
- ISA-5.1 ontology YAML (symbol classes + tag-letter tables) — analogous to `features.yaml`.
- `pid_rules.yaml` + handlers for TAG / CONN / LOOP rule families.
- P&ID node-feature vector for the GNN (symbol class one-hot, degree, tag-parse features) replacing the 16 geometric dims.
- (Deferred) perception front-end: vector/raster → graph.

### Implied refactor (clean, low-risk)
Split into **`omim.core`** (graph, provenance, rule-engine, validation, benchmark, export — domain-agnostic)
+ **`omim.domains.panel`** (current DXF/Shapely/MFG code) + **`omim.domains.pid`** (new).
The MGG becomes a generic "Engineering Semantic Graph"; panels and P&ID are adapters. This is a
package reorganization, not a rewrite, and it's the thing that turns OMIM from "a cabinet tool"
into "a standards-grounded CAD-validation framework."

---

## 5. Differentiation (be honest about the crowded part)

Most P&ID ML work is **symbol detection / digitization** (perception: image → symbols). That space
is busy (Digitize-PID, PID2Graph's own baselines, commercial OCR tools). **OMIM should NOT compete
on perception.** OMIM's differentiator is the layer *above* detection:

> Given a P&ID graph (from PID2Graph, or any digitizer), **validate ISA-5.1 compliance — tag
> grammar, connectivity integrity, loop completeness — with a full provenance/audit trail, and
> generate validator-gated synthetic P&IDs for training.**

That validation+provenance+synthetic-data niche is far less crowded than detection, and it is
exactly what OMIM already is.

---

## 6. Phased plan

| Phase | Deliverable | Needs HPC? | Proves |
|---|---|---|---|
| **P0** | `omim.core` extraction (refactor; panel tests still green) | no | architecture is domain-agnostic |
| **P1** | graphml→MGG adapter + ISA-5.1 ontology; load PID2Graph | no | real labeled graphs ingested |
| **P2** | TAG/CONN/LOOP rule families + handlers; validate PID2Graph; report compliance stats | no | **deterministic validation works on REAL data** (the panel domain never got this) |
| **P3** | synthetic P&ID generator (validator-gated) + KS-test vs PID2Graph distributions | no | synthetic matches real |
| **P4** | rules-vs-GNN gate **on real PID2Graph holdout** (not synthetic noise) | single GPU | the honest go/no-go, on real labels |
| **P5** | scale on Leonardo *iff* P4 shows lift | yes (conditional) | — |

Note P2 is the milestone the panel domain could never reach without buying/labeling data:
**deterministic, standards-cited validation measured against a real third-party labeled corpus.**

---

## 7. Risks / honest caveats

- **PID2Graph license is CC BY-SA** → derivatives must share-alike; fine for research/open, check before any closed-source product.
- **Perception is deferred, not solved** — OMIM v1 here assumes graph input. If the end goal needs raw-image→graph, that's a separate (crowded) build; lean on existing digitizers and own the validation layer.
- **ISA-5.1 has regional/vendor variants** (some shops deviate); encode `domain_applicability` on rules exactly as the panel ruleset already does, and keep confidence ceilings honest (`standards_derived` ≤ 0.95).
- **Don't over-claim novelty on detection.** The defensible, verified contribution is validation + provenance + synthetic data on a real labeled graph corpus.

---

## 8. One-paragraph pitch

OMIM already is a typed, provenance-tracked graph with a YAML-driven deterministic rule engine and
a validator-gated synthetic-data pipeline. A P&ID is natively a typed graph, ISA-5.1 is a formal
machine-checkable standard, and PID2Graph supplies real graph-annotated ground truth under a
permissive license. Porting means: extract a domain-agnostic core, add a thin graphml adapter, an
ISA-5.1 ontology, and three new rule families (tag grammar, connectivity, loop topology) — reusing
~70% of the codebase — and you get the thing the cabinet domain can't have without months of
hand-labeling: **a standards-grounded validator proven against real, third-party, labeled data.**
