## OMIM — Open Manufacturing Intelligence Middleware

This is my current understanding of your intended project direction, constraints, philosophy, goals, and execution model.

Review this carefully first.

---

# 1. PRIMARY PROJECT IDENTITY

You are NOT trying to build:

- a generic AI startup
    
- a chatbot wrapper
    
- a universal CAM replacement
    
- an autonomous manufacturing AGI
    
- automatic G-code generation
    

You ARE trying to build:

# an open-source, research-grade manufacturing intelligence infrastructure layer

focused on:

- semantic CAD/DXF understanding
    
- manufacturing intent understanding
    
- manufacturability reasoning
    
- manufacturing relationship preservation
    
- synthetic dataset generation
    
- benchmarkable manufacturing intelligence infrastructure
    

---

# 2. PRIMARY LONG-TERM GOAL

The real long-term value is NOT:

- the demo
    
- the hackathon model
    
- the UI
    

The real value is:

# the infrastructure and dataset ecosystem.

Specifically:

- manufacturing ontology
    
- manufacturing graph representation
    
- deterministic validation infrastructure
    
- semantic representation layer
    
- provenance-aware dataset system
    
- benchmark tasks
    
- synthetic manufacturing dataset generation
    
- future trainable manufacturing foundation datasets
    

---

# 3. PRIMARY HACKATHON DELIVERABLE

The MOST important deliverable is:

# a research-grade synthetic manufacturing dataset infrastructure

that:

- is actually usable
    
- scientifically defensible
    
- reproducible
    
- benchmarkable
    
- extensible
    
- reviewable by experts
    
- based on real standards/rules
    
- transparent about uncertainty
    

NOT:

- a flashy AI demo
    

---

# 4. DOMAIN SCOPE

Initial practical scope:

|Included|
|---|
|DXF|
|panel manufacturing|
|nested CNC milling|
|2.5D|
|3-axis assumptions|
|furniture/cabinet workflows initially|
|semantic manufacturing interpretation|
|operation inference|
|manufacturability validation|

---

# 5. FUTURE ARCHITECTURAL INTENT

The architecture MUST support future extension toward:

- 5-axis
    
- waterjet
    
- laser cutting
    
- 3D printing
    
- robotic manufacturing
    
- additional manufacturing domains
    

BUT:  
none of these are to be fully implemented during the hackathon.

The architecture should simply:

- support extensibility
    
- preserve abstraction boundaries
    
- avoid hardcoding furniture-only assumptions
    

---

# 6. CORE RESEARCH DIRECTION

The actual interesting problem is NOT geometry parsing.

It is:

# manufacturing semantic understanding

Meaning:  
the system should eventually understand:

- design intent
    
- operation intent
    
- manufacturing relationships
    
- manufacturability constraints
    
- operation dependencies
    
- tooling implications
    
- semantic meaning of geometry patterns
    

---

# 7. CENTRAL REPRESENTATION MODEL

The project is centered around:

# Manufacturing Geometry Graphs (MGG)

The graph is the core infrastructure layer.

The graph contains:

- geometry entities
    
- semantic features
    
- manufacturing relationships
    
- operation relationships
    
- manufacturability constraints
    
- inference metadata
    
- provenance metadata
    

The graph is intended to become:

# the canonical manufacturing representation layer.

---

# 8. CORE ENGINEERING PHILOSOPHY

## Deterministic-first architecture

Deterministic geometry and validation layers are authoritative.

ML is secondary.

---

# ML SHOULD ONLY:

- infer semantics
    
- rank hypotheses
    
- resolve ambiguity
    
- assist classification
    

---

# ML MUST NEVER:

- override geometry
    
- invent constraints
    
- fabricate manufacturing truth
    
- redefine deterministic facts
    

---

# 9. SCIENTIFIC CREDIBILITY REQUIREMENTS

You want the project to be:

- reviewable by experts
    
- peer-reviewable
    
- source-backed
    
- benchmarkable
    
- reproducible
    
- provenance-aware
    
- auditable
    
