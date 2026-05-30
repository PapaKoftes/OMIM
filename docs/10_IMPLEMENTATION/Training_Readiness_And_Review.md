# Training Readiness, Correctness Checklists & Detached Review

Version: v0.1.0
Section: 10_IMPLEMENTATION

See also: [[10_IMPLEMENTATION/ML_Integration]], [[01_FOUNDATION/External_Baselines]], [[09_BENCHMARKS/Benchmark_Tasks]], [[01_FOUNDATION/Authority_Hierarchy]]

> Scope: what it takes to train a *legitimate* model for OMIM on the Leonardo
> (CINECA) HPC — and an honest assessment of whether that is even the right move
> yet. Grounded in measured dataset statistics, not assertions.

---

## Measured baseline reality (seed=1, 300 samples)

| Fact | Value | Implication |
|---|---|---|
| Distinct feature classes generated | **6 of 14** | Model can only learn 6; 8 ontology classes have zero training signal |
| Class balance | SHELF_PIN 42.8% … HINGE_CUP 7.3% | ~6:1 imbalance — needs weighting/resampling |
| Invalid-sample yield | ~21% actual vs 30% requested | ~17% of injections fail to produce an ERROR and are dropped |
| Separability | 6 classes ≈ separable by diameter alone | A GNN risks learning a lookup table the rule engine already encodes |
| Deterministic BENCH-001 | macro-F1 ≈ 0.75 (present classes), node acc ≈ 0.87 | The "model to beat" is already strong on synthetic data |

These numbers are the reason the review section below is skeptical of training *now*.

---

# CHECKLIST 1 — Correctness & Soundness ("is it real, not vibes?")

Each item states **how to be certain**, not just what to assert. ☐ = open, ✅ = verified this session.

## 1A. Geometry & parsing (Authority Level 1–2)
- ✅ DXF entities parsed faithfully (CIRCLE/ARC/LINE/LWPOLYLINE/POLYLINE/SPLINE) — *verify:* round-trip a DXF, compare entity counts + coordinates to ezdxf ground truth.
- ✅ Units normalised to mm ($INSUNITS honoured) — *verify:* parse an inch file, assert ×25.4.
- ✅ Shapely-derived area/perimeter/centroid are authoritative & deterministic — *verify:* recompute independently, assert equality.
- ☐ **SPLINE approximation error bounded** — *verify:* approximate a known arc/spline, assert max chordal deviation < tolerance (currently 50 segments, unverified error bound).
- ☐ **Coordinate precision / float determinism across OS** — *verify:* hash MGG JSON on Linux (Leonardo) vs Windows; assert identical (HPC is Linux; dev is Windows — this is untested cross-platform).

## 1B. Graph construction (MGG)
- ✅ Every node carries provenance; no orphans/dangling edges/self-loops — *verify:* `check_graph_integrity()` returns [].
- ✅ CONTAINS/ADJACENT_TO/SAME_ROW/SAME_COLUMN built from geometry, not inference — *verify:* unit tests on known layouts.
- ☐ **Edge-construction thresholds are justified, not arbitrary** — ADJACENT_TO uses a proximity threshold, SAME_ROW/COLUMN a 1 mm tolerance. *verify:* trace each constant to a cited source (32 mm system, tool dia) or mark as a tunable with a documented default. Several thresholds are currently "reasonable" but uncited.
- ☐ **Graph is connected enough for message passing** — *verify:* report mean node degree / fraction of isolated nodes; a GNN on a near-edgeless graph degenerates to an MLP.

## 1C. Validation rules (Authority Level 3) — the scientific backbone
- ✅ All 20 rules (GEO-001–008, MFG-001–012) implemented and unit-tested.
- ✅ Layer-2 gated on Layer-1 pass; determinism enforced (sorted IDs, tolerances).
- ✅ Every threshold traces to a source (Rule_Provenance.md) — Blum/Häfele/DIN/EN/shop convention.
- ☐ **Rules MFG-003 (tool-radius corner) and MFG-004 (pocket width) are never exercised** — the generator produces no pockets/grooves. *verify:* add milled-feature fixtures OR mark these rules "untested by synthetic corpus" in Rule_Provenance.
- ☐ **Confidence ceilings match the literature** — *verify:* spot-check that shop-convention 8 mm edge clearance, 22.5 mm hinge setback, 32 mm grid match current Blum/Hettich catalog revisions (catalogs change; cite revision/year).
- ☐ **A real, expert-reviewed DXF passes/fails as a human expert would** — the only true correctness test. *verify:* 5–10 real cabinet DXFs, expert adjudication vs OMIM output (currently zero real DXFs validated).

