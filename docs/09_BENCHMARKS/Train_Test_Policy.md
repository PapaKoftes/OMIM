# Train-Test Policy

Version: v0.1.0  
Section: 09_BENCHMARKS  

See also: [[09_BENCHMARKS/Benchmark_Reproducibility]], [[07_SYNTHETIC_GENERATION/Dataset_Distribution_Policy]]

---

## Purpose

Defines the rules for dataset splits, test set integrity, and prevention of data leakage. These rules are non-negotiable for scientific validity.

---

## Split Assignments

```
train:  70% (700 samples) — used for model training; may be regenerated
val:    15% (150 samples) — hyperparameter tuning and early stopping
test:   15% (150 samples) — final evaluation only; FROZEN PERMANENTLY
```

Split assignment is determined by `sample_index % 100`:
- `sample_index % 100 < 70` → train
- `70 ≤ sample_index % 100 < 85` → val
- `85 ≤ sample_index % 100 < 100` → test

This deterministic assignment means split membership is reproducible from the sample index alone.

---

## Test Set Immutability Rules

**Rule T-001**: The test set is generated exactly once and never regenerated.

```
Test set seed: config.random_seed + 999_999  (fixed offset from train seed)
Test generation date: recorded in manifest.json
Test set hash: SHA256 of all test sample IDs stored in MANIFEST_TEST_HASH
```

**Rule T-002**: Test samples are not used for:
- Training
- Hyperparameter search
- Feature engineering decisions
- Threshold calibration
- Architecture search

Any use of test samples outside final evaluation is considered test set contamination.

**Rule T-003**: Test ground truth labels are not published until after the first public evaluation round.

This prevents models from being trained on test labels even indirectly.

---

## Data Leakage Prevention

### Leakage Type 1: Ground Truth in Input Features

The MGG must not contain ground-truth labels as node attributes. The `feature_class` field on a FeatureNode in the MGG is set by the semantic inference layer, not from labels.json.

```python
# CORRECT: MGG contains only geometry
mgg_node = GeometryNode(
    entity_type="CIRCLE",
    radius_mm=17.5,
    centroid=[22.5, 150.0]
    # No feature_class here — that's labels.json
)

# FORBIDDEN: MGG with labels embedded
mgg_node = GeometryNode(
    ...,
    feature_class="HINGE_CUP_HOLE"  # NEVER in input features
)
```

### Leakage Type 2: Validation Results as Features

Validation results (is_valid, failed rules) must not be used as input features for BENCH-002.

```python
# BENCH-002 input: only MGG
prediction = model.predict(mgg)  # CORRECT

# FORBIDDEN: using validation output as input
prediction = model.predict(mgg, validation_report)  # NEVER for BENCH-002
```

### Leakage Type 3: Test Set Statistics in Normalization

Feature normalization statistics (mean, std for continuous features) must be computed on the training set only.

```python
# CORRECT: fit normalizer on train set only
normalizer.fit(train_features)
test_features_normalized = normalizer.transform(test_features)

# FORBIDDEN: fit on full dataset including test
normalizer.fit(all_features)  # NEVER
```

---

## Cross-Validation Policy

Cross-validation on the training set is permitted and encouraged. K-fold CV on train+val is also permitted.

**CV constraint**: If using cross-validation, each fold's validation portion must not overlap with any other fold's validation. Standard K-fold satisfies this.

---

## Reporting Requirements

All published results must include:
1. Which split (train/val/test) the results are from
2. Whether hyperparameter tuning was performed and on which split
3. Random seed used for model training
4. Number of training samples used
5. Whether any data augmentation was applied

Results reported only on train or val sets must be clearly labeled as such. Only test-set results count as final evaluation.

---

## OMIM Validation Pipeline as Baseline

The OMIM rule-based pipeline is the baseline for all 4 benchmarks. Baseline results are computed on the test set:

| Task | OMIM Baseline | Notes |
|------|-------------|-------|
| BENCH-001 | Semantic inference Macro F1 | Reported in paper |
| BENCH-002 | Rule-based validation Binary F1 | Should achieve FNR=0 on synthetic data |
| BENCH-003 | Deterministic op mapping Macro F1 | Bounded by BENCH-001 baseline |
| BENCH-004 | Rule-based anomaly score | Validation error count as anomaly score |

Any submitted model must outperform the OMIM baseline on at least one benchmark task to be considered a contribution.
