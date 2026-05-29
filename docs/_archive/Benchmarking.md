# Benchmark Suite Specification

Version: v0.1.0  

See also: [[Dataset and Research Infrastructure]], [[Manufacturing Ontology]], [[Validation]]

---

## Purpose

The benchmark suite provides standardized evaluation tasks that allow external researchers to:
1. Compare manufacturing AI models fairly
2. Measure specific capabilities (feature classification, manufacturability reasoning, etc.)
3. Track progress as the field develops
4. Reproduce published results

Every benchmark task has: a defined input format, a defined output format, defined metrics, and a fixed test split that never changes once published.

---

## Benchmark Tasks

### BENCH-001: Manufacturing Feature Classification

**Task**: Given a Manufacturing Geometry Graph of a single panel, classify each geometry node into its manufacturing feature category.

**Input**: 
```json
{
  "mgg": { ... },        // ManufacturingGeometryGraph (without semantic annotations)
  "query_node_ids": ["node_001", "node_002", ...]  // nodes to classify
}
```

**Output**:
```json
{
  "predictions": [
    {
      "node_id": "node_001",
      "feature_class": "SHELF_PIN_HOLE",
      "confidence": 0.92
    }
  ]
}
```

**Target Classes** (from [[Manufacturing Ontology]]):
```
THROUGH_HOLE, BLIND_HOLE, SHELF_PIN_HOLE, HINGE_CUP_HOLE, 
CONFIRMAT_HOLE, DOWEL_HOLE, POCKET, GROOVE, RABBET, 
PROFILE_CUT, INTERNAL_CUTOUT, OPEN_SLOT, UNKNOWN_FEATURE
```

**Metrics**:
| Metric | Description | Primary? |
|--------|-------------|---------|
| Macro F1 | F1 averaged across all classes (unweighted) | ✓ Primary |
| Weighted F1 | F1 weighted by class frequency | Secondary |
| Per-class F1 | F1 for each feature class | Diagnostic |
| Accuracy | Overall correct classification rate | Secondary |
| Calibration (ECE) | Expected calibration error for confidence scores | Secondary |

**Evaluation Code**:
```python
def evaluate_bench001(predictions, ground_truth):
    y_pred = [p.feature_class for p in predictions]
    y_true = [g.feature_class for g in ground_truth]
    
    results = {
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "weighted_f1": f1_score(y_true, y_pred, average="weighted"),
        "accuracy": accuracy_score(y_true, y_pred),
        "per_class_f1": classification_report(y_true, y_pred, output_dict=True),
        "ece": expected_calibration_error(y_pred_proba, y_true),
    }
    return results
```

**Baseline** (majority class):
- Always predict `SHELF_PIN_HOLE` (most common in default distribution)
- Expected Macro F1: ~0.07 (13 classes, majority class baseline)
- Expected Accuracy: ~0.28

**Significance Threshold**: Macro F1 > 0.35 to be considered above random

---

### BENCH-002: Manufacturability Validation

**Task**: Given a Manufacturing Geometry Graph, predict whether the panel is manufacturable (valid/invalid) and identify which geometry nodes contribute to violations.

**Input**:
```json
{
  "mgg": { ... }         // ManufacturingGeometryGraph
}
```

**Output**:
```json
{
  "is_manufacturable": false,
  "confidence": 0.94,
  "violation_predictions": [
    {
      "node_id": "node_003",
      "violation_type": "too_close_to_edge",
      "rule_id": "MFG-001",
      "confidence": 0.91
    }
  ]
}
```

**Metrics**:
| Metric | Description | Primary? |
|--------|-------------|---------|
| Binary F1 (valid/invalid) | F1 for manufacturable vs. not | ✓ Primary |
| False Positive Rate | Rate of valid panels predicted as invalid | ✓ Primary |
| False Negative Rate | Rate of invalid panels predicted as valid | ✓ Primary (safety-critical) |
| Violation Localization F1 | F1 for identifying which nodes are violating | Secondary |
| AUROC | Area under ROC curve for binary prediction | Secondary |

**Important**: False Negatives (predicting "valid" when actually invalid) are more dangerous than False Positives (unnecessary rejection). Models should be penalized more heavily for FNR > 0.10.

