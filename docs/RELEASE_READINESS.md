# OMIM v1.0 Release Readiness

OMIM is research infrastructure (not a product). "v1.0" means the four vision
deliverables are credible, honest, and reproducible — not that the AI is perfect.
This is the checklist + the honest maturity map.

## The four deliverables (vision) and their state

| Pillar | State | Evidence |
|---|---|---|
| **Agnostic middleware** | ✅ done | `LayerProfile` (a shop's dialect → OMIM's own types); cabinet is one built-in profile, customer dialects load out-of-tree. `omim profiles`. |
| **Synthetic dataset infrastructure** | ✅ strong | Validator-gated, valid-by-construction, byte-reproducible; full provenance incl. first-class annotation records. |
| **Benchmark suite** | 🟡 partial | BENCH-001..004 + the P&ID real-data (non-circular) benchmark. Real-world track for panels runs out-of-tree against a held-out corpus (a validation fixture, never shipped data). |
| **Open research standard** | 🟡 partial | Schema-versioned (`spec_version`), Apache-2.0, this doc + STRATEGY.md + the domain registry. A public synthetic dataset/benchmark *release* is the remaining step. |

## What is grounded vs what is not (the honest line)

- **Grounded (catalog/standards-derived, production):** geometry, depth/2.5D,
  features (holes/pockets/hinge/dowel/engraving/chamfer/fillet), validation rules.
- **Not yet calibrated (experimental, review-gated):** part / assembly / project
  identification — hand-set confidences, validated only on synthetic geometry.
  `docs/STRATEGY.md` and the module docstrings carry this caveat; the domain
  registry's `maturity_note` surfaces it.

## Reproducibility contract

- Same DXF bytes → same MGG (deterministic ids; pinned timestamps in the dataset
  pipeline). `tests/test_reproducibility.py` enforces it.
- Same seed → identical synthetic dataset.
- A built dataset is byte-stable across runs (no wall-clock leakage).

## Schema versioning

- `omim.__version__` and `GraphMetadata.spec_version` track the MGG schema.
- Breaking schema changes bump `spec_version`; `serializer.load_mgg` validates
  structure and fails loudly on malformed/foreign documents.

## Clean-room / privacy guarantees

- `*.dxf` and `/secrets/` are git-ignored; no customer DXF, manifest, notes, or
  layer dialect is ever committed. Real corpora are used out-of-tree only.
- Only generic, format-level capabilities (e.g. P/V-decimal depth, the ENGRAVING
  class) and synthetic samples are committed — never a shop's conventions.

## The data gate (the one thing external data unlocks)

Everything downstream of features is gated on real labelled DXFs. The full loop is
built and tested with a simulated reviewer:

```
omim build-dataset <corpus> <out> --profile <shop.yaml>   # ingest any dialect
#   carpenter reviews <out>/review_sheet.csv (with panel thumbnails)
omim apply-review <out>                                    # answers -> gold labels
omim calibrate    <out>                                    # gold -> measured confidences
```

When a real packet runs through this, the experimental tier becomes measured and
this doc's 🟡 identification caveat can be dropped for that domain.

## Test + quality gates

- Full suite green (377+ tests), `ruff` clean. CI runs lint + tests + mypy.
- Honesty guards are tests: the domain registry test fails if a stub/planned
  domain claims a working module; the dataset-adapter test fails on a label that
  isn't a real OMIM class; the provenance test fails if an annotation drops to a
  thin record.

## Remaining for a tagged v1.0

1. Publish a **public synthetic dataset + benchmark** release with complete
   metadata (the "open standard" step).
2. Run **one real packet** through the data gate to calibrate one domain.
3. Promote a **second domain** (digital fabrication) to prove agnosticism.
4. Delivery hygiene: typed API responses, frontend build in CI, `pip install`
   smoke test.
