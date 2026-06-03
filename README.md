# OMIM — Open Manufacturing Intelligence Middleware

**Deterministic manufacturing geometry analysis with provenance-tracked semantic inference.**

OMIM transforms DXF manufacturing drawings into semantically-rich Manufacturing Geometry Graphs (MGGs), enabling automated validation, feature classification, and intelligent analysis of CNC panel machining data.

## Architecture

```
DXF File → Parser → MGG Builder → Feature Classifier → Validation Engine → API/Visualization
                         ↓
              Manufacturing Geometry Graph
              (NetworkX MultiDiGraph)
                         ↓
         ┌──────────────┼──────────────┐
    GeometryNodes   FeatureNodes   ConstraintNodes
    (immutable)     (classified)    (violations)
```

**Authority Hierarchy:** Geometry Truth > Validation Truth > Semantic Truth > AI Truth

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Analyze a DXF file
omim analyze panel.dxf

# Validate only
omim validate panel.dxf

# Analyse a multi-panel nest (stock sheet carrying many panels)
omim nest sheet.dxf            # text summary; -o out.json for full layout

# Generate a synthetic dataset (standards-grounded, validator-gated)
omim generate ./data/synthetic -n 1000 --seed 42 --invalid-ratio 0.30

# Verify a dataset/sample (schema + graph integrity)
omim verify ./data/synthetic

# Run the benchmark suite (BENCH-001..004) against a dataset
omim benchmark ./data/synthetic --split test

# Ground generation in a real DXF corpus (catalog-conformance check)
omim ingest ./real_dxfs
omim ground ./real_dxfs --profile-out grounding.json

# Train / predict with the optional GNN layer  (pip install 'omim[ml]')
omim train --dataset ./data/synthetic/samples --checkpoint-dir ./ckpt
omim predict panel.dxf --feature-checkpoint ./ckpt/feature_gnn.pt

# Start API server (8 endpoints incl. /analyze, /annotate, /generate, /ontology, /rules)
omim serve

# Run tests
pytest
```

## Layered architecture (authority hierarchy)

OMIM enforces a strict trust hierarchy — lower layers never override higher ones:

| Level | Layer | Authority | Module |
|---|---|---|---|
| 1–2 | Geometry / topology (Shapely) | **Absolute** | `parser`, `graph` |
| 3 | Standards & rules (20 GEO/MFG rules) | High, deterministic | `validation` |
| 4 | Deterministic heuristics | Medium | `semantic` (diameter/pattern) |
| 5 | Semantic inference | Low, confidence-bounded | `semantic` |
| 6 | ML (GNN) / LLM | **Advisory only** | `ml`, `semantic.llm_annotator` |

Every node, edge, rule result, and annotation carries a `ProvenanceRecord`
(inference method, confidence, evidence) — `provenance`. Integrity is checked by
`omim.integrity` (`check_graph_integrity`, `check_ontology_consistency`,
`check_dataset_consistency`). Benchmarks live in `omim.benchmarks`, real-corpus
grounding in `omim.corpus`, and the optional GNN layer in `omim.ml` (degrades
gracefully when `torch`/`torch_geometric` are absent).

## Synthetic Dataset Generation

OMIM generates training data **from manufacturing standards, not random geometry**.
Dimensions come from real manufacturer catalogs (Blum 35mm hinge cup / 22.5mm setback,
Häfele Confirmat 7mm, the European 32mm Rasterbohrsystem, DIN 7 dowels), and the
deterministic validator acts as the gatekeeper:

```
Manufacturing Standards → Generator → DXF → Parser → MGG → Validator (gate)
                                                              ↓
                                          keep iff is_valid matches intent
                                                              ↓
                                       5-file canonical sample + provenance
```

Each sample is emitted as the canonical 5-file format (`geometry.dxf`, `mgg.json`,
`validation.json`, `labels.json`, `provenance.json`) with train/val/test splits and
a dataset manifest. Ground-truth labels come from the **generation spec**, never from
inference. Same seed → identical dataset.

## Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

## API

```bash
# Full analysis pipeline
curl -X POST http://localhost:8000/api/v1/analyze -F "file=@panel.dxf"

# Parse only
curl -X POST http://localhost:8000/api/v1/parse -F "file=@panel.dxf"

# Validate only
curl -X POST http://localhost:8000/api/v1/validate -F "file=@panel.dxf"
```

## Project Structure

```
src/omim/
├── parser/          # DXF → RawGeometry (ezdxf)
├── graph/           # MGG construction & serialization (NetworkX, Shapely)
├── validation/      # Deterministic rule engine (GEO-*, MFG-*)
├── semantic/        # Feature classification + LLM annotation
├── ontology/        # Feature/operation definitions (YAML)
├── provenance/      # Inference decision tracking
├── export/          # JSON, Cytoscape.js export
├── api/             # FastAPI REST endpoints
└── cli.py           # Command-line interface

frontend/            # React + Cytoscape.js visualization
data/
├── ontology/        # Feature & operation YAML definitions
├── rules/           # Manufacturing constraint thresholds
└── fixtures/        # Sample DXF files for testing
```

## Domain

- **Material:** MDF, plywood, melamine panels (16–25mm)
- **Operations:** CNC drilling, routing, pocketing, engraving
- **Features:** Shelf pin holes, dowel holes, hinge cups, Euro screws, cable grommets, hardware holes, grooves
- **Validation:** Edge distances, hole spacing, diameter ranges, panel bounds, pocket width, sharp corners, blind-feature depth

## Depth / 2.5D

DXF is geometry-only, so machining depth is **inferred, not read**. OMIM recovers
depth from two real sources, each tagged with `depth_source` for provenance:

- **`z_elevation`** — true 2.5D geometry (a feature drawn below the top face);
  depth is *measured* (highest trust).
- **`layer_name`** — a shop convention such as `POCKET_D6` / `POCKET_6MM`;
  depth is *inferred*.

Pure-2D features with no depth cue keep `depth_mm = None` (never guessed). This
feeds MFG-007 (blind-feature depth).

## Multi-panel nesting

`omim nest file.dxf` (or `POST /api/v1/nest`) understands a DXF that is a whole
**nest** — a stock sheet carrying many panels — not just a single panel. It
detects the sheet (explicit `SHEET`/`STOCK` layer or a containing contour),
identifies the panels, assigns each feature to its panel, and reports utilization,
overlapping panels, and panels outside the sheet. Optional `omim[nesting]` extra
(`rectpack`) adds an ideal-packing comparison; it degrades gracefully when absent.

## Data-driven rules

Validation thresholds live in `data/rules/*.yaml` and are **loaded by the engine**
(not hardcoded): edit a threshold or set `enabled: false` and the verdict changes.
`RuleEngine(rules_dir=...)` selects a ruleset; the packaged defaults reproduce the
documented behaviour.

## P&ID: the real-data path

The P&ID domain ingests real, human-annotated graphs (PID2Graph, CC BY-SA — see
`data/pid/README.md`). Because ground-truth symbol classes are human annotations
and OMIM predicts independently from ISA-5.1 tags, `omim.domains.pid.benchmark`
gives a **non-circular** capability score — unlike the synthetic panel grounding.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Parser | ezdxf |
| Graph | NetworkX, Shapely |
| Models | Pydantic |
| API | FastAPI, uvicorn |
| Frontend | React, Cytoscape.js |
| LLM (advisory) | Featherless AI (OpenAI-compatible) |

## License

Apache 2.0
