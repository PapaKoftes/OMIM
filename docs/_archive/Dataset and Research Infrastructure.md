# Synthetic Dataset Generation & Research Infrastructure

Version: v0.1.0  

See also: [[Manufacturing Ontology]], [[Validation]], [[Benchmarking]], [[Provenence and Uncertainty]]

---

## Purpose

This document defines:
1. How synthetic manufacturing datasets are generated
2. The dataset schema and storage format
3. Reproducibility guarantees
4. Research-facing dataset documentation

The goal is to produce datasets that are:
- **Scientifically defensible**: Generated from real manufacturing rules, not random geometry
- **Benchmarkable**: Support standardized evaluation tasks
- **Reproducible**: Same seed + config → identical dataset
- **Transparent**: Every sample has complete provenance

---

## Generation Philosophy

The synthetic dataset is NOT random geometry with labels slapped on. It is:

> Rules-constrained procedural manufacturing generation

Generation algorithm at high level:
1. Start with valid manufacturing constraints (from [[Rule Engine and Standards]])
2. Procedurally generate geometry that satisfies or intentionally violates those constraints
3. Run through the full OMIM pipeline (parse → MGG → validate → semantics)
4. Use the pipeline outputs as ground truth labels
5. Package with provenance

This means every valid sample is genuinely manufacturable, and every invalid sample fails for a documented, specific reason.

---

## Generator Architecture

```python
# omim/synthetic/panel_generator.py

class PanelGeneratorConfig(BaseModel):
    """Configuration for procedural panel generation."""
    
    # Reproducibility
    seed: int                               # Master random seed
    
    # Panel geometry
    panel_width_range_mm: tuple[float, float] = (150.0, 2400.0)
    panel_height_range_mm: tuple[float, float] = (150.0, 1200.0)
    panel_thickness_mm: float = 18.0
    
    # Feature distribution
    feature_density: Literal["sparse", "medium", "dense"] = "medium"
    # sparse: 0-5 features per panel
    # medium: 3-15 features per panel
    # dense: 10-30 features per panel
    
    feature_distribution: dict | None = None  # override probability weights
    
    # Invalid sample generation
    include_invalid: bool = True
    invalid_ratio: float = 0.15             # 15% of samples are invalid
    max_violations_per_invalid: int = 3
    
    # Dataset size
    n_samples: int = 1000
    
    # Version pins (for reproducibility)
    ontology_version: str = "v0.1.0"
    ruleset_version: str = "v0.1.0"
    
    # Output
    output_dir: str = "data/synthetic"
    format: Literal["flat", "split"] = "split"  # flat=all in one dir, split=train/val/test
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15
```

### Feature Distribution (Default Weights)

Based on common occurrence in real panel manufacturing:

```yaml
feature_distribution:
  PROFILE_CUT: 1.00             # Every panel has an outer profile
  THROUGH_HOLE: 0.45            # Generic holes, common
  SHELF_PIN_HOLE: 0.60          # Very common in shelving panels
  HINGE_CUP_HOLE: 0.35          # Common in door panels
  CONFIRMAT_HOLE: 0.50          # Common joining holes
  DOWEL_HOLE: 0.40              # Common alignment holes
  GROOVE: 0.25                  # Back panel grooves, less common
  POCKET: 0.15                  # Less common in flat panels
  RABBET: 0.20                  # Common at panel edges
  OPEN_SLOT: 0.10               # Specialized
  INTERNAL_CUTOUT: 0.05         # Rare (cutout windows, etc.)
  
# Count distribution (features per panel given "medium" density)
feature_count_distribution:
  min: 3
  max: 15
  mean: 7
  distribution: "truncated_normal"
```

---

## Generation Algorithm (Detailed)

