# Manufacturing Geometry Graph (MGG) Schema

**Schema Version: v0.1.0**

Version: v0.1.0  
Section: 02_SCHEMA  

See also: [[02_SCHEMA/Canonical_Sample_Schema]], [[04_ONTOLOGY/Manufacturing_Ontology]], [[08_PROVENANCE_AND_CONFIDENCE/Provenance_System]]

---

## Purpose

The MGG is OMIM's canonical representation layer. It is the single data structure through which geometry, features, operations, constraints, relationships, and provenance are all represented.

---

## Minimalism Gate

**The MGG earns complexity by being needed, not by being possible.**

v0.1 MGG must contain ONLY:
- Geometry nodes (raw geometry)
- Feature nodes (semantic labels)
- Adjacency/containment edges (spatial relationships)
- Operation nodes (inferred machining operations)
- Constraint nodes (rule violations only)

Do NOT add until proven necessary: temporal sequence graphs, symbolic reasoning nodes, assembly relationship nodes.

---

## Implementation

```python
import networkx as nx

class ManufacturingGeometryGraph:
    """Wraps NetworkX MultiDiGraph with typed node/edge access."""
    
    def __init__(self):
        self._graph = nx.MultiDiGraph()
        self.metadata: GraphMetadata = None
    
    def add_geometry_node(self, node: GeometryNode) -> None: ...
    def add_feature_node(self, node: FeatureNode) -> None: ...
    def add_operation_node(self, node: OperationNode) -> None: ...
    def add_constraint_node(self, node: ConstraintNode) -> None: ...
    def add_edge(self, edge: RelationshipEdge) -> None: ...
    def query(self) -> MGGQuery: ...
    def to_json(self) -> dict: ...
    
    @classmethod
    def from_json(cls, data: dict) -> "ManufacturingGeometryGraph": ...
    
    def to_pyg_data(self) -> "torch_geometric.data.Data": ...
```

---

## Node Types

### GeometryNode
```python
class GeometryNode(BaseModel):
    node_id: str
    node_type: Literal["geometry"] = "geometry"
    geometry_type: str              # "circle" | "polyline" | "arc" | "line" | "contour"
    layer: str
    inferred_layer_type: str        # "cut" | "drill" | "pocket" | "engrave" | "unknown"
    coordinates: list               # circle: [cx,cy,r]; polyline: [[x,y],...]; arc: [cx,cy,r,start,end]
    is_closed: bool
    bounding_box: list[float]       # [xmin, ymin, xmax, ymax]
    area_mm2: float | None
    perimeter_mm: float | None
    centroid: list[float]           # [cx, cy]
    diameter_mm: float | None
    radius_mm: float | None
    is_outer_boundary: bool | None
    contains_node_ids: list[str]
    source_entity_id: str           # ezdxf entity handle
    source_file: str
    source_file_hash: str           # SHA256
    creation_method: Literal["parsed"] = "parsed"
    provenance: ProvenanceRecord    # REQUIRED, not Optional
```

### FeatureNode
```python
class FeatureNode(BaseModel):
    node_id: str
    node_type: Literal["feature"] = "feature"
    feature_class: str              # From ontology v0.1.0
    feature_label: str
    feature_category: str           # "HOLE_FEATURES" | "MILLED_FEATURES" | "PROFILE_FEATURES"
    confidence: float               # [0.0, 1.0]
    hypotheses: list[FeatureHypothesis]
    diameter_mm: float | None
    depth_mm: float | None
    width_mm: float | None
    length_mm: float | None
    position_mm: list[float]        # [x, y]
    inference_method: str           # "deterministic" | "heuristic" | "ml_gnn"
    evidence: list[EvidenceItem]
    geometry_node_ids: list[str]
    group_id: str | None
    provenance: ProvenanceRecord    # REQUIRED

class FeatureHypothesis(BaseModel):
    feature_class: str
    confidence: float
    evidence: list[str]
```

### OperationNode
```python
class OperationNode(BaseModel):
    node_id: str
    node_type: Literal["operation"] = "operation"
    operation_type: str             # "DRILLING" | "CNC_ROUTING" | "PROFILE_CUTTING" | "NESTING"
    confidence: float
    tool_diameter_mm: float | None
    depth_mm: float | None
    tool_type: str | None
    feature_node_ids: list[str]
    provenance: ProvenanceRecord
```

