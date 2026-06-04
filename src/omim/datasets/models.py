"""Shared models for external-dataset adapters.

OMIM does not bundle third-party datasets (they are large and carry their own
licenses — see each adapter's docstring). These adapters make a dataset *usable*
when the user has downloaded it: they map the dataset's native label vocabulary
onto OMIM's taxonomy and convert its records into OMIM structures (an MGG, or a
label manifest), so external data can pretrain/benchmark/augment OMIM models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DatasetSample(BaseModel):
    """One converted external sample: an OMIM-vocabulary view of a source record."""

    sample_id: str
    source_dataset: str          # "ArchCAD-400K" | "MFCAD++"
    source_file: str = ""
    # Per-element labels mapped into OMIM's vocabulary (element_id -> omim_class).
    element_labels: dict[str, str] = Field(default_factory=dict)
    # Labels that had NO OMIM mapping (kept for transparency / coverage stats).
    unmapped_labels: dict[str, str] = Field(default_factory=dict)
    element_count: int = 0
    mapped_count: int = 0
    provenance: dict | None = None


class DatasetManifest(BaseModel):
    """Summary of a converted external dataset (coverage + license provenance)."""

    dataset: str
    license: str
    redistributable: bool
    samples: int = 0
    total_elements: int = 0
    mapped_elements: int = 0
    label_coverage: float = 0.0   # mapped / total
    omim_classes_seen: list[str] = Field(default_factory=list)
    unmapped_source_labels: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
