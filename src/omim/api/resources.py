"""Lazy-loaded shared resources for the API (ontology + validation rules).

Loading happens on first use and is cached. Failures degrade gracefully — an
endpoint returns an empty-but-well-formed structure rather than a 500 if the
backing data files are missing.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from omim.config import get_settings
from omim.ontology.loader import Ontology, load_ontology

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_ontology() -> Ontology | None:
    """Load and cache the ontology. Returns ``None`` if unavailable."""
    settings = get_settings()
    try:
        if not settings.ontology_dir.exists():
            logger.warning("Ontology dir not found: %s", settings.ontology_dir)
            return None
        return load_ontology(settings.ontology_dir)
    except Exception:
        logger.exception("Failed to load ontology")
        return None


def ontology_payload() -> dict[str, Any]:
    """Serialise the loaded ontology into a JSON-friendly summary."""
    ont = get_ontology()
    if ont is None:
        return {
            "loaded": False,
            "version": None,
            "feature_classes": [],
            "operations": [],
            "constraints": [],
            "materials": [],
            "note": "Ontology data not available.",
        }

    feature_classes = [
        {
            "id": f.id,
            "label": f.label,
            "category": f.category,
            "operation": f.operation,
            "inference_method": f.inference_method,
            "description": f.description,
        }
        for f in ont.features.values()
    ]
    operations = [
        {
            "id": o.id,
            "label": o.label,
            "machine_type": o.machine_type,
            "produces_features": o.produces_features,
            "description": o.description,
        }
        for o in ont.operations.values()
    ]
    constraints = [
        {
            "id": c.id,
            "name": c.name,
            "unit": c.unit,
            "default_value": c.default_value,
            "source": c.source,
            "description": c.description,
        }
        for c in ont.constraints.values()
    ]
    materials = [
        {
            "id": m.id,
            "name": m.name,
            "standard": m.standard,
            "typical_thickness_mm": m.typical_thickness_mm,
        }
        for m in ont.materials.values()
    ]

    return {
        "loaded": True,
        "version": ont.version,
        "counts": {
            "feature_classes": len(feature_classes),
            "operations": len(operations),
            "constraints": len(constraints),
            "materials": len(materials),
            "relationships": len(ont.relationships),
        },
        "feature_classes": feature_classes,
        "operations": operations,
        "constraints": constraints,
        "materials": materials,
    }


@lru_cache(maxsize=1)
def _load_rule_files() -> list[dict[str, Any]]:
    """Load and cache validation rule definitions from the rules YAML files."""
    settings = get_settings()
    rules_dir: Path = settings.rules_dir
    rules: list[dict[str, Any]] = []
    if not rules_dir.exists():
        logger.warning("Rules dir not found: %s", rules_dir)
        return rules

    for yaml_file in sorted(rules_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            logger.exception("Failed to parse rule file %s", yaml_file)
            continue
        for rule in data.get("rules", []) or []:
            rules.append(
                {
                    "rule_id": rule.get("rule_id"),
                    "name": rule.get("name", ""),
                    "category": rule.get("category", rule.get("rule_type", "")),
                    "layer": rule.get("layer"),
                    "severity": rule.get("severity", ""),
                    "applies_to": rule.get("applies_to", []),
                    "parameters": rule.get("parameters", {}),
                    "enabled": rule.get("enabled", True),
                    "description": rule.get("description", ""),
                    "source_file": yaml_file.name,
                }
            )
    return rules


def rules_payload() -> dict[str, Any]:
    """Serialise the loaded validation rules into a JSON-friendly summary."""
    settings = get_settings()
    rules = _load_rule_files()
    by_layer: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for r in rules:
        layer_key = f"layer{r['layer']}" if r.get("layer") else "other"
        by_layer[layer_key] = by_layer.get(layer_key, 0) + 1
        sev = r.get("severity") or "UNSPECIFIED"
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return {
        "loaded": bool(rules),
        "ruleset_version": settings.ruleset_version,
        "count": len(rules),
        "by_layer": by_layer,
        "by_severity": by_severity,
        "rules": rules,
    }