**Baseline** (deterministic rule engine):
The OMIM deterministic validation engine serves as the baseline AND ground truth generator. ML models should aim to match or exceed it. The interesting research question is: can a GNN learn to detect violations without explicit rule programming?

**Test Set**: 300 samples (150 valid, 150 invalid) with known violations

---

### BENCH-003: Manufacturing Operation Inference

**Task**: Given a Manufacturing Geometry Graph, predict which operations (DRILLING, CNC_ROUTING, PROFILE_CUTTING, NESTING) are required to produce the panel.

**Input**:
```json
{
  "mgg": { ... }         // ManufacturingGeometryGraph with feature annotations
}
```

**Output**:
```json
{
  "operations": [
    {"operation": "DRILLING", "confidence": 0.97},
    {"operation": "PROFILE_CUTTING", "confidence": 0.99},
    {"operation": "CNC_ROUTING", "confidence": 0.62}
  ]
}
```

**Type**: Multi-label classification (a panel can require multiple operations simultaneously)

**Classes**: `DRILLING`, `CNC_ROUTING`, `PROFILE_CUTTING`, `NESTING`

**Metrics**:
| Metric | Description | Primary? |
|--------|-------------|---------|
| Macro F1 (per-label) | F1 for each operation label | ✓ Primary |
| Hamming Loss | Fraction of wrong labels | Secondary |
| Subset Accuracy | Exact match of full operation set | Secondary |

**Ground Truth**: Derived from feature types in synthetic data (deterministic mapping)

**Deterministic Mapping**:
```python
FEATURE_TO_OPERATIONS = {
    "THROUGH_HOLE": ["DRILLING"],
    "SHELF_PIN_HOLE": ["DRILLING"],
    "HINGE_CUP_HOLE": ["DRILLING"],  # technically boring, modeled as drilling in v0
    "CONFIRMAT_HOLE": ["DRILLING"],
    "DOWEL_HOLE": ["DRILLING"],
    "GROOVE": ["CNC_ROUTING"],
    "POCKET": ["CNC_ROUTING"],
    "RABBET": ["CNC_ROUTING"],
    "PROFILE_CUT": ["PROFILE_CUTTING"],
    "INTERNAL_CUTOUT": ["PROFILE_CUTTING"],
}
# Every panel with any feature requires "NESTING" (for multi-panel sheets)
```

---

### BENCH-004: Manufacturing Anomaly Detection

**Task**: Given a Manufacturing Geometry Graph, detect which geometry nodes are anomalous (unusual for the manufacturing domain — may indicate errors, intentional special features, or unseen feature types).

**Input**:
```json
{
  "mgg": { ... }         // ManufacturingGeometryGraph
}
```

**Output**:
```json
{
  "anomaly_scores": [
    {"node_id": "node_001", "anomaly_score": 0.05},
    {"node_id": "node_007", "anomaly_score": 0.94}
  ]
}
```

**Type**: Semi-supervised anomaly detection (train on normal panels, detect outliers at inference)

**Anomaly Types** (positive class):
- Geometric violations (spacing, clearance)
- Feature sizes outside normal ranges
- Unusual spatial arrangements
- Unknown feature types

**Metrics**:
| Metric | Description | Primary? |
|--------|-------------|---------|
| AUROC | Area under ROC for anomaly scores | ✓ Primary |
| AUPRC | Area under precision-recall curve | ✓ Primary |
| F1 at optimal threshold | F1 at the threshold maximizing F1 | Secondary |

**Test Set**: 300 nodes (200 normal, 100 anomalous)

---

## Evaluation Infrastructure

### Dataset Splits

Splits are fixed at dataset creation and never change:

```python
class BenchmarkSplitter:
    def create_splits(
        self,
        dataset: Dataset,
        seed: int = 42,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15
    ) -> DatasetSplits:
        """Stratified split preserving valid/invalid ratio."""
        
        # Stratify by: (is_valid, complexity, feature_density)
        # This ensures balanced representation in each split
        
        # IMPORTANT: test split is FIXED after first creation
        # DO NOT regenerate test split — it must be stable for reproducibility
```

### Split Usage Rules

