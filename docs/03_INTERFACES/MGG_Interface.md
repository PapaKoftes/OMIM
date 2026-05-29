# MGG Builder Interface Contract

Version: v0.1.0  
Section: 03_INTERFACES  

See also: [[02_SCHEMA/MGG_Schema]], [[03_INTERFACES/Parser_Interface]]

---

## Contract

```
Input:  RawGeometry (from Parser)
Output: ManufacturingGeometryGraph
```

The MGG Builder converts parsed geometry into the canonical graph representation. It does not parse DXF and does not run validation rules.

---

## Input

```python
# RawGeometry from Parser (see Parser_Interface.md)
# Must have parse_result.success == True
```

---

## Output

```python
class ManufacturingGeometryGraph:
    metadata: GraphMetadata
    _graph: nx.MultiDiGraph
    
    # All methods return typed objects, never raw dicts
    def add_geometry_node(self, node: GeometryNode) -> None: ...
    def add_feature_node(self, node: FeatureNode) -> None: ...
    def add_operation_node(self, node: OperationNode) -> None: ...
    def add_constraint_node(self, node: ConstraintNode) -> None: ...
    def add_edge(self, edge: RelationshipEdge) -> None: ...
    def query(self) -> MGGQuery: ...
    def to_json(self) -> dict: ...
    
    @classmethod
    def from_json(cls, data: dict) -> "ManufacturingGeometryGraph": ...
```

---

## Builder Pipeline

```python
class MGGBuilder:
    def __init__(self, ontology: Ontology, provenance_tracker: ProvenanceTracker): ...
    
    def build(self, geometry: RawGeometry) -> ManufacturingGeometryGraph:
        """
        Steps:
        1. Create GeometryNode for each RawEntity
        2. Compute Shapely geometry (area, perimeter, centroid) — AUTHORITATIVE
        3. Detect panel boundary (explicit or inferred)
        4. Build CONTAINS edges (Shapely containment)
        5. Build ADJACENT_TO edges (distance threshold)
        6. Build SAME_ROW / SAME_COLUMN edges (alignment detection)
        7. Set graph metadata
        All provenance recorded via ProvenanceTracker.
        """
```

---

## Module Boundaries

| Module | Can Access | Cannot Access |
|--------|-----------|---------------|
| MGG Builder | RawGeometry, Ontology (for vocab only), ProvenanceTracker | Validation results, Semantic annotations, ML models |
| Validation Engine | MGG (read-only) | Semantic annotations |
| Semantic Layer | MGG (read-only), ValidationReport (read-only) | MGG mutation |
| ML Layer | MGG (read-only), ValidationReport (read-only) | MGG mutation |

---

## Spatial Relationship Detection Algorithms

```python
# CONTAINS
# contour_polygon.contains(entity_centroid_point)
# Buffer: 1mm inward to handle edge-on entities

# ADJACENT_TO
# center_distance <= max(diameter_A, diameter_B) * 2 + proximity_threshold_mm
# Default proximity_threshold_mm: 10.0

# SAME_ROW
# abs(centroid_A.y - centroid_B.y) <= alignment_tolerance_mm (default: 1.0mm)

# SAME_COLUMN
# abs(centroid_A.x - centroid_B.x) <= alignment_tolerance_mm (default: 1.0mm)
```

---

## Provenance at MGG Build Time

Every node created by the builder has `inference_method="deterministic"` and `confidence=1.0` because spatial relationships (containment, adjacency) are computed geometrically, not inferred heuristically.

```python
provenance = tracker.create_record(
    inference_method=InferenceMethod.DETERMINISTIC,
    confidence=1.0,
    evidence=[EvidenceItem(
        evidence_type=EvidenceType.GEOMETRIC_MEASUREMENT,
        description=f"Shapely containment: {containment_result}",
        satisfied=True
    )],
    source_entity_ids=[entity.entity_id]
)
```

---

## Acceptance Tests

```python
def test_mgg_builds_from_geometry():
    """MGG builder creates GeometryNode for every RawEntity."""

def test_mgg_roundtrip():
    """MGG serializes to JSON and deserializes back identically."""

def test_mgg_contains_edges():
    """Panel boundary CONTAINS all interior geometry nodes."""

def test_mgg_provenance_on_all_nodes():
    """Every node in built MGG has non-null provenance."""

def test_mgg_same_row_detection():
    """3 circles at same Y coordinate get SAME_ROW edges."""
```
