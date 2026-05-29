# Canonical Sample Schema v0.1

**Status: FROZEN**  
**Schema Version: v0.1.0**  
**This file is the authoritative definition of one OMIM dataset atom.**

See also: [[Dataset and Research Infrastructure]], [[Manufacturing Geometry Graph (MGG) Specification]], [[Provenence and Uncertainty]], [[Benchmarking]]

---

## Purpose

This document defines the exact, frozen format of one manufacturing dataset sample.  

Every tool that reads or writes OMIM dataset samples MUST conform to this schema. No exceptions. No optional fields that are "sometimes" missing. No version drift between modules.

If you are unsure whether your output is correct: validate it against this document.

**Schema changes require a version bump to `v0.2.0` and migration tooling.**

---

## Disk Layout (Per Sample)

```
data/synthetic/samples/sample_{id:05d}/
├── geometry.dxf          # Source DXF (the geometry atom)
├── mgg.json              # Manufacturing Geometry Graph (see below)
├── validation.json       # ValidationReport (see below)
├── labels.json           # Ground truth labels (see below)
└── provenance.json       # Full pipeline provenance chain (see below)
```

**All five files are required.** A sample is incomplete (and must not be included in any benchmark split) if any file is missing.

---

## 1. `labels.json` — Ground Truth Labels

