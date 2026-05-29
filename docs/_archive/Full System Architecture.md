# Full System Architecture

See also: [[What Is OMIM]], [[Manufacturing Geometry Graph (MGG) Specification]], [[Execution Roadmap]]

---

## System Overview

OMIM is a pipeline architecture. Data flows in one direction through independently-bounded subsystems. Each subsystem has:
- Defined inputs and outputs (typed contracts)
- No shared mutable state with other subsystems
- Clear failure boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                        OMIM Pipeline v0                         │
│                                                                 │
│  [DXF File]                                                     │
│      │                                                          │
│      ▼                                                          │
│  ┌─────────┐    RawGeometry     ┌─────────────┐               │
│  │  DXF    │ ─────────────────▶ │    MGG      │               │
│  │ Parser  │                    │   Builder   │               │
│  └─────────┘                    └──────┬──────┘               │
│                                        │                        │
│                                        │  ManufacturingGeometryGraph      
│                                 ┌──────▼──────────────────┐    │
│                                 │    Validation Engine    │    │
│                                 │  (Layer 1: Geometry)    │    │
│                                 │  (Layer 2: Mfg Rules)   │    │
│                                 └──────┬──────────────────┘    │
│                                        │                        │
│                                        │  MGG + ValidationReport
│                                 ┌──────▼──────────────────┐    │
│                                 │    Semantic Layer        │    │
│                                 │  (Heuristics + GNN)     │    │
│                                 └──────┬──────────────────┘    │
│                                        │                        │
│                                        │  Annotated MGG         │
│                         ┌─────────────┬┴──────────────────┐    │
│                         │             │                    │    │
│                    ┌────▼───┐   ┌─────▼────┐   ┌────────▼┐    │
│                    │Dataset │   │Benchmark │   │  Demo   │    │
│                    │  Gen   │   │  Suite   │   │  API    │    │
│                    └────────┘   └──────────┘   └─────────┘    │
└─────────────────────────────────────────────────────────────────┘

Cross-cutting: Ontology, Provenance System, Rule Engine
```

---

## Module Map

### Core Modules

| Module | Path | Responsibility |
|--------|------|---------------|
| DXF Parser | `omim/parser/` | DXF → RawGeometry objects |
| MGG Builder | `omim/graph/` | RawGeometry → ManufacturingGeometryGraph |
| Validation Engine | `omim/validation/` | MGG → ValidationReport |
| Semantic Layer | `omim/semantic/` | MGG → Annotated MGG with feature labels |
| Provenance System | `omim/provenance/` | Cross-cutting traceability metadata |
| Rule Engine | `omim/rules/` | Load + execute externalized YAML rules |
| Ontology | `omim/ontology/` | Load + query manufacturing vocabulary |

### Data Generation Modules

| Module | Path | Responsibility |
|--------|------|---------------|
| Synthetic Generator | `omim/synthetic/` | Procedural manufacturing data generation |
| Dataset Builder | `omim/synthetic/dataset_builder.py` | Orchestrate generation → labeled dataset |

### Evaluation Modules

| Module | Path | Responsibility |
|--------|------|---------------|
| Benchmark Suite | `omim/benchmarks/` | Task definitions, evaluation, metrics |
| ML Integration | `omim/ml/` | GNN training + inference |

### Interface Modules

| Module | Path | Responsibility |
|--------|------|---------------|
| CLI | `omim/cli.py` | Command-line interface |
| Demo API | `omim/demo/api.py` | FastAPI demo server (optional) |

---

## Data Flow Contracts

### Contract 1: DXF Parser Output

```python
# omim/parser/geometry_objects.py
class RawGeometry(BaseModel):
    """Output of DXF parser. Inputs to MGG Builder."""
    source_file: str
    source_hash: str           # SHA256 of DXF file (for provenance)
    units: str                 # "mm" | "inch" (normalized to mm)
    entities: list[RawEntity]
    layer_map: dict[str, str]  # layer_name → inferred_layer_type
    bounding_box: BoundingBox
    parser_version: str
    parse_timestamp: str

class RawEntity(BaseModel):
    entity_id: str             # UUID (stable across re-parses of same file)
    entity_type: str           # "circle" | "line" | "arc" | "polyline"
    layer: str
    coordinates: list          # type-specific: [cx,cy,r] for circle, [[x,y],...] for polyline
    is_closed: bool
    area: float | None
    perimeter: float | None
    metadata: dict             # any additional ezdxf properties
```

### Contract 2: MGG Builder Output

```python
# omim/graph/mgg.py
class ManufacturingGeometryGraph(BaseModel):
    """Canonical manufacturing representation."""
    graph_id: str              # UUID
    version: str               # MGG spec version
    source_provenance: ProvenanceRecord
    nodes: dict[str, MGGNode]  # node_id → node
    edges: list[MGGEdge]
    metadata: GraphMetadata

