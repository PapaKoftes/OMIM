# External Datasets

OMIM does **not** bundle third-party datasets (they are large and carry their own
licenses). These notes record what to download and how OMIM uses each. The
adapters in `omim.datasets` make a downloaded dataset usable by mapping its native
labels onto OMIM's vocabulary — they do not require the data to be present to
import.

As of 2026, **no public dataset matches OMIM's exact niche** (2D DXF furniture
panels with machining-feature + part-type labels). The two below are the most
useful *adjacent* assets and are both permissively licensed.

## ArchCAD-400K  — `omim.datasets.archcad`

- **What:** ~400K (40K released subset) annotated vector-CAD architectural
  drawings; primitives tagged with a semantic class + instance id. Produced by
  layer-name auto-labelling **+ expert correction** — the same method OMIM uses.
- **License:** **CC0 1.0** (public domain) — fully redistributable.
- **Get it:** https://huggingface.co/datasets/jackluoluo/ArchCAD ·
  paper https://arxiv.org/abs/2503.22346 · repo https://github.com/ArchiAI-LAB/ArchCAD
- **OMIM use:** methodology precedent (vector primitives + auto-label-then-review);
  a CC0 corpus to pretrain a vector/graph backbone; has a `holes` class. It is
  **architectural, not furniture** — most classes have no OMIM analogue by design.
- **Wire it up:**
  ```python
  from omim.datasets import archcad
  samples = archcad.load_jsonl("data/datasets/archcad/export.jsonl")
  manifest = archcad.build_manifest(samples)   # label coverage + classes seen
  ```

## MFCAD / MFCAD++  — `omim.datasets.mfcad`

- **What:** ~59k synthetic 3D B-Rep models with per-face machining-feature labels
  (holes, pockets, slots, chamfers, steps). The standard MFR benchmark.
- **License:** **MIT** (GitLab mirror).
- **Get it:** https://gitlab.com/qub_femg/machine-learning/mfcad2-dataset ·
  orig https://pure.qub.ac.uk/en/datasets/mfcad-dataset
- **OMIM use:** OMIM is 2D DXF and MFCAD++ is 3D B-Rep, so the **geometry is not
  ingestible**. The reusable asset is the **label taxonomy** — a published,
  peer-reviewed machining-feature vocabulary OMIM aligns its feature classes to,
  plus a cross-dataset label reference. Chamfer/step/round have no 2D analogue.
- **Wire it up:**
  ```python
  from omim.datasets import mfcad
  samples = mfcad.load_json("data/datasets/mfcad/labels.json")
  manifest = mfcad.build_manifest(samples)
  ```

Place downloaded data under `data/datasets/<name>/` (gitignored). Neither is
committed to the repo.
