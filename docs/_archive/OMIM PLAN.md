```text
OMIM / Synthetic Manufacturing AI Plan
Cheap + Realistic + HPC-Optimized

CORE GOAL
Build:
- research-grade manufacturing dataset infrastructure
- semantic manufacturing understanding
- manufacturability reasoning system

NOT:
- full CAM replacement
- autonomous machining AI
- universal G-code generator

==================================================
PHASE 0 — PREP (BEFORE HACKATHON)
==================================================

SETUP
- Git repo
- Docker/dev env
- Claude Code workflows
- schema drafts
- ontology draft
- sample DXFs
- benchmark examples

CORE STACK
- ezdxf
- shapely
- networkx
- CadQuery
- PyTorch Geometric
- FastAPI
- React minimal frontend

OPEN SOURCE RESOURCES
Use existing:
- FreeCAD
- OpenCascade
- OpenCAMLib
- LinuxCNC
- CAMotics
- bCNC
- ncviewer
- OpenSCAD

USE PREEXISTING DATASETS
Search/use:
- DeepCAD
- ABC CAD Dataset
- Fusion360 Gallery Dataset
- Autodesk CAM samples
- GrabCAD public models
- Free machining DXFs
- LinuxCNC sample G-code
- Open manufacturing benchmark datasets

==================================================
PHASE 1 — DETERMINISTIC CORE
==================================================

INPUT
DXF / simple CAD

BUILD
- geometry parser
- normalization pipeline
- feature extraction
- graph builder

OUTPUT
Manufacturing Geometry Graph (MGG)

NODE TYPES
- geometry
- feature
- operation
- constraint
- semantic object

DO NOT USE ML HERE.

==================================================
PHASE 2 — VALIDATION ENGINE
==================================================

BUILD RULE ENGINE
Examples:
- minimum edge distance
- tool accessibility
- pocket width validity
- spacing rules
- manufacturability checks

RULES MUST BE:
- deterministic
- explainable
- versioned
- externally stored

OUTPUT
Validation reports + provenance

==================================================
PHASE 3 — SEMANTIC LAYER
==================================================

INFER:
- shelf pin patterns
- hinge holes
- grooves
- pockets
- drilling groups
- panel intent

METHOD
- deterministic heuristics first
- ML only assists ranking/confidence

OUTPUT
Semantic manufacturing graph

==================================================
PHASE 4 — SYNTHETIC DATASET GENERATION
==================================================

PROCEDURAL GENERATION
Generate:
- valid panels
- invalid panels
- tooling conflicts
- spacing failures
- semantic variations
- operation variations

GENERATE:
- DXFs
- graphs
- labels
- validation metadata
- provenance
- reasoning traces

IMPORTANT
Generate realistic manufacturing distributions.
NOT random nonsense geometry.

==================================================
PHASE 5 — HPC USAGE
==================================================

USE SUPERCOMPUTER FOR:
- mass procedural generation
- graph generation
- validation sweeps
- embeddings
- benchmark creation
- synthetic permutations
- GNN training

DO NOT WASTE HPC ON:
- tiny inference
- API wrappers
- chatbot demos

TARGET
100k–1M synthetic manufacturing samples

==================================================
PHASE 6 — ML
==================================================

CHEAPEST PATH

OPTION A (BEST)
Graph ML:
- GraphSAGE
- GAT
- node embeddings
- anomaly detection

OPTION B
LoRA fine-tuning:
- Qwen
- Llama
- Mistral

TRAIN FOR:
- manufacturability reasoning
- feature classification
- operation inference
- anomaly detection

NOT:
- AGI
- autonomous machining

==================================================
PHASE 7 — CLAUDE CODE USAGE
==================================================

USE CLAUDE FOR:
- orchestration
- codegen
- schema generation
- synthetic explanations
- dataset formatting
- instruction-tuning pairs
- pipeline automation

DO NOT USE CLAUDE AS:
- manufacturing truth source

==================================================
FINAL DELIVERABLE
==================================================

DEMO FLOW

upload DXF
    ↓
parse geometry
    ↓
generate MGG
    ↓
validate manufacturability
    ↓
infer semantics
    ↓
export structured dataset sample

FINAL OUTPUTS
- synthetic manufacturing dataset
- ontology
- validation engine
- semantic graph infrastructure
- benchmark suite
- baseline ML model

THE REAL VALUE
- manufacturing ontology
- graph representation
- validation infrastructure
- synthetic dataset pipeline
- benchmark corpus

NOT the demo model itself.
```