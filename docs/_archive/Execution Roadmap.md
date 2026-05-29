# Hackathon Execution Roadmap

**Duration**: 48 hours  
**Start**: Day 1, Hour 0  
**End**: Day 2, Hour 48  

See: [[Hard Limits and Constraints]], [[What Is OMIM]], [[Full System Architecture]]

---

## ⚠ ARCHITECTURE COMPLETE — BUILD NOW

> The architecture is done. The specs are done. The schemas are frozen. The ontology is defined.  
> **The only remaining high-value move is to write running code.**

Reading more docs does not move the project forward. Refining the ontology does not move the project forward. Adding more edge cases to the MGG spec does not move the project forward.

**The minimum success condition for this hackathon is:**

```
One DXF file
  → python -m omim.cli input.dxf --output out/
    → out/mgg.json           (exists, valid JSON, has nodes)
    → out/validation.json    (exists, overall_valid field present)
    → out/labels.json        (exists, features list present)
    → out/provenance.json    (exists, pipeline_stages present)
```

If that runs and produces output, the core thesis is proven. Everything else — ML, benchmarks, 1000+ samples, demo UI — is additive value on top of a working foundation.

**Architecture gravity is the most common way infra projects die.** The vault has enough. Stop reading. Start building. The specs exist to guide the implementation, not to replace it.

---

## Pre-Hackathon Checklist (Complete Before Hour 0)

### Environment
- [ ] Python 3.11+ installed, virtual environment created
- [ ] All dependencies installed: `ezdxf`, `shapely`, `networkx`, `pydantic`, `pytest`, `fastapi`, `uvicorn`, `torch`, `torch-geometric`, `numpy`, `scipy`
- [ ] Git repo initialized with branch structure: `main`, `dev`, `checkpoint/*`
- [ ] Docker installed (optional fallback for dependency isolation)
- [ ] VS Code / IDE configured with Python linting (ruff, mypy)

### Data Resources
- [ ] 5–10 real panel manufacturing DXF files collected (see sources below)
- [ ] 2–3 intentionally malformed DXFs collected for validation testing
- [ ] ABC Dataset sampled if available: https://deep-geometry.github.io/abc-dataset/
- [ ] Fusion360 Gallery sampled if applicable: https://github.com/AutodeskAILab/Fusion360GalleryDataset

### Pre-Written Specs
- [ ] [[Manufacturing Ontology]] reviewed and approved
- [ ] [[Manufacturing Geometry Graph (MGG) Specification]] reviewed
- [ ] [[Validation]] layers reviewed
- [ ] [[Rule Engine and Standards]] rules list reviewed
- [ ] [[Provenence and Uncertainty]] schema reviewed

### Sample DXF Sources
- FreeCAD sample files: https://github.com/FreeCAD/FreeCAD/tree/main/src/Mod/Import/Samples
- Open source CNC pattern libraries: ncviewer.com sample files
- GrabCAD free DXF panels: https://grabcad.com/library (search "panel DXF")
- LinuxCNC sample G-code patterns (reverse to DXF): https://linuxcnc.org/docs/html/gcode/
- Flatfab / OpenSCAD panel exports
- Manually create 3–5 representative test panels using FreeCAD or LibreCAD

---

## Phase 0 — Repository & Infrastructure (Hours 0–2)

### Goal
Get the project skeleton running. No real logic yet.

### Tasks
```
repo/
├── omim/
│   ├── __init__.py
│   ├── parser/           # DXF → raw geometry
│   ├── graph/            # geometry → MGG
│   ├── ontology/         # YAML ontology definitions
│   ├── validation/       # deterministic validators
│   ├── semantic/         # inference layer
│   ├── provenance/       # metadata tracking
│   ├── synthetic/        # dataset generator
│   ├── benchmarks/       # benchmark tasks
│   └── ml/               # GNN integration
├── data/
│   ├── test_dxfs/        # real DXFs for testing
│   ├── ontology/         # YAML files
│   └── rules/            # rule YAML files
├── tests/
├── notebooks/
├── README.md
└── pyproject.toml
```

