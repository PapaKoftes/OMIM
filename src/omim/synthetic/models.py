"""Synthetic data-generation models.

These are the GENERATION SPEC objects. Ground-truth labels for the dataset
come from these specs, never from inference. The deterministic validator is the
gatekeeper that decides whether a generated sample is kept.

Spec: 09_SYNTHETIC / PanelGenerator.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PanelGeneratorConfig(BaseModel):
    """Configuration for the synthetic panel generator."""

    random_seed: int = 42
    num_samples: int = 1000
    train_ratio: float = 0.70
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    min_panel_width_mm: float = 100.0
    max_panel_width_mm: float = 1200.0
    min_panel_height_mm: float = 100.0
    max_panel_height_mm: float = 2400.0
    panel_thickness_options_mm: list[float] = [12.0, 15.0, 16.0, 18.0, 22.0, 25.0]
    feature_density: Literal["sparse", "medium", "dense"] = "medium"
    invalid_sample_ratio: float = 0.30
    max_violations_per_invalid: int = 3
    dxf_version: str = "AC1024"
    units: str = "mm"
    format: Literal["flat", "split"] = "split"
    ruleset_version: str = "v0.1.0"
    schema_version: str = "v0.1.0"
    # Fixed timestamp stamped into every generated artifact (MGG creation
    # timestamp, dataset generated_at, dataset_metadata creation_timestamp) so
    # the generation pipeline is byte-reproducible. A constant, NOT now().
    generation_timestamp: str = "2026-01-01T00:00:00+00:00"


class PanelSpec(BaseModel):
    """Generated panel geometry specification (ground truth)."""

    width_mm: float
    height_mm: float
    thickness_mm: float
    boundary_points: list[tuple[float, float]]
    panel_type: str  # "side_panel" | "shelf" | "door" | "back_panel" | "bottom_top" | "generic"


class FeatureSpec(BaseModel):
    """Generated feature specification (ground truth).

    feature_class is the ontology feature id (e.g. SHELF_PIN_HOLE). entity_type
    is the DXF entity used to realise it. is_valid / violations carry the
    intended ground-truth label for any injected manufacturing violation.
    """

    feature_class: str
    entity_type: str  # "CIRCLE" | "LWPOLYLINE"
    center: tuple[float, float] | None = None
    radius_mm: float | None = None
    points: list[tuple[float, float]] | None = None
    is_closed: bool = False
    layer: str = "DRILL"
    depth_mm: float | None = None
    is_valid: bool = True
    violations: list[str] = Field(default_factory=list)
    group_id: str | None = None


class GeneratedSample(BaseModel):
    """A single generated sample: panel + features + ground-truth labels."""

    sample_id: str
    panel: PanelSpec
    features: list[FeatureSpec]
    is_invalid: bool
    injected_violations: list[str] = Field(default_factory=list)
    split: str = "train"


class DatasetManifest(BaseModel):
    """Manifest describing a generated dataset."""

    schema_version: str = "v0.1.0"
    dataset_id: str
    generated_at: str = ""
    generator_version: str = "v0.1.0"
    total_samples: int = 0
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    feature_type_counts: dict = Field(default_factory=dict)
    sample_ids: dict = Field(default_factory=dict)  # sample_id -> split