```python
class PanelGenerator:
    def __init__(self, config: PanelGeneratorConfig):
        self.config = config
        self.rng = numpy.random.default_rng(config.seed)  # seeded RNG
        self.ontology = OntologyLoader().load()
        self.rule_engine = RuleEngine.load()
        
    def generate_panel(self, panel_seed: int) -> PanelSpecification:
        """Generate one panel specification (before writing to DXF)."""
        rng = numpy.random.default_rng(panel_seed)
        
        # 1. Sample panel dimensions
        width = float(rng.uniform(*self.config.panel_width_range_mm))
        height = float(rng.uniform(*self.config.panel_height_range_mm))
        
        # 2. Sample features to place
        n_features = self._sample_feature_count(rng)
        feature_specs = []
        
        for _ in range(n_features):
            # Sample feature type
            feature_type = self._sample_feature_type(rng)
            
            # Generate feature parameters
            params = self._generate_feature_params(feature_type, rng)
            
            # Find valid position (respecting spacing constraints)
            position = self._find_valid_position(
                feature_type, params, feature_specs, width, height, rng
            )
            
            if position is None:
                continue  # Couldn't place; skip this feature
            
            feature_specs.append(FeatureSpec(
                feature_type=feature_type,
                position_mm=position,
                **params
            ))
        
        # 3. Add shelf pin rows if any shelf pins were placed
        feature_specs = self._complete_shelf_pin_rows(feature_specs, rng)
        
        return PanelSpecification(
            width_mm=width,
            height_mm=height,
            thickness_mm=self.config.panel_thickness_mm,
            features=feature_specs,
            is_valid=True,  # Valid by construction; invalidate later if needed
            seed=panel_seed
        )
    
    def inject_violations(self, spec: PanelSpecification, n_violations: int) -> PanelSpecification:
        """Inject manufacturing violations to create invalid samples."""
        violation_types = [
            "too_close_to_edge",      # MFG-001
            "holes_too_close",         # MFG-002
            "pocket_too_narrow",       # MFG-004
            "hole_outside_boundary",   # GEO-007
        ]
        
        for _ in range(min(n_violations, len(violation_types))):
            violation = self.rng.choice(violation_types)
            spec = self._apply_violation(spec, violation)
        
        spec.is_valid = False
        spec.injected_violations = ...  # record what was injected
        return spec
```

---

## Feature Parameter Sampling

### Hole Parameters
```python
def sample_hole_parameters(feature_type: str, rng) -> dict:
    """Sample geometric parameters for hole features."""
    
    if feature_type == "SHELF_PIN_HOLE":
        return {"diameter_mm": rng.normal(5.0, 0.05)}  # 5mm ± 0.05mm
    
    elif feature_type == "HINGE_CUP_HOLE":
        return {"diameter_mm": rng.normal(35.0, 0.1)}  # 35mm standard
    
    elif feature_type == "CONFIRMAT_HOLE":
        return {"diameter_mm": rng.normal(7.0, 0.05)}
    
    elif feature_type == "DOWEL_HOLE":
        return {"diameter_mm": float(rng.choice([8.0, 10.0]))}
    
    elif feature_type == "THROUGH_HOLE":
        # Uniformly sample from realistic range
        return {"diameter_mm": float(rng.uniform(4.0, 30.0))}
```

### Groove/Pocket Parameters
```python
def sample_groove_parameters(panel_width, panel_height, rng) -> dict:
    """Sample groove parameters: width and orientation."""
    width_mm = float(rng.uniform(6.0, 20.0))
    depth_mm = float(rng.uniform(6.0, 12.0))
    
    # Grooves run parallel to panel edges
    is_horizontal = bool(rng.choice([True, False]))
    length_mm = (panel_width if is_horizontal else panel_height) * rng.uniform(0.3, 0.9)
    
    return {
        "width_mm": width_mm,
        "depth_mm": depth_mm,
        "is_horizontal": is_horizontal,
        "length_mm": length_mm
    }
```

---

## DXF Writer