### Acceptance Tests
- [ ] `python -c "import omim"` works
- [ ] `pytest tests/` runs (0 tests, 0 failures)
- [ ] Git commit: `v0-skeleton`

### Hard Stop: 2 hours

---

## Phase 1 — Ontology Finalization (Hours 2–5)

### Goal
Lock the manufacturing vocabulary. This defines every label used throughout the system.

### Tasks
1. Create `data/ontology/features.yaml` — feature taxonomy
2. Create `data/ontology/operations.yaml` — operation taxonomy
3. Create `data/ontology/relationships.yaml` — relationship taxonomy
4. Create `data/ontology/constraints.yaml` — constraint taxonomy
5. Create `data/ontology/materials.yaml` — panel material types
6. Create `omim/ontology/loader.py` — YAML → typed Python objects
7. Write 5 unit tests: ontology loads, no duplicate terms, relationships are directional

### Key Entities to Define (Minimum)
See [[Manufacturing Ontology]] for full taxonomy.

**Features**: THROUGH_HOLE, BLIND_HOLE, COUNTERSINK, SHELF_PIN_HOLE, HINGE_CUP_HOLE, CONFIRMAT_HOLE, DOWEL_HOLE, POCKET, THROUGH_POCKET, GROOVE, RABBET, PROFILE_CUT, OPEN_SLOT, CHAMFER

**Operations**: DRILLING, CNC_ROUTING, PROFILE_CUTTING, NESTING

**Relationships**: CONTAINS, DEPENDS_ON, CONFLICTS_WITH, ADJACENT_TO, REQUIRES_TOOLING, SAME_GROUP

### Acceptance Tests
- [ ] All 14+ feature types load without error
- [ ] Every entity has: `id`, `label`, `description`, `source`, `confidence_method`
- [ ] No duplicate term IDs
- [ ] Relationships have direction defined
- [ ] `ontology.get_feature("SHELF_PIN_HOLE")` returns correct type

### Hard Stop: 3 hours from start of this phase

---

## Phase 2 — DXF Parser (Hours 5–9)

### Goal
Reliable, deterministic extraction of 2D geometry from DXF files.

### Technology
```python
# Primary library
import ezdxf  # https://ezdxf.readthedocs.io/

# Geometry processing
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
```

### Tasks
1. `omim/parser/dxf_reader.py` — read DXF file using ezdxf
2. `omim/parser/entity_extractor.py` — extract LINE, CIRCLE, ARC, LWPOLYLINE entities
3. `omim/parser/normalizer.py` — normalize coordinates, handle units (mm vs inches)
4. `omim/parser/contour_builder.py` — assemble connected entities into closed contours (Shapely)
5. `omim/parser/layer_classifier.py` — classify layers by convention (CUT, DRILL, ENGRAVE, etc.)
6. `omim/parser/geometry_objects.py` — Pydantic models: `RawGeometry`, `ContourGroup`, `CircleFeature`

### Entity Priority
| Priority | Entity | Why |
|----------|--------|-----|
| P0 | LWPOLYLINE | Most common for panel outlines |
| P0 | CIRCLE | Holes |
| P0 | ARC | Corner radii |
| P1 | LINE | Individual edges |
| P1 | POLYLINE | Legacy polylines |
| P2 | SPLINE | Approximate as polyline |
| Skip | TEXT, DIMENSION | Annotation only |
| Skip | HATCH | Fill only |

### Layer Convention (Standard for Panel CNC)
```yaml
# Standard DXF layer name conventions for CNC panel work
CUT:         # Profile cuts (outer contours)
DRILL:       # Drill holes
POCKET:      # Pocket operations
ENGRAVE:     # Engraving / decorative
MILL:        # General milling
V_CUT:       # V-groove scoring lines
BORDER:      # Sheet boundary (not machined)
```

### Acceptance Tests
- [ ] 5+ real DXF files parse without crash
- [ ] All CIRCLE entities extracted with correct center + radius
- [ ] Closed contours assembled correctly (tolerance: 0.01mm)
- [ ] Layer names preserved in output
- [ ] Units normalized to mm
- [ ] Source entity ID preserved in output (for provenance)
- [ ] Malformed DXF returns structured error, not stack trace

