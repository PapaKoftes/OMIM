"""Adapter for MFCAD / MFCAD++ — machining-feature recognition benchmark.

MFCAD++ (MIT) is the de-facto MFR benchmark: ~59k synthetic 3D B-Rep models with
per-FACE machining-feature labels (holes, pockets, slots, chamfers, steps...),
used by Hierarchical CADNet / AAGNet.

  Repo:  https://gitlab.com/qub_femg/machine-learning/mfcad2-dataset  (MIT)
  Orig:  https://pure.qub.ac.uk/en/datasets/mfcad-dataset

NOT bundled (large). Critically, OMIM is a 2D-DXF system and MFCAD++ is 3D B-Rep,
so OMIM CANNOT ingest its geometry. What IS reusable — and what this adapter
exposes — is the **label taxonomy**: MFCAD++'s feature classes map cleanly onto
OMIM's feature vocabulary, giving OMIM a published, peer-reviewed label schema to
align to and a cross-dataset evaluation reference. The converter maps face-label
lists (e.g. from a per-model labels file) into OMIM classes; it does not pretend
to build geometry.
"""

from __future__ import annotations

import json
from pathlib import Path

from omim.datasets.models import DatasetManifest, DatasetSample

#: MFCAD++ machining-feature class -> OMIM feature vocabulary. Holes/pockets/slots
#: map directly; 3D-only features that have no 2D-DXF analogue (chamfer/step/
#: blind variants) map to the closest OMIM class or are left unmapped honestly.
MFCAD_TO_OMIM: dict[str, str] = {
    # Holes
    "through_hole": "THROUGH_HOLE",
    "blind_hole": "THROUGH_HOLE",          # 2D can't see blind vs through (honest)
    "triangular_through_hole": "THROUGH_HOLE",
    "rectangular_through_hole": "INTERNAL_CUTOUT",
    "6sides_passage": "INTERNAL_CUTOUT",
    # Pockets
    "rectangular_pocket": "POCKET",
    "triangular_pocket": "POCKET",
    "circular_end_pocket": "POCKET",
    "rectangular_blind_slot": "GROOVE",
    "triangular_blind_step": "POCKET",
    # Slots / grooves
    "rectangular_through_slot": "GROOVE",
    "triangular_through_slot": "GROOVE",
    "circular_through_slot": "GROOVE",
    "v_circular_end_blind_slot": "GROOVE",
    "h_circular_end_blind_slot": "GROOVE",
    # Chamfers / rounds / steps — no clean 2D-DXF analogue (left unmapped on purpose)
}


def map_label(mfcad_label: str) -> str | None:
    """Map an MFCAD++ face-feature class to an OMIM class, or None."""
    return MFCAD_TO_OMIM.get((mfcad_label or "").strip().lower())


def convert_sample(record: dict, sample_id: str | None = None) -> DatasetSample:
    """Convert one MFCAD++ model record into a DatasetSample of OMIM labels.

    Expected (tolerant) shape: ``{"id": str, "faces": [{"id"/"face", "label"/
    "feature"/"class"}, ...]}`` — a per-face label list. We map each face label
    to OMIM; we do NOT construct geometry (3D B-Rep is out of OMIM's 2D scope).
    """
    sid = sample_id or str(record.get("id") or record.get("name") or "mfcad-sample")
    faces = record.get("faces") or record.get("labels") or []
    mapped: dict[str, str] = {}
    unmapped: dict[str, str] = {}
    for i, fc in enumerate(faces):
        if isinstance(fc, dict):
            fid = str(fc.get("id") or fc.get("face") or i)
            label = fc.get("label") or fc.get("feature") or fc.get("class") or ""
        else:  # a bare label string/int in a list
            fid = str(i)
            label = str(fc)
        omim = map_label(str(label))
        if omim is not None:
            mapped[fid] = omim
        elif label:
            unmapped[fid] = str(label)
    return DatasetSample(
        sample_id=sid,
        source_dataset="MFCAD++",
        element_labels=mapped,
        unmapped_labels=unmapped,
        element_count=len(faces),
        mapped_count=len(mapped),
        provenance={
            "inference_method": "synthetic",  # MFCAD++ labels are procedurally generated
            "pipeline_stage": "external_dataset_import",
            "module": "omim.datasets.mfcad",
            "license": "MIT",
        },
    )


def load_json(path: str | Path) -> list[DatasetSample]:
    """Load MFCAD++ label records from a JSON file (a list of model records)."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data if isinstance(data, list) else data.get("models", [])
    return [convert_sample(r) for r in records if isinstance(r, dict)]


def build_manifest(samples: list[DatasetSample]) -> DatasetManifest:
    total = sum(s.element_count for s in samples)
    mapped = sum(s.mapped_count for s in samples)
    omim_classes = sorted({c for s in samples for c in s.element_labels.values()})
    unmapped = sorted({lab for s in samples for lab in s.unmapped_labels.values()})
    return DatasetManifest(
        dataset="MFCAD++",
        license="MIT",
        redistributable=True,
        samples=len(samples),
        total_elements=total,
        mapped_elements=mapped,
        label_coverage=round(mapped / total, 4) if total else 0.0,
        omim_classes_seen=omim_classes,
        unmapped_source_labels=unmapped,
        notes=[
            "3D B-Rep, synthetic — OMIM (2D DXF) cannot ingest the geometry.",
            "Reusable as a published machining-feature TAXONOMY + cross-dataset "
            "label reference; chamfer/step/round have no 2D-DXF analogue (unmapped).",
        ],
    )
