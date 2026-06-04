"""Adapter for ArchCAD-400K — vector-CAD panoptic symbol dataset.

ArchCAD-400K (CC0 1.0, public domain) annotates architectural CAD drawings as
vector primitives each tagged with a semantic class + instance id — produced by
*layer-name auto-labelling + expert correction*, which is exactly OMIM's own
labelling philosophy. It is the closest published precedent for OMIM's approach
and a usable source for pretraining a vector/graph backbone.

  Paper:  https://arxiv.org/abs/2503.22346
  Data:   https://huggingface.co/datasets/jackluoluo/ArchCAD  (CC0)
  Repo:   https://github.com/ArchiAI-LAB/ArchCAD

NOT bundled (CC0 makes redistribution legal, but the corpus is large). Download
it yourself and point the adapter at the JSON records. This module is domain-
bridging only: ArchCAD is architectural floor plans, NOT furniture-machining
panels — so most classes do NOT map to OMIM features. The value is (a) the
``holes`` class, (b) the shared vector-primitive + auto-label methodology, and
(c) a permissive pretraining corpus. We never claim a 1:1 domain match.
"""

from __future__ import annotations

import json
from pathlib import Path

from omim.datasets.models import DatasetManifest, DatasetSample

#: ArchCAD semantic class -> OMIM vocabulary. Deliberately SMALL and honest: only
#: the few architectural classes with a real OMIM analogue are mapped; everything
#: else (walls, beams, columns, windows, stairs, text...) is intentionally left
#: unmapped because it has no furniture-machining meaning.
ARCHCAD_TO_OMIM: dict[str, str] = {
    "hole": "THROUGH_HOLE",
    "holes": "THROUGH_HOLE",
    "circle": "THROUGH_HOLE",      # bare circle primitive -> candidate hole
    "door": "DOOR",                # architectural door symbol ~ OMIM DOOR part
    "cabinet": "UNKNOWN_PART",     # furniture symbol present but not machining-typed
    "wardrobe": "UNKNOWN_PART",
}


def map_label(archcad_label: str) -> str | None:
    """Map an ArchCAD class to an OMIM class, or None if it has no analogue."""
    return ARCHCAD_TO_OMIM.get((archcad_label or "").strip().lower())


def convert_sample(record: dict, sample_id: str | None = None) -> DatasetSample:
    """Convert one ArchCAD record (dict of elements with 'label') to a DatasetSample.

    Expected record shape (tolerant): ``{"id": str, "elements": [{"id"/"instance",
    "label"/"class"/"semantic", ...}, ...]}``. Unknown shapes degrade to empty.
    """
    sid = sample_id or str(record.get("id") or record.get("name") or "archcad-sample")
    elements = record.get("elements") or record.get("primitives") or []
    mapped: dict[str, str] = {}
    unmapped: dict[str, str] = {}
    for i, el in enumerate(elements):
        if not isinstance(el, dict):
            continue
        eid = str(el.get("id") or el.get("instance") or el.get("instance_id") or i)
        label = el.get("label") or el.get("class") or el.get("semantic") or ""
        omim = map_label(str(label))
        if omim is not None:
            mapped[eid] = omim
        elif label:
            unmapped[eid] = str(label)
    return DatasetSample(
        sample_id=sid,
        source_dataset="ArchCAD-400K",
        element_labels=mapped,
        unmapped_labels=unmapped,
        element_count=len(elements),
        mapped_count=len(mapped),
        provenance={
            "inference_method": "human_annotated",  # auto-from-layers + expert fix
            "pipeline_stage": "external_dataset_import",
            "module": "omim.datasets.archcad",
            "license": "CC0-1.0",
        },
    )


def load_jsonl(path: str | Path) -> list[DatasetSample]:
    """Load an ArchCAD export where each JSONL line is one drawing record."""
    path = Path(path)
    out: list[DatasetSample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(convert_sample(json.loads(line)))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def build_manifest(samples: list[DatasetSample]) -> DatasetManifest:
    """Summarise converted samples: label coverage + which OMIM classes appear."""
    total = sum(s.element_count for s in samples)
    mapped = sum(s.mapped_count for s in samples)
    omim_classes = sorted({c for s in samples for c in s.element_labels.values()})
    unmapped = sorted({lab for s in samples for lab in s.unmapped_labels.values()})
    return DatasetManifest(
        dataset="ArchCAD-400K",
        license="CC0-1.0",
        redistributable=True,
        samples=len(samples),
        total_elements=total,
        mapped_elements=mapped,
        label_coverage=round(mapped / total, 4) if total else 0.0,
        omim_classes_seen=omim_classes,
        unmapped_source_labels=unmapped,
        notes=[
            "Architectural floor plans, NOT furniture panels — most classes have "
            "no OMIM analogue by design.",
            "Useful as a vector-primitive + auto-label-then-review methodology "
            "precedent and a CC0 pretraining corpus, not as panel ground truth.",
        ],
    )