| Split | Purpose |
|-------|---------|
| train | Model training |
| val | Hyperparameter tuning, early stopping |
| test | Final evaluation only — NEVER used during development |

**Rule**: Test split results must not be used to tune models. Report val performance during development, test performance in publications.

### Evaluation Runner

```python
# omim/benchmarks/evaluator.py

class BenchmarkEvaluator:
    def run_bench001(
        self,
        model: FeatureClassifier,
        test_split: list[DatasetSample]
    ) -> Bench001Results:
        """Run BENCH-001 feature classification evaluation."""
    
    def run_bench002(
        self,
        model: ManufacturabilityPredictor,
        test_split: list[DatasetSample]
    ) -> Bench002Results:
        """Run BENCH-002 manufacturability validation."""
    
    def run_bench003(
        self,
        model: OperationInferrer,
        test_split: list[DatasetSample]
    ) -> Bench003Results:
        """Run BENCH-003 operation inference."""
    
    def run_bench004(
        self,
        model: AnomalyDetector,
        test_split: list[DatasetSample]
    ) -> Bench004Results:
        """Run BENCH-004 anomaly detection."""
    
    def run_all(self, models: dict, test_split) -> BenchmarkReport: ...
```

---

## Baseline Results (v0.1.0)

These are the baselines that all future models should be compared against.

### Deterministic Baseline (Rule-Based)

| Benchmark | Metric | Score |
|-----------|--------|-------|
| BENCH-001 | Macro F1 | N/A (deterministic classifier) |
| BENCH-002 | Binary F1 | ~0.95+ (this IS the rule engine) |
| BENCH-003 | Macro F1 | ~0.90 (deterministic mapping) |
| BENCH-004 | AUROC | N/A (not an anomaly detector) |

### Majority Class Baseline

| Benchmark | Metric | Score |
|-----------|--------|-------|
| BENCH-001 | Macro F1 | ~0.07 |
| BENCH-002 | Binary F1 | ~0.82 (if dataset is 85% valid) |
| BENCH-003 | Macro F1 | ~0.25 |
| BENCH-004 | AUROC | ~0.50 |

### GNN Baseline (GraphSAGE, v0.1.0)

*To be filled in after training. Target:*

| Benchmark | Metric | Target |
|-----------|--------|--------|
| BENCH-001 | Macro F1 | > 0.65 |
| BENCH-002 | Binary F1 | > 0.88 |
| BENCH-003 | Macro F1 | > 0.75 |
| BENCH-004 | AUROC | > 0.75 |

---

## Benchmark Documentation (Researcher-Facing)

### Task Submission Format

External researchers submit predictions as JSON:

```bash
# BENCH-001 submission
python -m omim.benchmarks.evaluate \
  --task bench001 \
  --predictions predictions.json \
  --split test \
  --output results.json
```

### Citation

If using OMIM benchmarks in research:

```bibtex
@misc{omim2026,
  title={OMIM: Open Manufacturing Intelligence Middleware},
  author={OMIM Contributors},
  year={2026},
  url={https://github.com/[TODO]/omim},
  note={Open-source manufacturing intelligence infrastructure}
}
```

---

## Expert Validation Loop (v0.2 — Critical for Publication)

Synthetic-only evaluation creates a risk of self-reinforcing errors: the system generates data according to its own rules, then validates against its own rules. This produces good benchmark numbers but cannot guarantee alignment with real manufacturing practice.

**The evaluation loop that must exist before any publication:**

```
Step 1 — Expert Curated Subset
  Select 50–100 real panel DXF files (obtained from willing shops or open sources)
  Have a qualified CNC operator label features manually
  Create "expert_reviewed" split separate from synthetic split

Step 2 — Cross-Validation  
  Run OMIM pipeline on expert-labeled samples
  Compare OMIM labels vs expert labels
  Compute disagreement rate per feature class

Step 3 — Disagreement Analysis
  For disagreements: was OMIM wrong? Or was the expert inconsistent?
  Document systematic disagreements (these reveal ontology gaps)
  Update rules/heuristics based on expert feedback

Step 4 — Expert Benchmark
  Report performance on expert-labeled split SEPARATELY from synthetic split
  Expected: lower scores on expert split (harder, more realistic)
  This delta is scientifically interesting — it quantifies the synthetic-to-real gap
```