## 1D. Semantic classification (Authority Level 4–5)
- ✅ Deterministic-first, confidence-bounded, alternatives below 0.75, never mutates MGG.
- ✅ CONFIRMAT 7 mm diameter rule fixed (was layer-keyword-only).
- ☐ **Diameter tolerances don't collide** — *verify:* enumerate the diameter→class table and assert no overlapping ±tolerance bands (e.g. a 7.3 mm hole shouldn't be ambiguous between CONFIRMAT and a generic hole without an explicit alternative).
- ☐ **Classifier is honest about ambiguity on real data** — synthetic diameters are clean (±0.05–0.1); real DXFs vary. *verify:* inject Gaussian diameter noise (σ≈0.3 mm) and confirm confidence degrades and alternatives appear (not false certainty).

## 1E. Provenance & confidence (cross-cutting)
- ✅ DETERMINISTIC ⇒ confidence = 1.0; heuristic < 1.0; ML < 1.0 (Pydantic-enforced).
- ✅ Authority hierarchy structurally enforced (validation can't see semantics; ML additive only).
- ☐ **Confidence is calibrated, not just bounded** — *verify (post-training):* reliability diagram / ECE on a labelled set; a "0.75" should mean ~75% correct. Currently confidence is an epistemic ceiling, never calibrated against outcomes.

## 1F. Synthetic generator (the data factory)
- ✅ Standards-grounded dimensions; validator-gated; deterministic by seed; catalog-conformant.
- ☐ **Class coverage gap (CRITICAL)** — only 6/14 classes generated. *fix:* add generators for POCKET/GROOVE/DADO/RABBET/COUNTERSINK/COUNTERBORE/THROUGH_POCKET/INTERNAL_CUTOUT or formally descope them from v0.1 training.
- ☐ **Invalid-yield leak** — ~17% of injected violations don't fire. *verify:* assert injected rule_id actually appears in the validation report; raise yield to the requested ratio.
- ☐ **Distribution realism is asserted, not measured** — panel sizes/feature counts are catalog-derived priors, NOT fit to real data. *verify:* once a real corpus exists, KS-test synthetic vs real distributions.
- ☐ **No hidden generator→label shortcut** — labels must be derivable from geometry a model could see, not from generator-only state. *verify:* confirm `labels.json` positions/diameters equal what the parser re-extracts (currently true; keep a regression test).

## 1G. Benchmarks & metrics
- ✅ BENCH-001–004 implemented; pure-numpy metrics; deterministic; splitter disjoint.
- ☐ **Primary metric must be macro-F1 over *present* classes, reported with support** — full-14-class macro-F1 (0.32) is misleading. *fix:* make `macro_f1_present` the headline and always print per-class support.
- ☐ **A "skyline" and a "trivial" baseline** — report (a) the deterministic classifier (skyline the GNN must beat) and (b) majority-class / diameter-NN (floor). A learned model between these proves nothing.
- ☐ **Test set must be hard** — random synthetic split ≠ generalisation. *fix:* hold out by *generator regime* (unseen panel sizes, noised diameters, real DXFs) so test ≠ train distribution.

## 1H. Software integrity
- ✅ 152 tests pass, ruff clean, CI workflow present.
- ☐ **CI actually runs green on GitHub** — *verify:* check Actions tab after push (matrix 3.11/3.12); local pass ≠ CI pass.
- ☐ **Coverage measured** — *verify:* `pytest --cov`, target ≥80% on core modules; currently uncounted.
- ☐ **Type checking** — mypy is non-blocking; *verify:* run it and triage, don't let it rot.

---

# CHECKLIST 2 — Everything needed to train a proper model on Leonardo (CINECA)

## 2A. Data readiness (the real blocker)
- ☐ **Class coverage**: all target classes represented (fix 1F gap) OR scope explicitly to the 6 hole/profile classes.
- ☐ **Scale**: generate ≥ 50k–100k panels (synthetic is cheap) → ~500k+ labelled nodes. Verify generation is parallelisable and deterministic per shard (seed = base + shard_index).
- ☐ **Class-imbalance strategy**: inverse-frequency weights (GNNTrainer has this) AND/OR focal loss AND/OR resampling; decide and document.
- ☐ **Real-data holdout (NON-NEGOTIABLE for a credible model)**: ≥ a few hundred real DXFs (OpenBuilds/WikiHouse/OpenDesk/company) parsed + expert-or-rule-labelled, used as the **only** test set. Without this, training proves nothing transferable.
- ☐ **Noise augmentation**: diameter jitter, missing/renamed layers, rotation, duplicate entities, unit quirks — so the model learns robustness, not the generator's tells.
- ☐ **Frozen, versioned dataset**: `dataset_metadata.json` with seed, generator version, ontology/ruleset version, split hashes. Reproducible from seed. (Schema already exists — enforce it.)
- ☐ **Data integrity gate**: `check_dataset_consistency()` == [] before any training run.

## 2B. Model & task definition
- ☐ **Task that learning can actually win** (see review): not "classify a 5 mm hole" (a rule does that) but e.g. relational/ambiguous cases, missing-layer inference, anomaly detection on real noisy geometry.
- ☐ **Model spec frozen**: GraphSAGE feature-GNN (node classification) is implemented; confirm hidden dims, layers, dropout, aggregator are set and justified.
- ☐ **Node features audited** (16-dim vector): confirm each is finite, scaled, and leakage-free (no feature encodes the label). *verify:* train a logistic regression on the 16 features alone — if it already hits ~0.9, the GNN adds little and you've learned the features are the lookup.
- ☐ **Loss, optimizer, scheduler, early-stopping** specified (GNNTrainer has Adam + ReduceLROnPlateau + patience) — confirm metric for early stopping is macro-F1-present on val, not loss.
- ☐ **Baselines wired into the same eval**: deterministic skyline + trivial floor reported alongside every model run.

## 2C. Reproducibility & experiment tracking
- ☐ Global seeding: Python/NumPy/PyTorch/CUDA deterministic flags; `torch.use_deterministic_algorithms(True)` where feasible.
- ☐ Experiment tracking: TensorBoard (offline) or Weights & Biases in **offline mode** (compute nodes have no internet — sync from login node afterwards).
- ☐ Config-as-code: every run defined by a committed YAML/JSON (hparams, dataset version, seed); log the git SHA.
- ☐ Checkpointing: save best + last; resumable (Leonardo jobs are wall-clock limited — must checkpoint/restart).

## 2D. Leonardo / CINECA environment specifics
- ☐ **Allocation**: active project + GPU budget; know your `--account`, partition (`boost_usr_prod` for A100 64 GB, 4 GPU/node), and QOS/wall-clock limits.
- ☐ **No Docker on HPC** → build an **Apptainer/Singularity** image (or a conda/venv on `$WORK`) with torch + torch_geometric matching Leonardo's CUDA (A100 → CUDA 11.8/12.x; pick the PyG/cu wheels that match the loaded `module`).
- ☐ **Compute nodes have no internet** → pre-stage on the login node: dataset, container/env, pretrained weights, pip wheels. No `pip install` mid-job.
- ☐ **Filesystems**: code/env on `$WORK` (persistent, per-project); training data + checkpoints on `$SCRATCH`/`$CINECA_SCRATCH` (fast, **purged periodically** — copy results back to `$WORK`). `$HOME` is small.
- ☐ **SLURM batch script**: `#SBATCH` for `--nodes`, `--ntasks-per-node`, `--gres=gpu:4`, `--cpus-per-task`, `--time`, `--account`, `--partition`, `--mem`; `srun` launch; `module load` the right CUDA/Python.
- ☐ **Data → node-local/scratch staging** at job start (avoid hammering shared FS with 100k tiny files — pack samples into shards / WebDataset / a single HDF5 or `.pt` tensor file, NOT 100k loose dirs).
- ☐ **Multi-GPU only if it pays**: a panel-GNN is small; start single-A100. Use DDP (`torchrun`) only after profiling shows you're GPU-bound.
- ☐ **Dry run on a tiny allocation** (1 GPU, 10 min, 100 samples) before requesting real hours.

## 2E. Evaluation, governance, exit criteria
- ☐ **Held-out real-DXF test set** is the acceptance gate (not synthetic test).
- ☐ **The model must beat the deterministic skyline on a task the skyline can't trivially solve** — else ship the rules, not the model (Authority hierarchy: ML is Level 6, advisory).
- ☐ Calibration (ECE/reliability) reported; confidences feed the existing 0.30/0.60 thresholds.
- ☐ Inference path respects the hierarchy: GNN output is additive, never overrides geometry/validation (already enforced in `omim.ml` — keep it).
- ☐ Model card: training data version, intended use, limits, failure modes, that it's advisory.

---

# DETACHED REVIEW — is this the best idea & implementation?

*Stepping outside the project.*

## What is genuinely strong (keep, this is the moat)
1. **The deterministic core is excellent and honest.** Parser → MGG → 20 standards-cited rules → provenance, with a structurally enforced authority hierarchy. This is real engineering, well-tested, and unusually disciplined about not overclaiming.
2. **Standards-grounded, validator-gated synthetic generation** is the right idea and is correctly implemented — "valid by construction, verified by the gatekeeper." The executable grounding claim (generated geometry conforms to Blum/Hettich *and* passes all rules) is a genuinely good scientific artifact.
3. **Provenance everywhere** is the differentiator vs Analysis Situs / generic CAD-ML datasets. That is publishable framing.

## The hard truth (why I would NOT book Leonardo hours yet)
**Training a GNN on this data right now would largely teach a model to imitate a diameter lookup table — and prove nothing about the real world.** The evidence:
- Only **6 classes**, **near-separable by diameter alone**, with the deterministic classifier already at ~0.75–0.87. A GNN that scores 0.9 on synthetic test has likely just memorised the generator's clean diameter bands.
- **Labels and inputs share an origin.** The generator plants exact catalog diameters; the labels are those same diameters. A model "learning" this is circular — it will look great on synthetic test and likely fall apart on real DXFs (noisy diameters, missing layers, vendor quirks).
- **No real data exists in the loop.** Tier-2 (real DXFs) is the one thing that would make a learned model meaningful, and it's the documented gap.

In short: the *engineering* is mature; the *scientific premise of training now* is not. Spending A100 hours here optimises a number that doesn't generalise. That is the opposite of "industry-standard, already applicable."

## What would make it genuinely mature & applicable
**Refinements, in priority order:**
1. **Get real DXFs (highest leverage).** A few hundred real cabinet panels, parsed and rule/expert-labelled, as the *only* test set. This converts every benchmark from "synthetic self-consistency" to "real generalisation." Until this exists, the rules ARE the product and the GNN is premature.
2. **Define a task where learning beats rules.** The deterministic classifier already solves clean classification. A model earns its place only on: ambiguous/missing-layer DXFs, vendor-variant geometry, relational inference (is this hole part of a hinge pattern given neighbours?), or anomaly detection on real noise. Pick one and benchmark the GNN *against the rule skyline* on it.
3. **Close the generator gaps** before scaling data: 6→14 class coverage (or explicit descope), fix the ~17% invalid-yield leak, add noise/perturbation augmentation so the model can't cheat on clean tells.
4. **Calibrate, don't just bound, confidence.** Reliability diagrams; make confidence mean something downstream.
5. **Right-size the model.** For 2D panels with strong priors, a GNN may be overkill; a small classifier on the 16 features + the rule engine could match it. Prove the GNN is necessary (the logistic-regression-on-features test in 2B) before reaching for graph deep learning and HPC.
6. **Reframe the contribution honestly.** OMIM's strongest paper/product is *"a provenance-tracked, standards-grounded validation + dataset-generation framework for panel CNC, with a deterministic baseline."* The GNN is a future chapter, not the headline — and saying so is a strength, not a weakness.

## Bottom line
- **Is it the best idea?** The *framework* idea (deterministic validation + provenance + standards-grounded synthetic data) is excellent and largely best-in-class for this niche. The *"train a GNN on Leonardo next"* idea is, right now, the weakest link — it would produce an impressive-looking but hollow result.
- **Best implementation?** The deterministic stack is close to industry-grade (needs CI-green confirmation, coverage, real-DXF validation, the milled-feature gap). The ML stack is well-architected but should not be *trained for real* until real data and a learning-worthy task exist.
- **Recommended next move:** spend the next effort on **real DXF acquisition + a learning-worthy benchmark task + closing generator gaps** — *then* Leonardo. That sequence turns a strong demo into a defensible, applicable system.
