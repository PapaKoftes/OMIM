"""MGGQuery -- typed query interface for ManufacturingGeometryGraph.

Wraps an MGG and provides convenient, typed accessors for common
graph queries without exposing the raw NetworkX API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omim.graph.models import EdgeType

if TYPE_CHECKING:
    from omim.graph.mgg import ManufacturingGeometryGraph


class MGGQuery:
    """Read-only query facade over a :class:`ManufacturingGeometryGraph`."""

    def __init__(self, mgg: ManufacturingGeometryGraph) -> None:
        self._mgg = mgg

    # ------------------------------------------------------------------
    # All-node accessors
    # ------------------------------------------------------------------

    def get_all_nodes(self) -> list[tuple[str, dict]]:
        """Return every node as ``(node_id, data)`` pairs."""
        return list(self._mgg.graph.nodes(data=True))

    def get_geometry_nodes(self) -> list[tuple[str, dict]]:
        """Return all geometry nodes."""
        return list(self._mgg.geometry_nodes())

    def get_feature_nodes(self) -> list[tuple[str, dict]]:
        """Return all feature nodes."""
        return list(self._mgg.feature_nodes())

    def get_operation_nodes(self) -> list[tuple[str, dict]]:
        """Return all operation nodes."""
        return list(self._mgg.operation_nodes())

    def get_constraint_nodes(self) -> list[tuple[str, dict]]:
        """Return all constraint nodes."""
        return list(self._mgg.constraint_nodes())

    # ------------------------------------------------------------------
    # Geometry filters
    # ------------------------------------------------------------------

    def get_by_entity_type(self, entity_type: str) -> list[tuple[str, dict]]:
        """Return geometry nodes whose ``geometry_type`` matches *entity_type* (case-insensitive)."""
        et = entity_type.lower()
        return [
            (nid, data)
            for nid, data in self._mgg.geometry_nodes()
            if data.get("geometry_type", "").lower() == et
        ]

    def get_panel_boundary(self) -> dict | None:
        """Return the data dict for the panel boundary geometry node, or ``None``."""
        for _nid, data in self._mgg.geometry_nodes():
            if data.get("is_outer_boundary"):
                return data
        return None

    def get_panel_boundary_node(self) -> tuple[str, dict] | None:
        """Return ``(node_id, data)`` for the panel boundary, or ``None``."""
        for nid, data in self._mgg.geometry_nodes():
            if data.get("is_outer_boundary"):
                return (nid, data)
        return None

    def get_interior_nodes(self) -> list[tuple[str, dict]]:
        """Return geometry nodes that are *not* the outer boundary."""
        return [
            (nid, data)
            for nid, data in self._mgg.geometry_nodes()
            if not data.get("is_outer_boundary")
        ]

    def get_interior_closed_contours(self) -> list[tuple[str, dict]]:
        """Return closed, non-boundary geometry nodes."""
        return [
            (nid, data)
            for nid, data in self._mgg.geometry_nodes()
            if data.get("is_closed") and not data.get("is_outer_boundary")
        ]

    # ------------------------------------------------------------------
    # Feature filters
    # ------------------------------------------------------------------

    def get_features_by_class(self, feature_class: str) -> list[tuple[str, dict]]:
        """Return feature nodes whose ``feature_class`` matches (case-insensitive)."""
        fc = feature_class.upper()
        return [
            (nid, data)
            for nid, data in self._mgg.feature_nodes()
            if data.get("feature_class", "").upper() == fc
        ]

    def get_features_by_confidence(self, min_confidence: float) -> list[tuple[str, dict]]:
        """Return feature nodes with ``confidence >= min_confidence``."""
        return [
            (nid, data)
            for nid, data in self._mgg.feature_nodes()
            if data.get("confidence", 0.0) >= min_confidence
        ]

    def get_feature_groups(self) -> dict[str, list[tuple[str, dict]]]:
        """Return a dict mapping ``group_id`` to the list of feature nodes in that group.

        Feature nodes without a ``group_id`` are omitted.
        """
        groups: dict[str, list[tuple[str, dict]]] = {}
        for nid, data in self._mgg.feature_nodes():
            gid = data.get("group_id")
            if gid is not None:
                groups.setdefault(gid, []).append((nid, data))
        return groups

    # ------------------------------------------------------------------
    # Cross-type lookups
    # ------------------------------------------------------------------

    def get_geometry_for_feature(self, feature_id: str) -> list[tuple[str, dict]]:
        """Return geometry nodes linked to *feature_id* via COMPOSES edges."""
        result: list[tuple[str, dict]] = []
        g = self._mgg.graph
        if feature_id not in g:
            return result
        # COMPOSES goes geometry -> feature; check predecessors
        for pred in g.predecessors(feature_id):
            for _key, edata in g[pred][feature_id].items():
                if edata.get("edge_type") == EdgeType.COMPOSES.value:
                    ndata = g.nodes[pred]
                    if ndata.get("node_type") == "geometry":
                        result.append((pred, dict(ndata)))
        # Also check successors in case edge direction varies
        for succ in g.successors(feature_id):
            for _key, edata in g[feature_id][succ].items():
                if edata.get("edge_type") == EdgeType.COMPOSES.value:
                    ndata = g.nodes[succ]
                    if ndata.get("node_type") == "geometry":
                        result.append((succ, dict(ndata)))
        return result

    def get_features_for_geometry(self, geometry_id: str) -> list[tuple[str, dict]]:
        """Return feature nodes linked to *geometry_id* via COMPOSES edges."""
        return self._mgg.features_for_geometry(geometry_id)

    # ------------------------------------------------------------------
    # Edge queries
    # ------------------------------------------------------------------

    def get_edges_by_type(self, edge_type: str) -> list[tuple[str, str, dict]]:
        """Return edges whose ``edge_type`` value matches *edge_type*."""
        return [
            (u, v, d)
            for u, v, d in self._mgg.graph.edges(data=True)
            if d.get("edge_type") == edge_type
        ]

    def get_edges_from(self, node_id: str) -> list[tuple[str, str, dict]]:
        """Return all outgoing edges from *node_id*."""
        g = self._mgg.graph
        if node_id not in g:
            return []
        return [
            (node_id, v, dict(d))
            for v in g.successors(node_id)
            for _key, d in g[node_id][v].items()
        ]

    def get_edges_to(self, node_id: str) -> list[tuple[str, str, dict]]:
        """Return all incoming edges to *node_id*."""
        g = self._mgg.graph
        if node_id not in g:
            return []
        return [
            (u, node_id, dict(d))
            for u in g.predecessors(node_id)
            for _key, d in g[u][node_id].items()
        ]

    # ------------------------------------------------------------------
    # Node by ID
    # ------------------------------------------------------------------

    def get_node_by_id(self, node_id: str) -> dict | None:
        """Return the data dict for *node_id*, or ``None``."""
        return self._mgg.get_node(node_id)

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def get_conflicts(self) -> list[tuple[str, str]]:
        """Return ``(source, target)`` pairs for all CONFLICTS_WITH edges."""
        return [
            (u, v)
            for u, v, d in self._mgg.graph.edges(data=True)
            if d.get("edge_type") == EdgeType.CONFLICTS_WITH.value
        ]