class GraphMetadata(BaseModel):
    part_id: str
    source_file: str
    panel_dimensions: BoundingBox | None
    node_count: int
    edge_count: int
    ontology_version: str
    creation_timestamp: str
```

See [[Manufacturing Geometry Graph (MGG) Specification]] for full node/edge schemas.

### Contract 3: Validation Engine Output

```python
# omim/validation/report.py
class ValidationReport(BaseModel):
    report_id: str
    graph_id: str
    timestamp: str
    layer1_results: list[RuleResult]   # geometric validity
    layer2_results: list[RuleResult]   # manufacturing feasibility
    overall_valid: bool
    severity_summary: dict             # {"ERROR": N, "WARNING": N, "INFO": N}
    provenance: ProvenanceRecord

class RuleResult(BaseModel):
    rule_id: str
    rule_version: str
    rule_name: str
    passed: bool
    severity: str              # "ERROR" | "WARNING" | "INFO"
    message: str
    affected_node_ids: list[str]
    evidence: dict
    execution_time_ms: float
```

### Contract 4: Semantic Layer Output

```python
# omim/semantic/annotations.py
class SemanticAnnotation(BaseModel):
    """Attaches to FeatureNodes in MGG."""
    annotation_id: str
    node_id: str
    feature_class: str         # from ontology
    confidence: float          # 0.0 - 1.0
    hypotheses: list[ClassHypothesis]  # ranked alternatives
    inference_method: str
    evidence: list[EvidenceItem]
    provenance: ProvenanceRecord

class ClassHypothesis(BaseModel):
    feature_class: str
    confidence: float
    supporting_evidence: list[str]
```

### Contract 5: Dataset Sample

```python
# omim/synthetic/sample.py
class DatasetSample(BaseModel):
    sample_id: str
    split: str                 # "train" | "val" | "test"
    is_valid: bool             # True = passes all rules
    violations: list[str]      # if invalid: list of injected violation IDs
    
    # Paths (relative to dataset root)
    dxf_path: str
    mgg_path: str
    validation_path: str
    labels_path: str
    
    # Ground truth labels
    ground_truth: GroundTruthLabels
    provenance: ProvenanceRecord

class GroundTruthLabels(BaseModel):
    features: list[FeatureLabel]  # one per feature in the panel
    operations: list[str]         # operations used
    complexity: str               # "simple" | "medium" | "complex"
    
class FeatureLabel(BaseModel):
    geometry_entity_id: str
    feature_class: str
    diameter_mm: float | None
    depth_mm: float | None
    position_mm: list[float]
```

---

## Dependency Rules

### Allowed Dependencies (Bottom-Up)

```
ontology          ← no internal dependencies
provenance        ← ontology
rule_engine       ← ontology, provenance
parser            ← provenance
graph             ← ontology, provenance
validation        ← graph, rule_engine, provenance
semantic          ← graph, ontology, validation, provenance, (ml optional)
synthetic         ← parser, graph, validation, semantic, provenance
benchmarks        ← synthetic, validation, semantic
ml                ← graph, semantic, benchmarks
demo              ← all modules (thin integration layer only)
```

### Forbidden Dependencies

| Forbidden | Why |
|-----------|-----|
| `validation` → `semantic` | Validation must be semantics-free (deterministic layer) |
| `parser` → `graph` | Parser must not know about graph representation |
| `graph` → `validation` | Graph is pure representation; validation is a consumer |
| `ml` → `validation` | ML cannot override validation results |
| any module → `demo` | Demo is output-only |
| any module → `synthetic` | Synthetic is a generator, not a dependency |

---

## File System Layout

```
omim/                              # Python package root
├── __init__.py
├── cli.py                         # CLI entry point
│
├── ontology/                      # Vocabulary layer
│   ├── __init__.py
│   ├── loader.py                  # YAML → Python objects
│   └── models.py                  # Pydantic ontology types
│
├── parser/                        # DXF parsing
│   ├── __init__.py
│   ├── dxf_reader.py
│   ├── entity_extractor.py
│   ├── normalizer.py
│   ├── contour_builder.py
│   ├── layer_classifier.py
│   └── geometry_objects.py        # Pydantic types
│
├── graph/                         # MGG representation
│   ├── __init__.py
│   ├── mgg.py                     # ManufacturingGeometryGraph class
│   ├── nodes.py                   # Node types
│   ├── edges.py                   # Edge types
│   ├── builder.py                 # geometry → MGG
│   ├── serializer.py              # MGG ↔ JSON
│   └── queries.py                 # Graph queries
│
├── provenance/                    # Traceability
│   ├── __init__.py
│   ├── record.py                  # ProvenanceRecord
│   ├── tracker.py                 # ProvenanceTracker context manager
│   └── serializer.py
│
├── validation/                    # Deterministic validation
│   ├── __init__.py
│   ├── layer1_geometry.py
│   ├── layer2_manufacturability.py
│   ├── rule_engine.py
│   └── report.py
│
├── rules/                         # Rule engine
│   ├── __init__.py
│   └── loader.py
│
├── semantic/                      # Feature inference
│   ├── __init__.py
│   ├── inference_engine.py
│   ├── confidence_model.py
│   └── classifiers/
│       ├── hole_classifier.py
│       ├── contour_classifier.py
│       └── pattern_classifier.py
│
├── synthetic/                     # Dataset generation
│   ├── __init__.py
│   ├── panel_generator.py
│   ├── feature_sampler.py
│   ├── invalid_generator.py
│   ├── dxf_writer.py
│   ├── dataset_builder.py
│   └── configs/
│       └── default.yaml
│
├── benchmarks/                    # Evaluation suite
│   ├── __init__.py
│   ├── evaluator.py
│   ├── metrics.py
│   └── splits.py
│
└── ml/                            # Machine learning
    ├── __init__.py
    ├── graph_converter.py
    ├── trainer.py
    ├── evaluator.py
    └── models/
        └── gnn_classifier.py