### Hard Stop: 4 hours from start of this phase

---

## Phase 3 — Manufacturing Geometry Graph Builder (Hours 9–13)

### Goal
Convert parsed geometry into the canonical MGG representation.

### Technology
```python
import networkx as nx  # https://networkx.org/
from pydantic import BaseModel
import json
```

### Tasks
1. `omim/graph/mgg.py` — `ManufacturingGeometryGraph` class (NetworkX DiGraph wrapper)
2. `omim/graph/nodes.py` — Pydantic node schemas: `GeometryNode`, `FeatureNode`, `OperationNode`, `ConstraintNode`
3. `omim/graph/edges.py` — Pydantic edge schemas: `RelationshipEdge`
4. `omim/graph/builder.py` — geometry → MGG conversion pipeline
5. `omim/graph/serializer.py` — MGG → JSON, JSON → MGG (roundtrip)
6. `omim/graph/queries.py` — basic graph queries: get_features(), get_operations(), get_conflicts()

### Node Schema (Minimum)
```python
class GeometryNode(BaseModel):
    node_id: str           # UUID
    node_type: str = "geometry"
    geometry_type: str     # "circle", "contour", "arc", etc.
    coordinates: list      # [[x, y], ...] or [cx, cy, r]
    layer: str
    source_entity_id: str  # from DXF parser (provenance)
    bounding_box: list     # [xmin, ymin, xmax, ymax]
    area: float | None
    perimeter: float | None

class FeatureNode(BaseModel):
    node_id: str
    node_type: str = "feature"
    feature_class: str     # from ontology
    confidence: float      # 0.0 - 1.0
    evidence: list[str]    # evidence references
    inference_method: str  # "deterministic" | "heuristic" | "ml"
    geometry_node_ids: list[str]
    provenance: dict       # see [[Provenence and Uncertainty]]
```

### Acceptance Tests
- [ ] MGG builds from parsed DXF without error
- [ ] All geometry entities become GeometryNodes
- [ ] Graph serializes to JSON and deserializes back identically
- [ ] `get_features()` returns all FeatureNodes
- [ ] Graph supports provenance metadata on every node
- [ ] Roundtrip: `MGG → JSON → MGG → JSON` produces identical output

### Hard Stop: 4 hours from start of this phase

---

## Phase 4 — Validation Engine (Hours 13–17)

### Goal
Deterministic, rule-based manufacturability validation.

### Tasks
1. `omim/validation/layer1_geometry.py` — geometric validity (contour closure, self-intersections, topology)
2. `omim/validation/layer2_manufacturability.py` — manufacturing feasibility rules
3. `omim/validation/rule_engine.py` — load and execute rules from YAML
4. `omim/validation/report.py` — structured `ValidationReport` Pydantic model
5. `data/rules/panel_cnc_rules.yaml` — 15–25 externalized rules (see [[Rule Engine and Standards]])

### Layer 1 Rules (Geometric Validity — Deterministic)
```yaml
# Examples — see Rule Engine and Standards for full list
rule_id: GEO-001
name: contour_closure
description: All contours must be closed (no open endpoints)
tolerance_mm: 0.01
severity: ERROR

rule_id: GEO-002
name: no_self_intersection
description: Contours must not self-intersect
severity: ERROR

rule_id: GEO-003
name: positive_area
description: All closed contours must have positive area
severity: ERROR
```

### Layer 2 Rules (Manufacturing Feasibility — Deterministic)
```yaml
rule_id: MFG-001
name: minimum_edge_clearance
description: Features must be >= 8mm from panel edge
threshold_mm: 8.0
severity: ERROR
source: "Common panel CNC practice; see DIN 68xxx panel woodworking"

rule_id: MFG-002
name: minimum_drill_spacing
description: Drill holes must be >= diameter + 3mm apart (center to center)
formula: "center_distance >= d1/2 + d2/2 + 3.0"
severity: ERROR

rule_id: MFG-003
name: tool_radius_feasibility
description: Internal pocket corners must have radius >= tool_radius
default_tool_radius_mm: 3.0
severity: WARNING

rule_id: MFG-004
name: pocket_width_minimum
description: Pocket width must be >= 1.2 * tool_diameter
formula: "width >= tool_diameter * 1.2"
severity: ERROR
```

