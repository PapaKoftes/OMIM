# Evaluation Metrics

Version: v0.1.0  
Section: 09_BENCHMARKS  

See also: [[09_BENCHMARKS/Benchmark_Tasks]], [[09_BENCHMARKS/Train_Test_Policy]]

---

## Metric Definitions

### Macro F1-Score

Used for BENCH-001, BENCH-003.

```
Macro F1 = (1/N) × Σ F1_c for all classes c
where F1_c = 2 × precision_c × recall_c / (precision_c + recall_c)
```

Macro averaging gives equal weight to all classes regardless of frequency. This is appropriate because OMIM must handle rare feature types (CONFIRMAT_HOLE, DADO) with the same proficiency as common ones (SHELF_PIN_HOLE).

**Implementation**:
```python
sklearn.metrics.f1_score(y_true, y_pred, average="macro", zero_division=0)
```

`zero_division=0`: If a class has no predictions, its F1 is 0 (not an error). This penalizes models that fail to predict rare classes.

---

### Binary F1 + False Negative Rate

Used for BENCH-002.

```
Binary F1 = 2 × TP / (2×TP + FP + FN)
FNR = FN / (FN + TP)
```

FNR measures how often the model fails to flag an invalid panel. This is the safety-critical metric.

**Implementation**:
```python
from sklearn.metrics import f1_score, confusion_matrix

binary_f1 = f1_score(y_true, y_pred, pos_label=True)
tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[False, True]).ravel()
fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
```

---

### AUROC

Used for BENCH-004.

```
AUROC = Area Under the Receiver Operating Characteristic Curve
      = P(score(valid) < score(invalid))  for a randomly chosen pair
```

AUROC of 0.5 = random; 1.0 = perfect ranking.

**Implementation**:
```python
from sklearn.metrics import roc_auc_score
auroc = roc_auc_score(y_true, anomaly_scores)
```

---

## Pass/Fail Thresholds

| Task | Primary Metric | Threshold | Critical Metric | Critical Threshold |
|------|--------------|---------|----------------|-------------------|
| BENCH-001 | Macro F1 | ≥ 0.80 | — | — |
| BENCH-002 | Binary F1 | ≥ 0.85 | FNR | ≤ 0.10 |
| BENCH-003 | Macro F1 | ≥ 0.85 | — | — |
| BENCH-004 | AUROC | ≥ 0.80 | — | — |

**A submission passes if and only if ALL metrics meet their thresholds.**

For BENCH-002: a submission with Binary F1 = 0.95 but FNR = 0.15 **fails** — the FNR threshold is independent and hard.

---

## Per-Class Reporting (BENCH-001)

Even though Macro F1 is the primary metric, per-class F1 must be reported for all feature types:

```python
from sklearn.metrics import classification_report

report = classification_report(
    y_true, y_pred,
    target_names=FEATURE_CLASS_NAMES,
    zero_division=0
)
```

Required per-class reporting enables identification of which feature types are poorly classified — this is the primary driver of OMIM improvement.

---

## Metric Computation Script

```python
def evaluate_bench001(predictions: list[Prediction], ground_truth: dict) -> dict:
    y_true, y_pred = [], []
    for pred in predictions:
        for node_id, predicted_class in pred.prediction.items():
            true_class = ground_truth[pred.sample_id]["features"][node_id]["feature_class"]
            y_true.append(true_class)
            y_pred.append(predicted_class)
    
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    per_class = f1_score(y_true, y_pred, average=None, labels=FEATURE_CLASS_NAMES, zero_division=0)
    
    return {
        "task": "BENCH-001",
        "macro_f1": macro_f1,
        "passed": macro_f1 >= 0.80,
        "per_class_f1": dict(zip(FEATURE_CLASS_NAMES, per_class))
    }
```

---

## Confidence Calibration (Informational)

Not a pass/fail criterion for v0.1.0, but reported for research purposes:

```python
from sklearn.calibration import calibration_curve

fraction_of_positives, mean_predicted_value = calibration_curve(
    y_true, y_pred_proba, n_bins=10
)
# Plot reliability diagram; include in paper supplement
```

A well-calibrated model where confidence=0.8 means the prediction is correct ~80% of the time provides stronger scientific claims than uncalibrated scores.