```python
# omim/synthetic/dxf_writer.py

class DXFWriter:
    """Writes PanelSpecification to DXF format using ezdxf."""
    
    def write(self, spec: PanelSpecification, output_path: str) -> None:
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        
        # Add standard layers
        doc.layers.add("CUT", color=1)    # red = profile cuts
        doc.layers.add("DRILL", color=2)  # yellow = drill holes
        doc.layers.add("POCKET", color=3) # green = pocket operations
        doc.layers.add("BORDER", color=7) # white = sheet boundary (not machined)
        
        # Write outer profile
        self._write_panel_outline(msp, spec)
        
        # Write each feature
        for feature in spec.features:
            self._write_feature(msp, feature)
        
        # Set file metadata
        doc.header["$ACADVER"] = "AC1024"
        doc.header["$INSUNITS"] = 4  # mm
        
        doc.saveas(output_path)
    
    def _write_panel_outline(self, msp, spec: PanelSpecification):
        """Write rectangular panel boundary as closed polyline on CUT layer."""
        points = [
            (0, 0), (spec.width_mm, 0),
            (spec.width_mm, spec.height_mm), (0, spec.height_mm)
        ]
        msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "CUT"})
    
    def _write_circle_feature(self, msp, feature: FeatureSpec):
        """Write circle feature (holes) to DRILL layer."""
        msp.add_circle(
            center=(feature.position_mm[0], feature.position_mm[1]),
            radius=feature.diameter_mm / 2,
            dxfattribs={"layer": "DRILL"}
        )
```

---

## Dataset Schema

### Directory Structure

```
data/synthetic/
├── dataset_metadata.json          # Dataset-level metadata
├── splits/
│   ├── train.jsonl                # Sample IDs + summary for training set
│   ├── val.jsonl                  # Validation set
│   └── test.jsonl                 # Test set (held out)
└── samples/
    ├── sample_00001/
    │   ├── geometry.dxf           # Generated DXF file
    │   ├── mgg.json               # Manufacturing Geometry Graph (JSON)
    │   ├── validation.json        # ValidationReport (JSON)
    │   ├── labels.json            # Ground truth labels
    │   └── provenance.json        # Full provenance chain
    ├── sample_00002/
    │   └── ...
    └── ...
```

### dataset_metadata.json Schema

```json
{
  "dataset_id": "omim-synthetic-v0.1.0-2026-05-30",
  "omim_version": "v0.1.0",
  "ontology_version": "v0.1.0",
  "ruleset_version": "v0.1.0",
  "creation_timestamp": "2026-05-30T14:00:00Z",
  
  "generation_config": {
    "seed": 42,
    "n_samples": 1000,
    "feature_density": "medium",
    "invalid_ratio": 0.15,
    "panel_width_range_mm": [150, 2400],
    "panel_height_range_mm": [150, 1200],
    "panel_thickness_mm": 18.0
  },
  
  "statistics": {
    "total_samples": 1000,
    "valid_samples": 850,
    "invalid_samples": 150,
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
      "too_close_to_edge": 67,
      "holes_too_close": 58,
      "pocket_too_narrow": 25
    },
    "mean_features_per_panel": 7.2,
    "mean_panel_area_mm2": 412500
  },
  
  "schema_version": "v0.1.0",
  "license": "Apache 2.0",
  "citation": "OMIM: Open Manufacturing Intelligence Middleware (2026)"
}
```

### labels.json Schema (per sample)

```json
{
  "sample_id": "sample_00001",
  "is_valid": true,
  "injected_violations": [],
  
  "panel": {
    "width_mm": 800.0,
    "height_mm": 600.0,
    "thickness_mm": 18.0,
    "area_mm2": 480000.0
  },
  
  "features": [
    {
      "feature_id": "feat_001",
      "feature_class": "SHELF_PIN_HOLE",
      "diameter_mm": 5.0,
      "position_mm": [50.0, 32.0],
      "depth_mm": null,
      "is_through": false,
      "group_id": "shelf_pin_row_1",
      "inference_ground_truth": "synthetic",
      "confidence_ground_truth": 1.0
    }
  ],
  
  "operations": ["DRILLING", "PROFILE_CUTTING"],
  
  "complexity": "medium",
  
  "ground_truth_source": "synthetic_generator",
  "ontology_version": "v0.1.0"
}
```

