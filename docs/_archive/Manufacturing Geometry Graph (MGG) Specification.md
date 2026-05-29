# Manufacturing Geometry Graph (MGG) Specification

Version: v0.1.0  

See also: [[Manufacturing Ontology]], [[Full System Architecture]], [[Provenence and Uncertainty]]

---

## Purpose

The Manufacturing Geometry Graph (MGG) is the canonical representation layer of OMIM. It is the single data structure through which:
- Geometry is represented
- Features are attached
- Operations are linked
- Constraints are encoded
- Relationships are made explicit
- Provenance is tracked
- Confidence is stored

Everything in the system either produces an MGG or consumes one.

---

## MGG Minimalism Gate

**Warning**: The MGG can become a premature abstraction trap. Many manufacturing tasks are solvable with structured feature tables + spatial relationships. The graph should earn its complexity.

**v0.1 MGG must contain ONLY:**
- Geometry nodes (raw geometry)
- Feature nodes (semantic labels)
- Adjacency/containment edges (spatial relationships)
- Operation nodes (inferred machining operations)
- Constraint nodes (rule violations only)

**Do NOT add until proven necessary by a real use case:**
- Temporal sequence graphs
- Symbolic reasoning nodes
- Full ontology reasoning edges
- Abstract planning layers
- Assembly relationship nodes

The test: if you can accomplish the benchmark task without a graph feature, don't add it. The graph earns nodes and edge types by being needed, not by being possible.

---

## Design Principles

1. **Immutability after construction**: Once built from a DXF, the geometry layer of an MGG should not change. Semantic annotations are additive.
2. **Layered annotation**: Geometry nodes exist first; feature/operation nodes are overlaid second; semantic annotations are a third layer.
3. **Explicit provenance**: Every node records how it was created.
4. **Typed edges**: No unlabeled edges. Every edge has a `relationship_type` from the ontology.
5. **Confidence-aware**: Every non-deterministic node has `confidence` in [0.0, 1.0].
6. **Serializable**: MGG → JSON → MGG is lossless.

---

## Graph Structure

The MGG is a directed attributed multigraph:
- **Directed**: Edges have source and target (relationships are directional)
- **Attributed**: Nodes and edges carry structured metadata
- **Multigraph**: Multiple edges of different types can connect the same two nodes

Implementation: `networkx.MultiDiGraph`

---

## Node Types

### GeometryNode

Represents raw geometry extracted from the DXF. This layer is authoritative and deterministic.

```python
class GeometryNode(BaseModel):
    node_id: str                    # UUID, stable for given DXF entity
    node_type: Literal["geometry"] = "geometry"
    
    # Geometry
    geometry_type: str              # "circle" | "polyline" | "arc" | "line" | "contour"
    layer: str                      # DXF layer name
    inferred_layer_type: str        # "cut" | "drill" | "pocket" | "engrave" | "unknown"
    
    # Coordinates (geometry-type dependent)
    coordinates: list               # circle: [cx, cy, r]; polyline: [[x,y],...]; arc: [cx,cy,r,start_angle,end_angle]
    is_closed: bool
    
    # Derived geometry (computed by Shapely, authoritative)
    bounding_box: list[float]       # [xmin, ymin, xmax, ymax]
    area_mm2: float | None          # None for open geometries
    perimeter_mm: float | None
    centroid: list[float]           # [cx, cy]
    
    # For circles only
    diameter_mm: float | None
    radius_mm: float | None
    
    # For contours only
    is_outer_boundary: bool | None  # True if this is the outermost contour
    contains_node_ids: list[str]    # IDs of geometry nodes contained within this contour
    
    # Provenance
    source_entity_id: str           # ezdxf entity handle
    source_file: str
    source_file_hash: str           # SHA256
    creation_method: Literal["parsed"] = "parsed"
    provenance: ProvenanceRecord
```

### FeatureNode

Represents an inferred manufacturing feature (e.g., a shelf pin hole, a groove). Attached to one or more GeometryNodes.

