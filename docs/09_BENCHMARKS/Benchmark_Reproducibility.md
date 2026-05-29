# Benchmark Reproducibility

Version: v0.1.0  
Section: 09_BENCHMARKS  

See also: [[09_BENCHMARKS/Benchmark_Tasks]], [[09_BENCHMARKS/Train_Test_Policy]], [[07_SYNTHETIC_GENERATION/Synthetic_Generation_System]]

---

## Purpose

Documents how OMIM benchmarks are made reproducible and how reproducibility is verified. Scientific claims are only valid if other researchers can reproduce the same results.

---

## Reproducibility Requirements

### R-001: Dataset Reproducibility

The same dataset must be regeneratable from config alone:

```python
# Given this config, the dataset is always identical
config = PanelGeneratorConfig(
    random_seed=42,
    num_samples=1000,
    ruleset_version="0.1.0",
    schema_version="0.1.0"
)
dataset = PanelGenerator(config).generate_dataset()

# Verification: hash the generated files
manifest_hash = sha256_of_all_sample_ids(dataset.manifest)
assert manifest_hash == EXPECTED_MANIFEST_HASH_V0_1_0
```

The `EXPECTED_MANIFEST_HASH_V0_1_0` is published in the dataset release notes.

### R-002: Model Training Reproducibility

Published models must include:
- Model architecture (code, not prose description)
- Random seed for training
- Exact Python dependency versions (requirements.txt or Poetry lockfile)
- Training hardware specification (GPU type, memory)

### R-003: Evaluation Reproducibility

The evaluation script is part of the OMIM codebase and is not modifiable by benchmark participants:

```python
# omim/benchmark/evaluate.py — canonical evaluation script
def evaluate_submission(submission: BenchmarkSubmission, test_labels: dict) -> EvaluationResult:
    """Canonical evaluation. Results from this function are the official benchmark scores."""
```

All published results must use this function, not custom evaluation code.

---

## Dataset Version Tracking

Each published dataset version has:

```python
class DatasetVersion(BaseModel):
    version: str          # e.g., "0.1.0"
    config_hash: str      # SHA256 of PanelGeneratorConfig
    manifest_hash: str    # SHA256 of manifest.json
    sample_count: int
    release_date: str
    ruleset_version: str
    changelog: str
```

**Dataset versions are immutable.** If a bug is found, a new version is released with a new version number.

---

## Expert Validation Loop

Before the first public benchmark release, a manufacturing domain expert reviews synthetic data realism:

### Review Protocol

1. Randomly sample 30 valid panels from the test set
2. Randomly sample 10 invalid panels from the test set (without labels)
3. Present to CNC operator / cabinet manufacturing expert
4. Expert answers: "Is each panel geometrically plausible as a real cabinet component?"
5. Expert identifies any obviously unrealistic geometry

### Acceptance Criteria

- ≥ 80% of valid panels rated "plausible" by expert
- ≥ 70% of invalid panels identified as "suspicious or incorrect" by expert
- No valid sample contains geometry the expert would never produce

### Failure Action

If expert rejects more than 20% of valid panels as implausible:
1. Identify which generation rules produce implausible geometry
2. Update Realism_Constraints.md with new grounding
3. Regenerate dataset with updated constraints
4. Re-run expert review

Results of expert review are documented here:

```
v0.1.0 Expert Review: PENDING
Reviewer: [CNC operator, anonymized]
Review date: TBD
Result: TBD
```

---

## Benchmark Integrity Checks

Run before any evaluation:

```python
def check_benchmark_integrity(test_set_dir: str, manifest: DatasetManifest) -> list[str]:
    """Returns list of integrity violations (empty = clean)."""
    violations = []
    
    # 1. Verify all test samples are present
    expected = [s for s, split in manifest.sample_ids.items() if split == "test"]
    for sample_id in expected:
        if not os.path.exists(os.path.join(test_set_dir, sample_id)):
            violations.append(f"Missing test sample: {sample_id}")
    
    # 2. Verify manifest hash
    current_hash = compute_manifest_hash(test_set_dir)
    if current_hash != manifest.manifest_hash:
        violations.append("Manifest hash mismatch — test set may have been modified")
    
    # 3. Verify schema validity of all test samples
    for sample_id in expected:
        errors = validate_sample_schema(os.path.join(test_set_dir, sample_id))
        if errors:
            violations.append(f"Sample {sample_id} failed schema: {errors}")
    
    return violations
```

This check runs as part of CI before any evaluation results are accepted.

---

## Dependency Lock

Benchmark evaluation depends on exact library versions. Breaking changes in sklearn or numpy can change metric values.

```
# requirements-benchmark.txt (locked versions)
scikit-learn==1.5.0
numpy==1.26.4
pydantic==2.7.1
```

Evaluation results published with different dependency versions are not comparable to v0.1.0 results.