---

## Reproducibility Guarantee

### What "Reproducible" Means Here

Given:
- `generation_config` (from `dataset_metadata.json`)
- The same version of `omim` code
- The same `ontology_version` and `ruleset_version`

→ Re-running generation produces byte-identical DXF files and identical labels.

### How This Is Ensured

1. **Seeded RNG**: `numpy.random.default_rng(seed)` used throughout
2. **Per-sample seeds**: Each sample gets `seed + sample_index` (child seed)
3. **No global state**: Generator is pure — same input → same output
4. **Dependency pinning**: `pyproject.toml` pins all library versions
5. **File hashes**: `dataset_metadata.json` records SHA256 of each DXF file

### Reproducibility Test

```python
def test_dataset_reproducibility():
    config = PanelGeneratorConfig(seed=42, n_samples=10)
    
    # Generate twice
    gen1 = generate_dataset(config, output_dir="tmp/run1")
    gen2 = generate_dataset(config, output_dir="tmp/run2")
    
    # Compare
    for sample_id in gen1.sample_ids:
        assert file_hash(f"tmp/run1/{sample_id}/geometry.dxf") == \
               file_hash(f"tmp/run2/{sample_id}/geometry.dxf")
        assert load_labels(f"tmp/run1/{sample_id}") == \
               load_labels(f"tmp/run2/{sample_id}")
```

---

## Dataset Distribution Policy

This is critical: without a defined distribution, the generator produces biased data that trains biased models.

### Feature Frequency Targets (Default Config)

Based on typical European furniture cabinet panel production patterns:

| Feature Class | Target Frequency | Reasoning |
|--------------|-----------------|-----------|
| SHELF_PIN_HOLE | 35–45% of all hole features | Dominant — most panels have multiple shelf pin rows |
| CONFIRMAT_HOLE | 15–20% | Very common joinery method |
| THROUGH_HOLE | 10–15% | Generic fastener holes |
| DOWEL_HOLE | 8–12% | Dowel joining common |
| HINGE_CUP_HOLE | 5–10% | Only on door/hinge panels |
| PROFILE_CUT | 1 per panel (100%) | Every panel has exactly one |
| GROOVE | 10–15% of panels | Back panel grooves |
| RABBET | 5–10% of panels | Edge rebates |
| POCKET | 3–7% of panels | Less common in flat panels |
| CONFIRMAT_HOLE | 15–20% | Joining hardware |

### Panel Size Distribution

```yaml
panel_size_distribution:
  # Based on common European furniture carcass components
  # Source: standard cabinet construction dimensions
  
  small:      # drawer fronts, small doors
    weight: 0.15
    width_mm: [150, 450]
    height_mm: [100, 500]
    
  medium:     # standard shelf panels, side panels
    weight: 0.50
    width_mm: [400, 900]
    height_mm: [300, 800]
    
  large:      # full cabinet sides, top/bottom panels
    weight: 0.25
    width_mm: [800, 1200]
    height_mm: [600, 900]
    
  full_sheet: # large backs, worktops
    weight: 0.10
    width_mm: [1200, 2440]
    height_mm: [600, 1220]
```

### Invalid Sample Distribution

```yaml
invalid_sample_targets:
  total_invalid_ratio: 0.15       # 15% of all samples
  
  violation_distribution:
    too_close_to_edge: 0.35       # most common real-world error
    holes_too_close: 0.30         # second most common
    pocket_too_narrow: 0.15       # narrower pocket than tool
    mixed_violations: 0.15        # 2+ violations in one panel
    geometry_invalid: 0.05        # degenerate geometry (for boundary testing)
```

### Ambiguity Distribution