### ValidationReport Schema
```python
class ValidationReport(BaseModel):
    part_id: str
    validation_timestamp: str  # ISO 8601
    layer1_results: list[RuleResult]
    layer2_results: list[RuleResult]
    overall_valid: bool
    severity_counts: dict      # {"ERROR": 2, "WARNING": 1}
    provenance: ProvenanceRecord

class RuleResult(BaseModel):
    rule_id: str
    rule_version: str
    passed: bool
    severity: str              # "ERROR" | "WARNING" | "INFO"
    message: str
    affected_nodes: list[str]  # geometry node IDs
    evidence: dict
```

### Acceptance Tests
- [ ] Open contours detected (GEO-001)
- [ ] Self-intersections detected (GEO-002)
- [ ] Edge clearance violations detected (MFG-001)
- [ ] Too-close holes detected (MFG-002)
- [ ] ValidationReport serializes to JSON
- [ ] Same input always produces same report (determinism test)
- [ ] Invalid geometry tested against 3+ real violation cases

### Hard Stop: 4 hours from start of this phase

---

## Phase 5 — Provenance System (Hours 17–19)

### Goal
Scientific traceability for every inference and label.

### Tasks
1. `omim/provenance/record.py` — `ProvenanceRecord` Pydantic model
2. `omim/provenance/tracker.py` — `ProvenanceTracker` context manager
3. `omim/provenance/serializer.py` — provenance → JSON
4. Inject provenance into: FeatureNode, ValidationReport, DatasetSample

### ProvenanceRecord Schema
See [[Provenence and Uncertainty]] for full spec.

```python
class ProvenanceRecord(BaseModel):
    record_id: str             # UUID
    timestamp: str             # ISO 8601
    generator: str             # "omim-v0.1.0"
    ontology_version: str      # "v0.1.0"
    ruleset_version: str       # "v0.1.0"
    inference_method: str      # "deterministic" | "heuristic" | "ml_gnn" | "ml_llm"
    confidence: float          # 0.0 - 1.0
    evidence: list[EvidenceItem]
    source_file: str | None
    source_entity_ids: list[str]
    review_status: str         # "unreviewed" | "expert_reviewed" | "auto_validated"
    
class EvidenceItem(BaseModel):
    type: str                  # "geometric_measurement" | "rule_match" | "pattern_match"
    description: str
    value: float | str | None
    rule_id: str | None
```

### Acceptance Tests
- [ ] Every FeatureNode has non-null provenance
- [ ] Every ValidationReport entry has non-null provenance
- [ ] ProvenanceRecord round-trips through JSON without data loss
- [ ] `inference_method = "deterministic"` never has `confidence < 1.0`
- [ ] `inference_method = "ml_*"` always has evidence list

### Hard Stop: 2 hours from start of this phase

---

## Phase 6 — Semantic Layer (Hours 19–23)

### Goal
Infer manufacturing intent (feature classes) from geometry patterns.

### Strategy: Deterministic Rules First, ML Second

### Tasks
1. `omim/semantic/classifiers/hole_classifier.py` — classify circles as feature types
2. `omim/semantic/classifiers/contour_classifier.py` — classify contours
3. `omim/semantic/classifiers/pattern_classifier.py` — classify groups (shelf pin rows, etc.)
4. `omim/semantic/inference_engine.py` — orchestrate classifiers, merge hypotheses
5. `omim/semantic/confidence_model.py` — rule-based confidence scoring