```python
class FeatureNode(BaseModel):
    node_id: str                    # UUID
    node_type: Literal["feature"] = "feature"
    
    # Ontology reference
    feature_class: str              # ID from ontology (e.g., "SHELF_PIN_HOLE")
    feature_label: str              # Human-readable (e.g., "Shelf Pin Hole")
    feature_category: str           # "HOLE_FEATURES" | "MILLED_FEATURES" | "PROFILE_FEATURES"
    
    # Confidence and alternatives
    confidence: float               # Primary hypothesis confidence [0.0, 1.0]
    hypotheses: list[FeatureHypothesis]  # All ranked hypotheses
    
    # Physical parameters (inferred or deterministic)
    diameter_mm: float | None
    depth_mm: float | None
    width_mm: float | None
    length_mm: float | None
    position_mm: list[float]        # [x, y] centroid in panel coordinates
    
    # Inference metadata
    inference_method: str           # "deterministic" | "heuristic" | "ml_gnn" | "ml_llm"
    evidence: list[EvidenceItem]
    
    # Links
    geometry_node_ids: list[str]    # Geometry nodes that compose this feature
    group_id: str | None            # If part of a feature group (e.g., shelf pin row)
    
    # Provenance
    provenance: ProvenanceRecord
    ontology_version: str

class FeatureHypothesis(BaseModel):
    feature_class: str
    confidence: float
    evidence: list[str]             # Short evidence descriptions
```

### OperationNode

Represents a manufacturing operation inferred from the features.

```python
class OperationNode(BaseModel):
    node_id: str
    node_type: Literal["operation"] = "operation"
    
    # Ontology reference
    operation_type: str             # "DRILLING" | "CNC_ROUTING" | "PROFILE_CUTTING" | "NESTING"
    
    # Confidence
    confidence: float
    
    # Parameters
    tool_diameter_mm: float | None
    depth_mm: float | None
    tool_type: str | None           # "twist_drill" | "end_mill" | "v_bit" | etc.
    
    # Links
    feature_node_ids: list[str]     # Features produced by this operation
    
    # Provenance
    provenance: ProvenanceRecord
```

### ConstraintNode

Represents a manufacturing constraint (either geometric or process-based).

```python
class ConstraintNode(BaseModel):
    node_id: str
    node_type: Literal["constraint"] = "constraint"
    
    # Constraint definition
    constraint_type: str            # from ontology constraint taxonomy
    constraint_value: float         # numeric value (mm, ratio, etc.)
    constraint_unit: str            # "mm" | "ratio" | "degrees"
    
    # Context
    is_violated: bool               # True if constraint is currently violated
    violation_severity: str | None  # "ERROR" | "WARNING" if violated
    
    # Links
    applies_to_node_ids: list[str]  # nodes this constraint applies to
    rule_id: str                    # which rule generated this constraint
    
    # Provenance
    provenance: ProvenanceRecord
```

---

## Edge Types

All edges carry structured metadata. No bare untyped edges.

```python
class RelationshipEdge(BaseModel):
    edge_id: str                    # UUID
    source_id: str                  # source node ID
    target_id: str                  # target node ID
    relationship_type: str          # from ontology relationship taxonomy
    
    # Optional
    confidence: float = 1.0         # 1.0 for deterministic relationships
    weight: float | None            # for spatial/distance edges
    metadata: dict = {}
    
    # Provenance
    provenance: ProvenanceRecord
```

### Edge Type Reference

| edge_type | source | target | Deterministic? | Description |
|-----------|--------|--------|----------------|-------------|
| CONTAINS | GeometryNode (contour) | GeometryNode | Yes | Contour geometrically contains entity |
| COMPOSES | GeometryNode | FeatureNode | Yes | Geometry is part of this feature |
| PRODUCES | OperationNode | FeatureNode | Heuristic | Operation produces this feature |
| DEPENDS_ON | OperationNode | OperationNode | Heuristic | Op A must run before Op B |
| CONFLICTS_WITH | FeatureNode/GeometryNode | FeatureNode/GeometryNode | Yes | Spatial conflict or rule violation |
| ADJACENT_TO | GeometryNode | GeometryNode | Yes | Within proximity threshold |
| REQUIRES_TOOLING | FeatureNode | OperationNode | Heuristic | Feature requires specific tooling |
| SAME_GROUP | FeatureNode | FeatureNode | Heuristic | Logical grouping |
| SAME_ROW | FeatureNode | FeatureNode | Deterministic | Collinear features |
| SAME_COLUMN | FeatureNode | FeatureNode | Deterministic | Collinear features (vertical) |
| APPLIES_TO | ConstraintNode | GeometryNode/FeatureNode | Yes | Constraint applies to this node |

