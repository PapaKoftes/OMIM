# P&ID Data — Real Labeled Corpus (PID2Graph)

The P&ID domain is OMIM's **real-data** path. Unlike the panel domain (which has
no public labeled dataset and must rely on validator-gated synthetic data), a
real, human-annotated P&ID corpus exists and can be plugged in directly:

- **PID2Graph** — first public real-world P&ID dataset annotated with the full
  graph (symbols as nodes, lines as edges).
  - Paper: https://arxiv.org/abs/2411.13929
  - Data: https://zenodo.org/records/14803338  (~9.3 GB)
  - **License: CC BY-SA 4.0** — redistributable *with attribution + ShareAlike*.
    Keep any downloaded/derived data under this directory (it is **not** vendored
    into the repo) and preserve the CC BY-SA license. ShareAlike does not affect
    OMIM's Apache-2.0 *code*, only redistributed *data derivatives*.

## Why this matters (de-circularization)

The panel grounding claim is circular: panels are generated from a catalog and
then validated against the same catalog. P&ID breaks that loop — the ground-truth
symbol classes are **human annotations** carried on the graphml nodes, while
OMIM's prediction is derived **independently** from the ISA-5.1 tag string. Labels
and predictions come from different sources, so a good benchmark score is real
evidence of capability.

## How to use it

1. Download the PID2Graph release from the Zenodo link above (not bundled — the
   build environment has no network access, and the data is large + ShareAlike).
2. Place the `.graphml` files under `data/pid/corpus/` (gitignored).
3. Ingest a graph into the core MGG:

   ```python
   from omim.domains.pid.ingest import ingest_graphml
   result = ingest_graphml("data/pid/corpus/plant_001.graphml")
   print(result.component_count, result.connection_count)
   ```

4. Run the real-data symbol-classification benchmark:

   ```python
   from omim.domains.pid.benchmark import evaluate_graphml
   res = evaluate_graphml("data/pid/corpus/plant_001.graphml")
   print(res.macro_f1_present, res.accuracy, res.passed)
   ```

   If the source uses different node-attribute names for the tag / symbol class,
   pass a `FieldMap` (see `omim.domains.pid.ingest.FieldMap`).

## What ships here

- **`pid_rules.yaml`** — ISA-5.1 deterministic rule definitions for the P&ID
  validation rules (tag grammar, connectivity, control-loop completeness).
- No corpus is bundled. `data/pid/corpus/` is where you place real graphml.