### Hole Classification Logic (Deterministic Heuristics)
```python
# Based on diameter ranges — panel manufacturing standards
def classify_hole(diameter_mm: float) -> tuple[str, float]:
    """Returns (feature_class, confidence)"""
    if 4.5 <= diameter_mm <= 5.5:
        return "SHELF_PIN_HOLE", 0.90      # 5mm standard shelf pin
    elif 34.0 <= diameter_mm <= 36.0:
        return "HINGE_CUP_HOLE", 0.92      # 35mm Blum-style hinge cup
    elif 6.5 <= diameter_mm <= 7.5:
        return "CONFIRMAT_HOLE", 0.85       # 7mm Euro screw
    elif 7.5 <= diameter_mm <= 10.5:
        return "DOWEL_HOLE", 0.75           # 8–10mm dowel
    elif 2.0 <= diameter_mm <= 4.5:
        return "THROUGH_HOLE", 0.65         # Small fastener hole
    elif diameter_mm > 10.5:
        return "THROUGH_HOLE", 0.60         # Large through hole
    else:
        return "UNKNOWN_HOLE", 0.30
```

### Pattern Classification Logic
```python
# Shelf pin row detection (32mm system)
# Reference: European "Rasterbohrsystem" (32mm grid system)
# Standard: holes spaced 32mm apart in a column, 5mm diameter
def detect_shelf_pin_row(holes: list[CircleFeature]) -> bool:
    """Detect 5mm holes spaced exactly 32mm apart in a column."""
    # Filter for 5mm holes
    # Check collinearity (same X or Y within tolerance)
    # Check spacing = 32mm ± 1mm
    # Minimum 3 holes to confirm pattern
```

### Acceptance Tests
- [ ] HINGE_CUP_HOLE correctly identified (35mm circles)
- [ ] SHELF_PIN_HOLE correctly identified (5mm circles in 32mm grid)
- [ ] CONFIRMAT_HOLE identified (7mm circles)
- [ ] Shelf pin row pattern detected from column of 5mm holes
- [ ] Every inference has confidence score
- [ ] Every inference has evidence chain
- [ ] Ambiguous features have multiple hypotheses with ranked confidence

### Hard Stop: 4 hours from start of this phase

---

## Phase 7 — Synthetic Dataset Generator (Hours 23–27)

### Goal
Generate large quantities of labeled manufacturing samples for training and benchmarking.

### Tasks
1. `omim/synthetic/panel_generator.py` — procedural panel geometry generation
2. `omim/synthetic/feature_sampler.py` — sample features from ontology distribution
3. `omim/synthetic/invalid_generator.py` — inject manufacturing violations
4. `omim/synthetic/dxf_writer.py` — write generated panels to DXF
5. `omim/synthetic/dataset_builder.py` — orchestrate generation, add metadata, write to disk
6. `omim/synthetic/configs/default.yaml` — generation configuration

### Generator Logic
```python
class PanelGeneratorConfig(BaseModel):
    seed: int                           # for reproducibility
    panel_width_range_mm: tuple = (200, 2400)
    panel_height_range_mm: tuple = (200, 1200)
    panel_thickness_mm: float = 18.0    # default
    feature_density: str = "medium"     # "sparse" | "medium" | "dense"
    include_invalid: bool = True        # generate some invalid cases
    invalid_ratio: float = 0.15         # 15% invalid samples
    n_samples: int = 1000
    ontology_version: str = "v0.1.0"
    ruleset_version: str = "v0.1.0"
```

### Generation Algorithm
```
For each sample:
  1. Sample panel dimensions from config range
  2. Place panel features procedurally:
     a. Add outer profile cut (panel boundary)
     b. Sample N features from distribution (shelf pins, hinges, etc.)
     c. Check spacing constraints during placement
     d. Place features that pass constraints
  3. If invalid sample:
     a. Inject 1–3 manufacturing violations (close holes, edge violations, etc.)
  4. Write to DXF via ezdxf
  5. Run through full pipeline: parse → MGG → validate → semantics
  6. Attach ground-truth labels + provenance
  7. Write dataset sample (DXF + MGG JSON + labels JSON)
```