This is the primary ML target. It answers: "what is in this panel?"

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
  
  "feature_counts": {
    "SHELF_PIN_HOLE": 4,
    "HINGE_CUP_HOLE": 0,
    "THROUGH_HOLE": 2,
    "CONFIRMAT_HOLE": 3,
    "DOWEL_HOLE": 0,
    "POCKET": 0,
    "GROOVE": 1,
    "PROFILE_CUT": 1
  },
  
  "operations": ["DRILLING", "CNC_ROUTING", "PROFILE_CUTTING"],
  
  "complexity": "medium",
  
  "split": "train"
}
```

### labels.json Field Specification

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `$schema` | string | yes | Must be `"omim-labels-v0.1.0"` |
| `sample_id` | string | yes | Matches directory name |
| `schema_version` | string | yes | `"v0.1.0"` |
| `is_valid` | boolean | yes | True iff passes all ERROR-level validation rules |
| `injected_violations` | list[string] | yes | List of rule_ids injected (empty for valid samples) |
| `panel.width_mm` | float | yes | Panel width in mm |
| `panel.height_mm` | float | yes | Panel height in mm |
| `panel.thickness_mm` | float | yes | Panel thickness in mm (18.0 default) |
| `panel.area_mm2` | float | yes | Computed: width × height |
| `panel.material` | string | yes | From ontology materials (e.g., `"MDF"`) |
| `features` | list[FeatureLabel] | yes | One entry per machined feature |
| `features[].feature_id` | string | yes | Unique within sample (e.g., `"feat_001"`) |
| `features[].feature_class` | string | yes | Ontology feature ID (e.g., `"SHELF_PIN_HOLE"`) |
| `features[].ontology_version` | string | yes | `"v0.1.0"` |
| `features[].diameter_mm` | float\|null | yes | Null for non-circular features |
| `features[].depth_mm` | float\|null | yes | Null if not tracked (2D DXF) |
| `features[].is_through` | boolean | yes | True for through features |
| `features[].position_mm` | [float, float] | yes | [x, y] centroid in panel coordinates |
| `features[].group_id` | string\|null | yes | Null if not part of a group |
| `features[].geometry_entity_id` | string | yes | ID of corresponding GeometryNode in MGG |
| `features[].ground_truth_source` | string | yes | `"synthetic_generator"` \| `"human_annotated"` |
| `features[].confidence` | float | yes | 1.0 for synthetic ground truth |
| `feature_counts` | dict[str, int] | yes | Count of each feature class (0 if absent) |
| `operations` | list[string] | yes | Required operations from ontology |
| `complexity` | string | yes | `"simple"` \| `"medium"` \| `"complex"` |
| `split` | string | yes | `"train"` \| `"val"` \| `"test"` |

---

## 2. `mgg.json` — Manufacturing Geometry Graph

Full MGG serialization. See [[Manufacturing Geometry Graph (MGG) Specification]] for node/edge schemas.

```json
{
  "$schema": "omim-mgg-v0.1.0",
  "omim_mgg_version": "v0.1.0",
  
  "metadata": {
    "graph_id": "3f9a1b2c-...",
    "spec_version": "v0.1.0",
    "ontology_version": "v0.1.0",
    "source_file": "geometry.dxf",
    "source_file_hash": "sha256:abc123...",
    "part_id": "sample_00001",
    "panel_bounding_box": [0.0, 0.0, 800.0, 600.0],
    "panel_area_mm2": 480000.0,
    "geometry_node_count": 12,
    "feature_node_count": 11,
    "operation_node_count": 3,
    "constraint_node_count": 0,
    "edge_count": 28,
    "creation_timestamp": "2026-05-30T14:23:05Z",
    "parser_version": "omim-v0.1.0"
  },
  
  "nodes": [
    {
      "id": "circle_a3f2",
      "data": {
        "node_id": "circle_a3f2",
        "node_type": "geometry",
        "geometry_type": "circle",
        "layer": "DRILL",
        "inferred_layer_type": "drill",
        "coordinates": [50.0, 32.0, 2.5],
        "is_closed": true,
        "bounding_box": [47.5, 29.5, 52.5, 34.5],
        "area_mm2": 19.635,
        "perimeter_mm": 15.708,
        "centroid": [50.0, 32.0],
        "diameter_mm": 5.0,
        "radius_mm": 2.5,
        "is_outer_boundary": false,
        "contains_node_ids": [],
        "source_entity_id": "2A",
        "source_file": "geometry.dxf",
        "source_file_hash": "sha256:abc123...",
        "creation_method": "parsed",
        "provenance": { "..." : "..." }
      }
    }
  ],
  
  "links": [
    {
      "source": "panel_contour_01",
      "target": "circle_a3f2",
      "key": "edge_001",
      "data": {
        "edge_id": "edge_001",
        "source_id": "panel_contour_01",
        "target_id": "circle_a3f2",
        "relationship_type": "CONTAINS",
        "confidence": 1.0,
        "provenance": { "..." : "..." }
      }
    }
  ]
}
```

### mgg.json Required Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `$schema` | string | yes | `"omim-mgg-v0.1.0"` |
| `omim_mgg_version` | string | yes | `"v0.1.0"` |
| `metadata` | GraphMetadata | yes | Full metadata object |
| `metadata.graph_id` | UUID string | yes | |
| `metadata.spec_version` | string | yes | `"v0.1.0"` |
| `metadata.source_file_hash` | string | yes | `sha256:...` format |
| `nodes` | list | yes | At minimum: one panel boundary node + one per DXF entity |
| `links` | list | yes | At minimum: CONTAINS edges from panel to features |
| Every node | has `provenance` | yes | No provenance-less nodes |

---

## 3. `validation.json` — ValidationReport

```json
{
  "$schema": "omim-validation-v0.1.0",
  "report_id": "val_9f2a3...",
  "graph_id": "3f9a1b2c-...",
  "schema_version": "v0.1.0",
  "timestamp": "2026-05-30T14:23:06Z",
  
  "ruleset_version": "v0.1.0",
  
  "layer1_passed": true,
  "layer2_passed": true,
  "overall_valid": true,
  "has_warnings": false,
  
  "severity_summary": {
    "ERROR": 0,
    "WARNING": 0,
    "INFO": 0,
    "SYSTEM_ERROR": 0
  },
  
  "layer1_results": [
    {
      "rule_id": "GEO-001",
      "rule_version": "v0.1.0",
      "rule_name": "contour_closure",
      "passed": true,
      "severity": "ERROR",
      "message": "All contours are closed",
      "affected_node_ids": [],
      "evidence": {},
      "execution_time_ms": 0.8
    }
  ],
  
  "layer2_results": [
    {
      "rule_id": "MFG-001",
      "rule_version": "v0.1.0",
      "rule_name": "minimum_edge_clearance",
      "passed": true,
      "severity": "ERROR",
      "message": "All features within edge clearance bounds",
      "affected_node_ids": [],
      "evidence": {"min_measured_mm": 12.4, "threshold_mm": 8.0},
      "execution_time_ms": 2.1
    }
  ],
  
  "failed_node_ids": [],
  "validation_time_ms": 15.3,
  
  "provenance": {
    "record_id": "...",
    "generator": "omim",
    "generator_version": "v0.1.0",
    "inference_method": "deterministic",
    "confidence": 1.0,
    "ruleset_version": "v0.1.0"
  }
}
```

### validation.json Required Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `$schema` | string | yes | `"omim-validation-v0.1.0"` |
| `layer1_passed` | boolean | yes | |
| `layer2_passed` | boolean | yes | |
| `overall_valid` | boolean | yes | True iff zero ERROR results |
| `ruleset_version` | string | yes | Must match active ruleset |
| `layer1_results` | list[RuleResult] | yes | One entry per rule evaluated |
| `layer2_results` | list[RuleResult] | yes | One entry per rule evaluated |
| Every RuleResult | has `rule_id`, `rule_version`, `passed`, `severity` | yes | |
| `provenance` | ProvenanceRecord | yes | inference_method MUST be `"deterministic"` |

### Validation Result for Invalid Samples (Example)

```json
{
  "overall_valid": false,
  "layer2_passed": false,
  "layer2_results": [
    {
      "rule_id": "MFG-001",
      "rule_version": "v0.1.0",
      "rule_name": "minimum_edge_clearance",
      "passed": false,
      "severity": "ERROR",
      "message": "Circle at (4.0, 50.0) is 4.0mm from panel edge (threshold: 8.0mm)",
      "affected_node_ids": ["circle_b7f1"],
      "evidence": {
        "measured_mm": 4.0,
        "threshold_mm": 8.0,
        "feature_centroid": [4.0, 50.0],
        "nearest_edge": "left"
      }
    }
  ]
}
```

---

## 4. `provenance.json` — Full Provenance Chain

```json
{
  "$schema": "omim-provenance-v0.1.0",
  "sample_id": "sample_00001",
  "schema_version": "v0.1.0",
  
  "pipeline_stages": [
    {
      "stage": "synthetic_generator",
      "record_id": "...",
      "timestamp": "2026-05-30T14:23:05Z",
      "generator": "omim",
      "generator_version": "v0.1.0",
      "ontology_version": "v0.1.0",
      "ruleset_version": "v0.1.0",
      "inference_method": "synthetic",
      "confidence": 1.0,
      "generation_seed": 1001,
      "generation_config": "default.yaml",
      "module": "omim.synthetic.panel_generator"
    },
    {
      "stage": "parser",
      "record_id": "...",
      "timestamp": "2026-05-30T14:23:05Z",
      "inference_method": "deterministic",
      "confidence": 1.0,
      "source_file": "geometry.dxf",
      "source_file_hash": "sha256:abc123...",
      "module": "omim.parser.dxf_reader"
    },
    {
      "stage": "graph_builder",
      "record_id": "...",
      "timestamp": "2026-05-30T14:23:05Z",
      "inference_method": "deterministic",
      "confidence": 1.0,
      "parent_record_ids": ["parser_record_id"],
      "module": "omim.graph.builder"
    },
    {
      "stage": "validation",
      "record_id": "...",
      "timestamp": "2026-05-30T14:23:06Z",
      "inference_method": "deterministic",
      "confidence": 1.0,
      "ruleset_version": "v0.1.0",
      "rules_evaluated": ["GEO-001", "GEO-002", "GEO-003", "MFG-001", "MFG-002"],
      "module": "omim.validation.rule_engine"
    },
    {
      "stage": "semantic",
      "record_id": "...",
      "timestamp": "2026-05-30T14:23:06Z",
      "inference_method": "heuristic",
      "confidence": 0.88,
      "evidence_summary": "Diameter-based classification + 32mm pattern detection",
      "module": "omim.semantic.inference_engine"
    }
  ],
  
  "generation_config_hash": "sha256:def456...",
  "dataset_version": "omim-synthetic-v0.1.0"
}
```

### provenance.json Required Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `$schema` | string | yes | `"omim-provenance-v0.1.0"` |
| `pipeline_stages` | list | yes | One entry per pipeline stage run |
| Every stage | has `stage`, `timestamp`, `inference_method`, `confidence`, `generator_version` | yes | |
| `dataset_version` | string | yes | `"omim-synthetic-v0.1.0"` |

---

## 5. `geometry.dxf` — Source DXF

The DXF file is the canonical geometry source. It must:
- Use standard layer names: `CUT`, `DRILL`, `POCKET`, `BORDER`
- Set `$INSUNITS = 4` (mm) in DXF header
- Contain only 2D entities (Z = 0 for all coordinates)
- Be reproducible from `(generation_seed, generation_config)` pair

---

## Completeness Invariant

The following identity must hold for any valid sample:

```python
# The geometry.dxf, when passed through the OMIM pipeline, must produce
# output consistent with the stored mgg.json, validation.json, labels.json.

