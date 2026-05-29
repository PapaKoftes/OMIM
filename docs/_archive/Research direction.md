# Research Integrity & Claim Boundaries

Version: v0.1.0  

See also: [[What Is OMIM]], [[Vision and Scope]], [[Provenence and Uncertainty]], [[Benchmarking]]

---

## Purpose

This document defines what OMIM claims, what it explicitly does NOT claim, and how the project maintains scientific credibility. It also defines the contribution governance model for the open-source project.

The goal: OMIM should be reviewable by any qualified manufacturing engineer or ML researcher. No claim should survive that cannot be directly verified from system outputs.

---

## Language Discipline (Required Terminology)

The words used to describe OMIM's capabilities directly affect scientific credibility. These rules apply everywhere: papers, demos, README, presentations, conversations with judges.

### Approved Language

| Instead of... | Use... | Why |
|--------------|--------|-----|
| "understands manufacturing" | "infers manufacturing intent" | Understanding implies cognition; inference is honest |
| "knows machining intent" | "classifies geometry as probable machining features" | Know implies certainty; classify is accurate |
| "autonomous manufacturing reasoning" | "rule-based manufacturability checking" | Autonomous is a strong claim; rule-based is accurate |
| "AI detects features" | "heuristic classifier identifies feature candidates" | AI is vague; heuristic is precise |
| "the model understands the panel" | "the model assigns feature class probabilities to geometry nodes" | Specificity builds credibility |
| "validates manufacturability" | "checks against programmed geometric rules derived from standards" | The former implies completeness; the latter is accurate |
| "manufacturing intelligence" | "manufacturing semantic inference infrastructure" | Intelligence is a loaded term |
| "smart CNC planning" | "structured feature recognition + rule-based validation" | Smart is meaningless |

### OMIM Performs (Approved Claims)
- Constrained semantic inference from geometry
- Probabilistic feature classification
- Rule-based manufacturability approximation
- Structured pattern recognition
- Provenance-tracked label generation
- Geometry-to-graph representation

### OMIM Does NOT Perform (Disallowed Claims)
- Human-level manufacturing understanding
- Physics-based manufacturability simulation
- Machine-specific toolpath optimization
- Autonomous manufacturing decision-making
- Complete semantic understanding of manufacturing intent

---

## What OMIM Claims (v0.1.0)

### Architectural Claims

| Claim | Verifiable How |
|-------|---------------|
| MGG is a deterministic, reproducible representation | Roundtrip serialization test |
| Validation engine is deterministic | Same-input-same-output test |
| Every semantic label has confidence + evidence | Schema enforcement (Pydantic validation) |
| Every dataset sample has complete provenance | Provenance completeness test |
| Synthetic dataset is reproducible from seed | Regeneration comparison test |
| Rules trace to cited sources | Rule YAML source fields |

### Performance Claims

Performance claims may ONLY be stated with:
1. Dataset version specified (`omim-synthetic-v0.1.0`)
2. Split specified (always `test` split)
3. Metric defined exactly (macro F1, AUROC, etc.)
4. Confidence interval or standard deviation (for ML results)

**Example correct claim**:
> "GraphSAGE baseline on BENCH-001 achieves Macro F1 = 0.71 ± 0.02 on the test split of omim-synthetic-v0.1.0 (n=150 panels)."

**Example incorrect claim**:
> "Our model achieves 71% accuracy on manufacturing feature classification."

(Wrong: no dataset specified, no split specified, wrong metric for multi-class)

---

## What OMIM Does NOT Claim

### Technical Non-Claims

| Non-Claim | Why |
|-----------|-----|
| "OMIM validates real-world manufacturability" | It validates against programmed rules; real shops may differ |
| "OMIM can identify all manufacturing features" | Only features in the ontology are detectable |
| "OMIM outputs can be used directly for CNC programming" | G-code generation is out of scope; human review required |
| "OMIM achieves human-level manufacturing understanding" | Heuristic/ML inference is not human expertise |
| "The ontology is complete" | It covers panel manufacturing only; explicitly incomplete by design |
| "Rules are certified by any standards body" | Rules are research-grade; not industrially certified |
| "Synthetic data matches real manufacturing data distribution" | Procedurally generated; domain gap is expected and acknowledged |
| "Models trained on synthetic data deploy to production" | Research infrastructure; production use requires validation |

### Epistemic Humility Requirements

Every ML model evaluation MUST acknowledge:
- Dataset is synthetic (not real industrial data)
- Domain gap between synthetic and real data is unknown
- Performance may not generalize to real CNC shop workflows
- Ontology coverage is limited to panel manufacturing v0.1.0

---

## Limitation Disclosures

These limitations are not weaknesses to hide — they are the honest scope of v0.1.0 and must be documented in any publication or presentation.

### Scope Limitations
- **Domain**: Panel manufacturing only (furniture/cabinet grade CNC)
- **Format**: DXF only (2D entities)
- **Geometry**: 2.5D assumed; true 3D features not representable
- **Semantics**: Only features in ontology v0.1.0 are detectable
- **Rules**: Layer 1+2 rules only; semantic plausibility layer is advisory

