# Dropping in a real labelled dataset

This is the one input OMIM cannot generate for itself, and the thing that turns
the identification claims from *plausible* into *measured*. When your friend's
real, labelled panel DXFs are available, here is exactly how they plug in — no
code changes required, everything below is already built and waiting.

## What "good" looks like

- Real production panel DXFs (any shop / CAM dialect — the profile system handles
  the layer names).
- Enough to matter: ~50 panels is a useful seed; a few hundred makes the
  capability test and calibration meaningful.
- Labels from a **human** (the carpenter/maker), not from OMIM's own rules — that
  independence is the whole point.

## The loop (all of this exists today)

```bash
# 1. Ingest the real DXFs. If the shop's layer dialect isn't the cabinet default,
#    write a one-file profile (out-of-tree) mapping their prefixes to OMIM types.
omim build-dataset <real_dxf_dir> secrets/real_ds --profile secrets/their_profile.yaml

# 2. The maker reviews secrets/real_ds/review_sheet.csv in Excel/Sheets, looking
#    at the panel pictures (thumbnails/), and fills the two answer columns.
#    (Guide: docs/FOR_THE_REVIEWER.md)

# 3. Fold their answers back in -> their judgements become GOLD ground truth.
omim apply-review secrets/real_ds

# 4. Calibrate: gold labels -> measured confidences (no longer hand-set guesses).
omim calibrate secrets/real_ds
```

Everything lands in git-ignored `secrets/` — real customer DXFs never enter the
public repo (same clean-room rule as before).

## Activating the capability test (the honest status line)

Once `secrets/real_ds/samples/*/labels.json` carry human-gold labels:

```bash
set OMIM_REAL_CORPUS=secrets/real_ds/samples   # PowerShell: $env:OMIM_REAL_CORPUS=...
pytest tests/test_capability_on_real_data.py -v
```

That test (skipped until now) measures OMIM's **layer-blind** feature inference
against the human labels. It is the only test in the repo that checks external
validity rather than internal consistency. When it goes green at a real accuracy
bar, the "semantic inference" claim is earned on real data — and the 🟡 caveats in
STRATEGY.md / RELEASE_READINESS.md can be dropped for that domain.

## What it unlocks, in order

1. **Calibrated confidences** (immediately, step 4 above).
2. **Proven layer-blind inference** (the capability test goes green).
3. **A real, independent benchmark** as the corpus grows across shops — the
   "open standard" pillar, earned bottom-up through use.

Nothing here waits on more engineering from OMIM's side. The platform, the review
loop, the calibration gate, and the capability test are all in place. It waits
only on the real data.