### Dataset Sample Structure
```
data/synthetic/samples/
├── sample_00001/
│   ├── geometry.dxf           # generated DXF
│   ├── mgg.json               # Manufacturing Geometry Graph
│   ├── validation.json        # ValidationReport
│   ├── labels.json            # ground truth labels
│   └── provenance.json        # full provenance chain
├── sample_00002/
│   └── ...
└── dataset_metadata.json      # generation config, stats, versions
```

### Acceptance Tests
- [ ] 1000+ samples generated in < 30 minutes
- [ ] Valid samples pass Layer 1+2 validation
- [ ] Invalid samples fail validation at injected violation location
- [ ] Labels match injected features (ground truth is correct)
- [ ] Dataset reproducible from same seed + config
- [ ] `dataset_metadata.json` contains: generator version, ontology version, ruleset version, creation timestamp, sample count, valid/invalid split

### Hard Stop: 4 hours from start of this phase

---

## Phase 8 — Benchmark Suite (Hours 27–29)

### Goal
Define standardized evaluation tasks for external researchers to measure model performance.

### Tasks
1. `omim/benchmarks/task_definitions.yaml` — 4 benchmark task definitions
2. `omim/benchmarks/evaluator.py` — standard evaluation runner
3. `omim/benchmarks/metrics.py` — precision, recall, F1, accuracy
4. `omim/benchmarks/splits.py` — train/val/test split generator
5. `README_BENCHMARKS.md` — researcher-facing benchmark documentation

### Benchmark Tasks
See [[Benchmarking]] for full specifications.

| Task ID | Name | Type | Primary Metric |
|---------|------|------|---------------|
| BENCH-001 | Feature Classification | Multi-class classification | Macro F1 |
| BENCH-002 | Manufacturability Validation | Binary classification | F1, FPR |
| BENCH-003 | Operation Inference | Multi-label classification | Macro F1 |
| BENCH-004 | Anomaly Detection | Anomaly detection | AUROC |

### Acceptance Tests
- [ ] All 4 benchmark tasks have: description, input format, output format, metric definition
- [ ] Evaluator produces numeric scores for baseline (majority class)
- [ ] Train/val/test splits are stratified and reproducible
- [ ] Benchmark documentation is readable by external researcher

### Hard Stop: 2 hours from start of this phase

---

## Phase 9 — ML Integration (Hours 29–32)

### Goal
Baseline GNN that demonstrates the infrastructure is trainable. NOT production-grade ML.

### Technology
```python
import torch
import torch_geometric
from torch_geometric.nn import SAGEConv, GATConv
```

### Tasks
1. `omim/ml/graph_converter.py` — MGG → PyTorch Geometric Data object
2. `omim/ml/models/gnn_classifier.py` — GraphSAGE-based feature classifier
3. `omim/ml/trainer.py` — training loop with early stopping
4. `omim/ml/evaluator.py` — evaluation on BENCH-001

### Model Architecture (Minimal Viable)
```python
class ManufacturingGNN(torch.nn.Module):
    """GraphSAGE-based manufacturing feature classifier.
    
    Reference: Hamilton et al., "Inductive Representation Learning on 
    Large Graphs." NeurIPS 2017. arXiv:1706.02216
    """
    def __init__(self, in_channels, hidden_channels, out_channels):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, hidden_channels)
        self.classifier = torch.nn.Linear(hidden_channels, out_channels)
    
    def forward(self, x, edge_index):
        x = F.relu(self.conv1(x, edge_index))
        x = F.dropout(x, p=0.3, training=self.training)
        x = F.relu(self.conv2(x, edge_index))
        return self.classifier(x)
```

### Node Features (Input)
```python
# Node feature vector for each GeometryNode
features = [
    area_normalized,           # normalized area
    perimeter_normalized,      # normalized perimeter
    aspect_ratio,              # bounding box aspect ratio
    circularity,               # 4π·area/perimeter²
    layer_encoded,             # one-hot layer type
    is_closed,                 # binary
    depth_normalized,          # feature depth if known
    diameter_normalized,       # for circles
]
# Input dimension: 8–16 features
```

