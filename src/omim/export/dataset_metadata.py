"""Dataset-level metadata builder.

Produces the ``dataset_metadata.json`` content described in
docs/02_SCHEMA/Canonical_Sample_Schema.md (section 6).

Invariants (validated here when the data is present):
  - statistics.valid_samples + statistics.invalid_samples == total_samples
  - statistics.train_samples + statistics.val_samples + statistics.test_samples == total_samples
  - generation_config.seed must be present for reproducibility
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

SCHEMA = "omim-dataset-metadata-v0.1.0"
SCHEMA_VERSION = "v0.1.0"
OMIM_VERSION = "v0.1.0"
ONTOLOGY_VERSION = "v0.1.0"
RULESET_VERSION = "v0.1.0"

DEFAULT_LICENSE = "Apache 2.0"
DEFAULT_CITATION = "OMIM: Open Manufacturing Intelligence Middleware (2026)"
DEFAULT_GROUNDING_NOTE = (
    "Feature frequencies based on European cabinet construction conventions "
    "and manufacturer catalogs; not validated against a real DXF corpus."
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_dataset_metadata(config: dict, statistics: dict) -> dict:
    """Build the canonical ``dataset_metadata.json`` content.

    Parameters
    ----------
    config:
        Generation config. Recognized keys: ``seed`` (required for
        reproducibility), ``n_samples``, ``feature_density``, ``invalid_ratio``,
        ``panel_width_range_mm``, ``panel_height_range_mm``,
        ``panel_thickness_options_mm``, plus optional top-level overrides
        ``dataset_id``, ``creation_timestamp``, ``license``, ``citation``,
        ``source_type``, ``contains_external_data``, ``grounding_note``.
    statistics:
        Dataset statistics block (total/valid/invalid/train/val/test counts,
        feature_counts, violation_counts, etc.).
    """
    config = dict(config or {})
    statistics = dict(statistics or {})

    timestamp = config.get("creation_timestamp") or _utc_now_iso()
    date_str = timestamp[:10]
    dataset_id = config.get("dataset_id") or f"omim-synthetic-{SCHEMA_VERSION}-{date_str}"

    generation_config: dict[str, Any] = {
        "seed": config.get("seed"),
        "n_samples": config.get("n_samples"),
        "feature_density": config.get("feature_density", "medium"),
        "invalid_ratio": config.get("invalid_ratio"),
        "panel_width_range_mm": config.get("panel_width_range_mm"),
        "panel_height_range_mm": config.get("panel_height_range_mm"),
        "panel_thickness_options_mm": config.get("panel_thickness_options_mm"),
    }

    metadata: dict[str, Any] = {
        "$schema": SCHEMA,
        "dataset_id": dataset_id,
        "omim_version": OMIM_VERSION,
        "ontology_version": ONTOLOGY_VERSION,
        "ruleset_version": RULESET_VERSION,
        "creation_timestamp": timestamp,
        "generation_config": generation_config,
        "statistics": statistics,
        "schema_version": SCHEMA_VERSION,
        "license": config.get("license", DEFAULT_LICENSE),
        "citation": config.get("citation", DEFAULT_CITATION),
        "source_type": config.get("source_type", "synthetic_generated"),
        "contains_external_data": config.get("contains_external_data", False),
        "grounding_note": config.get("grounding_note", DEFAULT_GROUNDING_NOTE),
    }
    return metadata