- uncertainty-aware
    
- standards-based
    

You explicitly want to avoid:

- hallucinated labels
    
- fake semantics
    
- AI-generated nonsense
    
- unverifiable claims
    
- “AI startup hype”
    

---

# 10. RULESYSTEM REQUIREMENTS

Rules must:

- come from mature industry sources whenever possible
    
- be externally defined
    
- be reviewable
    
- be traceable
    
- be versioned
    
- be benchmarkable
    
- store provenance
    

Preferred rule sources:

- ISO
    
- DIN
    
- industrial CAM practices
    
- machining handbooks
    
- open-source CAM systems
    
- academic manufacturing research
    
- OEM guidelines
    

Custom heuristics are a last resort.

---

# 11. VALIDATION PHILOSOPHY

Validation must be layered.

---

## Layer 1

Deterministic geometric validity.

Examples:

- contour closure
    
- topology integrity
    
- self intersections
    

---

## Layer 2

Manufacturing feasibility rules.

Examples:

- tool access
    
- minimum spacing
    
- edge clearance
    
- tooling radius feasibility
    

---

## Layer 3

Semantic plausibility.

Probabilistic inference only.

---

# 12. UNCERTAINTY REQUIREMENTS

The system MUST:

- preserve uncertainty
    
- expose confidence
    
- preserve evidence chains
    
- expose provenance
    

No semantic label should exist without:

- confidence
    
- evidence
    
- inference source
    

---

# 13. PROVENANCE REQUIREMENTS

Every generated output should store:

- generator version
    
- ontology version
    
- ruleset version
    
- generation method
    
- evidence
    
- source geometry
    
- confidence
    
- review status
    

You want:

# provenance-aware infrastructure.

---

# 14. DATASET PHILOSOPHY

The synthetic dataset should NOT be random.

It must be:

# rules-constrained procedural manufacturing generation.

The generated data should:

- reflect actual manufacturing logic
    
- reflect manufacturable geometry
    
- reflect known operation patterns
    
- contain both valid and invalid cases
    
- support benchmarking
    

---

# 15. BENCHMARKING GOALS

The dataset should support:

- feature classification
    
- operation inference
    
- manufacturability validation
    
- anomaly detection
    
- semantic inference
    
- operation relationship understanding
    

You want:

# research-grade benchmark infrastructure.

---

# 16. OPEN SOURCE PHILOSOPHY

The project is intended to become:

# an open collaborative manufacturing intelligence research standard.

You want:

- public review
    
- future contributions
    
- extensibility
    
- peer review
    
- industry collaboration
    
- research adoption
    

You believe:  
the infrastructure itself being public is acceptable because:  
the real future commercial value likely lies in:

- integrations
    
- industrial deployment
    
- production heuristics
    
- machine-specific optimization
    
- operational expertise
    

---

# 17. HACKATHON EXECUTION CONSTRAINTS

You believe the rules require:

- implementation during the event
    
- no prebuilt proprietary project code
    
- no pre-existing finished infrastructure
    

BUT:

- research
    
- architecture planning
    
- ontology planning
    
- standards review
    
- implementation planning
    
- environment preparation
    

are acceptable beforehand.

---

# 18. AI-ASSISTED DEVELOPMENT STRATEGY

You plan to use:

## Claude Code heavily

BUT:  
you want:

# spec-driven constrained development.

Meaning:  
AI must NOT invent architecture.

Instead:

- architecture/specification comes first
    
- interfaces are predefined
    
- schemas are fixed
    
- AI implements constrained modules only
    

You want:

- minimal AI drift
    
- minimal hallucination
    
- no uncontrolled abstraction creep
    
- no random infrastructure bloat
    

---

# 19. SOFTWARE ENGINEERING PHILOSOPHY

You want:

- modularity
    
- strict interfaces
    
- typed contracts
    
- failure isolation
    
- reviewability
    
- incremental utility
    

Every checkpoint should already:

- function
    
- export useful artifacts
    
- remain independently valuable
    

---