**Why this matters**: A system that achieves Macro F1 = 0.85 on synthetic data but 0.50 on expert-labeled real data has a serious domain gap problem. That problem is not visible without the expert loop.

**Hackathon**: The full 4-step loop is NOT achievable in 48 hours. But a minimal version is:

### Minimal Human Review (Achievable During Hackathon)

Find one person with CNC or cabinet manufacturing experience. Show them the following and record their answers:

```
Show them 5 generated panels (visual DXF or simple SVG render).
Ask 3 questions:
  1. "Does this panel look like something you'd actually machine?" (yes/no/maybe)
  2. "Are these hole positions realistic for this panel type?" (yes/no/unrealistic)
  3. "What's wrong with the invalid panel?" (open answer — compare to what OMIM detected)

Record: name, date, background (machinist/designer/hobbyist), answers
Store in: data/expert_review/hackathon_review_2026-05-30.json
```

This is 15 minutes of time. It produces the first data point in the expert validation chain. It counts. A system that can explain itself to one qualified human is already more credible than most academic synthetic dataset systems.

Post-hackathon: expand to 5+ reviewers, 50+ panels, formal inter-annotator agreement.

```python
# Planned split in evaluator.py
# BENCH-001 has two evaluation modes:
# Mode 1: synthetic (available now)  
# Mode 2: expert_reviewed (available post-hackathon, requires labeled real DXFs)
```

---

## Future Benchmarks (v0.2+)

| Task ID | Name | Description |
|---------|------|-------------|
| BENCH-005 | Semantic Relationship Inference | Predict edges (SAME_GROUP, DEPENDS_ON) |
| BENCH-006 | Operation Sequencing | Predict correct operation execution order |
| BENCH-007 | Multi-Panel Assembly Reasoning | Reason about how panels fit together |
| BENCH-008 | Material-Aware Manufacturability | Predict violations given specific material properties |

---

## Pass/Fail Thresholds (Publication Standards)

These thresholds define what constitutes a meaningful result vs. noise:

| Benchmark | Metric | Meaningless Baseline | Noteworthy Threshold | Strong Result |
|-----------|--------|---------------------|---------------------|--------------|
| BENCH-001 | Macro F1 | < 0.20 (random) | > 0.50 | > 0.75 |
| BENCH-002 | Binary F1 | < 0.82 (majority) | > 0.88 | > 0.95 |
| BENCH-002 | FNR | > 0.20 (unacceptable) | < 0.10 | < 0.05 |
| BENCH-003 | Macro F1 | < 0.25 (majority) | > 0.70 | > 0.88 |
| BENCH-004 | AUROC | < 0.55 (random) | > 0.75 | > 0.88 |

**BENCH-002 False Negative Rate (FNR) is special**: Predicting "valid" when actually invalid is the dangerous failure mode (bad panels escape to machine). Any model with FNR > 0.20 must NOT be used in any advisory capacity, even in research demos. The deterministic rule engine has FNR ≈ 0.0 (by construction) and is always the safety baseline.

### Hackathon Acceptance Threshold

For the hackathon deliverable, the following minimum is required:

| Benchmark | Minimum Acceptable (for demo) |
|-----------|-------------------------------|
| BENCH-001 | Evaluator runs without error; reports any numeric F1 |
| BENCH-002 | Deterministic baseline ≥ 0.88 Binary F1 (this is automatic) |
| BENCH-003 | Evaluator runs without error; reports any numeric F1 |
| BENCH-004 | Anomaly scorer runs; AUROC reported (even if 0.50) |

The GNN baseline does NOT need to beat these thresholds for the hackathon. The infrastructure for measuring them is the deliverable.

---

## Benchmark Integrity Rules

1. **Test set is immutable**: Once generated, the test set never changes between versions
2. **No test set leakage**: Models must not be trained on test data
3. **Metric reporting**: Always report primary metric; secondary metrics are optional
4. **Baseline always reported**: Every paper must report at least the majority-class baseline
5. **Reproducibility**: Predictions must be reproducible from a model checkpoint
