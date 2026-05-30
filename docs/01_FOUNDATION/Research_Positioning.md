# Research Positioning & Scientific Integrity

Version: v0.1.0  
Section: 01_FOUNDATION  

See also: [[01_FOUNDATION/Vision_and_Scope]], [[01_FOUNDATION/Non_Goals]], [[01_FOUNDATION/External_Baselines]], [[08_PROVENANCE_AND_CONFIDENCE/Provenance_System]]

---

## Purpose

This document defines what OMIM claims, what it explicitly does NOT claim, and how the project maintains scientific credibility. It also defines the contribution governance model.

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

### Performance Claims — Correct Format

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

---

## Required Limitation Disclosures

Every ML model evaluation MUST acknowledge:
- Dataset is synthetic (not real industrial data)
- Domain gap between synthetic and real data is unknown
- Performance may not generalize to real CNC shop workflows
- Ontology coverage is limited to panel manufacturing v0.1.0

### Deterministic Validation Disclaimer
> The OMIM validation engine checks geometry against a defined ruleset (v0.1.0). Passing validation means the part satisfies these specific rules. It does NOT mean the part is certifiably manufacturable on any specific machine in any specific shop.

### Semantic Inference Disclaimer
> Feature classifications produced by the semantic layer are probabilistic estimates based on geometric patterns. They represent hypotheses, not ground truth. Human review is recommended for any classification that will be acted upon.

### Synthetic Dataset Disclaimer
> The OMIM synthetic dataset is generated from programmatic rules designed to reflect common panel manufacturing patterns. It is not a statistical sample of real-world manufacturing DXFs. Distribution shifts between synthetic and real data are expected.

---

## Overclaiming Prevention Rules

These govern all OMIM-related communication (papers, presentations, README, demos):

1. **No "can" claims without evidence**: "OMIM can detect shelf pin rows" requires a test case showing it actually does
2. **No comparative claims without baselines**: "Better than existing approaches" requires a defined baseline and fair comparison
3. **No generalization without domain specification**: "Works for manufacturing parts" must be scoped to "works for panel manufacturing DXF files within the tested ontology"
4. **No precision without methodology**: "92% accuracy" must specify: accuracy for what task, on what dataset split, using what evaluation protocol
5. **No capability implied by architecture**: Having a GNN in the pipeline does not mean "AI-powered manufacturing intelligence"
6. **Always cite the rule source**: "Too close to edge" violation must reference the rule (MFG-001) and the rule's source

---

## Contribution Governance

### Ontology Governance

Changes require:
1. New term: definition, detection criteria, at least one source, initial confidence method
2. Modified term: document what changed and why; bump ontology version
3. Removed term: document why; migration path for existing data with that label

**Freeze rule**: The ontology is frozen at version v0.1.0 for the hackathon.

### Rule Governance

1. New rule: rule_id, version, description, algorithm, parameters, at least one source
2. Modified rule: bump rule version; re-run all validation tests; document change
3. Deprecated rule: mark `status: deprecated`; never delete (provenance references may exist)
4. Custom heuristics must be labeled `note: "Heuristic: no direct standard"` — not hidden

### Scientific Integrity Checklist

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

The long-term goal is to be the foundational layer for manufacturing intelligence research — analogous to what ImageNet was for computer vision, or what GLUE/SuperGLUE was for NLP:

1. **Ontology**: A peer-reviewed, community-maintained manufacturing feature taxonomy — the shared vocabulary that lets models, tools, and researchers talk about manufacturing in a common language
2. **Representation standard**: The MGG as a common format for exchanging manufacturing geometry + semantics across tools, papers, and institutions (cf. HuggingFace datasets as a neutral exchange format)
3. **Benchmark ecosystem**: A growing suite of standardized tasks that make progress measurable and comparable — the "GLUE for manufacturing AI"
4. **Dataset infrastructure**: Tools for generating large-scale labeled manufacturing datasets without expensive manual annotation — enabling large-scale ML research in a domain currently starved of data
5. **Foundation for manufacturing AI**: A credible, reproducible starting point for foundation models trained on manufacturing data — the "ImageNet moment" for manufacturing intelligence

**Why this matters**: Manufacturing intelligence has no shared foundation. Every company and research lab starts from scratch with proprietary data, proprietary ontologies, and non-comparable evaluations. OMIM provides the open, neutral infrastructure layer that makes manufacturing AI research cumulative rather than fragmented.

**The honest version of this claim**: We are not claiming to have achieved this. We are claiming to have built the infrastructure that makes it possible to work toward it systematically. The synthetic dataset is small (1,000 samples). The ontology covers one domain. The benchmarks are simple. But the infrastructure is designed to scale, the provenance is real, and the extension points are clean.
