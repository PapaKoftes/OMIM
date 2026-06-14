# OMIM Strategy & Honest State

This document states, plainly, what OMIM is grounded in, what it can prove today,
and the one gap that everything hinges on. It is the source of truth that the
module docstrings point to.

## The thesis (and why it's right)

OMIM generates and validates manufacturing geometry **from real manufacturing
standards, not from random CAD**. The synthetic pipeline is, in code:

```
manufacturing standard (Blum / Hettich / Häfele / 32mm / DIN / EN)
  → constraint grammar
  → feature generator
  → deterministic validator   ← THE GATEKEEPER
  → keep ONLY if validator outcome matches intent, else discard
  → MGG → labelled sample
```

Result: **every kept sample is valid by construction.** This is enforced (see
`omim/synthetic/generator.py`) and tested (`tests/test_grounding_claim.py`,
`tests/test_reproducibility.py`). The 2026 DFM-dataset research (e.g. BenDFM)
independently converged on this same validator-gated approach — it is the
defensible core.

## What is catalog-grounded vs what is not (the key distinction)

| Layer | Grounded in | Trust |
|---|---|---|
| **Geometry** (parse, depth, nesting) | Shapely + DXF facts | high |
| **Features** (hole/pocket/hinge/dowel…) | real catalogs (`catalog_ground_truth.py`, verified vs live 2026 sources) | high |
| **Validation** (20 GEO/MFG rules) | catalog + standards, data-driven YAML | high |
| **Part type** (DOOR/SIDE/SHELF…) | **hand-set heuristics — NOT catalog-derived** | low, uncalibrated |
| **Assembly / project** (which panels form one cabinet) | **hand-set heuristics — NOT catalog-derived** | lowest, uncalibrated |

The catalogs are excellent labels for *features and validation*. They are **not**
labels for *identification* — no catalog says "this panel is a door" or "these
five panels are one carcass". Those are heuristics whose confidence numbers are
plausible guesses, validated only on synthetic geometry.

## The single best baseline (how we know the data is good)

> Can OMIM reproduce cabinet geometry that conforms to Blum/Hettich/32mm
> specifications and passes all deterministic validation rules?

**Yes — proven** (`test_grounding_claim.py`). That makes the *feature/validation*
data grounded in manufacturing reality rather than random shapes.

The honest second half:

> Does OMIM's *identification* (part type, assembly) agree with a human on a
> real drawing?

**Unknown.** This is the gap. The only truly independent (non-circular) check in
the project today is the **P&ID benchmark**, where labels come from humans, not
from OMIM's own rules — which is exactly why P&ID is the most credible domain.

## The identification gap (what closes it)

Everything downstream of features is gated on **real labelled DXF data**:
- a small expert-labelled real cabinet corpus (even ~20–50 panels) would let us
  calibrate the part/assembly confidences (isotonic calibrator already exists,
  `omim/semantic/calibration.py`) and replace guesses with measured accuracy;
- a real corpus also breaks the residual circularity (validator generates labels
  *and* checks them) that the catalogs structurally cannot break.

Until then: **part/assembly outputs are advisory and routed through the human
review queue** (`omim/labeling/review.py`). The module docstrings carry this
caveat so it cannot get lost.

## Positioning

The defensible asset is not the rule engine — it is **the open, validator-gated,
provenance-tracked labelled dataset/benchmark for sheet-and-panel fabrication**.
That is the thing nobody else has built openly, and the thing even
drawing-reading VLMs will need for training and evaluation.

## External baselines worth citing (not ingestible, conceptual references)

- **Analysis Situs** — gold-standard CAD feature/graph reference (B-rep; concept,
  not 2D-DXF-ingestible).
- **MFCAD++ / AAGNet** — machining-feature taxonomy + graph-MFR method (3D;
  taxonomy reusable, wired via `omim.datasets.mfcad`).
- **ArchCAD-400K** — vector-CAD auto-label-then-review precedent (CC0; wired via
  `omim.datasets.archcad`).
- **PID2Graph** — the one real labelled corpus for an OMIM domain (P&ID).

## The end-to-end plan, anchored to the vision (not to "ship a product")

OMIM is research infrastructure, NOT a product (see Vision_and_Scope.md). Its four
named deliverables are: agnostic **middleware**, **synthetic dataset
infrastructure**, a **benchmark suite**, and an **open research standard**. The
finish line is a credible v1.0 of *those*, not a customer deployment. A real shop
corpus is a **validation/test fixture used out-of-tree**, never a shipped dataset
and never a source of generalized conventions (we proved naive tuning overfits one
shop and corrupts the catalog — see "conventions are per-shop" below).

What "conventions are per-shop" taught us: there is no single manufacturing
convention to generalize. Each shop has its own layer dialect, decimal notation,
and feature set. So OMIM must *be the translation layer*, not *be the convention*.
The cabinet/Blum/32mm catalog is **one built-in profile, not "the truth."**

Plan (critical path A -> benchmark -> standard; B/F raise the floor in parallel):

- **A. Middleware = first-class profiles (keystone).** Replace the hard-coded
  `DEFAULT_LAYER_MAP` + ad-hoc `ParserConfig` override with a real `LayerProfile`:
  a named profile maps a shop's layer dialect onto OMIM's OWN type vocabulary
  (cut/drill/pocket/border/engrave). `cabinet` ships in-repo as one default
  adapter; customer profiles load from a path and live out-of-tree. This makes the
  code structurally *be* the agnostic middleware the name claims.
- **B. Dataset + provenance infrastructure.** Finish first-class annotation
  provenance + the 2D-decidable classifier coverage so every synthetic sample is
  reproducible and fully traceable.
- **C. Benchmark suite as a first-class deliverable.** Standardized eval tasks
  others can measure against; add a **real-world validation track** that runs a
  profile against a held-out real corpus OUT OF TREE (the 631->50 UNKNOWN result
  is that track's first datapoint). This is how OMIM becomes a *standard*, not a
  tool.
- **D. Calibrate on real labels (the data gate).** One real packet through
  build-dataset -> carpenter review (visual) -> apply-review -> calibrate turns the
  part/assembly confidences from guessed into measured. Reframed honestly: this
  validates the middleware + feeds the benchmark's real track; it is not a service
  for a customer.
- **E. Second domain (prove agnosticism).** Promote `digital_fabrication`
  (tab-and-slot; joints in geometry + open CC data) — same core, different
  profile, structurally different domain. One domain is an anecdote; two is a
  middleware.
- **F. Open-standard hygiene.** Schema versioning, a public *synthetic* dataset +
  benchmark release, a contribution/review path.

Explicitly NOT doing: chasing ML accuracy before D; building the 11 stub domains;
generalizing any shop's conventions into core (the profile system in A is what
makes resisting that structural); positioning OMIM as a product.
