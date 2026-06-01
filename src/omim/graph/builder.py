"""MGGBuilder -- converts RawGeometry into a ManufacturingGeometryGraph.

Pipeline: RawGeometry -> GeometryNodes -> Shapely enrichment -> panel detection
          -> CONTAINS -> ADJACENT_TO -> SAME_ROW -> SAME_COLUMN -> MGG
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from shapely.geometry import Point, Polygon

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.graph.models import EdgeType, GeometryNode, GraphMetadata
from omim.parser.models import RawEntity, RawGeometry
from omim.provenance.models import InferenceMethod
from omim.provenance.tracker import ProvenanceTracker

logger = logging.getLogger(__name__)


class MGGBuilder:
    """Build a ManufacturingGeometryGraph from parsed DXF geometry."""

    def __init__(
        self,
        ontology: object | None = None,
        provenance_tracker: ProvenanceTracker | None = None,
    ) -> None:
        self.ontology = ontology
        self.provenance_tracker = provenance_tracker

    def build(
        self,
        raw: RawGeometry,
        *,
        creation_timestamp: str | None = None,
    ) -> ManufacturingGeometryGraph:
        # Derive graph_id deterministically from the source file hash. This is
        # both reproducible (same bytes -> same id) and sensible for the live
        # one-off path (the same file always maps to the same graph id). The
        # hash already has a "sha256:" prefix; take the last 12 hex chars.
        digest = raw.source_file_hash.split(":")[-1]
        graph_id = f"mgg-{digest[:12]}" if digest else "mgg-unknown"

        # creation_timestamp is INJECTABLE so the synthetic generator can pin a
        # fixed constant for byte-reproducible artifacts. The live path leaves
        # it None and gets a real wall-clock timestamp.
        if creation_timestamp is None:
            creation_timestamp = datetime.now(UTC).isoformat()

        metadata = GraphMetadata(
            graph_id=graph_id,
            source_file=raw.source_file,
            source_file_hash=raw.source_file_hash,
            creation_timestamp=creation_timestamp,
        )

        mgg = ManufacturingGeometryGraph(metadata)

        # Create a provenance tracker for the build if one was not provided
        tracker = self.provenance_tracker or ProvenanceTracker(
            stage="graph_builder",
            module="omim.graph.builder",
            source_file=raw.source_file,
            source_file_hash=raw.source_file_hash,
        )

        # Phase 1: Create geometry nodes with Shapely enrichment
        for entity in raw.entities:
            geom_node = self._entity_to_geometry_node(
                entity, raw, tracker, creation_timestamp
            )
            mgg.add_geometry_node(geom_node)

        # Phase 2: Detect panel boundary
        self._detect_panel_boundary(mgg, raw, metadata)

        # Phase 3: Build CONTAINS edges (Shapely containment)
        self._build_contains_edges(mgg)

        # Phase 4: Build ADJACENT_TO edges (spatial proximity)
        self._build_adjacency_edges(mgg)

        # Phase 5: Build SAME_ROW edges (collinear horizontal)
        self._build_same_row_edges(mgg)

        # Phase 6: Build SAME_COLUMN edges (collinear vertical)
        self._build_same_column_edges(mgg)

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
        self,
        entity: RawEntity,
        raw: RawGeometry,
        tracker: ProvenanceTracker,
        creation_timestamp: str,
    ) -> GeometryNode:
        node_id = f"geom-{entity.entity_id}"
        geom_type = entity.entity_type.lower()

        # Properties already computed at parse time by the parser
        bounding_box = entity.bounding_box
        area = entity.area_mm2
        perimeter = entity.perimeter_mm
        centroid = list(entity.centroid) if entity.centroid else None
        diameter = entity.diameter_mm
        radius = entity.radius_mm

        # Create provenance record (DETERMINISTIC, confidence=1.0)
        provenance = tracker.create_record(
            inference_method=InferenceMethod.DETERMINISTIC,
            confidence=1.0,
            source_entity_ids=[entity.entity_id],
            confidence_method="geometric_computation",
        )
        # The tracker stamps a random record_id and a wall-clock timestamp,
        # which would make mgg.json non-reproducible. Overwrite them with
        # values DERIVED from the (deterministic) entity id and the injected
        # creation_timestamp. The tracker itself is left untouched so the live
        # one-off pipeline keeps its real uuid/now provenance.
        provenance.record_id = f"prov-{node_id}"
        provenance.timestamp = creation_timestamp

        return GeometryNode(
            node_id=node_id,
            geometry_type=geom_type,
            layer=entity.layer,
            inferred_layer_type=entity.inferred_layer_type,
            coordinates=entity.coordinates,
            is_closed=entity.is_closed,
            bounding_box=bounding_box,
            area_mm2=round(area, 4) if area is not None else None,
            perimeter_mm=round(perimeter, 4) if perimeter is not None else None,
            centroid=centroid,
            diameter_mm=round(diameter, 4) if diameter is not None else None,
            radius_mm=round(radius, 4) if radius is not None else None,
            depth_mm=entity.depth_mm,
            depth_source=entity.depth_source,
            elevation_z=entity.elevation_z,
            is_approximated=entity.is_approximated,
            is_outer_boundary=False,
            source_entity_id=entity.entity_id,
            source_file=raw.source_file,
            source_file_hash=raw.source_file_hash,
            provenance=provenance,
        )

    def _detect_panel_boundary(
        self,
        mgg: ManufacturingGeometryGraph,
        raw: RawGeometry,
        metadata: GraphMetadata,
    ) -> None:
        """Mark the panel boundary node and update metadata dimensions."""
        if raw.panel_boundary is not None:
            boundary_id = f"geom-{raw.panel_boundary.entity_id}"
            node_data = mgg.get_node(boundary_id)
            if node_data:
                mgg.graph.nodes[boundary_id]["is_outer_boundary"] = True
                bbox = node_data.get("bounding_box")
                if bbox:
                    xmin, ymin, xmax, ymax = bbox
                    metadata.panel_bbox = list(bbox)
                    metadata.panel_width_mm = xmax - xmin
                    metadata.panel_height_mm = ymax - ymin
            elif raw.panel_boundary.bounding_box:
                # Panel boundary was inferred (no matching entity node)
                bbox = raw.panel_boundary.bounding_box
                xmin, ymin, xmax, ymax = bbox
                metadata.panel_bbox = list(bbox)
                metadata.panel_width_mm = xmax - xmin
                metadata.panel_height_mm = ymax - ymin

    def _build_contains_edges(self, mgg: ManufacturingGeometryGraph) -> None:
        """Add CONTAINS edges: panel polygon contains entity centroid with 1mm inward buffer."""
        # Find the panel boundary
        panel_id: str | None = None
        panel_points: list | None = None
        for nid, data in mgg.geometry_nodes():
            if data.get("is_outer_boundary"):
                panel_id = nid
                coords = data.get("coordinates", [])
                # Polyline coordinates are [[x,y], ...]
                if coords and isinstance(coords[0], list):
                    panel_points = [tuple(p) for p in coords]
                break

        if panel_id is None or panel_points is None or len(panel_points) < 3:
            return

        # Build a Shapely polygon from the panel boundary and buffer inward 1mm
        panel_polygon = Polygon(panel_points).buffer(-1.0)
        if panel_polygon.is_empty:
            return

        for nid, data in mgg.geometry_nodes():
            if nid == panel_id:
                continue
            centroid = data.get("centroid")
            if centroid is None:
                continue
            pt = Point(centroid[0], centroid[1])
            if panel_polygon.contains(pt):
                mgg.add_edge(panel_id, nid, EdgeType.CONTAINS)

    def _build_adjacency_edges(self, mgg: ManufacturingGeometryGraph) -> None:
        """Add ADJACENT_TO edges between geometry nodes based on proximity.

        Threshold: center_distance <= max(dia_A, dia_B) * 2 + 10.0 mm
        Excludes the panel boundary.
        """
        nodes = [
            (nid, data)
            for nid, data in mgg.geometry_nodes()
            if not data.get("is_outer_boundary") and data.get("centroid")
        ]

        for i, (id_a, data_a) in enumerate(nodes):
            cx_a, cy_a = data_a["centroid"]
            dia_a = data_a.get("diameter_mm") or 0.0
            for id_b, data_b in nodes[i + 1 :]:
                cx_b, cy_b = data_b["centroid"]
                dia_b = data_b.get("diameter_mm") or 0.0
                dist = ((cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2) ** 0.5
                threshold = max(dia_a, dia_b) * 2 + 10.0
                if dist <= threshold:
                    mgg.add_edge(
                        id_a,
                        id_b,
                        EdgeType.ADJACENT_TO,
                        distance_mm=round(dist, 4),
                    )

    def _build_same_row_edges(self, mgg: ManufacturingGeometryGraph) -> None:
        """Add SAME_ROW edges: abs(centroid_A.y - centroid_B.y) <= 1.0 mm.

        Excludes the panel boundary.
        """
        nodes = [
            (nid, data)
            for nid, data in mgg.geometry_nodes()
            if not data.get("is_outer_boundary") and data.get("centroid")
        ]

        for i, (id_a, data_a) in enumerate(nodes):
            cy_a = data_a["centroid"][1]
            for id_b, data_b in nodes[i + 1 :]:
                cy_b = data_b["centroid"][1]
                if abs(cy_a - cy_b) <= 1.0:
                    mgg.add_edge(id_a, id_b, EdgeType.SAME_ROW)

    def _build_same_column_edges(self, mgg: ManufacturingGeometryGraph) -> None:
        """Add SAME_COLUMN edges: abs(centroid_A.x - centroid_B.x) <= 1.0 mm.

        Excludes the panel boundary.
        """
        nodes = [
            (nid, data)
            for nid, data in mgg.geometry_nodes()
            if not data.get("is_outer_boundary") and data.get("centroid")
        ]

        for i, (id_a, data_a) in enumerate(nodes):
            cx_a = data_a["centroid"][0]
            for id_b, data_b in nodes[i + 1 :]:
                cx_b = data_b["centroid"][0]
                if abs(cx_a - cx_b) <= 1.0:
                    mgg.add_edge(id_a, id_b, EdgeType.SAME_COLUMN)