### ConstraintNode
```python
class ConstraintNode(BaseModel):
    node_id: str
    node_type: Literal["constraint"] = "constraint"
    constraint_type: str
    constraint_value: float
    constraint_unit: str            # "mm" | "ratio" | "degrees"
    is_violated: bool
    violation_severity: str | None  # "ERROR" | "WARNING"
    applies_to_node_ids: list[str]
    rule_id: str
    provenance: ProvenanceRecord
```

---

## Edge Types

```python
class RelationshipEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    relationship_type: str
    confidence: float = 1.0
    weight: float | None
    metadata: dict = {}
    provenance: ProvenanceRecord
```

| edge_type | Source | Target | Det? | Description |
|-----------|--------|--------|------|-------------|
| CONTAINS | GeometryNode (contour) | GeometryNode | Yes | Contour geometrically contains entity |
| COMPOSES | GeometryNode | FeatureNode | Yes | Geometry is part of this feature |
| PRODUCES | OperationNode | FeatureNode | Heuristic | Operation produces this feature |
| DEPENDS_ON | OperationNode | OperationNode | Heuristic | Op A must run before Op B |
| CONFLICTS_WITH | FeatureNode | FeatureNode | Yes | Spatial conflict or rule violation |
| ADJACENT_TO | GeometryNode | GeometryNode | Yes | Within proximity threshold |
| REQUIRES_TOOLING | FeatureNode | OperationNode | Heuristic | Feature requires specific tooling |
| SAME_GROUP | FeatureNode | FeatureNode | Heuristic | Logical grouping |
| SAME_ROW | FeatureNode | FeatureNode | Det | Collinear (horizontal) |
| SAME_COLUMN | FeatureNode | FeatureNode | Det | Collinear (vertical) |
| APPLIES_TO | ConstraintNode | GeometryNode | Yes | Constraint applies here |

---

## Serialization (JSON)

```json
{
  "$schema": "omim-mgg-v0.1.0",
  "omim_mgg_version": "v0.1.0",
  "metadata": {
    "graph_id": "UUID",
    "spec_version": "v0.1.0",
    "ontology_version": "v0.1.0",
    "source_file": "geometry.dxf",
    "source_file_hash": "sha256:...",
    "geometry_node_count": 12,
    "feature_node_count": 11,
    "operation_node_count": 3,
    "constraint_node_count": 0,
    "edge_count": 28,
    "creation_timestamp": "2026-05-30T14:23:05Z",
    "parser_version": "omim-v0.1.0"
  },
  "nodes": [{"id": "...", "data": {...}}],
  "links": [{"source": "...", "target": "...", "key": "...", "data": {...}}]
}
```

### Roundtrip Guarantee

```python
def test_mgg_roundtrip(mgg):
    """mgg_from_json(mgg_to_json(mgg)) == mgg — required acceptance test."""
    json_data = mgg.to_json()
    mgg2 = ManufacturingGeometryGraph.from_json(json_data)
    assert json.dumps(mgg.to_json(), sort_keys=True) == json.dumps(mgg2.to_json(), sort_keys=True)
```

---

## Spatial Relationship Detection

```python
# CONTAINS: Shapely containment
# contour_polygon.contains(entity_centroid_point)
# Tolerance: 1mm inward buffer

# ADJACENT_TO: distance threshold
# center_distance <= max(dia_A, dia_B) * 2 + 10.0mm

# SAME_ROW: horizontal alignment
# abs(centroid_A.y - centroid_B.y) <= 1.0mm

# SAME_COLUMN: vertical alignment
# abs(centroid_A.x - centroid_B.x) <= 1.0mm
```

---

## Full MGGQuery API