# 20. CHECKPOINT PHILOSOPHY

Each milestone should already produce:

- useful outputs
    
- reusable infrastructure
    
- independently valuable systems
    

Even if later stages fail.

---

# 21. PERSONAL CONSTRAINTS

You explicitly consider yourself:

- inexperienced in industrial AI research
    
- inexperienced in research infrastructure design
    
- inexperienced in scientific validation
    

Therefore:  
you want:

- verification
    
- rigor
    
- standards
    
- formalization
    
- structured architecture
    
- falsifiability
    
- reviewability
    

You are actively trying to prevent:

# amateur mistakes disguised as sophistication.

---

# 22. MOST IMPORTANT META-GOAL

You do NOT want:

# “a cool hackathon project”

You want:

# the beginning of a serious long-term manufacturing intelligence research infrastructure

that:

- can survive scrutiny
    
- can be reviewed by experts
    
- can be extended later
    
- can train future manufacturing AI systems
    
- can become foundational infrastructure
    

---

# 23. MOST IMPORTANT TECHNICAL PRIORITY

The actual core project is:

|Priority|Importance|
|---|---|
|ontology|critical|
|representation layer|critical|
|provenance|critical|
|deterministic validation|critical|
|benchmarkability|critical|
|schema quality|critical|
|standards integration|critical|
|ML sophistication|secondary|

---

# 24. MOST IMPORTANT FAILURE MODES YOU WANT TO AVOID

|Failure|
|---|
|fake semantics|
|hallucinated labels|
|unverifiable outputs|
|architecture incoherence|
|AI-generated infrastructure bloat|
|overscoping|
|non-reviewable rules|
|hidden assumptions|
|probabilistic layers pretending to be deterministic|
|weak provenance|
|random synthetic garbage data|

---

# 25. CURRENT IMPLICIT PROJECT THESIS

Your current thesis appears to be:

> Manufacturing AI currently lacks a robust semantic manufacturing representation layer with transparent provenance, deterministic validation, and benchmarkable synthetic manufacturing datasets.

And OMIM attempts to become:

# that foundational infrastructure layer.

---

---

# VAULT STATUS: COMPLETE

The documentation phase of this project is finished. Every subsystem has been specified, every schema is frozen, every claim has been bounded, every failure mode has been catalogued.

The vault now contains:
- Frozen canonical sample schema with automated validation
- Typed interface contracts for every module boundary
- 6-category rule provenance taxonomy
- Real-world manufacturing grounding (Blum, Hettich, EN 309, 32mm system)
- Dataset distribution policy with feature frequency targets
- 3-mechanism provenance enforcement (Pydantic, write-time validation, audit function)
- Formal 6-level trust and authority hierarchy
- Concrete test fixture list with expected outputs
- Minimal human review protocol (achievable in 15 min during hackathon)
- Approved/forbidden claim language table
- MGG minimalism gate
- BUILD NOW gate with exact CLI success condition
- HPC strategy with storage/IO migration ladder
- Automated graph + ontology + dataset consistency checks
- Hard scope locks

**Writing more documentation will not improve the project. Only running code will.**

---

Review this first.

If this accurately captures your intentions and priorities, then the next step is:

# producing the actual full systems-engineering-grade master architecture and execution plan.


# formal completion criteria.

Without that, you will absolutely spiral into:

- architecture loops
- ontology perfectionism
- endless abstractions
- premature generalization

Research infrastructure projects die from this constantly.

So now we add:

# Exit Conditions

# Acceptance Tests

# Definition of Done (DoD)

# Scope Locks

# Engineering Gates

This is what turns your idea into an executable systems project.

---

# CORE EXECUTION PRINCIPLE

# Every subsystem must have:

- objective purpose
- bounded scope
- explicit inputs/outputs
- acceptance tests
- failure conditions
- completion criteria

If it does not:  
you are still ideating, not engineering.

---

# THE MOST IMPORTANT RULE

# “Good enough to validate the architecture”

NOT

# “perfect forever solution”

You are building:

- v0 research infrastructure
- not the final manufacturing standard

This distinction must stay explicit at all times.

---

# GLOBAL PROJECT EXIT CONDITION

The project is considered:

# successful

IF all of the following exist:

|Deliverable|Required|
|---|---|
|Manufacturing ontology v0.1|yes|
|Manufacturing Geometry Graph spec|yes|
|Deterministic parsing pipeline|yes|
|Validation engine|yes|
|Provenance system|yes|
|Confidence/uncertainty system|yes|
|Synthetic dataset generator|yes|
|Benchmark tasks|yes|
|Example dataset|yes|
|DXF → semantic graph demo|yes|

NOT required:

- SOTA ML
- perfect inference
- full CAM
- industrial certification

---

# MOST IMPORTANT META-RULE

# Every subsystem gets:

1. scope
2. deliverable
3. acceptance tests
4. hard stop condition

This is how you stop rabbit holes.

---

# MASTER SYSTEM BREAKDOWN

Now we turn the project into:

# independently completable engineering blocks.

---

# SYSTEM 1 — ONTOLOGY

# Purpose

Formal manufacturing vocabulary.

---

# Scope

ONLY:

- panel manufacturing
- 2.5D CNC
- nested workflows

---

# Deliverable

```
ontology/ ├── features.yaml ├── operations.yaml ├── constraints.yaml ├── relationships.yaml └── manufacturing_objects.yaml
```

---

# Acceptance Tests

✅ Every entity belongs somewhere in hierarchy  
✅ No duplicate semantic meanings  
✅ Relationships are directional and typed  
✅ Terms are human-readable  
✅ Terms are source-backed where possible

---

# STOP CONDITION

STOP when:

- common panel manufacturing concepts are representable
- graph relationships work
- no unresolved naming ambiguity remains

DO NOT:

- model all manufacturing
- model all CNC operations
- model aerospace machining

---

# SYSTEM 2 — MANUFACTURING GEOMETRY GRAPH (MGG)

# Purpose

Canonical manufacturing representation layer.

---

# Deliverable

```
GeometryNodeFeatureNodeOperationNodeConstraintNodeRelationshipEdge
```

---

# Acceptance Tests

✅ Graph can represent:

- holes
- pockets
- contours
- relationships
- operation dependencies

✅ Graph serializes/deserializes  
✅ Graph supports provenance metadata  
✅ Graph supports confidence metadata

---

# STOP CONDITION

STOP when:

- furniture-grade panel workflows are representable
- graph survives roundtrip export/import
- relationships are queryable

DO NOT:

- optimize graph databases
- build distributed graph infra
- overengineer graph traversal

---

# SYSTEM 3 — DXF PARSER

# Purpose

Reliable deterministic geometry extraction.

---

# Deliverable

```
DXF → normalized geometry objects
```

---

# Acceptance Tests

✅ Correctly parses:

- lines
- circles
- arcs
- polylines

✅ Handles malformed DXFs gracefully  
✅ Preserves source entity references  
✅ Coordinates normalize correctly

---

# STOP CONDITION

STOP when:

- 90%+ of your test DXFs parse reliably
- geometry exports into graph layer correctly

DO NOT:

- support every DXF edge case
- support every CAD format
- optimize performance prematurely

---

# SYSTEM 4 — VALIDATION ENGINE

# Purpose

Deterministic manufacturability validation.

---

# Deliverable

```
validation/ ├── geometry/ ├── manufacturability/ └── rule_engine/
```

---

# Acceptance Tests

✅ Invalid contours detected  
✅ Edge clearance rules work  
✅ Tool radius constraints work  
✅ Validation reports are reproducible  
✅ Rules are externalized

---

# STOP CONDITION

STOP when:

- common manufacturing violations are detectable
- reports are stable and explainable

DO NOT:

- simulate machining physics
- attempt full collision simulation
- implement full CAM verification

---

# SYSTEM 5 — PROVENANCE SYSTEM

# Purpose

Scientific traceability.

---

# Deliverable