### Acceptance Tests
- [ ] MGG converts to PyG Data object without error
- [ ] Model trains for 10+ epochs without NaN loss
- [ ] Evaluation produces valid F1 score on BENCH-001
- [ ] Model inference runs without error on new DXF
- [ ] Training is reproducible from same seed

**HARD LIMIT**: If ML integration takes > 3 hours, STOP. Record baseline (majority class) performance. Ship deterministic pipeline without trained model.

### Hard Stop: 3 hours from start of this phase

---

## Phase 10 — Demo & Packaging (Hours 32–36)

### Goal
End-to-end pipeline that communicates value in < 2 minutes.

### Option A: CLI Demo (Recommended if time is short)
```bash
python -m omim.demo.cli input.dxf --output demo_output/
# Produces:
# demo_output/mgg.json
# demo_output/validation_report.json
# demo_output/semantic_labels.json
# demo_output/summary.txt
```

### Option B: Web Demo (If time permits)
```python
# FastAPI + simple HTML frontend
# POST /analyze  →  { dxf_file }  →  { mgg, validation, semantics }
# GET /visualize  →  simple SVG graph visualization
```

### Demo Scope Lock

The demo is LOCKED to exactly this flow. Nothing more. Nothing less.

Adding UI polish, extra visualizations, or new features to the demo is scope creep and is forbidden until the core pipeline works end-to-end.

### Demo Flow
```
1. Upload/input DXF file
      ↓
2. Parse geometry (ezdxf)
      ↓  
3. Build MGG (NetworkX)
      ↓
4. Run validation (deterministic rules)
      ↓
5. Infer semantics (heuristics + optional GNN)
      ↓
6. Export: MGG JSON + ValidationReport + SemanticLabels + Provenance
      ↓
7. Display summary + confidence scores
```

### Acceptance Tests
- [ ] End-to-end pipeline runs on real DXF without error
- [ ] Output files contain expected fields
- [ ] Semantic labels have confidence scores visible
- [ ] Validation violations clearly reported
- [ ] Demo understandable by non-expert in < 2 minutes
- [ ] Demo works from clean environment (test this!)

### Hard Stop: 4 hours from start of this phase

---

## Phase 11 — Documentation & Dataset Release (Hours 36–40)

### Tasks
1. `README.md` — project overview, installation, quickstart
2. `docs/ARCHITECTURE.md` — system architecture overview
3. `data/synthetic/README.md` — dataset documentation for researchers
4. `BENCHMARKS.md` — benchmark task guide
5. `CONTRIBUTING.md` — contribution guidelines
6. Tag release: `git tag v0.1.0-hackathon`
7. Create sample dataset: package 1000 samples as ZIP

### README Must Include
- What OMIM is (1 paragraph)
- What it is NOT (list)
- Installation instructions
- Quickstart example (3 commands)
- Dataset overview
- Benchmark overview
- Citation format (for researchers)

### Hard Stop: 4 hours from start of this phase

---

## Checkpoint Schedule

| Checkpoint | Target Time | Must Have |
|------------|-------------|-----------|
| v0-skeleton | Hour 2 | Repo structure, imports work |
| v0-ontology | Hour 5 | All ontology terms load |
| v0-parser | Hour 9 | DXFs parse, geometry extracted |
| v0-graph | Hour 13 | MGG builds + serializes |
| v0-validation | Hour 17 | 10+ rules fire correctly |
| v0-provenance | Hour 19 | Every label traceable |
| v0-semantic | Hour 23 | Feature classification works |
| v0-synthetic | Hour 27 | 1000+ samples generated |
| v0-benchmarks | Hour 29 | 4 benchmark tasks defined |
| v0-ml | Hour 32 | GNN trains (or cut scope) |
| v0-demo | Hour 36 | End-to-end pipeline demo |
| v0-release | Hour 40 | README, dataset packaged |

---

## Contingency Plans

### If DXF parser takes > 4 hours
→ Use ezdxf directly in downstream modules without abstraction layer
→ Skip layer classification for now
→ Proceed with raw geometry extraction only

### If MGG becomes too complex
→ Use raw NetworkX DiGraph with Python dicts on nodes
→ Skip Pydantic schemas until after demo
→ Serialize with `nx.node_link_data(G)`