### Data Limitations
- **Dataset**: Synthetic only; no real industrial DXF data in v0.1.0
- **Distribution**: Feature frequencies reflect design choices, not real-world survey data
- **Scale**: 1,000–10,000 samples for hackathon; larger scale needed for publication
- **Validation**: Rules are heuristic in several cases; no industrial certification

### ML Limitations
- **Architecture**: GraphSAGE is a baseline, not a state-of-the-art GNN
- **Training scale**: Hackathon training is proof-of-concept, not production-grade
- **Generalization**: Untested on real DXF files; domain adaptation required
- **Calibration**: Confidence scores are softmax outputs; may be overconfident

---

## Validation Disclaimers

### Deterministic Validation (Layers 1-2)
> The OMIM validation engine checks geometry against a defined ruleset (v0.1.0). Passing validation means the part satisfies these specific rules. It does NOT mean the part is certifiably manufacturable on any specific machine in any specific shop. Manufacturing feasibility always depends on machine capabilities, tooling availability, material properties, and operator expertise.

### Semantic Inference
> Feature classifications produced by the semantic layer are probabilistic estimates based on geometric patterns and learned associations. They represent hypotheses, not ground truth. Confidence scores indicate model certainty, not manufacturing truth. Human review is recommended for any classification that will be acted upon.

### Synthetic Dataset
> The OMIM synthetic dataset is generated from programmatic rules designed to reflect common panel manufacturing patterns. It is not a statistical sample of real-world manufacturing DXFs. Distribution shifts between synthetic and real data are expected. Research results on this dataset should be validated against real data before deployment claims are made.

---

## Overclaiming Prevention Rules

These rules govern all OMIM-related communication (papers, presentations, README, demos):

1. **No "can" claims without evidence**: "OMIM can detect shelf pin rows" requires a test case showing it actually does

2. **No comparative claims without baselines**: "Better than existing approaches" requires a defined baseline and fair comparison

3. **No generalization without domain specification**: "Works for manufacturing parts" must be scoped to "works for panel manufacturing DXF files within the tested ontology"

4. **No precision without methodology**: "92% accuracy" must specify: accuracy for what task, on what dataset split, using what evaluation protocol

5. **No capability implied by architecture**: Having a GNN in the pipeline does not mean "AI-powered manufacturing intelligence"

6. **Always cite the rule source**: "Too close to edge" violation must reference the rule (MFG-001) and the rule's source

---

## Review & Contribution Governance

### Ontology Governance

Changes to the ontology require:
1. New term: provide definition, detection criteria, at least one source, initial confidence method
2. Modified term: document what changed and why; bump ontology version
3. Removed term: document why; migration path for existing data with that label
4. Review by at least one other contributor before merge (when project has contributors)

**Freeze rule**: The ontology is frozen at version v0.1.0 for the hackathon. No changes during implementation.

### Rule Governance

Changes to rules require:
1. New rule: rule_id, version, description, algorithm, parameters, at least one source
2. Modified rule: bump rule version; re-run all validation tests; document change
3. Deprecated rule: mark `status: deprecated`; never delete (provenance references may exist)
4. Custom heuristics must be labeled `note: "Heuristic: no direct standard"` — not hidden

### Dataset Governance

For any public dataset release:
1. `dataset_metadata.json` must be complete (all fields)
2. Provenance records must be complete for all samples
3. Known issues must be documented in `KNOWN_ISSUES.md`
4. License must be specified (Apache 2.0 proposed)
5. Citation guidance must be provided

### Code Contribution Standards

Pull requests to core systems (parser, graph, validation, provenance) must:
1. Not break existing acceptance tests
2. Maintain provenance chain for all new outputs
3. Follow typed contract model (Pydantic schemas; no raw dicts crossing module boundaries)
4. Include tests for new functionality
5. Not introduce hardcoded domain-specific assumptions that would block future domain expansion

---

## Scientific Integrity Checklist

Before any presentation or publication using OMIM:

- [ ] All performance metrics are on test split (not val or train)
- [ ] Dataset version specified in all metric claims
- [ ] Limitations section present and honest
- [ ] Synthetic vs. real data distinction made explicit
- [ ] Deterministic baseline reported alongside ML results
- [ ] Confidence intervals computed for ML results (at least n=5 runs)
- [ ] Feature class distribution acknowledged (class imbalance discussion)
- [ ] No claims about deployment or industrial use without industrial validation

---

## Long-Term Research Vision

OMIM's long-term contribution to manufacturing AI research:

1. **Ontology**: A peer-reviewed, community-maintained manufacturing feature taxonomy that the research community can build on

2. **Representation standard**: The MGG as a common format for exchanging manufacturing geometry + semantics between systems (like HuggingFace datasets for NLP)

3. **Benchmark ecosystem**: A growing suite of benchmark tasks that make progress measurable, analogous to GLUE/SuperGLUE for NLP or ImageNet for vision

4. **Dataset infrastructure**: Tools and methods for generating large-scale labeled manufacturing datasets without expensive manual annotation

5. **Foundation for manufacturing AI**: A credible starting point for foundation models trained on manufacturing data — the "ImageNet moment" for manufacturing intelligence

These goals are multi-year. The hackathon delivers v0.1.0 of the foundation. Scientific credibility now protects the long-term value of the research.
