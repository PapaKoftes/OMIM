# Canonical Sample Schema

**Status: FROZEN**  
**Schema Version: v0.1.0**

Version: v0.1.0  
Section: 02_SCHEMA  

See also: [[02_SCHEMA/MGG_Schema]], [[02_SCHEMA/Validation_Report_Schema]], [[02_SCHEMA/Provenance_Schema]]

---

## Purpose

This document defines the exact, frozen format of one OMIM dataset sample — the atomic unit of every dataset, benchmark, and training corpus.

**Schema changes require version bump to `v0.2.0` and migration tooling.**

---

## Disk Layout

### Dataset Level

```
data/synthetic/
├── dataset_metadata.json          # Dataset-level metadata (generation config, statistics)
├── splits/
│   ├── train.jsonl                # Sample IDs for training set
│   ├── val.jsonl                  # Sample IDs for validation set
│   └── test.jsonl                 # Sample IDs for test set (held out)
└── samples/
    ├── sample_00001/
    │   ├── geometry.dxf           # Source DXF (geometry atom)
    │   ├── mgg.json               # Manufacturing Geometry Graph
    │   ├── validation.json        # ValidationReport
    │   ├── labels.json            # Ground truth labels
    │   └── provenance.json        # Full pipeline provenance chain
    ├── sample_00002/
    │   └── ...
    └── ...
```

### Per-Sample Files

```
data/synthetic/samples/sample_{id:05d}/
├── geometry.dxf          # Source DXF (geometry atom)
├── mgg.json              # Manufacturing Geometry Graph
├── validation.json       # ValidationReport
├── labels.json           # Ground truth labels
└── provenance.json       # Full pipeline provenance chain
```

**All five files are required.** A sample missing any file must NOT be included in any benchmark split.

---

## 1. `labels.json` — Ground Truth Labels

```json
{
  "$schema": "omim-labels-v0.1.0",
  "sample_id": "sample_00001",
  "schema_version": "v0.1.0",
  "is_valid": true,
  "injected_violations": [],
  "panel": {
    "width_mm": 800.0,
    "height_mm": 600.0,
    "thickness_mm": 18.0,
    "area_mm2": 480000.0,
    "material": "MDF"
  },
  "features": [
    {
      "feature_id": "feat_001",
      "feature_class": "SHELF_PIN_HOLE",
      "ontology_version": "v0.1.0",
      "diameter_mm": 5.0,
      "depth_mm": null,
      "is_through": false,
      "position_mm": [50.0, 32.0],
      "group_id": "shelf_pin_row_left",
      "geometry_entity_id": "circle_a3f2",
      "ground_truth_source": "synthetic_generator",
      "confidence": 1.0
    }
  ],
  "feature_counts": {"SHELF_PIN_HOLE": 4, "PROFILE_CUT": 1},
  "operations": ["DRILLING", "PROFILE_CUTTING"],
  "complexity": "medium",
  "split": "train"
}
```

### Required Fields

| Field | Type | Notes |
|-------|------|-------|
| `$schema` | string | Must be `"omim-labels-v0.1.0"` |
| `is_valid` | boolean | True iff passes all ERROR-level rules |
| `injected_violations` | list[string] | Rule IDs injected (empty for valid) |
| `panel.thickness_mm` | float | 18.0 default |
| `features[].feature_class` | string | Ontology v0.1.0 ID |
| `features[].position_mm` | [float, float] | [x, y] in panel coordinates |
| `features[].confidence` | float | 1.0 for synthetic ground truth |
| `split` | string | `"train"` \| `"val"` \| `"test"` |

---

## 2. `mgg.json` — Manufacturing Geometry Graph

See [[02_SCHEMA/MGG_Schema]] for the full node/edge schema.

```json
{
  "$schema": "omim-mgg-v0.1.0",
  "omim_mgg_version": "v0.1.0",
  "metadata": {
    "graph_id": "UUID",
    "spec_version": "v0.1.0",
    "ontology_version": "v0.1.0",
    "source_file": "geometry.dxf",
    "source_file_hash": "sha256:abc123...",
    "geometry_node_count": 12,
    "feature_node_count": 11,
    "creation_timestamp": "2026-05-30T14:23:05Z"
  },
  "nodes": [...],
  "links": [...]
}
```

**Invariant**: Every node must have a `provenance` field.

---

## 3. `validation.json` — ValidationReport

See [[02_SCHEMA/Validation_Report_Schema]] for the full schema.

```json
{
  "$schema": "omim-validation-v0.1.0",
  "layer1_passed": true,
  "layer2_passed": true,
  "overall_valid": true,
  "ruleset_version": "v0.1.0",
  "layer1_results": [...],
  "layer2_results": [...],
  "provenance": {"inference_method": "deterministic", "confidence": 1.0}
}
```

---

## 4. `provenance.json` — Pipeline Provenance

