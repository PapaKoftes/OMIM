# Real DXF Corpus Grounding

This directory holds **grounding profiles**: statistical distributions of real
manufacturing dimensions that re-ground OMIM's synthetic generator in reality
rather than guesses. A profile is a JSON file describing hole-diameter clusters,
panel dimensions, edge setbacks, pairwise spacings, and per-panel hole counts,
all traceable to manufacturer catalogs and standards.

## What ships here

- **`catalog_reference_profile.json`** — the shipped **Tier 1** profile. It is
  *catalog-derived*: every number is seeded directly from manufacturer catalog
  ground truth (Blum, Hettich, Häfele, System 32) and EN/DIN standards. No real
  corpus has been ingested. This profile doubles as the **conformance
  reference** that any ingested corpus is validated against.

Regenerate it at any time:

```python
from omim.corpus.reference_profile import write_reference_profile
write_reference_profile()  # rewrites data/grounding/catalog_reference_profile.json
```

## Trust hierarchy

| Tier | Source | Trust | Status |
|------|--------|-------|--------|
| **Tier 1** | Catalog-derived (manufacturer catalogs + EN/DIN standards) | Authoritative spec | **Shipped** (`catalog_reference_profile.json`) |
| **Tier 2** | Empirical profile from an ingested real corpus | High (real geometry, validated vs. Tier 1) | Pending a real corpus |
| **Tier 3** | Community / unvetted corpora (OpenBuilds, GrabCAD, …) | Low — license + annotation review required | Reference only |

The shipped profile is **Tier 1**. It is replaced — not deleted — by a Tier 2
profile once a real corpus is ingested. Tier 1 always remains the ground truth
the validator checks against.

## Pointing OMIM at a real corpus

Real internet downloads are **not** available in the build environment, so no
corpus is bundled. To ground OMIM on real files:

1. **Collect DXFs.** Drop real `.dxf` files into a folder, e.g. `data/grounding/corpus/`.
   Good sources (verify license per file — see
   `docs/06_REAL_WORLD_GROUNDING/Real_DXF_Corpus_Sources.md`):
   - **OpenBuilds** (openbuilds.com) — CNC router / panel projects, mostly CC BY.
   - **WikiHouse** (wikihouse.cc) — open-source CNC-cut plywood building parts.
   - **OpenDesk** (opendesk.cc) — open-source CNC furniture (CC BY-SA).
   - **FreeCAD** sample/exported DXFs — clean, valid happy-path fixtures.
   - **Company files** — your own production cabinet DXFs (highest relevance).

   Files may be nested in sub-directories; ingestion walks recursively.

2. **Ingest + extract a Tier 2 profile:**

   ```python
   from omim.corpus.ingest import CorpusIngestor
   from omim.corpus.distribution_extractor import extract_distributions
   import json, pathlib

   stats = CorpusIngestor().ingest_directory("data/grounding/corpus")
   profile = extract_distributions(stats)
   pathlib.Path("data/grounding/corpus_profile.json").write_text(
       json.dumps(profile, indent=2)
   )
   ```

   Parse failures are logged and skipped — a few bad files never abort a run.
   `stats.summary()` reports how many files parsed vs. failed.

3. **Validate the corpus against the catalog ground truth:**

   ```python
   from omim.corpus.validator import validate_against_catalog
   report = validate_against_catalog(stats)
   print("Conformant:", report.overall_conformant)
   for check in report.checks:
       print(check.message)
   ```

   This answers: *"Does this corpus conform to Blum / Hettich / Häfele /
   System 32 / DIN specs?"* It flags clusters that drift outside catalog
   tolerance — e.g. a corpus whose hinge-cup cluster centers at 34 mm instead
   of the 35 mm Blum spec.

4. **Feed the profile into the generator.** A profile is loadable by the
   synthetic generator without editing the generator's code:

   ```python
   from omim.corpus.reference_profile import load_grounding_profile
   profile = load_grounding_profile("data/grounding/corpus_profile.json")
   # profile["panel_thickness"]["values"/"weights"], profile["diameter"]["clusters"],
   # profile["hole_count"]["by_panel_type"], ... mirror the constants in
   # omim.synthetic.distributions, so they can re-seed the sampler directly.
   ```

## Profile schema (summary)

Both Tier 1 and Tier 2 profiles share the same shape:

- `diameter.clusters` — per known bore size (5/7/8/10/15/35 mm): count,
  frequency, measured mean/stdev, deviation from catalog nominal, feature class.
  An `unclustered` bucket holds holes outside every catalog band (e.g. generic
  through-holes) so they do not pollute the catalog clusters.
- `panel_width` / `panel_height` / `panel_thickness` — `values` + `weights`
  lists (the same shape `omim.synthetic.distributions` uses) plus summary stats.
- `edge_setback` / `pairwise_spacing` — stats + histograms (the latter recovers
  the 32 mm System-32 grid pitch).
- `hole_count` — Poisson lambda + per-panel-type ranges (catalog profile uses
  the feature-count table from `Panel_Dimension_Standards.md`).
