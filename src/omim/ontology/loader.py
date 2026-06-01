"""Ontology loader -- reads YAML definitions from data/ontology/.

Loads all 5 ontology domains per 04_ONTOLOGY/Manufacturing_Ontology.md:
  features, operations, relationships, constraints, materials.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain definition dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FeatureDefinition:
    """A manufacturing feature class definition from features.yaml."""

    id: str
    label: str = ""
    category: str = ""
    description: str = ""
    detection: dict = field(default_factory=dict)
    confidence: dict = field(default_factory=dict)
    inference_method: str = ""
    sources: list[str] = field(default_factory=list)
    operation: str = ""
    parameters: dict = field(default_factory=dict)


@dataclass
class OperationDefinition:
    """A CNC operation definition from operations.yaml."""

    id: str
    label: str = ""
    description: str = ""
    produces_features: list[str] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    machine_type: str = ""
    source: str = ""
    inference_rule: str = ""


@dataclass
class RelationshipDefinition:
    """A relationship type from relationships.yaml."""

    id: str
    direction: str = ""
    description: str = ""


@dataclass
class ConstraintDefinition:
    """A constraint type from constraints.yaml."""

    id: str
    name: str = ""
    description: str = ""
    unit: str = "mm"
    source: str = ""
    default_value: float | None = None


@dataclass
class MaterialDefinition:
    """A material definition from materials.yaml."""

    id: str
    name: str = ""
    standard: str = ""
    typical_thickness_mm: list[float] = field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Ontology (aggregate root)
# ---------------------------------------------------------------------------


@dataclass
class Ontology:
    """Loaded ontology with lookup helpers.

    Replaces the old ``ManufacturingOntology`` class.
    """

    version: str
    features: dict[str, FeatureDefinition] = field(default_factory=dict)
    operations: dict[str, OperationDefinition] = field(default_factory=dict)
    relationships: dict[str, RelationshipDefinition] = field(default_factory=dict)
    constraints: dict[str, ConstraintDefinition] = field(default_factory=dict)
    materials: dict[str, MaterialDefinition] = field(default_factory=dict)
    #: Raw rule definitions keyed by rule_id, populated from data/rules/*.yaml
    #: when the ontology is loaded with a ``rules_dir``. Each value is the rule's
    #: parsed YAML dict (rule_id, applies_to, parameters, severity, ...).
    rules: dict[str, dict] = field(default_factory=dict)

    # -- Feature queries ---------------------------------------------------

    def get_feature(self, feature_id: str) -> FeatureDefinition | None:
        """Return the feature definition for *feature_id*, or ``None``."""
        return self.features.get(feature_id)

    def get_features_by_category(self, category: str) -> list[FeatureDefinition]:
        """Return all features in the given *category* (e.g. ``HOLE_FEATURES``)."""
        return [f for f in self.features.values() if f.category == category]

    def is_valid_feature_id(self, feature_id: str) -> bool:
        """Return whether *feature_id* is a known feature in the ontology."""
        return feature_id in self.features

    def get_operation_for_feature(self, feature_id: str) -> str | None:
        """Return the primary operation type for *feature_id*, or ``None``."""
        feat = self.features.get(feature_id)
        if feat and feat.operation:
            return feat.operation
        return None

    def feature_names(self) -> list[str]:
        """Return all feature IDs as a list."""
        return list(self.features.keys())

    def operations_for_feature(self, feature_name: str) -> list[str]:
        """Return operation IDs applicable to *feature_name*."""
        feat = self.features.get(feature_name)
        if feat and feat.operation:
            return [feat.operation]
        return []

    # -- Backwards-compat helpers ------------------------------------------

    def has_feature(self, name: str) -> bool:
        return name in self.features

    def has_operation(self, name: str) -> bool:
        return name in self.operations

    # -- Rule cross-reference ----------------------------------------------

    #: DXF entity-type tokens that may appear in a rule's ``applies_to`` but are
    #: NOT feature classes (so they are excluded from feature references).
    _DXF_ENTITY_TYPES = frozenset({
        "CIRCLE", "LWPOLYLINE", "POLYLINE", "LINE", "ARC", "SPLINE",
        "ELLIPSE", "ALL", "ALL_GEOMETRY",
    })

    def get_rule_feature_references(self) -> dict[str, list[str]]:
        """Return mapping of ``rule_id -> [feature_class, ...]`` for rules
        with feature-specific applicability.

        Reads the rule definitions loaded into :attr:`rules` (populated when the
        ontology is loaded with a ``rules_dir``). For each rule, an ``applies_to``
        token counts as a feature reference only when it is not a plain DXF entity
        type and either is a known ontology feature id or is UPPER_SNAKE_CASE
        (the feature-id shape, e.g. ``CONFIRMAT_HOLE``). Returns ``{}`` when no
        rules were loaded (callers fall back to scanning rule YAML directly).
        """
        result: dict[str, list[str]] = {}
        for rule_id, rule in self.rules.items():
            applies_to = rule.get("applies_to", []) or []
            feature_refs = [
                token
                for token in applies_to
                if isinstance(token, str)
                and token.upper() not in self._DXF_ENTITY_TYPES
                and (self.is_valid_feature_id(token) or (token.isupper() and "_" in token))
            ]
            if feature_refs:
                result[rule_id] = feature_refs
        return result


# ---------------------------------------------------------------------------
# Backwards-compatible alias
# ---------------------------------------------------------------------------

ManufacturingOntology = Ontology


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class OntologyLoadError(Exception):
    """Raised when a required ontology file is missing or malformed."""


class OntologyLoader:
    """Load ontology from a directory of YAML files."""

    def load(self, ontology_dir: str | Path, rules_dir: str | Path | None = None) -> Ontology:
        """Load and return a fully populated ``Ontology``."""
        return load_ontology(ontology_dir, rules_dir=rules_dir)


def load_ontology(ontology_dir: str | Path, rules_dir: str | Path | None = None) -> Ontology:
    """Load ontology from a directory containing YAML definitions.

    Expected files (per Manufacturing_Ontology.md):
        features.yaml, operations.yaml, relationships.yaml,
        constraints.yaml, materials.yaml, VERSION

    If *rules_dir* is given (or a sibling ``rules/`` directory exists next to
    *ontology_dir*), rule definitions are loaded into ``ontology.rules`` so that
    :meth:`Ontology.get_rule_feature_references` works.
    """
    ontology_dir = Path(ontology_dir)

    # -- Version -----------------------------------------------------------
    version_file = ontology_dir / "VERSION"
    version = "v0.1.0"
    if version_file.exists():
        version = version_file.read_text(encoding="utf-8").strip()

    ontology = Ontology(version=version)

    # -- Features ----------------------------------------------------------
    _load_features(ontology, ontology_dir / "features.yaml")

    # -- Operations --------------------------------------------------------
    _load_operations(ontology, ontology_dir / "operations.yaml")

    # -- Relationships -----------------------------------------------------
    _load_relationships(ontology, ontology_dir / "relationships.yaml")

    # -- Constraints -------------------------------------------------------
    _load_constraints(ontology, ontology_dir / "constraints.yaml")

    # -- Materials ---------------------------------------------------------
    _load_materials(ontology, ontology_dir / "materials.yaml")

    # -- Rules (optional) --------------------------------------------------
    if rules_dir is None:
        sibling = ontology_dir.parent / "rules"
        if sibling.is_dir():
            rules_dir = sibling
    if rules_dir is not None:
        _load_rules(ontology, Path(rules_dir))

    return ontology


def _load_rules(ontology: Ontology, rules_dir: Path) -> None:
    """Load rule definitions from ``*.yaml`` under *rules_dir* into ``ontology.rules``."""
    if not rules_dir.is_dir():
        return
    for yaml_file in sorted(rules_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            logger.warning("Skipping malformed rule file: %s", yaml_file)
            continue
        for rule in data.get("rules", []) or []:
            rule_id = rule.get("rule_id")
            if rule_id:
                ontology.rules[rule_id] = rule
    logger.info("Loaded %d rule definitions", len(ontology.rules))


# ---------------------------------------------------------------------------
# Private loaders
# ---------------------------------------------------------------------------


def _load_features(ontology: Ontology, path: Path) -> None:
    if not path.exists():
        logger.warning("Features file not found: %s", path)
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for entry in data.get("features", []):
        feat = FeatureDefinition(
            id=entry["id"],
            label=entry.get("label", ""),
            category=entry.get("category", ""),
            description=entry.get("description", ""),
            detection=entry.get("detection", {}),
            confidence=entry.get("confidence", {}),
            inference_method=entry.get("inference_method", ""),
            sources=entry.get("sources", []),
            operation=entry.get("operation", ""),
            parameters=entry.get("parameters", {}),
        )
        ontology.features[feat.id] = feat
    logger.info("Loaded %d feature definitions", len(ontology.features))


def _load_operations(ontology: Ontology, path: Path) -> None:
    if not path.exists():
        logger.warning("Operations file not found: %s", path)
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for entry in data.get("operations", []):
        op = OperationDefinition(
            id=entry["id"],
            label=entry.get("label", ""),
            description=entry.get("description", ""),
            produces_features=entry.get("produces_features", []),
            parameters=entry.get("parameters", []),
            machine_type=entry.get("machine_type", ""),
            source=entry.get("source", ""),
            inference_rule=entry.get("inference_rule", ""),
        )
        ontology.operations[op.id] = op
    logger.info("Loaded %d operation definitions", len(ontology.operations))


def _load_relationships(ontology: Ontology, path: Path) -> None:
    if not path.exists():
        logger.warning("Relationships file not found: %s", path)
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for entry in data.get("relationships", []):
        rel = RelationshipDefinition(
            id=entry["id"],
            direction=entry.get("direction", ""),
            description=entry.get("description", ""),
        )
        ontology.relationships[rel.id] = rel
    logger.info("Loaded %d relationship definitions", len(ontology.relationships))


def _load_constraints(ontology: Ontology, path: Path) -> None:
    if not path.exists():
        logger.warning("Constraints file not found: %s", path)
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for entry in data.get("constraints", []):
        con = ConstraintDefinition(
            id=entry["id"],
            name=entry.get("name", ""),
            description=entry.get("description", ""),
            unit=entry.get("unit", "mm"),
            source=entry.get("source", ""),
            default_value=entry.get("default_value"),
        )
        ontology.constraints[con.id] = con
    logger.info("Loaded %d constraint definitions", len(ontology.constraints))


def _load_materials(ontology: Ontology, path: Path) -> None:
    if not path.exists():
        logger.warning("Materials file not found: %s", path)
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for mid, mdata in data.get("materials", {}).items():
        mat = MaterialDefinition(
            id=mid,
            name=mdata.get("name", ""),
            standard=mdata.get("standard", ""),
            typical_thickness_mm=mdata.get("typical_thickness_mm", []),
            notes=mdata.get("notes", ""),
        )
        ontology.materials[mat.id] = mat
    logger.info("Loaded %d material definitions", len(ontology.materials))