See [[02_SCHEMA/Provenance_Schema]] for the full schema.

```json
{
  "$schema": "omim-provenance-v0.1.0",
  "sample_id": "sample_00001",
  "pipeline_stages": [
    {"stage": "synthetic_generator", "inference_method": "synthetic", "confidence": 1.0},
    {"stage": "parser", "inference_method": "deterministic", "confidence": 1.0},
    {"stage": "graph_builder", "inference_method": "deterministic", "confidence": 1.0},
    {"stage": "validation", "inference_method": "deterministic", "confidence": 1.0},
    {"stage": "semantic", "inference_method": "heuristic", "confidence": 0.88}
  ],
  "dataset_version": "omim-synthetic-v0.1.0"
}
```

---

## 5. `geometry.dxf` — Source DXF

Requirements:
- `$INSUNITS = 4` (mm) in DXF header
- Standard layers: `CUT`, `DRILL`, `POCKET`, `BORDER`
- All Z coordinates = 0
- Reproducible from `(generation_seed, generation_config)` pair

---

## 6. `dataset_metadata.json` — Dataset-Level Metadata

```json
{
  "$schema": "omim-dataset-metadata-v0.1.0",
  "dataset_id": "omim-synthetic-v0.1.0-2026-05-30",
  "omim_version": "v0.1.0",
  "ontology_version": "v0.1.0",
  "ruleset_version": "v0.1.0",
  "creation_timestamp": "2026-05-30T14:00:00Z",

  "generation_config": {
    "seed": 42,
    "n_samples": 1000,
    "feature_density": "medium",
    "invalid_ratio": 0.30,
    "panel_width_range_mm": [100, 1200],
    "panel_height_range_mm": [100, 2400],
    "panel_thickness_options_mm": [12.0, 15.0, 16.0, 18.0, 22.0, 25.0]
  },

  "statistics": {
    "total_samples": 1000,
    "valid_samples": 700,
    "invalid_samples": 300,
    "train_samples": 700,
    "val_samples": 150,
    "test_samples": 150,
    "feature_counts": {
      "SHELF_PIN_HOLE": 3241,
      "HINGE_CUP_HOLE": 512,
      "THROUGH_HOLE": 1823,
      "CONFIRMAT_HOLE": 1456
    },
    "violation_counts": {
      "MFG-001": 120,
      "MFG-002": 95,
      "MFG-004": 65,
      "GEO-007": 42
    },
    "mean_features_per_panel": 7.2,
    "mean_panel_area_mm2": 412500
  },

  "schema_version": "v0.1.0",
  "license": "Apache 2.0",
  "citation": "OMIM: Open Manufacturing Intelligence Middleware (2026)",
  "source_type": "synthetic_generated",
  "contains_external_data": false,
  "grounding_note": "Feature frequencies based on European cabinet construction conventions and manufacturer catalogs; not validated against a real DXF corpus."
}
```

**Invariants**:
- `statistics.valid_samples + statistics.invalid_samples == statistics.total_samples`
- `statistics.train_samples + statistics.val_samples + statistics.test_samples == statistics.total_samples`
- `generation_config.seed` must be recorded for reproducibility

---

## Schema Validation Function

```python
def validate_sample_schema(sample_dir: str) -> list[str]:
    """Returns list of violations (empty = valid)."""
    errors = []
    for fname in ["geometry.dxf", "mgg.json", "validation.json", "labels.json", "provenance.json"]:
        if not Path(f"{sample_dir}/{fname}").exists():
            errors.append(f"MISSING FILE: {fname}")
    
    labels = json.loads(Path(f"{sample_dir}/labels.json").read_text())
    if labels.get("$schema") != "omim-labels-v0.1.0":
        errors.append("labels.json: wrong $schema version")
    for i, feat in enumerate(labels.get("features", [])):
        for req in ["feature_id", "feature_class", "position_mm", "ground_truth_source", "confidence"]:
            if req not in feat:
                errors.append(f"features[{i}]: missing '{req}'")
    
    mgg = json.loads(Path(f"{sample_dir}/mgg.json").read_text())
    for node in mgg.get("nodes", []):
        if "provenance" not in node.get("data", {}):
            errors.append(f"mgg.json node {node['id']}: missing provenance")
    return errors
```

---

## Automated Consistency Checks

| Check | When | Blocking? |
|-------|------|-----------|
| `check_ontology_consistency()` | At startup, before any processing | Yes — fail fast |
| `check_graph_integrity()` | After every MGG is built | Yes — don't continue with broken graph |
| `validate_sample_schema()` | Before adding sample to dataset | Yes — reject bad samples |
| `check_dataset_consistency()` | After bulk generation | Yes — don't release broken dataset |

### `check_graph_integrity()`

