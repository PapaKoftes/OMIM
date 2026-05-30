"""Ingest a P&ID graph (graphml) into the core MGG.

PID2Graph and similar datasets ship `.graphml`. Since the MGG is a
``networkx.MultiDiGraph`` under the hood, ``nx.read_graphml`` loads it directly;
this adapter maps node/edge attributes onto core ``FeatureNode`` (components) and
``RelationshipEdge`` (connections), attaching HUMAN_ANNOTATED provenance (the
labels are real ground truth — Authority Level 3). No perception step is needed.

Attribute names vary by source, so a configurable ``FieldMap`` maps source
attributes onto the canonical (tag, symbol_class, connection-type) fields.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import networkx as nx

from omim.domains.pid.isa_ontology import parse_tag
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.graph.models import FeatureNode, GraphMetadata, RelationshipEdge
from omim.provenance.models import (
    EvidenceItem,
    EvidenceType,
    InferenceMethod,
    ProvenanceRecord,
    ReviewStatus,
)


@dataclass
class FieldMap:
    """Maps source graphml attribute names onto canonical fields."""

    tag_attrs: tuple[str, ...] = ("tag", "label", "text", "name")
    symbol_attrs: tuple[str, ...] = ("symbol_class", "class", "type", "category", "symbol")
    edge_type_attrs: tuple[str, ...] = ("relationship", "type", "kind", "edge_type")
    loop_attrs: tuple[str, ...] = ("loop", "loop_number", "loop_no")
    default_edge_type: str = "CONNECTED_TO"
    annotation_source: str = "external_graphml"


def _first_attr(data: dict, names: tuple[str, ...]) -> str | None:
    for n in names:
        if n in data and data[n] not in (None, ""):
            return str(data[n])
    return None


def _annotated_provenance(source_file: str, node_id: str) -> ProvenanceRecord:
    """Real labels from an external annotated corpus -> HUMAN_ANNOTATED, conf 1.0."""
    return ProvenanceRecord(
        record_id=str(uuid.uuid4()),
        pipeline_stage="pid_ingest",
        module="omim.domains.pid.ingest",
        inference_method=InferenceMethod.HUMAN_ANNOTATED,
        confidence=1.0,
        confidence_method="expert_annotation",
        evidence=[
            EvidenceItem(
                evidence_type=EvidenceType.LAYER_CONVENTION,
                description="ingested from externally annotated P&ID graph",
                node_id=node_id,
            )
        ],
        source_file=source_file,
        source_entity_ids=[node_id],
        review_status=ReviewStatus.EXPERT_REVIEWED,
    )


@dataclass
class PIDIngestResult:
    mgg: ManufacturingGeometryGraph
    component_count: int = 0
    connection_count: int = 0
    tagged_count: int = 0
    warnings: list[str] = field(default_factory=list)


def ingest_graphml(
    path: str,
    field_map: FieldMap | None = None,
) -> PIDIngestResult:
    """Load a `.graphml` P&ID into a core MGG of ComponentNodes + connections."""
    fm = field_map or FieldMap()
    g = nx.read_graphml(path)
    return ingest_nx_graph(g, source_file=path, field_map=fm)


def ingest_nx_graph(
    g: nx.Graph,
    source_file: str = "",
    field_map: FieldMap | None = None,
) -> PIDIngestResult:
    """Adapt an in-memory networkx P&ID graph into a core MGG.

    Components -> FeatureNode (feature_class = ISA symbol class; feature_label = tag).
    Connections -> RelationshipEdge (relationship_type from the source, default
    CONNECTED_TO). All provenance is HUMAN_ANNOTATED (external ground truth).
    """
    fm = field_map or FieldMap()
    meta = GraphMetadata(graph_id=f"pid-{uuid.uuid4().hex[:12]}", source_file=source_file)
    mgg = ManufacturingGeometryGraph(meta)
    warnings: list[str] = []
    tagged = 0

    for nid, data in g.nodes(data=True):
        node_id = str(nid)
        tag = _first_attr(data, fm.tag_attrs)
        symbol = _first_attr(data, fm.symbol_attrs)
        loop = _first_attr(data, fm.loop_attrs)

        feature_class = symbol or "UNKNOWN_INSTRUMENT"
        if tag:
            tagged += 1
            parsed = parse_tag(tag)
            if symbol is None and parsed.valid:
                feature_class = parsed.symbol_class
            if loop is None and parsed.loop_number:
                loop = parsed.loop_number

        node = FeatureNode(
            node_id=node_id,
            feature_class=feature_class,
            feature_label=tag or "",
            group_id=loop,
            evidence=[{"source_attrs": {k: str(v) for k, v in data.items()}}],
            provenance=_annotated_provenance(source_file, node_id),
        )
        mgg.add_feature_node(node)

    connection_count = 0
    for u, v, data in g.edges(data=True):
        rel = _first_attr(data, fm.edge_type_attrs) or fm.default_edge_type
        edge = RelationshipEdge(
            edge_id=f"e-{uuid.uuid4().hex[:10]}",
            source_id=str(u),
            target_id=str(v),
            relationship_type=rel,
            confidence=1.0,
            metadata={k: str(val) for k, val in data.items()},
            provenance=_annotated_provenance(source_file, f"{u}->{v}"),
        )
        mgg.add_edge(edge)
        connection_count += 1

    return PIDIngestResult(
        mgg=mgg,
        component_count=mgg.metadata.feature_node_count,
        connection_count=connection_count,
        tagged_count=tagged,
        warnings=warnings,
    )