### If validation engine takes > 4 hours
→ Implement only Layer 1 (geometric validity)
→ Hard-code 5 rules instead of YAML rule engine
→ Skip manufacturing feasibility rules for v0

### If time runs out before ML
→ Ship WITHOUT ML
→ Mark as v0.2 milestone
→ Deterministic pipeline alone is sufficient for demo

### If web demo is too complex
→ Ship CLI demo
→ Save FastAPI for post-hackathon
→ Spend time on better README instead

---

## HPC Execution Strategy

If HPC (supercomputer/GPU cluster) is available during or after the hackathon, these are the only valid uses:

### USE HPC FOR (High Value)
| Task | Why HPC | Target Output |
|------|---------|--------------|
| Mass synthetic panel generation | CPU-parallelizable; embarrassingly parallel | 100k–1M samples |
| Graph generation from DXFs | Parallel per-sample | 1M MGG files |
| Validation sweeps | Each sample independent | Full validation corpus |
| GNN training | GPU-accelerated | Trained model checkpoint |
| Benchmark suite evaluation | Parallel per-model | Full benchmark scores |
| Node embedding computation | GPU matrix operations | Pre-computed embeddings |

### DO NOT WASTE HPC ON
| Anti-Pattern | Why Wasteful |
|-------------|-------------|
| Training giant LLMs | Out of scope; LLMs are not the core architecture |
| Running chatbot demos | Demo runs on a laptop |
| API serving | Local laptop demo is sufficient for hackathon |
| Hyper-parameter search before baseline | Premature optimization |
| Generating 1M samples before 1k is validated | Validate at small scale first |

### HPC Job Structure (Post-Hackathon)

```bash
# Mass generation job
#SBATCH --ntasks=1000
#SBATCH --cpus-per-task=1
#SBATCH --time=4:00:00

# Each task generates N/1000 samples
python -m omim.synthetic.generate \
  --seed $SLURM_ARRAY_TASK_ID \
  --n_samples 1000 \
  --output_dir /scratch/omim/samples/

# GNN training job
#SBATCH --gres=gpu:1
#SBATCH --time=8:00:00
python -m omim.ml.train \
  --dataset /scratch/omim/dataset_v0.1.0/ \
  --model graphsage \
  --task bench001
```

### Storage & IO at Scale

**Storage and IO become the bottleneck before compute does.** At 100k+ samples, JSON-per-sample causes filesystem and read speed problems.

| Format | Use Case | Notes |
|--------|----------|-------|
| JSON per sample | Hackathon (< 10k samples) | Human-readable; easy to debug |
| JSONL shards | v0.2 (10k–100k) | 1000 samples per shard; fast sequential read |
| Parquet | v0.3 (100k+) | Columnar; fast filtering; pandas/polars compatible |
| MessagePack | Graph-heavy workloads | 3–5× smaller than JSON for graph data |
| torch.save() | ML training | Pre-convert MGGs to PyG tensors; skip JSON entirely at training time |

**For hackathon**: JSON per sample is correct. Note the migration path exists.

### Scale Targets

| Scale | Samples | Expected Time (single machine) | Notes |
|-------|---------|-------------------------------|-------|
| Hackathon demo | 1,000 | ~5 min | Must be achievable on laptop |
| Post-hackathon v0.2 | 10,000 | ~30 min | Reasonable for local machine |
| Research scale | 100,000 | ~5 hours single / ~20 min HPC | HPC strongly recommended |
| Publication scale | 1,000,000 | ~50 hours single / ~3 hours HPC | Requires HPC |

---

## Post-Hackathon Roadmap (Not During Hackathon)

See [[Full System Architecture]] for detailed post-hackathon directions.

- v0.2: 5000+ synthetic samples, GNN trained baseline
- v0.3: Real panel DXF dataset integration (with permission)
- v0.4: Expert review of ontology and rules
- v1.0: HuggingFace dataset release
- v1.1: Paper submission to manufacturing AI venue
- v2.0: Industrial domain expansion (waterjet, laser)