```python
def check_graph_integrity(mgg: ManufacturingGeometryGraph) -> list[str]:
    """
    Verify internal MGG consistency.
    These catch structural problems that per-field Pydantic validation cannot.
    Returns list of violations (empty = clean).
    """
    violations = []

    # 1. No orphan geometry nodes
    # Every GeometryNode must be referenced by at least one FeatureNode
    # OR be the panel boundary itself
    all_geo_ids = {n.node_id for n in mgg.query().get_geometry_nodes()}
    referenced_geo_ids = set()
    for feat in mgg.query().get_feature_nodes():
        referenced_geo_ids.update(feat.geometry_node_ids)
    panel_boundary_ids = {n.node_id for n in mgg.query().get_geometry_nodes() if n.is_outer_boundary}

    orphans = all_geo_ids - referenced_geo_ids - panel_boundary_ids
    for orphan_id in orphans:
        violations.append(f"ORPHAN_GEOMETRY: {orphan_id} not referenced by any FeatureNode")

    # 2. No dangling edges
    # Every edge source and target must exist as a node
    all_node_ids = {n for n in mgg._graph.nodes()}
    for src, tgt, _ in mgg._graph.edges(data=True):
        if src not in all_node_ids:
            violations.append(f"DANGLING_EDGE_SOURCE: {src}")
        if tgt not in all_node_ids:
            violations.append(f"DANGLING_EDGE_TARGET: {tgt}")

    # 3. No self-loops
    for src, tgt, _ in mgg._graph.edges(data=True):
        if src == tgt:
            violations.append(f"SELF_LOOP: node {src} has edge to itself")

    # 4. Feature confidence within [0.0, 1.0]
    for feat in mgg.query().get_feature_nodes():
        if not 0.0 <= feat.confidence <= 1.0:
            violations.append(
                f"INVALID_CONFIDENCE: {feat.node_id} has confidence={feat.confidence}"
            )

    # 5. Every feature class is in the loaded ontology
    ontology = get_ontology()  # singleton
    for feat in mgg.query().get_feature_nodes():
        if feat.feature_class != "UNKNOWN_FEATURE" and not ontology.is_valid_feature_id(feat.feature_class):
            violations.append(
                f"UNKNOWN_FEATURE_CLASS: {feat.node_id} class='{feat.feature_class}' "
                f"not in ontology v{ontology.version}"
            )

    # 6. No geometry nodes with zero or negative dimensions
    for geo in mgg.query().get_geometry_nodes():
        if geo.area_mm2 is not None and geo.area_mm2 < 0:
            violations.append(f"NEGATIVE_AREA: {geo.node_id} area={geo.area_mm2}")
        if geo.diameter_mm is not None and geo.diameter_mm <= 0:
            violations.append(f"NON_POSITIVE_DIAMETER: {geo.node_id} diameter={geo.diameter_mm}")

    return violations
```

### `check_dataset_consistency()`

```python
def check_dataset_consistency(dataset_dir: str) -> list[str]:
    """
    Verify all samples in a dataset directory are schema-valid and consistent.
    Returns list of violations (empty = clean).

    Checks:
    - Every sample has all required files
    - Every sample validates against canonical schema
    - Train/val/test splits are disjoint (no sample appears in multiple splits)
    - Total sample count matches dataset_metadata.json
    """
    violations = []

    # Load splits
    train_ids = set(load_split_ids(f"{dataset_dir}/splits/train.jsonl"))
    val_ids   = set(load_split_ids(f"{dataset_dir}/splits/val.jsonl"))
    test_ids  = set(load_split_ids(f"{dataset_dir}/splits/test.jsonl"))

    # Check split disjointness
    if overlap := train_ids & val_ids:
        violations.append(f"SPLIT_OVERLAP train/val: {sorted(overlap)[:5]}...")
    if overlap := train_ids & test_ids:
        violations.append(f"SPLIT_OVERLAP train/test: {sorted(overlap)[:5]}...")
    if overlap := val_ids & test_ids:
        violations.append(f"SPLIT_OVERLAP val/test: {sorted(overlap)[:5]}...")

    # Per-sample schema validation
    for sample_id in (train_ids | val_ids | test_ids):
        sample_errors = validate_sample_schema(f"{dataset_dir}/samples/{sample_id}")
        violations.extend(sample_errors)

    # Check total count matches metadata
    metadata = json.loads(Path(f"{dataset_dir}/dataset_metadata.json").read_text())
    expected_total = metadata["statistics"]["total_samples"]
    actual_total = len(train_ids) + len(val_ids) + len(test_ids)
    if expected_total != actual_total:
        violations.append(
            f"SAMPLE_COUNT_MISMATCH: metadata says {expected_total}, "
            f"splits contain {actual_total}"
        )

    return violations
```

---

## Version & Migration Policy

| Version | Date | Status |
|---------|------|--------|
| v0.1.0 | 2026-05-30 | Active, frozen for hackathon |

Schema changes require: version bump, migration script `tools/migrate_dataset_v{old}_to_v{new}.py`, updated validation function, changelog entry.