```yaml
ambiguity_targets:
  # Samples where semantic classification is genuinely ambiguous
  # These are valuable for ML training — model must learn to express uncertainty
  
  ambiguous_ratio: 0.08           # 8% of valid samples have at least one ambiguous feature
  # Ambiguous features: diameter exactly at classification boundary, unusual hole size, etc.
```

### Complexity Distribution

```yaml
complexity_targets:
  simple: 0.25      # 1-4 features, single feature type
  medium: 0.55      # 5-12 features, 2-4 feature types
  complex: 0.20     # 13+ features, 4+ feature types, groups
```

### Balance Enforcement

```python
# omim/synthetic/dataset_builder.py

def enforce_distribution(samples: list[DatasetSample], config: DistributionConfig) -> list[DatasetSample]:
    """
    After generation, verify distribution matches targets.
    Warn (do not fail) if distribution deviates > 10% from target.
    """
    actual_invalid_ratio = sum(1 for s in samples if not s.is_valid) / len(samples)
    if abs(actual_invalid_ratio - config.invalid_ratio) > 0.10:
        logger.warning(f"Invalid ratio {actual_invalid_ratio:.2f} deviates from target {config.invalid_ratio:.2f}")
```

---

## Existing Datasets to Reference/Integrate

These publicly available datasets are adjacent to OMIM's domain and may be useful for comparison or integration:

| Dataset | Source | Description | Relevance |
|---------|--------|-------------|-----------|
| ABC Dataset | Koch et al., CVPR 2019 | 1M+ CAD models with B-rep topology | Geometry diversity; lacks manufacturing semantics |
| DeepCAD | Wu et al., ICCV 2021 | CAD construction sequences | Sequential CAD ops; not manufacturing focus |
| Fusion 360 Gallery | Willis et al., TOG 2021 | CAD segmentation + assembly | Feature segmentation reference |
| MFCAD (Machining Feature) | Shi et al., 2018 | 15,000 labeled machining features | Feature classification reference; limited |
| GrabCAD public models | grabcad.com/library | Community CAD models | Panel models exist; manual labeling needed |

**Key differentiator**: None of these provide:
- Panel manufacturing focus
- 32mm system / furniture hardware semantics
- Explicit manufacturing rule validation
- Provenance-tracked labels
- Synthetic generation infrastructure

---

## Real-World Manufacturing Grounding

Synthetic data that drifts from reality produces models that fail on real DXFs. These are the grounding sources that constrain the generator to realistic patterns.

### Manufacturing Realism Sources

| Source | What It Provides | How Used |
|--------|-----------------|---------|
| European cabinet construction | Panel dimensions, feature positions, standard part types | Panel size distribution; feature frequency |
| Blum/Hettich/Grass catalogs | Exact hardware hole dimensions and positions | Hole diameter ranges; edge distances (Blum 22.5mm) |
| 32mm modular system (Rasterbohrsystem) | Shelf pin spacing = exactly 32mm | `MFG-005` rule; shelf pin pattern generator |
| EN 309 panel thickness standard | 9, 12, 15, 18, 22, 25mm standard thicknesses | Default `panel_thickness_mm = 18.0` |
| LinuxCNC sample G-code programs | Real CNC operation patterns and conventions | DXF layer naming conventions |
| OpenCAMLib source code | CNC toolpath constraints | Pocket width ratios, corner radius rules |
| FreeCAD Path workbench | Real CAM operation sequencing | Operation inference logic |
| KCMA A161.1 cabinet standard | Kitchen cabinet construction specifications | Panel dimensions and hardware positions |

### Feature Frequency Validation

Before finalizing the `feature_distribution` weights, they should be cross-validated against:
1. At least 10 real panel DXF files (if obtainable)
2. At least 3 cabinet construction books/catalogs
3. At least 1 CNC operator's practical experience