Every generated artifact stores:

- source
- generator version
- rule IDs
- evidence
- confidence
- timestamps

---

# Acceptance Tests

✅ Every semantic output traceable  
✅ Every rule invocation recorded  
✅ Every dataset sample reproducible  
✅ Missing provenance impossible

---

# STOP CONDITION

STOP when:

- every inference is auditable
- provenance survives export/import

DO NOT:

- build blockchain nonsense
- overengineer storage systems

---

# SYSTEM 6 — SYNTHETIC DATASET GENERATOR

# Purpose

Generate benchmarkable manufacturing data.

---

# Deliverable

```
synthetic/ ├── valid_panels/ ├── invalid_panels/ ├── edge_cases/ └── configs/
```

---

# Acceptance Tests

✅ Generated panels geometrically valid  
✅ Invalid cases intentionally fail validation  
✅ Labels generated deterministically  
✅ Dataset reproducible from seed/config

---

# STOP CONDITION

STOP when:

- hundreds/thousands of valid samples generate
- metadata/provenance complete
- benchmark tasks usable

DO NOT:

- chase infinite realism
- generate every possible manufacturing domain
- attempt photorealistic CAD synthesis

---

# SYSTEM 7 — SEMANTIC LAYER

# Purpose

Probabilistic manufacturing meaning inference.

---

# Deliverable

```
{  "semantic_class": "...",  "confidence": 0.84,  "evidence": [...]}
```

---

# Acceptance Tests

✅ Confidence always present  
✅ Multiple hypotheses supported  
✅ Semantic inference never overrides geometry  
✅ Evidence chains preserved

---

# STOP CONDITION

STOP when:

- common furniture features infer reasonably
- ambiguity represented properly

DO NOT:

- attempt AGI-level understanding
- hide uncertainty
- overtrain tiny models

---

# SYSTEM 8 — BENCHMARK SUITE

# Purpose

Research usability.

---

# Deliverable

```
benchmarks/ ├── feature_classification/ ├── manufacturability/ ├── operation_inference/ └── anomaly_detection/
```

---

# Acceptance Tests

✅ Benchmark inputs standardized  
✅ Metrics documented  
✅ Tasks reproducible  
✅ Dataset versions tracked

---

# STOP CONDITION

STOP when:

- external researchers could theoretically evaluate models

DO NOT:

- invent complicated evaluation theory
- overbuild leaderboard systems

---

# SYSTEM 9 — DEMO

# Purpose

Communicate system value.

---

# Deliverable

```
Upload DXF → visualize graph → show semantic interpretation → show validation results → export dataset sample
```

---

# Acceptance Tests

✅ End-to-end pipeline works  
✅ Outputs understandable visually  
✅ Validation visible  
✅ Semantic confidence visible

---

# STOP CONDITION

STOP when:

- judges can understand pipeline in <2 minutes

DO NOT:

- build enterprise frontend
- overdesign UI
- chase polish over clarity

---

# HACKATHON EXECUTION GATES

Now the critical anti-rabbit-hole mechanism.

---

# RULE:

# NO PHASE MAY CONTINUE

until:

- current acceptance tests pass
- deliverable exports correctly
- repo committed/tagged
- milestone documented

---

# HARD PHASE GATES

|Phase|Must Exist Before Continuing|
|---|---|
|ontology|schema approved|
|graph layer|parser integrated|
|parser|graph export works|
|validation|deterministic reports work|
|synthetic|validation integrated|
|ML|stable dataset exists|
|demo|full pipeline operational|

This prevents chaos.

---

# MOST IMPORTANT ENGINEERING RULE

# NEVER BUILD FOR HYPOTHETICAL FUTURE NEEDS

Only:

- define extension points
- define interfaces
- define schemas

DO NOT:

- implement future abstractions

This is where solo infra projects die.

---

# FINAL META-RULE

Whenever you ask:

> “should I continue improving this?”

Ask instead:

# “Does improving this unblock another system?”

If NO:  
STOP.

That single rule will save you enormous amounts of time.