def verify_sample_consistency(sample_dir: str) -> bool:
    """
    Re-run pipeline on stored DXF. Compare with stored files.
    Returns True if all outputs match stored files.
    """
    dxf_path = f"{sample_dir}/geometry.dxf"
    result = analyze_dxf(dxf_path)  # full pipeline
    
    stored_labels = load_labels(sample_dir)
    stored_validation = load_validation(sample_dir)
    stored_mgg = load_mgg(sample_dir)
    
    # Check consistency (not byte-identical — floating point may vary)
    assert result.validation.overall_valid == stored_labels["is_valid"]
    assert set(result.feature_classes) == set(f["feature_class"] for f in stored_labels["features"])
    
    return True
```

---

## Schema Validation (At Write Time)

Every sample MUST be validated against this schema before being added to any dataset:

```python
# omim/synthetic/dataset_builder.py

def validate_sample_schema(sample_dir: str) -> list[str]:
    """
    Returns list of schema violations (empty = valid).
    Raises DatasetIntegrityError if critical fields missing.
    """
    errors = []
    
    # Check all files exist
    for fname in ["geometry.dxf", "mgg.json", "validation.json", "labels.json", "provenance.json"]:
        if not Path(f"{sample_dir}/{fname}").exists():
            errors.append(f"MISSING FILE: {fname}")
    
    # Load and validate labels.json
    labels = json.loads(Path(f"{sample_dir}/labels.json").read_text())
    if labels.get("$schema") != "omim-labels-v0.1.0":
        errors.append("labels.json: wrong $schema version")
    if "features" not in labels:
        errors.append("labels.json: missing 'features' field")
    if "is_valid" not in labels:
        errors.append("labels.json: missing 'is_valid' field")
    
    # Check every feature has required fields
    for i, feat in enumerate(labels.get("features", [])):
        for required in ["feature_id", "feature_class", "position_mm", "ground_truth_source", "confidence"]:
            if required not in feat:
                errors.append(f"labels.json features[{i}]: missing '{required}'")
    
    # Check provenance exists in mgg.json nodes
    mgg = json.loads(Path(f"{sample_dir}/mgg.json").read_text())
    for node in mgg.get("nodes", []):
        if "provenance" not in node.get("data", {}):
            errors.append(f"mgg.json: node {node['id']} missing provenance")
    
    return errors
