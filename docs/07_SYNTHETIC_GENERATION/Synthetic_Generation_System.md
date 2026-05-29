# Synthetic Generation System

Version: v0.1.0  
Section: 07_SYNTHETIC_GENERATION  

See also: [[07_SYNTHETIC_GENERATION/Sample_Generation_Flow]], [[07_SYNTHETIC_GENERATION/Dataset_Distribution_Policy]], [[06_REAL_WORLD_GROUNDING/Panel_Dimension_Standards]]

---

## Purpose

Defines the system that generates synthetic panel manufacturing DXF files and their ground-truth labels. The synthetic generator is the primary source of training data for OMIM v0.1.0.

**Generation guarantee**: Same seed + same config → identical dataset. The generator is deterministic.

---

## PanelGeneratorConfig

```python
class PanelGeneratorConfig(BaseModel):
    # Reproducibility
    random_seed: int = 42
    
    # Dataset size
    num_samples: int = 1000
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15   # Must sum to 1.0
    
    # Panel geometry bounds
    min_panel_width_mm: float = 100.0
    max_panel_width_mm: float = 1200.0
    min_panel_height_mm: float = 100.0
    max_panel_height_mm: float = 2400.0
    panel_thickness_options_mm: list[float] = [12.0, 15.0, 16.0, 18.0, 22.0, 25.0]
    
    # Feature density
    # sparse:  0–5  features per panel
    # medium:  3–15 features per panel
    # dense:   10–30 features per panel
    feature_density: Literal["sparse", "medium", "dense"] = "medium"
    feature_distribution: dict | None = None  # override default probability weights
    
    # Invalid sample generation
    invalid_sample_ratio: float = 0.30      # 30% intentionally invalid
    max_violations_per_invalid: int = 3      # maximum injected violations per invalid sample
    
    # DXF output
    dxf_version: str = "AC1024"       # R2010
    units: str = "mm"
    format: Literal["flat", "split"] = "split"  # flat=all in one dir; split=train/val/test
    
    # Ruleset version for ground truth
    ruleset_version: str = "0.1.0"
    schema_version: str = "0.1.0"
```

---

## Generator Architecture

```python
class PanelGenerator:
    def __init__(self, config: PanelGeneratorConfig):
        self.config = config
        self.rng = np.random.default_rng(config.random_seed)
        self.ontology = OntologyLoader.load()
    
    def generate_dataset(self) -> DatasetManifest:
        """Generate all samples and write to disk."""
    
    def generate_sample(self, sample_id: str, is_invalid: bool = False) -> GeneratedSample:
        """Generate a single panel sample with ground-truth labels."""
    
    def _generate_panel_spec(self) -> PanelSpec:
        """Sample panel dimensions from realistic distribution."""
    
    def _generate_features(self, panel: PanelSpec) -> list[FeatureSpec]:
        """Generate features consistent with panel type."""
    
    def _complete_shelf_pin_rows(
        self,
        features: list[FeatureSpec],
        panel: PanelSpec,
        rng
    ) -> list[FeatureSpec]:
        """
        If any SHELF_PIN_HOLE was placed, complete it into a proper row of 4+.
        Isolated shelf pin holes are unrealistic; real panels have them in rows.
        Adds additional holes at 32mm spacing in the same column until
        the panel boundary is reached or the max_shelf_pins_per_row limit is hit.
        """
    
    def _apply_invalidation(self, features: list[FeatureSpec]) -> list[FeatureSpec]:
        """
        Inject manufacturing violations to create invalid samples.
        Randomly selects up to max_violations_per_invalid violation types.
        """
    
    def _write_dxf(self, panel: PanelSpec, features: list[FeatureSpec]) -> str:
        """Write DXF file; return file path."""
    
    def _compute_ground_truth(self, panel: PanelSpec, features: list[FeatureSpec]) -> dict:
        """Compute labels.json ground truth from generation spec (not from inference)."""
```

---

## Ground Truth Source

For synthetic samples, ground-truth labels come from the **generation spec**, not from inference. This is a critical distinction:

```python
# CORRECT: Labels derived from generation spec (authoritative)
feature_spec = FeatureSpec(
    feature_class="SHELF_PIN_HOLE",
    diameter_mm=5.0,
    position=(100.0, 37.0),
    ...
)
labels["features"].append({
    "feature_class": "SHELF_PIN_HOLE",  # from spec, not inferred
    "node_id": ...,
    "confidence": 1.0,                  # generation is deterministic
    "source": "synthetic_generation"
})

# FORBIDDEN: Running semantic inference on synthetic data and using that as ground truth
annotations = semantic_engine.classify(mgg)  # NOT the ground truth source for synthetic samples
```

This ensures that benchmark evaluation measures inference quality against true labels, not against another inference system's labels.

---

## Violation Injection

For invalid samples, violations are injected explicitly and recorded:

```python
def inject_violations(
    self,
    spec: PanelSpec,
    features: list[FeatureSpec],
    n_violations: int
) -> list[FeatureSpec]:
    """
    Inject up to n_violations manufacturing violations into an otherwise valid spec.
    Returns modified features list; sets spec.is_valid = False.
    """
    violation_types = [
        "too_close_to_edge",       # MFG-001: move a feature within 8mm of edge
        "holes_too_close",          # MFG-002: move two circles within 3mm wall
        "pocket_too_narrow",        # MFG-004: shrink a pocket below 1.2×tool_dia
        "hole_outside_boundary",    # GEO-007: move a feature outside panel bounds
    ]
    
    selected = self.rng.choice(
        violation_types,
        size=min(n_violations, len(violation_types)),
        replace=False
    )
    for violation in selected:
        features = self._apply_single_violation(features, violation, spec)
    
    return features
```

**Verification**: After injection, the validation engine is run to confirm the violation fires. If it doesn't (edge case geometry), the injection is retried or the violation is skipped and documented.

---

## Feature Parameter Sampling

Feature parameters are sampled from realistic distributions, not uniform ranges:

```python
def sample_hole_parameters(feature_type: str, rng) -> dict:
    """Sample geometric parameters for hole features."""
    
    if feature_type == "SHELF_PIN_HOLE":
        return {"diameter_mm": float(rng.normal(5.0, 0.05))}   # 5mm ± 0.05mm
    
    elif feature_type == "HINGE_CUP_HOLE":
        return {"diameter_mm": float(rng.normal(35.0, 0.1))}   # 35mm standard
    
    elif feature_type == "CONFIRMAT_HOLE":
        return {"diameter_mm": float(rng.normal(7.0, 0.05))}   # 7mm body
    
    elif feature_type == "DOWEL_HOLE":
        return {"diameter_mm": float(rng.choice([8.0, 10.0]))} # DIN 7 standard sizes
    
    elif feature_type == "THROUGH_HOLE":
        return {"diameter_mm": float(rng.uniform(4.0, 30.0))}  # realistic range


def sample_groove_parameters(panel_width: float, panel_height: float, rng) -> dict:
    """Sample groove parameters: width, depth, and orientation."""
    width_mm = float(rng.uniform(6.0, 20.0))
    depth_mm = float(rng.uniform(6.0, 12.0))
    is_horizontal = bool(rng.choice([True, False]))
    length_mm = (panel_width if is_horizontal else panel_height) * rng.uniform(0.3, 0.9)
    return {
        "width_mm": width_mm,
        "depth_mm": depth_mm,
        "is_horizontal": is_horizontal,
        "length_mm": length_mm,
    }
```

**Rationale for normal distribution on shelf pins**: Real shelf pin holes are drilled on dedicated drill heads with minimal tolerance variation. Using `rng.normal(5.0, 0.05)` rather than `rng.uniform(4.8, 5.2)` reflects the Gaussian error distribution of repeated drilling, producing a more realistic dataset.

---

## DXF Writer

```python
class DXFWriter:
    def write_panel(
        self,
        panel: PanelSpec,
        features: list[FeatureSpec],
        output_path: str
    ) -> str:
        doc = ezdxf.new(dxfversion="AC1024")
        doc.header["$INSUNITS"] = 4  # mm
        msp = doc.modelspace()
        
        # Write panel boundary on BORDER layer
        msp.add_lwpolyline(
            panel.boundary_points,
            dxfattribs={"layer": "BORDER", "closed": True}
        )
        
        # Write each feature on appropriate layer
        for feat in features:
            layer = FEATURE_CLASS_TO_LAYER[feat.feature_class]
            if feat.entity_type == "CIRCLE":
                msp.add_circle(feat.center, feat.radius_mm, dxfattribs={"layer": layer})
            elif feat.entity_type == "LWPOLYLINE":
                msp.add_lwpolyline(feat.points, dxfattribs={"layer": layer, "closed": feat.is_closed})
        
        doc.saveas(output_path)
        return output_path
```

---

## PanelSpec and FeatureSpec

```python
class PanelSpec(BaseModel):
    width_mm: float
    height_mm: float
    thickness_mm: float
    boundary_points: list[tuple[float, float]]  # closed rectangle
    panel_type: str  # "side_panel" | "shelf" | "door" | "back" | "generic"

class FeatureSpec(BaseModel):
    feature_class: str          # from Feature_Taxonomy
    entity_type: str            # "CIRCLE" | "LWPOLYLINE"
    center: tuple[float, float] | None    # for circles
    radius_mm: float | None     # for circles
    points: list[tuple[float, float]] | None  # for polylines
    is_closed: bool
    layer: str                  # DXF layer name
    depth_mm: float | None      # for 3D-relevant features (not in DXF)
    is_valid: bool              # does this feature pass all rules?
    violations: list[str]       # rule IDs violated, if any
```

---

## Acceptance Tests

```python
def test_generator_deterministic():
    """Same seed → identical dataset (byte-for-byte DXF files)."""

def test_generator_invalid_ratio():
    """30% of generated samples have at least one validation ERROR."""

def test_generator_feature_distribution():
    """SHELF_PIN_HOLE is most common feature type (> 40% of circles)."""

def test_generated_labels_not_inferred():
    """labels.json 'source' field == 'synthetic_generation' for all synthetic samples."""

def test_dxf_passes_ezdxf_audit():
    """All generated DXFs pass ezdxf.audit() with zero critical errors."""
```
