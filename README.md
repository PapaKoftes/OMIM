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

# Start API server
omim serve

# Run tests
pytest
```

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
- **Features:** Shelf pin holes, dowel holes, hinge cups, Euro screws, cable grommets
- **Validation:** Edge distances, hole spacing, diameter ranges, panel bounds

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
