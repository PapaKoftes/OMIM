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

## Highest-leverage next steps (in order)

1. **Acquire one real cabinet DXF** — turns identification from plausible into
   measured; nothing else substitutes.
2. **Promote `digital_fabrication`** (tab-and-slot) to a working domain — joints
   live in the 2D geometry and open CC data (WikiHouse/OpenDesk) exists to
   validate the assembly inference for real.
3. Calibrate part/assembly confidences once (1) or (2) provides labels.