data/
├── ontology/                      # YAML vocabulary definitions
│   ├── features.yaml
│   ├── operations.yaml
│   ├── relationships.yaml
│   ├── constraints.yaml
│   └── materials.yaml
│
├── rules/                         # YAML rule definitions
│   ├── panel_cnc_rules.yaml       # Layer 1+2 rules
│   └── rules_changelog.md
│
├── test_dxfs/                     # Real DXFs for testing
│   ├── valid/
│   ├── invalid/
│   └── edge_cases/
│
└── synthetic/                     # Generated dataset
    ├── samples/
    │   ├── sample_00001/
    │   │   ├── geometry.dxf
    │   │   ├── mgg.json
    │   │   ├── validation.json
    │   │   ├── labels.json
    │   │   └── provenance.json
    │   └── ...
    ├── splits/
    │   ├── train.jsonl
    │   ├── val.jsonl
    │   └── test.jsonl
    └── dataset_metadata.json

tests/
├── test_parser.py
├── test_graph.py
├── test_validation.py
├── test_semantic.py
├── test_provenance.py
├── test_synthetic.py
└── fixtures/
    └── sample_dxfs/

docs/
├── ARCHITECTURE.md
├── ONTOLOGY.md
└── BENCHMARKS.md
```

---

## Technology Stack

### Core Dependencies

| Library | Version | Purpose | Docs |
|---------|---------|---------|------|
| ezdxf | ≥1.3.0 | DXF parsing | https://ezdxf.readthedocs.io/ |
| shapely | ≥2.0.0 | 2D geometric operations | https://shapely.readthedocs.io/ |
| networkx | ≥3.3 | Graph data structure | https://networkx.org/ |
| pydantic | ≥2.0 | Data validation / schemas | https://docs.pydantic.dev/ |
| numpy | ≥1.26 | Numerical operations | https://numpy.org/ |
| scipy | ≥1.12 | Spatial algorithms | https://scipy.org/ |
| PyYAML | ≥6.0 | Rule/ontology YAML loading | https://pyyaml.org/ |
| pytest | ≥8.0 | Testing framework | https://docs.pytest.org/ |

### Optional Dependencies

| Library | Version | Purpose | Docs |
|---------|---------|---------|------|
| torch | ≥2.3 | ML training | https://pytorch.org/ |
| torch-geometric | ≥2.5 | Graph neural networks | https://pytorch-geometric.readthedocs.io/ |
| fastapi | ≥0.111 | Demo API server | https://fastapi.tiangolo.com/ |
| uvicorn | ≥0.29 | ASGI server for FastAPI | https://www.uvicorn.org/ |
| cadquery | ≥2.4 | Programmatic CAD (synthetic gen) | https://cadquery.readthedocs.io/ |

### Dev Tools

| Tool | Purpose |
|------|---------|
| ruff | Fast Python linter |
| mypy | Static type checking |
| black | Code formatting |
| pre-commit | Git hook automation |
| pytest-cov | Code coverage |

---

## Interface Contracts (API Boundaries)

All subsystems communicate through typed Pydantic models. This prevents:
- Silent data corruption between modules
- AI-generated "duck typing" that hides bugs
- Schema drift between writer and reader

**Rule**: Never pass raw dicts between modules. Always use typed models.

### Pipeline Functions (Top-Level API)

```python
# omim/pipeline.py — thin orchestration layer

def parse_dxf(dxf_path: str) -> RawGeometry:
    """Parse DXF file into raw geometry objects."""