---

## Graph Metadata

```python
class GraphMetadata(BaseModel):
    graph_id: str                   # UUID for this MGG instance
    spec_version: str               # "v0.1.0" (this document version)
    ontology_version: str           # "v0.1.0"
    
    # Source information
    source_file: str
    source_file_hash: str           # SHA256
    part_id: str                    # Logical part identifier
    
    # Dimensions
    panel_bounding_box: list[float] | None  # [xmin, ymin, xmax, ymax] in mm
    panel_area_mm2: float | None
    
    # Statistics
    geometry_node_count: int
    feature_node_count: int
    operation_node_count: int
    constraint_node_count: int
    edge_count: int
    
    # Timestamps
    creation_timestamp: str         # ISO 8601
    parser_version: str
    
    # Provenance
    pipeline_provenance: ProvenanceRecord
```

---

## Serialization Format

The MGG serializes to JSON using NetworkX's `node_link_data` format, extended with OMIM metadata.

### JSON Schema (Top Level)

```json
{
  "omim_mgg_version": "v0.1.0",
  "metadata": { ... },              // GraphMetadata
  "nodes": [
    {
      "id": "...",                  // node_id
      "data": { ... }               // Full node object (GeometryNode | FeatureNode | OperationNode | ConstraintNode)
    }
  ],
  "links": [
    {
      "source": "...",              // source node_id
      "target": "...",              // target node_id
      "key": "...",                 // edge_id (for multigraph)
      "data": { ... }               // RelationshipEdge
    }
  ]
}
```

### Serializer Implementation

```python
# omim/graph/serializer.py

def mgg_to_json(mgg: ManufacturingGeometryGraph) -> dict:
    """Serialize MGG to JSON-compatible dict."""
    
def mgg_from_json(data: dict) -> ManufacturingGeometryGraph:
    """Deserialize MGG from JSON dict."""
    
def mgg_to_file(mgg: ManufacturingGeometryGraph, path: str) -> None:
    """Write MGG to JSON file."""
    
def mgg_from_file(path: str) -> ManufacturingGeometryGraph:
    """Load MGG from JSON file."""
```

### Roundtrip Guarantee

```python
# Test: mgg_from_json(mgg_to_json(mgg)) == mgg
# All nodes, edges, and metadata must be identical after roundtrip.
# This is a required acceptance test.
```

---

## Graph Queries

```python
# omim/graph/queries.py

class MGGQuery:
    def __init__(self, mgg: ManufacturingGeometryGraph): ...
    
    def get_geometry_nodes(self) -> list[GeometryNode]: ...
    def get_feature_nodes(self) -> list[FeatureNode]: ...
    def get_operation_nodes(self) -> list[OperationNode]: ...
    def get_constraint_nodes(self) -> list[ConstraintNode]: ...
    
    def get_features_by_class(self, feature_class: str) -> list[FeatureNode]: ...
    def get_features_by_confidence(self, min_confidence: float) -> list[FeatureNode]: ...
    
    def get_conflicts(self) -> list[tuple[str, str]]: ...
    def get_feature_groups(self) -> dict[str, list[FeatureNode]]: ...
    
    def get_geometry_for_feature(self, feature_id: str) -> list[GeometryNode]: ...
    def get_features_for_geometry(self, geometry_id: str) -> list[FeatureNode]: ...
    
    def get_adjacent_features(self, feature_id: str, max_distance_mm: float) -> list[FeatureNode]: ...
    
    def get_node_by_id(self, node_id: str) -> MGGNode | None: ...
```

---

## ManufacturingGeometryGraph Class

