# Sample Generation Flow

Version: v0.1.0  
Section: 07_SYNTHETIC_GENERATION  

See also: [[07_SYNTHETIC_GENERATION/Synthetic_Generation_System]], [[07_SYNTHETIC_GENERATION/Constraint_Grammar]], [[03_INTERFACES/Dataset_Export_Interface]]

---

## Overview

End-to-end flow for generating a single labeled sample. Each step is deterministic given the sample's assigned seed.

---

## Step-by-Step Generation

### Step 1: Assign Sample Seed

```python
sample_rng = np.random.default_rng(config.random_seed + sample_index)
```

Each sample has a unique derived seed. The dataset seed + sample index → fully reproducible per-sample generation.

---

### Step 2: Sample Panel Spec

```python
panel_type = sample_from_distribution(PANEL_TYPE_DISTRIBUTION, sample_rng)
width = sample_from_distribution(WIDTH_DISTRIBUTION[panel_type], sample_rng)
height = sample_from_distribution(HEIGHT_DISTRIBUTION[panel_type], sample_rng)
thickness = sample_from_distribution(THICKNESS_DISTRIBUTION, sample_rng)
is_invalid = sample_rng.random() < config.invalid_sample_ratio

panel = PanelSpec(
    width_mm=width,
    height_mm=height,
    thickness_mm=thickness,
    panel_type=panel_type,
    boundary_points=[(0,0), (width,0), (width,height), (0,height)]
)
```

---

### Step 3: Generate Features

```python
allowed = PANEL_TYPE_ALLOWED_FEATURES[panel_type]
feature_count = sample_hole_count(panel_type, sample_rng)
features = []

# Generate PROFILE_CUT (always present)
features.append(generate_profile_cut(panel))

# Generate holes according to distribution
for _ in range(feature_count):
    feature_class = sample_from_distribution(
        FEATURE_TYPE_DISTRIBUTION,
        sample_rng,
        allowed_classes=allowed
    )
    feature = generate_feature(feature_class, panel, features, sample_rng)
    if feature is not None:  # None if placement failed (e.g., no room)
        features.append(feature)
```

---

### Step 4: Validate Feature Placement (Generation-Side)

Before writing the DXF, verify all features satisfy the constraint grammar:

```python
for feature in features:
    if not satisfies_edge_clearance(feature, panel, GENERATION_MARGIN):
        # Retry placement up to 10 times, then skip feature
    if not satisfies_wall_thickness(feature, features, GENERATION_MARGIN):
        # Retry placement up to 10 times, then skip feature
```

This pre-check ensures valid samples don't accidentally contain violations.

---

### Step 5: Apply Invalidation (If Invalid Sample)

```python
if is_invalid:
    invalidation_type = sample_rng.choice(list(INVALIDATION_TYPES.keys()))
    features = INVALIDATION_TYPES[invalidation_type](panel, features, sample_rng)
    # features now contains exactly one violation
```

---

### Step 6: Write DXF File

```python
dxf_path = os.path.join(output_dir, sample_id, "geometry.dxf")
writer = DXFWriter()
writer.write_panel(panel, features, dxf_path)
```

DXF is written with:
- `$INSUNITS = 4` (millimeters)
- DXF version R2010 (AC1024)
- All features on appropriate layer names (DRILL, CUT, POCKET, BORDER)

---

### Step 7: Run OMIM Pipeline on Generated DXF

The generated DXF is processed through the standard pipeline to produce mgg.json and validation.json:

```python
parse_result = parser.parse(dxf_path)
mgg = mgg_builder.build(parse_result.geometry)
validation_report = rule_engine.validate_mgg(mgg, ruleset_version="0.1.0")
```

This step verifies the generator is working correctly: valid samples should produce `overall_valid=True`.

---

### Step 8: Build Ground-Truth Labels

Labels come from the **generation spec**, not from the pipeline:

```python
labels = {
    "schema_version": "0.1.0",
    "sample_id": sample_id,
    "is_valid": not is_invalid,
    "panel_width_mm": panel.width_mm,
    "panel_height_mm": panel.height_mm,
    "panel_thickness_mm": panel.thickness_mm,
    "features": [
        {
            "node_id": feature_to_node_id(feat, mgg),  # map back to MGG node
            "feature_class": feat.feature_class,
            "confidence": 1.0,
            "source": "synthetic_generation"
        }
        for feat in features
    ],
    "validation_errors": [feat.violations for feat in features if not feat.is_valid],
    "split": assigned_split
}
```

---

### Step 9: Export Sample

```python
exporter.export(ExportRequest(
    mgg=mgg,
    validation_report=validation_report,
    semantic_annotations=None,          # synthetic: labels come from spec, not semantic layer
    source_dxf_path=dxf_path,
    output_dir=output_dir,
    sample_id=sample_id,
    split=assigned_split
))
```

---

### Step 10: Verify Output

```python
errors = exporter.validate_export(sample_dir)
assert len(errors) == 0, f"Sample {sample_id} failed schema validation: {errors}"

# Cross-check: valid samples must pass validation
if not is_invalid:
    assert validation_report.overall_valid == True, \
        f"Generated valid sample {sample_id} failed validation — constraint grammar error"

# Cross-check: invalid samples must fail validation
if is_invalid:
    assert validation_report.overall_valid == False, \
        f"Generated invalid sample {sample_id} passed validation — invalidation failed"
```

---

## Dataset Manifest

After all samples are generated:

```python
class DatasetManifest(BaseModel):
    schema_version: str = "0.1.0"
    dataset_id: str          # UUID for this dataset generation run
    generated_at: str
    generator_version: str   # OMIM version
    config: PanelGeneratorConfig
    
    total_samples: int
    train_count: int
    val_count: int
    test_count: int
    
    valid_count: int
    invalid_count: int
    
    feature_type_counts: dict[str, int]  # actual distribution
    sample_ids: dict[str, str]           # sample_id → split
```

Written to `{output_dir}/manifest.json`.

---

## Generation Time Budget

Target: 1000 samples in < 10 minutes on a standard development machine.

```
Per sample (expected):
  DXF generation:  ~5ms
  OMIM pipeline:   ~50ms (parse + MGG + validation)
  Export + verify: ~10ms
  Total per sample: ~65ms
  1000 samples:    ~65 seconds
```
