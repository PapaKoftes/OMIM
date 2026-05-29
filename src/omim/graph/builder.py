"""MGGBuilder — converts RawGeometry into a ManufacturingGeometryGraph.

Pipeline: RawGeometry → GeometryNodes → Shapely enrichment → panel detection → MGG
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from shapely.geometry import LinearRing, LineString, Point, Polygon

from omim.graph.models import EdgeType, GeometryNode, GraphMetadata
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.parser.models import RawEntity, RawGeometry

logger = logging.getLogger(__name__)


class MGGBuilder:
    """Build a ManufacturingGeometryGraph from parsed DXF geometry."""

    def build(self, raw: RawGeometry) -> ManufacturingGeometryGraph:
        graph_id = f"mgg-{uuid.uuid4().hex[:12]}"

        metadata = GraphMetadata(
            graph_id=graph_id,
            source_file=raw.source_file,
            source_file_hash=raw.source_file_hash,
            creation_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        mgg = ManufacturingGeometryGraph(metadata)

        # Phase 1: Create geometry nodes with Shapely enrichment
        for entity in raw.entities:
            geom_node = self._entity_to_geometry_node(entity, raw)
            mgg.add_geometry_node(geom_node)

        # Phase 2: Mark panel boundary
        if raw.panel_boundary_detected and raw.panel_boundary_entity_id:
            boundary_id = f"geom-{raw.panel_boundary_entity_id}"
            node_data = mgg.get_node(boundary_id)
            if node_data:
                # Update the node in-place
                mgg.graph.nodes[boundary_id]["is_outer_boundary"] = True
                bbox = node_data.get("bbox")
                if bbox:
                    xmin, ymin, xmax, ymax = bbox
                    metadata.panel_bbox = tuple(bbox)
                    metadata.panel_width_mm = xmax - xmin
                    metadata.panel_height_mm = ymax - ymin

        # Phase 3: Build ADJACENT_TO edges (spatial proximity)
        self._build_adjacency_edges(mgg)

        logger.info(
            "Built MGG %s: %d nodes, %d edges",
            graph_id,
            mgg.node_count,
            mgg.edge_count,
        )

        return mgg

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _entity_to_geometry_node(
        self, entity: RawEntity, raw: RawGeometry
    ) -> GeometryNode:
        node_id = f"geom-{entity.entity_id}"
        geom_type = entity.entity_type.lower()

        # Compute Shapely-derived properties
        bbox = entity.bbox
        area = None
        perimeter = None
        centroid = None
        diameter = None
        radius = None

        if entity.entity_type == "CIRCLE" and entity.center and entity.radius_mm:
            cx, cy = entity.center
            r = entity.radius_mm
            shape = Point(cx, cy).buffer(r, resolution=64)
            area = shape.area
            perimeter = shape.length
            centroid = (cx, cy)
            diameter = r * 2
            radius = r

        elif entity.entity_type in ("LWPOLYLINE", "LINE") and entity.points:
            pts = entity.points
            if entity.is_closed and len(pts) >= 3:
                ring = LinearRing(pts)
                shape = Polygon(ring)
                area = shape.area
                perimeter = ring.length
                c = shape.centroid
                centroid = (c.x, c.y)
            elif len(pts) >= 2:
                line = LineString(pts)
                perimeter = line.length
                c = line.centroid
                centroid = (c.x, c.y)

        elif entity.entity_type == "ARC" and entity.center and entity.radius_mm:
            cx, cy = entity.center
            centroid = (cx, cy)
            radius = entity.radius_mm
            diameter = radius * 2

        coordinates: list = []
        if entity.entity_type == "CIRCLE" and entity.center and entity.radius_mm:
            coordinates = [entity.center[0], entity.center[1], entity.radius_mm]
        elif entity.points:
            coordinates = [list(p) for p in entity.points]
        elif entity.center:
            coordinates = [entity.center[0], entity.center[1]]

        return GeometryNode(
            node_id=node_id,
            geometry_type=geom_type,
            layer=entity.layer,
            inferred_layer_type=entity.inferred_layer_type,
            coordinates=coordinates,
            is_closed=entity.is_closed,
            bbox=bbox,
            area_mm2=round(area, 4) if area is not None else None,
            perimeter_mm=round(perimeter, 4) if perimeter is not None else None,
            centroid=centroid,
            diameter_mm=round(diameter, 4) if diameter is not None else None,
            radius_mm=round(radius, 4) if radius is not None else None,
            is_outer_boundary=False,
            source_entity_id=entity.entity_id,
            source_file=raw.source_file,
            source_file_hash=raw.source_file_hash,
        )

    def _build_adjacency_edges(
        self,
        mgg: ManufacturingGeometryGraph,
        threshold_mm: float = 5.0,
    ) -> None:
        """Add ADJACENT_TO edges between geometry nodes whose centroids
        are within *threshold_mm* of each other (excluding the panel boundary)."""
        nodes = [
            (nid, data)
            for nid, data in mgg.geometry_nodes()
            if not data.get("is_outer_boundary") and data.get("centroid")
        ]

        for i, (id_a, data_a) in enumerate(nodes):
            cx_a, cy_a = data_a["centroid"]
            for id_b, data_b in nodes[i + 1 :]:
                cx_b, cy_b = data_b["centroid"]
                dist = ((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2) ** 0.5
                if dist <= threshold_mm:
                    mgg.add_edge(
                        id_a,
                        id_b,
                        EdgeType.ADJACENT_TO,
                        distance_mm=round(dist, 4),
                    )
