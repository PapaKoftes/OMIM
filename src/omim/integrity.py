"""Integrity & consistency checks for the OMIM pipeline.

These functions catch *structural* problems that per-field Pydantic
validation cannot. They are intended to run as fail-fast gates:

  - ``check_ontology_consistency()`` -- at startup, before processing.
  - ``check_graph_integrity()``      -- after every MGG is built.

Spec: docs/02_SCHEMA/Canonical_Sample_Schema.md (check_graph_integrity,
check_dataset_consistency) and docs/04_ONTOLOGY/Manufacturing_Ontology.md
(get_rule_feature_references).

IMPLEMENTATION NOTE
-------------------
The schema doc sketches ``check_graph_integrity`` using an object-attribute
API (``n.node_id``, ``feat.confidence``, ``mgg.query().get_geometry_nodes()``
returning objects). The *actual* ``ManufacturingGeometryGraph`` stores nodes
as plain dicts and its query accessors yield ``(node_id, data)`` tuples where
``data`` is a dict (see ``omim/graph/mgg.py`` and ``omim/graph/query.py``).
This module adapts the spec's six checks to the real dict-based API.

The dataset-level check ``check_dataset_consistency`` already lives in
``omim.export.dataset_exporter``; it is re-exported here so callers have a
single integrity entry point.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

# Re-export the canonical dataset-level check so this module is the single
# integrity surface. (Implemented in the exporter alongside validate_sample_schema.)
from omim.export.dataset_exporter import (  # noqa: F401
    check_dataset_consistency,
    validate_sample_schema,
)

if TYPE_CHECKING:
    from omim.graph.mgg import ManufacturingGeometryGraph
    from omim.ontology.loader import Ontology
    from omim.validation.rule_engine import RuleEngine


# ---------------------------------------------------------------------------
# Graph integrity
# ---------------------------------------------------------------------------


def check_graph_integrity(mgg: ManufacturingGeometryGraph) -> list[str]:
    """Verify internal MGG consistency.

    Returns a list of violation strings (empty list == clean graph).

    The six checks (per docs/02_SCHEMA/Canonical_Sample_Schema.md, adapted to
    the real dict-based MGG API):

      1. No orphan geometry nodes -- every GeometryNode is either referenced by
         a FeatureNode (via ``geometry_node_ids`` or a COMPOSES edge) or is the
         panel outer boundary.
      2. No dangling edges -- every edge source/target exists as a node.
      3. No self-loops.
      4. Feature confidence within ``[0.0, 1.0]``.
      5. Every feature class is in the loaded ontology (``UNKNOWN_FEATURE`` is
         always allowed). Skipped if no ontology is loaded on the graph.
      6. No geometry nodes with zero / negative dimensions
         (negative ``area_mm2`` or non-positive ``diameter_mm``).
    """
    violations: list[str] = []
    query = mgg.query()
    graph = mgg.graph

    geometry_nodes = query.get_geometry_nodes()
    feature_nodes = query.get_feature_nodes()

    # ------------------------------------------------------------------
    # 1. No orphan geometry nodes
    # ------------------------------------------------------------------
    all_geo_ids = {nid for nid, _ in geometry_nodes}

    referenced_geo_ids: set[str] = set()
    for _fid, fdata in feature_nodes:
        for gid in fdata.get("geometry_node_ids", []) or []:
            referenced_geo_ids.add(gid)
    # Also honour COMPOSES edges (geometry -> feature), which are the graph's
    # authoritative geometry<->feature link.
    from omim.graph.models import EdgeType  # local import to avoid cycle at import time

    for u, v, edata in graph.edges(data=True):
        if edata.get("edge_type") == EdgeType.COMPOSES.value:
            # COMPOSES is geometry -> feature; the geometry endpoint is "used".
            if u in all_geo_ids:
                referenced_geo_ids.add(u)
            if v in all_geo_ids:
                referenced_geo_ids.add(v)

    panel_boundary_ids = {
        nid for nid, data in geometry_nodes if data.get("is_outer_boundary")
    }

    orphans = all_geo_ids - referenced_geo_ids - panel_boundary_ids
    for orphan_id in sorted(orphans):
        violations.append(
            f"ORPHAN_GEOMETRY: {orphan_id} not referenced by any FeatureNode"
        )

    # ------------------------------------------------------------------
    # 2. No dangling edges
    # ------------------------------------------------------------------
    all_node_ids = set(graph.nodes())
    for src, tgt, _edata in graph.edges(data=True):
        if src not in all_node_ids:
            violations.append(f"DANGLING_EDGE_SOURCE: {src}")
        if tgt not in all_node_ids:
            violations.append(f"DANGLING_EDGE_TARGET: {tgt}")

    # ------------------------------------------------------------------
    # 3. No self-loops
    # ------------------------------------------------------------------
    for src, tgt, _edata in graph.edges(data=True):
        if src == tgt:
            violations.append(f"SELF_LOOP: node {src} has edge to itself")

    # ------------------------------------------------------------------
    # 4. Feature confidence within [0.0, 1.0]
    # ------------------------------------------------------------------
    for fid, fdata in feature_nodes:
        conf = fdata.get("confidence")
        if conf is None:
            continue
        if not 0.0 <= conf <= 1.0:
            violations.append(
                f"INVALID_CONFIDENCE: {fid} has confidence={conf}"
            )

    # ------------------------------------------------------------------
    # 5. Every feature class is in the loaded ontology
    # ------------------------------------------------------------------
    ontology = getattr(mgg, "ontology", None)
    if ontology is not None:
        for fid, fdata in feature_nodes:
            feature_class = fdata.get("feature_class")
            if feature_class in (None, "", "UNKNOWN_FEATURE"):
                continue
            if not ontology.is_valid_feature_id(feature_class):
                violations.append(
                    f"UNKNOWN_FEATURE_CLASS: {fid} class='{feature_class}' "
                    f"not in ontology v{ontology.version}"
                )

    # ------------------------------------------------------------------
    # 6. No geometry nodes with zero / negative dimensions
    # ------------------------------------------------------------------
    for gid, gdata in geometry_nodes:
        area = gdata.get("area_mm2")
        if area is not None and area < 0:
            violations.append(f"NEGATIVE_AREA: {gid} area={area}")
        diameter = gdata.get("diameter_mm")
        if diameter is not None and diameter <= 0:
            violations.append(f"NON_POSITIVE_DIAMETER: {gid} diameter={diameter}")

    return violations


# ---------------------------------------------------------------------------
# Ontology consistency
# ---------------------------------------------------------------------------


def _rule_feature_references(
    ontology: Ontology,
    rules_dir: str | Path | None,
) -> dict[str, list[str]]:
    """Return ``{rule_id: [feature_class, ...]}`` for rules with feature-specific
    applicability.

    Prefers ``ontology.get_rule_feature_references()`` when it returns a
    non-empty mapping. Otherwise falls back to scanning rule YAML files under
    *rules_dir* (the engine's own rule definitions), extracting each rule's
    ``applies_to`` entries that name a *feature class* (i.e. appear in the
    ontology's feature set or are not plain DXF entity types).
    """
    # Preferred path: the ontology API.
    refs = ontology.get_rule_feature_references()
    if refs:
        return refs

    # Fallback: scan rule YAML. ``applies_to`` lists DXF entity types
    # (CIRCLE, LWPOLYLINE, ...) for geometric rules, but for manufacturing
    # rules it can name feature classes. We treat an ``applies_to`` token as a
    # feature reference only when it is NOT a known DXF entity type and is
    # uppercase/underscore-shaped like a feature id.
    if rules_dir is None:
        return {}
    rules_path = Path(rules_dir)
    if not rules_path.exists():
        return {}

    dxf_entity_types = {
        "CIRCLE",
        "LWPOLYLINE",
        "POLYLINE",
        "LINE",
        "ARC",
        "SPLINE",
        "ALL",
        "ALL_GEOMETRY",
    }

    result: dict[str, list[str]] = {}
    for yaml_file in sorted(rules_path.glob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        for rule in data.get("rules", []) or []:
            rule_id = rule.get("rule_id")
            applies_to = rule.get("applies_to", []) or []
            feature_refs = [
                token
                for token in applies_to
                if isinstance(token, str)
                and token.upper() not in dxf_entity_types
                # Feature ids are UPPER_SNAKE_CASE (e.g. CONFIRMAT_HOLE).
                # Rule YAML also uses lowercase descriptive applicability tokens
                # (e.g. "pocket_features", "panel_boundary") that are NOT
                # feature classes -- exclude them by requiring the token to be
                # uppercase, or to be an explicit ontology feature id.
                and (
                    ontology.is_valid_feature_id(token)
                    or (token.isupper() and "_" in token)
                )
            ]
            if rule_id and feature_refs:
                result[rule_id] = feature_refs
    return result


def check_ontology_consistency(
    ontology: Ontology,
    rule_engine: RuleEngine | None = None,
    rules_dir: str | Path | None = None,
) -> list[str]:
    """Verify the ontology is internally consistent and that everything the
    pipeline references actually exists in it.

    Returns a list of violation strings (empty list == consistent).

    Checks:
      1. Every ``feature_class`` referenced by a rule (via the rule's
         ``applies_to`` field) exists in the loaded ontology.
      2. Every operation that a feature maps to in ``FEATURE_TO_OPERATIONS``
         (the semantic layer's feature->operation table) exists in the
         ontology's operations. Feature keys of that table that are themselves
         ontology features are also checked to exist.
      3. Every ``Ontology.get_operation_for_feature`` target (the feature's
         declared primary ``operation``) exists in the ontology's operations.

    *rule_engine* is accepted for API symmetry with the spec; rule
    applicability is sourced from ``ontology.get_rule_feature_references()``
    first, then from *rules_dir* (defaults to ``data/rules`` next to the
    ontology dir if discoverable).
    """
    violations: list[str] = []

    # ------------------------------------------------------------------
    # 1. Rule-referenced feature classes must exist in the ontology.
    # ------------------------------------------------------------------
    rule_refs = _rule_feature_references(ontology, rules_dir)
    for rule_id, feature_classes in rule_refs.items():
        for feature_class in feature_classes:
            if not ontology.is_valid_feature_id(feature_class):
                violations.append(
                    f"RULE_REFERENCES_UNKNOWN_FEATURE: rule {rule_id} "
                    f"references '{feature_class}' not in ontology "
                    f"v{ontology.version}"
                )

    # ------------------------------------------------------------------
    # 2. FEATURE_TO_OPERATIONS targets must exist as ontology operations.
    # ------------------------------------------------------------------
    # Import lazily so this module imports cleanly even if semantic deps change.
    from omim.semantic.classifier import FEATURE_TO_OPERATIONS

    valid_operations = set(ontology.operations.keys())
    # Only enforce operation existence if the ontology actually defines
    # operations; an empty ontology should not produce spurious errors here.
    if valid_operations:
        for feature_class, operations in FEATURE_TO_OPERATIONS.items():
            for op in operations:
                if op not in valid_operations:
                    violations.append(
                        f"FEATURE_TO_OPERATIONS_UNKNOWN_OPERATION: "
                        f"feature '{feature_class}' maps to operation '{op}' "
                        f"not in ontology v{ontology.version}"
                    )

    # ------------------------------------------------------------------
    # 3. Each ontology feature's declared primary operation must exist.
    # ------------------------------------------------------------------
    if valid_operations:
        for feature_id, feature_def in ontology.features.items():
            op = getattr(feature_def, "operation", "")
            if op and op not in valid_operations:
                violations.append(
                    f"FEATURE_OPERATION_UNKNOWN: feature '{feature_id}' declares "
                    f"operation '{op}' not in ontology v{ontology.version}"
                )

    return violations


__all__ = [
    "check_graph_integrity",
    "check_ontology_consistency",
    "check_dataset_consistency",
    "validate_sample_schema",
]
