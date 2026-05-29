"""Ontology loader — reads YAML definitions of features, operations, constraints."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class FeatureDefinition:
    """A manufacturing feature class definition."""

    name: str
    category: str = ""
    description: str = ""
    typical_diameter_mm: tuple[float, float] | None = None
    typical_depth_mm: tuple[float, float] | None = None
    operations: list[str] = field(default_factory=list)


@dataclass
class OperationDefinition:
    """A CNC operation definition."""

    name: str
    tool_type: str = ""
    description: str = ""


@dataclass
class ManufacturingOntology:
    """Loaded ontology with lookup helpers."""

    version: str
    features: dict[str, FeatureDefinition] = field(default_factory=dict)
    operations: dict[str, OperationDefinition] = field(default_factory=dict)

    def has_feature(self, name: str) -> bool:
        return name in self.features

    def get_feature(self, name: str) -> FeatureDefinition | None:
        return self.features.get(name)

    def feature_names(self) -> list[str]:
        return list(self.features.keys())

    def has_operation(self, name: str) -> bool:
        return name in self.operations

    def operations_for_feature(self, feature_name: str) -> list[str]:
        feat = self.features.get(feature_name)
        if feat:
            return feat.operations
        return []


def load_ontology(ontology_dir: str | Path) -> ManufacturingOntology:
    """Load ontology from a directory containing features.yaml and operations.yaml."""
    ontology_dir = Path(ontology_dir)
    version_file = ontology_dir / "VERSION"
    version = "v0.1.0"
    if version_file.exists():
        version = version_file.read_text(encoding="utf-8").strip()

    ontology = ManufacturingOntology(version=version)

    # Load features
    features_file = ontology_dir / "features.yaml"
    if features_file.exists():
        data = yaml.safe_load(features_file.read_text(encoding="utf-8"))
        for entry in data.get("features", []):
            diam = entry.get("typical_diameter_mm")
            depth = entry.get("typical_depth_mm")
            feat = FeatureDefinition(
                name=entry["name"],
                category=entry.get("category", ""),
                description=entry.get("description", ""),
                typical_diameter_mm=tuple(diam) if diam else None,
                typical_depth_mm=tuple(depth) if depth else None,
                operations=entry.get("operations", []),
            )
            ontology.features[feat.name] = feat
        logger.info("Loaded %d feature definitions", len(ontology.features))

    # Load operations
    operations_file = ontology_dir / "operations.yaml"
    if operations_file.exists():
        data = yaml.safe_load(operations_file.read_text(encoding="utf-8"))
        for entry in data.get("operations", []):
            op = OperationDefinition(
                name=entry["name"],
                tool_type=entry.get("tool_type", ""),
                description=entry.get("description", ""),
            )
            ontology.operations[op.name] = op
        logger.info("Loaded %d operation definitions", len(ontology.operations))

    return ontology
