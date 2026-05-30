"""Manufacturing Geometry Graph -- the canonical OMIM representation.

An MGG is a NetworkX MultiDiGraph where:
  - Nodes are GeometryNode | FeatureNode | OperationNode | ConstraintNode
  - Edges carry an EdgeType and optional metadata
  - GraphMetadata tracks provenance and summary statistics
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import networkx as nx

from omim.graph.models import (
    ConstraintNode,
    EdgeType,
    FeatureNode,
    GeometryNode,
    GraphMetadata,
    OperationNode,
    RelationshipEdge,
)

if TYPE_CHECKING:
    from omim.graph.query import MGGQuery


class ManufacturingGeometryGraph:
    """Thin wrapper around ``nx.MultiDiGraph`` with typed helpers."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, metadata: GraphMetadata) -> None:
        self._g = nx.MultiDiGraph()
        self.metadata = metadata

    # ------------------------------------------------------------------
    # Node helpers
    # ------------------------------------------------------------------

    def add_geometry_node(self, node: GeometryNode) -> None:
        self._g.add_node(node.node_id, **node.model_dump())
        self.metadata.geometry_node_count = len(list(self.geometry_nodes()))

    def add_feature_node(self, node: FeatureNode) -> None:
        self._g.add_node(node.node_id, **node.model_dump())
        self.metadata.feature_node_count = len(list(self.feature_nodes()))

    def add_operation_node(self, node: OperationNode) -> None:
        self._g.add_node(node.node_id, **node.model_dump())
        self.metadata.operation_node_count = len(list(self.operation_nodes()))

    def add_constraint_node(self, node: ConstraintNode) -> None:
        self._g.add_node(node.node_id, **node.model_dump())
        self.metadata.constraint_node_count = len(list(self.constraint_nodes()))

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        if node_id in self._g:
            return dict(self._g.nodes[node_id])
        return None

    def has_node(self, node_id: str) -> bool:
        return node_id in self._g

    def geometry_nodes(self) -> Iterator[tuple[str, dict]]:
        for nid, data in self._g.nodes(data=True):
            if data.get("node_type") == "geometry":
                yield nid, data

    def feature_nodes(self) -> Iterator[tuple[str, dict]]:
        for nid, data in self._g.nodes(data=True):
            if data.get("node_type") == "feature":
                yield nid, data

    def operation_nodes(self) -> Iterator[tuple[str, dict]]:
        for nid, data in self._g.nodes(data=True):
            if data.get("node_type") == "operation":
                yield nid, data

    def constraint_nodes(self) -> Iterator[tuple[str, dict]]:
        for nid, data in self._g.nodes(data=True):
            if data.get("node_type") == "constraint":
                yield nid, data

    # ------------------------------------------------------------------
    # Edge helpers
    # ------------------------------------------------------------------

    def add_edge(
        self,
        source_or_edge: str | RelationshipEdge,
        target: str | None = None,
        edge_type: EdgeType | None = None,
        **attrs: Any,
    ) -> int:
        """Add a typed edge, returning the edge key.

        Accepts either a ``RelationshipEdge`` object or the legacy
        ``(source, target, edge_type, **attrs)`` signature for backward
        compatibility.
        """
        if isinstance(source_or_edge, RelationshipEdge):
            edge = source_or_edge
            key = self._g.add_edge(
                edge.source_id,
                edge.target_id,
                edge_type=edge.relationship_type,
                edge_id=edge.edge_id,
                confidence=edge.confidence,
                weight=edge.weight,
                **edge.metadata,
            )
        else:
            if target is None or edge_type is None:
                raise ValueError(
                    "When passing positional args, source, target, and edge_type are all required."
                )
            key = self._g.add_edge(
                source_or_edge, target, edge_type=edge_type.value, **attrs
            )
        self.metadata.edge_count = self._g.number_of_edges()
        return key

    def edges_by_type(self, edge_type: EdgeType) -> list[tuple[str, str, dict]]:
        return [
            (u, v, d)
            for u, v, d in self._g.edges(data=True)
            if d.get("edge_type") == edge_type.value
        ]

    def neighbors(self, node_id: str) -> list[str]:
        if node_id not in self._g:
            return []
        return list(self._g.successors(node_id)) + list(self._g.predecessors(node_id))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def query(self) -> MGGQuery:
        """Return an MGGQuery helper bound to this graph."""
        from omim.graph.query import MGGQuery

        return MGGQuery(self)

    @property
    def graph(self) -> nx.MultiDiGraph:
        """Direct access to the underlying NetworkX graph."""
        return self._g

    @property
    def node_count(self) -> int:
        return self._g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._g.number_of_edges()

    def features_for_geometry(self, geometry_node_id: str) -> list[tuple[str, dict]]:
        """Return feature nodes connected to a geometry node via COMPOSES edges."""
        result = []
        for pred in self._g.predecessors(geometry_node_id):
            for _key, data in self._g[pred][geometry_node_id].items():
                if data.get("edge_type") == EdgeType.COMPOSES.value:
                    node_data = self._g.nodes[pred]
                    if node_data.get("node_type") == "feature":
                        result.append((pred, dict(node_data)))
        # Also check successors (COMPOSES is geometry -> feature)
        for succ in self._g.successors(geometry_node_id):
            for _key, data in self._g[geometry_node_id][succ].items():
                if data.get("edge_type") == EdgeType.COMPOSES.value:
                    node_data = self._g.nodes[succ]
                    if node_data.get("node_type") == "feature":
                        result.append((succ, dict(node_data)))
        return result

    def violations_for_feature(self, feature_node_id: str) -> list[tuple[str, dict]]:
        """Return constraint nodes connected to this node via APPLIES_TO edges.

        Constraints are linked to the geometry/feature they affect with an
        ``APPLIES_TO`` edge (constraint -> node). We therefore inspect both
        directions to find constraint nodes touching *feature_node_id*.
        """
        result = []
        seen: set[str] = set()
        neighbors = set(self._g.successors(feature_node_id)) | set(
            self._g.predecessors(feature_node_id)
        )
        for other in neighbors:
            node_data = self._g.nodes[other]
            if node_data.get("node_type") != "constraint" or other in seen:
                continue
            # Confirm there is an APPLIES_TO edge in either direction.
            edges = []
            if self._g.has_edge(other, feature_node_id):
                edges += list(self._g[other][feature_node_id].values())
            if self._g.has_edge(feature_node_id, other):
                edges += list(self._g[feature_node_id][other].values())
            if any(e.get("edge_type") == EdgeType.APPLIES_TO.value for e in edges):
                result.append((other, dict(node_data)))
                seen.add(other)
        return result

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full MGG to a plain dict (JSON-ready)."""
        nodes = []
        for nid, data in self._g.nodes(data=True):
            nodes.append({"id": nid, "data": dict(data)})

        links = []
        for u, v, key, data in self._g.edges(data=True, keys=True):
            links.append({"source": u, "target": v, "key": key, "data": dict(data)})

        return {
            "$schema": "omim-mgg-v0.1.0",
            "omim_mgg_version": "v0.1.0",
            "metadata": self.metadata.model_dump(),
            "nodes": nodes,
            "links": links,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManufacturingGeometryGraph:
        """Reconstruct an MGG from a serialized dict."""
        metadata = GraphMetadata(**data["metadata"])
        mgg = cls(metadata)

        for node in data.get("nodes", []):
            if "data" in node:
                # New format: {"id": ..., "data": {...}}
                nid = node["id"]
                mgg._g.add_node(nid, **node["data"])
            else:
                # Legacy format: {"id": ..., **flat_data}
                node_copy = dict(node)
                nid = node_copy.pop("id")
                mgg._g.add_node(nid, **node_copy)

        # Support both "links" (new) and "edges" (legacy) keys
        edge_list = data.get("links", data.get("edges", []))
        for edge in edge_list:
            if "data" in edge:
                # New format: {"source": ..., "target": ..., "key": ..., "data": {...}}
                src = edge["source"]
                tgt = edge["target"]
                mgg._g.add_edge(src, tgt, **edge["data"])
            else:
                # Legacy format: {"source": ..., "target": ..., **flat_data}
                edge_copy = dict(edge)
                src = edge_copy.pop("source")
                tgt = edge_copy.pop("target")
                mgg._g.add_edge(src, tgt, **edge_copy)

        return mgg

    @classmethod
    def from_json(cls, json_str: str) -> ManufacturingGeometryGraph:
        return cls.from_dict(json.loads(json_str))

    # ------------------------------------------------------------------
    # Copy
    # ------------------------------------------------------------------

    def copy(self) -> ManufacturingGeometryGraph:
        new = ManufacturingGeometryGraph(self.metadata.model_copy(deep=True))
        new._g = copy.deepcopy(self._g)
        return new

    def __repr__(self) -> str:
        return (
            f"ManufacturingGeometryGraph("
            f"nodes={self.node_count}, "
            f"edges={self.edge_count}, "
            f"graph_id={self.metadata.graph_id!r})"
        )
