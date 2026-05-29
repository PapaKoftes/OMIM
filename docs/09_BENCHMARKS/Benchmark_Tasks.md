# Benchmark Tasks

Version: v0.1.0  
Section: 09_BENCHMARKS  

See also: [[09_BENCHMARKS/Evaluation_Metrics]], [[09_BENCHMARKS/Train_Test_Policy]], [[10_IMPLEMENTATION/Definition_of_Done]]

---

## Overview

OMIM v0.1.0 defines 4 benchmark tasks. All tasks evaluate against the frozen test set. Ground truth comes from synthetic generation specs (not from OMIM's own inference).

---

## BENCH-001: Feature Classification

**Goal**: Classify each geometry node into its correct feature type.

```
Task type:    Multi-class classification
Input:        ManufacturingGeometryGraph (geometry + spatial relationships)
Output:       feature_class per node (from Feature_Taxonomy)
Ground truth: labels.json feature_class (from generation spec)
```

### Classes

All 14 feature types from Feature_Taxonomy plus UNKNOWN_FEATURE:
`THROUGH_HOLE, BLIND_HOLE, SHELF_PIN_HOLE, HINGE_CUP_HOLE, CONFIRMAT_HOLE, DOWEL_HOLE, POCKET, GROOVE, DADO, RABBET, OPEN_SLOT, PROFILE_CUT, INTERNAL_CUTOUT, UNKNOWN_FEATURE`

### Evaluation

**Primary metric**: Macro F1-score (all classes equally weighted)  
**Secondary metric**: Per-class F1 for each feature type  
**Pass threshold**: Macro F1 ≥ 0.80

```python
from sklearn.metrics import f1_score

macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
```

### Baseline

Rule-based semantic inference (OMIM's built-in semantic layer). Any submitted model should beat this baseline.

---

## BENCH-002: Manufacturability Prediction

**Goal**: Predict whether a panel is manufacturable and identify which nodes contribute to violations.

```
Task type:    Binary classification (panel-level) + node attribution (optional)
Input:        ManufacturingGeometryGraph
Output:       is_valid ∈ {True, False} + optional violation_predictions per node
Ground truth: labels.json is_valid (from generation spec)
```

**Output format**:
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

**Test set**: 300 samples — 150 valid, 150 invalid (stratified by violation type)

### Evaluation

| Metric | Description | Primary? |
|--------|-------------|---------|
| Binary F1 | F1 for manufacturable vs. not | ✓ Primary |
| False Positive Rate (FPR) | Rate of valid panels predicted as invalid | ✓ Primary |
| False Negative Rate (FNR) | Rate of invalid panels predicted as valid | ✓ Primary (safety-critical) |
| Violation Localization F1 | F1 for identifying which nodes are violating | Secondary |
| AUROC | Area under ROC curve for binary prediction | Secondary |

```python
from sklearn.metrics import f1_score, confusion_matrix, roc_auc_score

binary_f1 = f1_score(y_true, y_pred, pos_label=True)
tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
fnr = fn / (fn + tp)   # false negative rate — safety-critical
fpr = fp / (fp + tn)   # false positive rate
auroc = roc_auc_score(y_true, confidence_scores)
```

**FNR is safety-critical**: Predicting a defective panel as valid can cause manufacturing failures. FNR ≤ 0.10 is a hard pass requirement. False positives are annoying; false negatives are dangerous.

### Baseline

OMIM rule-based validation achieves FNR = 0.0 on synthetic data (it generated the violations). Any ML model must match or exceed this on held-out distributions. The research question: can a GNN learn to detect violations without explicit rule programming?

---

## BENCH-003: Operation Inference

**Goal**: Infer the required manufacturing operations from geometry.

```
Task type:    Multi-label classification (a panel may need multiple operations)
Input:        ManufacturingGeometryGraph
Output:       set of operations required ∈ {DRILLING, CNC_ROUTING, PROFILE_CUTTING, NESTING}
Ground truth: FEATURE_TO_OPERATIONS mapping applied to labels.json features
```

### Ground Truth Derivation

```python
FEATURE_TO_OPERATIONS = {
    "THROUGH_HOLE":     ["DRILLING"],
    "SHELF_PIN_HOLE":   ["DRILLING"],
    "HINGE_CUP_HOLE":   ["DRILLING"],   # technically boring; modeled as drilling in v0
    "CONFIRMAT_HOLE":   ["DRILLING"],
    "DOWEL_HOLE":       ["DRILLING"],
    "GROOVE":           ["CNC_ROUTING"],
    "POCKET":           ["CNC_ROUTING"],
    "RABBET":           ["CNC_ROUTING"],
    "PROFILE_CUT":      ["PROFILE_CUTTING"],
    "INTERNAL_CUTOUT":  ["PROFILE_CUTTING"],
}
# Every panel with any feature requires NESTING consideration
NESTING_IS_UNIVERSAL = True

def compute_operation_ground_truth(labels: dict) -> set[str]:
    operations = set()
    for feat in labels["features"]:
        ops = FEATURE_TO_OPERATIONS.get(feat["feature_class"], [])
        operations.update(ops)
    operations.add("NESTING")
    return operations
```

### Evaluation

| Metric | Description | Primary? |
|--------|-------------|---------|
| Macro F1 (per-label) | F1 for each operation label | ✓ Primary |
| Hamming Loss | Fraction of wrong labels | Secondary |
| Subset Accuracy | Exact match of full operation set | Secondary |

```python
from sklearn.metrics import f1_score, hamming_loss, accuracy_score

operation_f1 = f1_score(y_true_multilabel, y_pred_multilabel, average="macro")
h_loss = hamming_loss(y_true_multilabel, y_pred_multilabel)
subset_acc = accuracy_score(y_true_multilabel, y_pred_multilabel)  # exact match
```

**Pass threshold**: Macro F1 ≥ 0.85

### Baseline

Deterministic mapping from BENCH-001 classifications to operations. BENCH-003 score is bounded by BENCH-001 accuracy.

---

## BENCH-004: Anomaly Detection

**Goal**: Detect nodes/panels with unusual or out-of-distribution geometry without prior knowledge of specific violation types.

```
Task type:    Semi-supervised anomaly detection (train on normal panels, detect outliers)
Input:        ManufacturingGeometryGraph
Output:       anomaly_score ∈ [0.0, 1.0] per node (higher = more anomalous)
Ground truth: is_valid from labels.json (anomalous = invalid)
```

**Anomaly types** (positive class):
- Geometric violations (edge clearance, feature spacing)
- Feature sizes outside normal diameter ranges
- Unusual spatial arrangements
- Unknown feature types (UNKNOWN_FEATURE)

**Test set**: 300 nodes — 200 normal, 100 anomalous

### Evaluation

| Metric | Description | Primary? |
|--------|-------------|---------|
| AUROC | Area under ROC for anomaly scores | ✓ Primary |
| AUPRC | Area under precision-recall curve | ✓ Primary |
| F1 at optimal threshold | F1 at threshold maximizing F1 | Secondary |

```python
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score
import numpy as np

auroc = roc_auc_score(y_true, anomaly_scores)
auprc = average_precision_score(y_true, anomaly_scores)

# F1 at optimal threshold
thresholds = np.linspace(0, 1, 100)
f1s = [f1_score(y_true, anomaly_scores >= t) for t in thresholds]
f1_optimal = max(f1s)
```

**Pass threshold**: AUROC ≥ 0.80

### Distinction from BENCH-002

BENCH-002 uses a threshold binary classifier with known rule structure; BENCH-004 uses an unsupervised ranking/scoring approach. BENCH-004 tests whether a model can assign higher anomaly scores to invalid panels even without knowing the specific manufacturing rules.

---

## Evaluation Infrastructure

### BenchmarkSplitter

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
        """
        Stratified split preserving valid/invalid ratio across splits.
        Stratifies by: (is_valid, complexity, feature_density)
        
        IMPORTANT: test split is FIXED after first creation.
        DO NOT regenerate test split — it must be stable for reproducibility.
        """
```

### BenchmarkEvaluator

```python
class BenchmarkEvaluator:
    def run_bench001(
        self, model: FeatureClassifier, test_split: list[DatasetSample]
    ) -> Bench001Results:
        """Run BENCH-001 feature classification evaluation."""

    def run_bench002(
        self, model: ManufacturabilityPredictor, test_split: list[DatasetSample]
    ) -> Bench002Results:
        """Run BENCH-002 manufacturability validation."""

    def run_bench003(
        self, model: OperationInferrer, test_split: list[DatasetSample]
    ) -> Bench003Results:
        """Run BENCH-003 operation inference."""

    def run_bench004(
        self, model: AnomalyDetector, test_split: list[DatasetSample]
    ) -> Bench004Results:
        """Run BENCH-004 anomaly detection."""

    def run_all(self, models: dict, test_split) -> BenchmarkReport: ...
```

### CLI Evaluation

```bash
python -m omim.benchmarks.evaluate \
  --task bench001 \
  --predictions predictions.json \
  --split test \
  --output results.json
```

---

## Benchmark Submission Protocol

For each benchmark task, a submission must provide:

```python
class BenchmarkSubmission(BaseModel):
    task_id: str                  # "BENCH-001" through "BENCH-004"
    model_name: str
    predictions: list[Prediction] # one per test sample
    metadata: dict                # architecture, training config, etc.

class Prediction(BaseModel):
    sample_id: str
    # BENCH-001: dict[node_id, feature_class]
    # BENCH-002: bool
    # BENCH-003: list[str] (operation names)
    # BENCH-004: float (anomaly score)
    prediction: Any
    confidence: float | None
```

---

## Baseline Results (v0.1.0)

| Baseline | BENCH-001 Macro F1 | BENCH-002 Binary F1 | BENCH-003 Macro F1 | BENCH-004 AUROC |
|----------|-------------------|--------------------|--------------------|----------------|
| Majority class | ~0.07 | ~0.82 | ~0.25 | ~0.50 |
| Deterministic rule-based | N/A | ~0.95+ | ~0.90 | N/A |
| GNN GraphSAGE (target) | > 0.65 | > 0.88 | > 0.75 | > 0.75 |

*GNN targets to be filled in after training.*

---

## Pass/Fail Thresholds (Publication Standards)

| Benchmark | Metric | Meaningless Baseline | Noteworthy | Strong Result |
|-----------|--------|---------------------|------------|--------------|
| BENCH-001 | Macro F1 | < 0.20 (random) | > 0.50 | > 0.75 |
| BENCH-002 | Binary F1 | < 0.82 (majority) | > 0.88 | > 0.95 |
| BENCH-002 | FNR | > 0.20 (unacceptable) | < 0.10 | < 0.05 |
| BENCH-003 | Macro F1 | < 0.25 (majority) | > 0.70 | > 0.88 |
| BENCH-004 | AUROC | < 0.55 (near random) | > 0.75 | > 0.90 |

---

## Expert Validation Loop (v0.2 — Required Before Publication)

Synthetic-only evaluation creates a risk of self-reinforcing errors: the system generates data according to its own rules, then validates against its own rules. This produces good benchmark numbers but cannot guarantee alignment with real manufacturing practice.

### Full 4-Step Expert Loop

```
Step 1 — Expert Curated Subset
  Collect 50–100 real panel DXF files (from willing shops or open sources)
  Have a qualified CNC operator label features manually
  Create "expert_reviewed" split separate from synthetic split

Step 2 — Cross-Validation
  Run OMIM pipeline on expert-labeled samples
  Compare OMIM labels vs expert labels
  Compute disagreement rate per feature class

Step 3 — Disagreement Analysis
  For each disagreement: was OMIM wrong, or was the expert inconsistent?
  Document systematic disagreements (these reveal ontology gaps)
  Update rules/heuristics based on expert feedback

Step 4 — Expert Benchmark
  Report performance on expert-labeled split SEPARATELY from synthetic split
  Expected: lower scores on expert split (harder, more realistic)
  This delta quantifies the synthetic-to-real gap — scientifically interesting
```

### Minimal Hackathon Expert Review

*15 minutes, achievable during the hackathon:*

Find one person with CNC or cabinet manufacturing experience. Show them 5 generated panels (DXF or SVG render) and ask:
1. "Does this panel look like something you'd actually machine?" (yes / no / maybe)
2. "Are these hole positions realistic for this panel type?" (yes / no / unrealistic)
3. "What's wrong with the invalid panel?" (open answer — compare to what OMIM detected)

Store results in `data/expert_review/hackathon_review_2026-05-30.json`.

This is the first data point in the expert validation chain. A system that can explain itself to one qualified human is already more credible than most academic synthetic dataset systems.

---

## Future Benchmarks (v0.2+)

| Task ID | Name | Description |
|---------|------|-------------|
| BENCH-005 | Semantic Relationship Inference | Predict edges (SAME_GROUP, DEPENDS_ON) |
| BENCH-006 | Operation Sequencing | Predict correct operation execution order |
| BENCH-007 | Multi-Panel Assembly Reasoning | Reason about how panels fit together |
| BENCH-008 | Material-Aware Manufacturability | Predict violations given specific material properties |

---

## Citation

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

## Test Set Integrity

**The test set is never used for training or hyperparameter tuning.**  
See [[09_BENCHMARKS/Train_Test_Policy]] for complete policy.

Any model that shows evidence of test set contamination is disqualified.