If real DXFs cannot be obtained, document this explicitly in `dataset_metadata.json`:
```json
"grounding_note": "Feature frequencies based on catalog analysis only; not validated against real DXF corpus"
```

### What Real Panels Look Like (Reference Notes)

- **Standard Euro kitchen cabinet side panel (720mm × 560mm × 18mm)**:
  - 2 rows of shelf pins (32mm apart, 5mm diameter, ~20 holes per row)
  - 4 Confirmat holes for joining (7mm, 100mm from top/bottom)
  - 1 groove for back panel (6mm wide × 6mm deep, 12mm from rear edge)
  - Profile cut (outer contour)

- **Standard door panel (196mm × 716mm × 18mm)**:
  - 2 hinge cup holes (35mm, 22.5mm from edge, 100mm from top/bottom)
  - 2 Confirmat holes (for handle)
  - Profile cut (outer contour)

These are reference cases that should appear in the test DXF collection.

---

## Dataset Export Formats

### v0 (Hackathon)
- DXF files + JSON per-sample files
- JSONL split files
- ZIP archive for distribution

### v0.2 (Post-Hackathon)
- Parquet format for large-scale processing
- HuggingFace Datasets compatible format
- NetworkX graph format for direct GNN loading

## Dataset Licensing Policy

**Dataset contamination is a real risk.** Several referenced sources have licensing restrictions that affect redistribution rights.

### License Audit for Referenced Datasets

| Dataset | License | Redistribution | Derivative Generation | OMIM Use |
|---------|---------|----------------|----------------------|----------|
| ABC Dataset | MIT | ✅ Free | ✅ Allowed | Safe to use as reference |
| Fusion360 Gallery | Research only | ⚠ Non-commercial | ⚠ Check terms | Do NOT redistribute; use only as reference |
| DeepCAD | MIT | ✅ Free | ✅ Allowed | Safe to use |
| GrabCAD library files | Per-model | ⚠ Varies by upload | ⚠ Check per file | Must check each file before using |
| LinuxCNC sample files | GPL | ✅ Free (copyleft) | ✅ Allowed (with attribution) | Safe; note GPL requirement |
| FreeCAD samples | LGPL | ✅ Free | ✅ Allowed | Safe |
| Blum/Hettich catalogs | © Manufacturer | ❌ Not redistributable | ❌ Cannot include in dataset | Use only as reference for parameter values |
| Manually created DXFs | Your own | ✅ Own copyright | ✅ Full control | Preferred for test corpus |

### Rules for OMIM Synthetic Dataset

1. **Procedurally generated geometry is original** — OMIM's synthetic DXFs are generated by OMIM code from OMIM rules. They are not derived from any copyrighted DXF. License: Apache 2.0.

2. **Parameter values from manufacturer catalogs are facts** — "35mm hinge cup hole" is a dimension, not copyrightable expression. Using this value in generation is legal.

3. **Real DXF files used for testing** — if included in the repo, each file needs a license declaration. Use only:
   - Files you create yourself
   - Files with explicit open-source licenses
   - Files obtained with explicit written permission

4. **Every dataset sample stores source attribution** in provenance.json: `"source_license": "Apache 2.0 (OMIM synthetic)"` or `"source_license": "MIT (ABC Dataset)"` etc.

```json
// provenance.json — dataset source field
{
  "dataset_version": "omim-synthetic-v0.1.0",
  "source_license": "Apache 2.0",
  "source_type": "synthetic_generated",
  "generated_by": "omim-v0.1.0",
  "contains_external_data": false
}
```

### HuggingFace Datasets Integration (v0.2 plan)

```python
# Future: push to HuggingFace Hub
from datasets import Dataset, DatasetDict

# Convert to HF format
hf_dataset = DatasetDict({
    "train": Dataset.from_list(train_samples),
    "validation": Dataset.from_list(val_samples),
    "test": Dataset.from_list(test_samples),
})

hf_dataset.push_to_hub("omim-project/omim-panel-manufacturing-v0.1")
```