```python
class MGGQuery:
    def __init__(self, mgg: ManufacturingGeometryGraph): ...

    # Node access by type
    def get_all_nodes(self) -> list[MGGNode]: ...
    def get_geometry_nodes(self) -> list[GeometryNode]: ...
    def get_feature_nodes(self) -> list[FeatureNode]: ...
    def get_operation_nodes(self) -> list[OperationNode]: ...
    def get_constraint_nodes(self) -> list[ConstraintNode]: ...

    # Geometry queries
    def get_by_type(self, entity_types: list[str]) -> list[GeometryNode]: ...
    def get_by_entity_type(self, entity_type: str) -> list[GeometryNode]: ...
    def get_panel_boundary_node(self) -> GeometryNode: ...
    def get_panel_boundary(self) -> GeometryNode: ...        # alias
    def get_interior_nodes(self) -> list[GeometryNode]: ...  # non-boundary nodes
    def get_interior_closed_contours(self) -> list[GeometryNode]: ...
    def get_outer_contours(self) -> list[GeometryNode]: ...
    def get_interior_contours(self) -> list[GeometryNode]: ...
    def get_by_role(self, role: str) -> list[GeometryNode]: ...  # e.g. "panel_boundary"

    # Feature queries
    def get_features_by_class(self, feature_class: str) -> list[FeatureNode]: ...
    def get_features_by_confidence(self, min_confidence: float) -> list[FeatureNode]: ...
    def get_feature_groups(self) -> dict[str, list[FeatureNode]]: ...
    def get_geometry_for_feature(self, feature_id: str) -> list[GeometryNode]: ...
    def get_features_for_geometry(self, geometry_id: str) -> list[FeatureNode]: ...
    def get_adjacent_features(self, feature_id: str, max_distance_mm: float) -> list[FeatureNode]: ...

    # Edge queries
    def get_all_edges(self) -> list[RelationshipEdge]: ...
    def get_edges(self, source_id: str, edge_type: str) -> list[RelationshipEdge]: ...
    def get_edges_by_type(self, edge_type: str) -> list[RelationshipEdge]: ...
    def get_edges_from(self, node_id: str) -> list[RelationshipEdge]: ...
    def get_edges_to(self, node_id: str) -> list[RelationshipEdge]: ...
    def get_conflicts(self) -> list[tuple[str, str]]: ...

    # Node lookup
    def get_node_by_id(self, node_id: str) -> MGGNode | None: ...
```

---

## Design Principles

1. **Immutability after construction**: Once built from a DXF, the geometry layer of an MGG should not change. Semantic annotations are additive — they overlay the geometry layer without modifying it.
2. **Layered annotation**: Geometry nodes exist first; feature/operation nodes are overlaid second; semantic annotations are a third layer. Never merge layers.
3. **Explicit provenance**: Every node records how it was created. No anonymous nodes.
4. **Typed edges**: No unlabeled edges. Every edge has a `relationship_type` from the ontology.
5. **Confidence-aware**: Every non-deterministic node has `confidence` in [0.0, 1.0].
6. **Serializable**: `mgg.to_json()` → `ManufacturingGeometryGraph.from_json()` is lossless.

---

## Future Extensions (Not v0)

- `VolumetricGeometryNode`: 3D geometry for 5-axis support
- `SimulationResultNode`: Attach simulation outputs to features
- `MachineNode`: Machine-specific constraints
- `OperationSequenceGraph`: Explicit operation scheduling
- `MaterialNode`: Material properties per panel

### NestingNode (v0.2 Extension)

Panel manufacturing is inseparable from nesting — placing multiple panels onto a sheet to maximize material utilization. This is a known v0.1 gap, documented here rather than pretended away.

```python
class NestingNode(BaseModel):
    """Represents a nesting sheet and the panels placed on it."""
    node_id: str
    node_type: Literal["nesting"] = "nesting"
    sheet_dimensions_mm: list[float]     # [width, height]
    sheet_material: str
    placed_panel_ids: list[str]          # MGG graph IDs of placed panels
    placement_positions: list[dict]      # [{"panel_id": ..., "x": ..., "y": ..., "rotation": ...}]
    material_utilization_pct: float      # (total panel area / sheet area) × 100

# v0.2 edge types added with NestingNode:
# PLACED_ON  — PanelGeometryNode → NestingNode: panel placed on this sheet
# SAME_SHEET — PanelGeometryNode → PanelGeometryNode: two panels share a setup
```

**Why this matters**: Nesting affects operation grouping (panels on the same sheet share a setup), toolpath ordering, cutting direction, and manufacturing cost. Without nesting, OMIM can classify features but cannot reason about the manufacturing batch. This is a deliberate v0.2 deferral — not an oversight.

**Nesting tool references**: OpenNest, SVGnest, DeepNest.