def build_mgg(geometry: RawGeometry, ontology_version: str = "v0.1.0") -> ManufacturingGeometryGraph:
    """Convert raw geometry into Manufacturing Geometry Graph."""

def validate_mgg(mgg: ManufacturingGeometryGraph, ruleset_version: str = "v0.1.0") -> ValidationReport:
    """Run deterministic validation rules against MGG."""

def infer_semantics(mgg: ManufacturingGeometryGraph, validation: ValidationReport) -> AnnotatedMGG:
    """Infer manufacturing feature semantics (heuristics + optional GNN)."""

def analyze_dxf(dxf_path: str) -> AnalysisResult:
    """Run full pipeline: parse → MGG → validate → semantics."""

class AnalysisResult(BaseModel):
    geometry: RawGeometry
    mgg: ManufacturingGeometryGraph
    validation: ValidationReport
    annotations: list[SemanticAnnotation]
    pipeline_provenance: ProvenanceRecord
```

---

## NetworkX Scaling Constraints

NetworkX is the right choice for v0. It is not the right choice forever.

| Scale | NetworkX Performance | Action |
|-------|---------------------|--------|
| < 10,000 nodes per graph | Fast; no issues | Use NetworkX |
| 10,000 – 100,000 nodes | Slow serialization; memory pressure | Start using PyG tensors for ML path |
| > 100,000 nodes | Unacceptable for HPC batch workloads | Migrate to `rustworkx` or `graph-tool` |

**For the hackathon**: NetworkX is correct. Panel DXFs have 10–500 nodes. No scaling issue.

**For 1M sample generation**: Each sample is independent (< 500 nodes). Parallelization avoids the NetworkX scaling problem entirely — run 1000 processes each with their own small NetworkX graph.

**Migration path** (when needed):
```python
# When switching to PyTorch Geometric tensors:
# 1. Keep NetworkX for graph construction + querying (it's still good for that)
# 2. Use mgg.to_pyg_data() to convert to tensor format for ML only
# 3. Serialize as PyG Data objects (torch.save) for fast ML loading
# Do NOT replace NetworkX prematurely. Prove the need first.
```

---

## Future Interoperability Map

OMIM is intentionally isolated from industrial ecosystems in v0. But the abstraction boundaries are designed to allow these connections later.

| Integration Target | What It Enables | Implementation Complexity |
|-------------------|-----------------|--------------------------|
| **STEP-NC / ISO 14649** | Read richer semantic data when available; compare STEP-NC labels vs OMIM inference | High — requires STEP parser |
| **MTConnect** | Consume real-time machine data to enrich manufacturing context | High — real-time streaming |
| **OPC-UA Manufacturing** | Industrial equipment communication for live feedback | Very High — hardware integration |
| **CAM system export** | Parse FreeCAD Path, Mastercam XML, etc. for ground truth comparison | Medium — per-system parsers |
| **ERP/MES** | Link panels to BOMs, work orders, job tracking | High — enterprise integration |
| **HuggingFace Datasets** | Publish OMIM datasets for community use | Low — dataset formatting only |

**v0 rule**: None of these are implemented. The rule engine, graph, and provenance layers are designed so they can consume additional data sources without architectural changes — but no effort is spent on the integration itself until v0 is working.

---

## Error Handling Philosophy

### Parser Errors
- Unsupported entity type → log warning, skip entity, continue
- Malformed DXF → return structured `ParseError`, do not raise
- Empty file → return empty `RawGeometry` with warning

### Validation Errors
- Rule evaluation crash → return `RuleResult` with `passed=False`, `severity="SYSTEM_ERROR"`
- Rule YAML malformed → raise at load time (fail fast, not silently)

### ML Errors
- Model inference crash → fall back to heuristic inference
- Model not loaded → use heuristics only, log warning
- NaN in embeddings → log error, return `confidence=0.0` for that node

### General Principle
Every public function either:
1. Returns a result (possibly with errors embedded in the result object), or
2. Raises a clearly typed exception

Silent failures are forbidden.

---

## Post-Hackathon Architecture Extensions

### v0.2 — Scale
- HPC-parallel dataset generation (1M+ samples)
- Parquet dataset format for large-scale storage
- DVC (Data Version Control) integration

### v0.3 — Domain Expansion
- Waterjet/laser cutting domain (new ontology YAML, new rules)
- STEP/IGES format parser
- 3D geometry support (requires 3D graph layer)

### v0.4 — Production Infrastructure
- REST API with proper authentication
- Dataset versioning (DVC or similar)
- HuggingFace Datasets integration

### v1.0 — Research Publication
- Expert review of ontology and rules
- Paper: "OMIM: Open Manufacturing Intelligence Middleware"
- Target venues: CIRP CMS, IJAMT, ICLR Manufacturing Track
