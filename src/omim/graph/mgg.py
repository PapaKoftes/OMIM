"""Manufacturing Geometry Graph — the canonical OMIM representation.

An MGG is a NetworkX MultiDiGraph where:
  - Nodes are GeometryNode | FeatureNode | ConstraintNode
  - Edges carry an EdgeType and optional metadata
  - GraphMetadata tracks provenance and summary statistics
"""

from __future__ import annotations

import copy
import json
from typing import Any, Iterator

import networkx as nx

from omim.graph.models import (
    ConstraintNode,
    EdgeType,
    FeatureNode,
    GeometryNode,
    GraphMetadata,
)


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

    def add_constraint_node(self, node: ConstraintNode) -> None:
        self._g.add_node(node.node_id, **node.model_dump())
        self.metadata.constraint_node_count = len(list(self.constraint_nodes()))

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        if node_id in self._g:
            return dict(self._g.nodes[node_id])
        return None

    def has_node(self, node_id: str) -> bool:
        return node_id in self._g

    def geometry_nodes(self) -> Iterator[tuple[str, dict[str, Any]]]:
        for nid, data in self._g.nodes(data=True):
            if data.get("node_type") == "geometry":
                yield nid, data

    def feature_nodes(self) -> Iterator[tuple[str, dict[str, Any]]]:
        for nid, data in self._g.nodes(data=True):
            if data.get("node_type") == "feature":
                yield nid, data

    def constraint_nodes(self) -> Iterator[tuple[str, dict[str, Any]]]:
        for nid, data in self._g.nodes(data=True):
            if data.get("node_type") == "constraint":
                yield nid, data

    # ------------------------------------------------------------------
    # Edge helpers
    # ------------------------------------------------------------------

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: EdgeType,
        **attrs: Any,
    ) -> int:
        """Add a typed edge, returning the edge key."""
        key = self._g.add_edge(source, target, edge_type=edge_type.value, **attrs)
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
        # Also check successors (COMPOSES is geometry → feature)
        for succ in self._g.successors(geometry_node_id):
            for _key, data in self._g[geometry_node_id][succ].items():
                if data.get("edge_type") == EdgeType.COMPOSES.value:
                    node_data = self._g.nodes[succ]
                    if node_data.get("node_type") == "feature":
                        result.append((succ, dict(node_data)))
        return result

    def violations_for_feature(self, feature_node_id: str) -> list[tuple[str, dict]]:
        """Return constraint nodes connected via VIOLATES edges."""
        result = []
        for succ in self._g.successors(feature_node_id):
            for _key, data in self._g[feature_node_id][succ].items():
                if data.get("edge_type") == EdgeType.VIOLATES.value:
                    node_data = self._g.nodes[succ]
                    if node_data.get("node_type") == "constraint":
                        result.append((succ, dict(node_data)))
        return result

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full MGG to a plain dict (JSON-ready)."""
        nodes = []
        for nid, data in self._g.nodes(data=True):
            nodes.append({"id": nid, **data})

        edges = []
        for u, v, data in self._g.edges(data=True):
            edges.append({"source": u, "target": v, **data})

        return {
            "metadata": self.metadata.model_dump(),
            "nodes": nodes,
            "edges": edges,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManufacturingGeometryGraph:
        """Reconstruct an MGG from a serialized dict."""
        metadata = GraphMetadata(**data["metadata"])
        mgg = cls(metadata)

        for node in data.get("nodes", []):
            node_copy = dict(node)
            nid = node_copy.pop("id")
            mgg._g.add_node(nid, **node_copy)

        for edge in data.get("edges", []):
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