```python
# omim/graph/mgg.py

class ManufacturingGeometryGraph:
    """Canonical manufacturing representation.
    
    Wraps NetworkX MultiDiGraph with typed node/edge access.
    """
    
    def __init__(self):
        self._graph = nx.MultiDiGraph()
        self.metadata: GraphMetadata = None
    
    def add_geometry_node(self, node: GeometryNode) -> None: ...
    def add_feature_node(self, node: FeatureNode) -> None: ...
    def add_operation_node(self, node: OperationNode) -> None: ...
    def add_constraint_node(self, node: ConstraintNode) -> None: ...
    
    def add_edge(self, edge: RelationshipEdge) -> None: ...
    
    def get_node(self, node_id: str) -> MGGNode | None: ...
    def get_edges_from(self, node_id: str) -> list[RelationshipEdge]: ...
    def get_edges_to(self, node_id: str) -> list[RelationshipEdge]: ...
    
    def query(self) -> MGGQuery: ...
    
    def to_json(self) -> dict: ...
    
    @classmethod
    def from_json(cls, data: dict) -> "ManufacturingGeometryGraph": ...
    
    def to_pyg_data(self) -> "torch_geometric.data.Data":
        """Convert to PyTorch Geometric Data for GNN training."""
        # Returns node feature matrix X, edge index, and labels y
```

---

## Builder Pipeline

```python
# omim/graph/builder.py

class MGGBuilder:
    """Converts RawGeometry (from DXF parser) into ManufacturingGeometryGraph."""
    
    def __init__(self, ontology: Ontology, provenance_tracker: ProvenanceTracker):
        self.ontology = ontology
        self.provenance_tracker = provenance_tracker
    
    def build(self, geometry: RawGeometry) -> ManufacturingGeometryGraph:
        """
        Pipeline:
        1. Create GeometryNodes from RawEntities
        2. Compute derived geometry (area, perimeter, bounding box) using Shapely
        3. Build spatial relationships (CONTAINS, ADJACENT_TO)
        4. Identify feature candidates (initial pass)
        5. Create FeatureNodes with provisional labels
        6. Set metadata
        """
```

### Spatial Relationship Detection

```python
# CONTAINS detection
# A contour "contains" another geometry if:
#   Shapely: contour_polygon.contains(entity_centroid_point)
# Tolerance: 1mm inward buffer to handle edge cases

# ADJACENT_TO detection  
# Two features are adjacent if:
#   center_distance <= max(diameter_A, diameter_B) * 2 + proximity_threshold_mm
# Default proximity_threshold_mm: 10.0

# SAME_ROW detection
# Two features are in the same row if:
#   abs(centroid_A.y - centroid_B.y) <= alignment_tolerance_mm
# Default alignment_tolerance_mm: 1.0

# SAME_COLUMN detection
# Two features are in the same column if:
#   abs(centroid_A.x - centroid_B.x) <= alignment_tolerance_mm
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v0.1.0 | 2026-05-30 | Initial spec; panel manufacturing domain |

## Future Extensions (Not v0)

- `VolumetricGeometryNode`: 3D geometry for 5-axis support
- `SimulationResultNode`: Attach simulation outputs to features
- `MachineNode`: Represent specific machine constraints
- `OperationSequenceGraph`: Explicit operation scheduling
- `MaterialNode`: Material properties per panel

### Nesting Representation (v0.2 Extension)

Panel manufacturing is inseparable from nesting — placing multiple panels onto a sheet to maximize material utilization. This is a critical gap in v0.1 that must be addressed in v0.2.

```python
# Future: NestingNode
class NestingNode(BaseModel):
    """Represents a nesting sheet and panel placement context."""
    node_id: str
    node_type: Literal["nesting"] = "nesting"
    sheet_dimensions_mm: list[float]   # [width, height]
    sheet_material: str
    placed_panel_ids: list[str]        # panel graph IDs placed on this sheet
    placement_positions: list[dict]    # [{panel_id, x, y, rotation}]
    material_utilization_pct: float    # waste metric
    
# Future: PLACED_ON edge
# NestingNode → GeometryNode (panel outline): panel is placed on this sheet
# SAME_SHEET edge: two panels on the same sheet (affects cutting order)
```

**Why this matters**: Nesting affects operation grouping (all panels on same sheet share a setup), toolpath ordering, and manufacturing cost. Without nesting representation, OMIM can classify features but cannot reason about the manufacturing batch. This is a known gap in v0.1 — document it, don't pretend it doesn't exist.

**Tool reference**: OpenNest (https://github.com/AndrewCarterUK/simple-nesting), SVGnest (https://svgnest.com/), DeepNest (https://deepnest.io/)
