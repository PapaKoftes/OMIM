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

# Turn a friend's folder of panel DXFs into a labeled dataset + review queue
omim tune-ruleset ./delivery -o tuned.yaml     # 1. tune thresholds to the corpus
omim build-dataset ./delivery ./dataset        # 2. auto-detect layout, identify,
                                               #    auto-label every panel, emit dataset
# 3. open ./dataset/review_queue.jsonl, set each row's decision, re-import to finalize

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

## From a DXF delivery to a labeled dataset

Point OMIM at a folder of panel DXFs (from a friend, a shop, anywhere) and it
builds both an **identification ruleset** and a **large labeled dataset** — with a
human-in-the-loop review step so the labels are trustworthy, not just plausible.
The identification stack is layered into separate modules:

| Layer | Module | What it identifies |
|---|---|---|
| Feature | `omim.semantic.classifier` | holes, pockets, grooves, hinge cups… per node |
| Part | `omim.identify.parts` | each panel: DOOR / SIDE_PANEL / SHELF / BACK… |
| Assembly | `omim.identify.assembly` | which panels form one 3D construction (+ joins) |
| Project | `omim.identify.project` | the full tree: project → assemblies → panels |

The pipeline (`omim build-dataset`):
1. **auto-detects layout** — per-project folders, a flat pile, or multi-panel nest
   files (`omim.pipeline.detect`);
2. **auto-labels** every panel with per-label confidence (`omim.labeling.AutoLabeler`);
3. **routes low-confidence labels to a review queue** — an editable JSONL where you
   set `confirm` / `correct` / `reject`; corrections become gold ground truth
   (`omim.labeling.ReviewQueue`);
4. **writes** per-panel samples (`mgg.json` + `labels.json`), project trees, the
   review queue, and a manifest.

`omim tune-ruleset` first measures the corpus and emits thresholds tuned to *your*
parts (e.g. the shop's actual hole sizes and grid), keeping catalog defaults where
the corpus is too sparse — fully transparent about measured-vs-defaulted.

## P&ID: the real-data path

The P&ID domain ingests real, human-annotated graphs (PID2Graph, CC BY-SA — see
`data/pid/README.md`). Because ground-truth symbol classes are human annotations
and OMIM predicts independently from ISA-5.1 tags, `omim.domains.pid.benchmark`
gives a **non-circular** capability score — unlike the synthetic panel grounding.

## Domains beyond furniture

The core (parse → graph → features → validate → nest → label → dataset) is
domain-agnostic. Every fabrication domain OMIM can apply to — with an honest
status, vocabulary, researched datasets, and open-source tools to reuse — is
recorded in a queryable registry:

```bash
omim domains                            # all 13 domains + status + has-real-data
omim domains --key digital_fabrication  # full detail for one
```

Two are **production** (panel furniture, P&ID); the rest are **stub** (vocabulary
+ datasets scoped, no inference yet) or **planned**. The recommended next domain
is **tab-and-slot digital fabrication** — the joints live in the 2D geometry and
open CC data (WikiHouse/OpenDesk) exists to validate the assembly inference. See
`docs/10_IMPLEMENTATION/Domain_Expansion_Roadmap.md`.

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