```

---

## Automated Consistency Checks

Beyond per-sample schema validation, the following system-level consistency checks run automatically. Bad data must not silently enter the corpus.

### Graph-Level Checks

```python
# omim/validation/consistency.py

def check_graph_integrity(mgg: ManufacturingGeometryGraph) -> list[ConsistencyError]:
    """
    Run all automated graph integrity checks.
    These catch structural problems that per-field Pydantic validation cannot.
    """
    errors = []
    
    # 1. No orphan geometry nodes
    # Every GeometryNode must be reachable from at least one FeatureNode
    # OR be the panel boundary itself
    all_geo_ids = {n.node_id for n in mgg.query().get_geometry_nodes()}
    referenced_geo_ids = set()
    for feat in mgg.query().get_feature_nodes():
        referenced_geo_ids.update(feat.geometry_node_ids)
    panel_boundary_ids = {n.node_id for n in mgg.query().get_geometry_nodes() if n.is_outer_boundary}
    
    orphans = all_geo_ids - referenced_geo_ids - panel_boundary_ids
    for orphan_id in orphans:
        errors.append(ConsistencyError(
            check="orphan_geometry_node",
            node_id=orphan_id,
            message=f"GeometryNode {orphan_id} not referenced by any FeatureNode"
        ))
    
    # 2. No dangling edges
    # Every edge source and target must exist as a node
    all_node_ids = {n["id"] for n in mgg._graph.nodes(data=True)}
    for src, tgt, data in mgg._graph.edges(data=True):
        if src not in all_node_ids:
            errors.append(ConsistencyError(check="dangling_edge_source", message=f"Edge source {src} not found"))
        if tgt not in all_node_ids:
            errors.append(ConsistencyError(check="dangling_edge_target", message=f"Edge target {tgt} not found"))
    
    # 3. No self-loops (a node pointing to itself)
    for src, tgt, _ in mgg._graph.edges(data=True):
        if src == tgt:
            errors.append(ConsistencyError(check="self_loop", node_id=src, message=f"Self-loop on node {src}"))
    
    # 4. Feature confidence within range
    for feat in mgg.query().get_feature_nodes():
        if not 0.0 <= feat.confidence <= 1.0:
            errors.append(ConsistencyError(
                check="invalid_confidence",
                node_id=feat.node_id,
                message=f"Confidence {feat.confidence} outside [0.0, 1.0]"
            ))
    
    # 5. Every feature class is in the loaded ontology
    ontology = get_ontology()  # singleton
    for feat in mgg.query().get_feature_nodes():
        if feat.feature_class != "UNKNOWN_FEATURE" and not ontology.is_valid_feature_id(feat.feature_class):
            errors.append(ConsistencyError(
                check="unknown_feature_class",
                node_id=feat.node_id,
                message=f"Feature class '{feat.feature_class}' not in ontology v{ontology.version}"
            ))
    
    # 6. No geometry nodes with zero or negative dimensions
    for geo in mgg.query().get_geometry_nodes():
        if geo.area_mm2 is not None and geo.area_mm2 < 0:
            errors.append(ConsistencyError(check="negative_area", node_id=geo.node_id))
        if geo.diameter_mm is not None and geo.diameter_mm <= 0:
            errors.append(ConsistencyError(check="non_positive_diameter", node_id=geo.node_id))
    
    return errors


