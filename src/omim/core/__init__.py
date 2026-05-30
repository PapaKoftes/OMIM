"""omim.core — the domain-agnostic core API surface.

This package does NOT move any files. It re-exports the modules that are
independent of any one engineering domain (graph, provenance, validation
contracts, integrity), so that domain adapters (``omim.domains.panel``,
``omim.domains.pid``) can depend on a stable "core" boundary.

The split is conceptual: anything importable from here is reusable across
domains; domain-specific logic lives under ``omim.domains.*``. A future
physical reorganization can move the underlying files behind these names
without changing consumers.
"""

from omim.graph.builder import MGGBuilder
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.graph.models import (
    ConstraintNode,
    EdgeType,
    FeatureNode,
    GeometryNode,
    GraphMetadata,
    OperationNode,
    RelationshipEdge,
)
from omim.integrity import check_graph_integrity, check_ontology_consistency
from omim.provenance.models import (
    EvidenceItem,
    EvidenceType,
    InferenceMethod,
    ProvenanceRecord,
    ReviewStatus,
)
from omim.provenance.tracker import ProvenanceTracker
from omim.validation.models import Rule, RuleResult, ValidationReport

__all__ = [
    # graph
    "ManufacturingGeometryGraph",
    "MGGBuilder",
    "GraphMetadata",
    "EdgeType",
    "GeometryNode",
    "FeatureNode",
    "OperationNode",
    "ConstraintNode",
    "RelationshipEdge",
    # provenance
    "ProvenanceTracker",
    "ProvenanceRecord",
    "InferenceMethod",
    "EvidenceItem",
    "EvidenceType",
    "ReviewStatus",
    # validation contracts
    "Rule",
    "RuleResult",
    "ValidationReport",
    # integrity
    "check_graph_integrity",
    "check_ontology_consistency",
]