def check_ontology_consistency(ontology: Ontology) -> list[ConsistencyError]:
    """
    Check the loaded ontology for internal consistency.
    Run once at startup before any processing begins.
    """
    errors = []
    
    # 1. No duplicate feature IDs
    seen_ids = set()
    for feat_id in ontology.features:
        if feat_id in seen_ids:
            errors.append(ConsistencyError(check="duplicate_feature_id", message=f"Duplicate: {feat_id}"))
        seen_ids.add(feat_id)
    
    # 2. Every relationship has a defined direction (source_type, target_type)
    for rel_id, rel in ontology.relationships.items():
        if not hasattr(rel, 'source_types') or not hasattr(rel, 'target_types'):
            errors.append(ConsistencyError(check="undirected_relationship", message=f"{rel_id} missing direction"))
    
    # 3. Every operation references valid feature classes it produces
    for op_id, op in ontology.operations.items():
        for feat_id in getattr(op, 'produces_features', []):
            if feat_id not in ontology.features:
                errors.append(ConsistencyError(
                    check="operation_references_unknown_feature",
                    message=f"Operation {op_id} references unknown feature {feat_id}"
                ))
    
    return errors


def check_dataset_consistency(dataset_dir: str, n_samples: int = None) -> ConsistencyReport:
    """
    Run all consistency checks across an entire dataset directory.
    
    Checks:
    - Every sample has all required files
    - Every sample validates against canonical schema
    - No sample appears in multiple splits
    - Train/val/test splits are disjoint
    - Feature distribution roughly matches target distribution
    """
    # Load splits
    train_ids = load_split_ids(f"{dataset_dir}/splits/train.jsonl")
    val_ids = load_split_ids(f"{dataset_dir}/splits/val.jsonl")
    test_ids = load_split_ids(f"{dataset_dir}/splits/test.jsonl")
    
    # Check split disjointness
    if train_ids & val_ids:
        raise ConsistencyError(check="split_overlap", message="train/val overlap")
    if train_ids & test_ids:
        raise ConsistencyError(check="split_overlap", message="train/test overlap")
    if val_ids & test_ids:
        raise ConsistencyError(check="split_overlap", message="val/test overlap")
    
    # Per-sample checks
    errors = []
    for sample_id in (train_ids | val_ids | test_ids):
        sample_errors = validate_sample_schema(f"{dataset_dir}/samples/{sample_id}")
        errors.extend(sample_errors)
    
    return ConsistencyReport(
        total_samples=len(train_ids) + len(val_ids) + len(test_ids),
        errors=errors,
        is_clean=len(errors) == 0
    )
```

### When Consistency Checks Run

| Check | When | Blocking? |
|-------|------|-----------|
| `check_ontology_consistency()` | At startup, before any processing | Yes — fail fast |
| `check_graph_integrity()` | After every MGG is built | Yes — don't continue with broken graph |
| `validate_sample_schema()` | Before adding sample to dataset | Yes — reject bad samples |
| `check_dataset_consistency()` | After bulk generation | Yes — don't release broken dataset |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.1.0 | 2026-05-30 | Initial frozen schema |

## Migration Policy

Schema changes require:
1. Version bump (v0.1.0 → v0.2.0)
2. Migration script: `tools/migrate_dataset_v0.1_to_v0.2.py`
3. Updated validation function
4. Changelog entry

**Never silently change field names or semantics within a version.**
