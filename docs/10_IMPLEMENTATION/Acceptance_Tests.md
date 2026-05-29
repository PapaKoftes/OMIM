# Acceptance Tests

Version: v0.1.0  
Section: 10_IMPLEMENTATION  

See also: [[10_IMPLEMENTATION/Definition_of_Done]], [[10_IMPLEMENTATION/CI_Validation_Strategy]]

---

## Mandatory Test Fixtures

These DXF files must exist in `tests/fixtures/` before any acceptance tests can run:

| Filename | Description | Expected Outcome |
|---------|-------------|-----------------|
| `simple_panel.dxf` | 400×400 panel + 4 circles at valid positions | All rules pass |
| `panel_with_open_contour.dxf` | LWPOLYLINE with 0.5mm gap at endpoints | GEO-001 ERROR |
| `panel_with_edge_violation.dxf` | Circle at (3, 50) on 400×400 panel | MFG-001 ERROR |
| `panel_with_close_holes.dxf` | Two 10mm circles with centers 8mm apart | MFG-002 ERROR |
| `panel_no_boundary.dxf` | Circles only; no explicit panel boundary | Parser infers boundary |
| `panel_shelf_pins.dxf` | 8 circles at 5mm diam, 32mm spacing | SHELF_PIN_HOLE classification |
| `panel_hinge_cups.dxf` | Two 35mm circles at 22.5mm from edge | HINGE_CUP_HOLE classification |
| `panel_with_pocket.dxf` | Closed LWPOLYLINE interior (pocket) | POCKET classification |
| `panel_inches.dxf` | Same geometry in inch units | units_converted warning; correct mm |
| `panel_corrupt.dxf` | Corrupt file (invalid DXF bytes) | ParseResult(success=False) |
| `panel_self_intersect.dxf` | Self-intersecting LWPOLYLINE profile | GEO-002 ERROR |
| `panel_narrow_pocket.dxf` | Pocket narrower than 7.2mm | MFG-004 ERROR |

These fixtures are the minimum. Synthetic generator provides the larger test corpus.

---

## Parser Acceptance Tests

```python
def test_parser_circle_extraction():
    """Parser extracts circles with correct center and radius."""
    result = parser.parse("fixtures/simple_panel.dxf")
    circles = [e for e in result.geometry.entities if e.entity_type == "CIRCLE"]
    assert len(circles) == 4
    assert all(e.centroid is not None for e in circles)
    assert all(e.radius_mm > 0 for e in circles)

def test_parser_units_normalization():
    """Parser converts inches to mm when $INSUNITS=1."""
    result = parser.parse("fixtures/panel_inches.dxf")
    assert result.geometry.units_normalized_to == "mm"
    assert any(w.warning_code == "units_converted" for w in result.geometry.warnings)

def test_parser_handles_malformed_dxf():
    """Parser returns ParseResult with error code, not stack trace."""
    result = parser.parse("fixtures/panel_corrupt.dxf")
    assert result.success == False
    assert result.errors[0].error_code == "DXF_CORRUPT"
    assert result.geometry is None

def test_parser_preserves_entity_handle():
    """Parser stores ezdxf entity handle in RawEntity.ezdxf_handle."""
    result = parser.parse("fixtures/simple_panel.dxf")
    circles = [e for e in result.geometry.entities if e.entity_type == "CIRCLE"]
    assert all(e.ezdxf_handle is not None for e in circles)
    assert all(len(e.ezdxf_handle) > 0 for e in circles)

def test_parser_layer_classification():
    """DRILL layer circles get inferred_layer_type='drill'."""
    result = parser.parse("fixtures/panel_shelf_pins.dxf")
    drill_circles = [e for e in result.geometry.entities 
                     if e.entity_type == "CIRCLE" and e.layer.upper().startswith("DRILL")]
    assert all(e.inferred_layer_type == "drill" for e in drill_circles)
```

---

## MGG Acceptance Tests

```python
def test_mgg_builds_from_geometry():
    """MGG builder creates GeometryNode for every RawEntity."""
    result = parser.parse("fixtures/simple_panel.dxf")
    mgg = builder.build(result.geometry)
    entity_count = len(result.geometry.entities)
    node_count = len(list(mgg.query().get_geometry_nodes()))
    assert node_count == entity_count

def test_mgg_roundtrip():
    """MGG serializes to JSON and deserializes back identically."""
    mgg = build_mgg("fixtures/simple_panel.dxf")
    json_data = mgg.to_json()
    mgg2 = ManufacturingGeometryGraph.from_json(json_data)
    assert mgg.metadata.graph_id == mgg2.metadata.graph_id
    assert len(mgg.query().get_all_nodes()) == len(mgg2.query().get_all_nodes())

def test_mgg_contains_edges():
    """Panel boundary CONTAINS all interior geometry nodes."""
    mgg = build_mgg("fixtures/simple_panel.dxf")
    boundary_node = mgg.query().get_panel_boundary_node()
    interior_nodes = [n for n in mgg.query().get_geometry_nodes() if n != boundary_node]
    for node in interior_nodes:
        edges = mgg.query().get_edges(boundary_node.node_id, "CONTAINS")
        assert any(e.target_id == node.node_id for e in edges)

def test_mgg_provenance_on_all_nodes():
    """Every node in built MGG has non-null provenance."""
    mgg = build_mgg("fixtures/simple_panel.dxf")
    violations = audit_provenance(mgg)
    assert violations == []

def test_mgg_same_row_detection():
    """3 circles at same Y coordinate get SAME_ROW edges."""
    mgg = build_mgg("fixtures/panel_shelf_pins.dxf")
    same_row_edges = list(mgg.query().get_edges_by_type("SAME_ROW"))
    assert len(same_row_edges) > 0
```

---

## Validation Acceptance Tests

```python
def test_edge_clearance_violation_detected():
    """MFG-001: Circle at (3, 50) on 400×400 panel flagged as ERROR."""
    mgg = build_mgg("fixtures/panel_with_edge_violation.dxf")
    report = engine.validate_mgg(mgg, ruleset_version="0.1.0")
    mfg001_results = [r for r in report.layer2_results if r.rule_id == "MFG-001"]
    assert any(r.severity == "ERROR" for r in mfg001_results)
    assert report.overall_valid == False

def test_valid_panel_passes_all_rules():
    """Well-formed panel with correct spacing produces zero ERRORs."""
    mgg = build_mgg("fixtures/simple_panel.dxf")
    report = engine.validate_mgg(mgg, ruleset_version="0.1.0")
    all_results = report.layer1_results + report.layer2_results
    assert not any(r.severity == "ERROR" for r in all_results)
    assert report.overall_valid == True

def test_validation_determinism():
    """Same MGG always produces identical ValidationReport."""
    mgg = build_mgg("fixtures/simple_panel.dxf")
    report1 = engine.validate_mgg(mgg, ruleset_version="0.1.0")
    report2 = engine.validate_mgg(mgg, ruleset_version="0.1.0")
    assert report1.model_dump_json() == report2.model_dump_json()

def test_open_contour_detected():
    """GEO-001: LWPOLYLINE with gap > 0.01mm at endpoints flagged as ERROR."""
    mgg = build_mgg("fixtures/panel_with_open_contour.dxf")
    report = engine.validate_mgg(mgg, ruleset_version="0.1.0")
    geo001_results = [r for r in report.layer1_results if r.rule_id == "GEO-001"]
    assert any(r.severity == "ERROR" for r in geo001_results)

def test_overlapping_holes_detected():
    """MFG-002: Two 10mm circles with centers 8mm apart → wall = -2mm → ERROR."""
    mgg = build_mgg("fixtures/panel_with_close_holes.dxf")
    report = engine.validate_mgg(mgg, ruleset_version="0.1.0")
    mfg002_results = [r for r in report.layer2_results if r.rule_id == "MFG-002"]
    assert any(r.severity == "ERROR" for r in mfg002_results)

def test_validation_report_serializes():
    """ValidationReport.model_dump_json() produces valid JSON."""
    mgg = build_mgg("fixtures/simple_panel.dxf")
    report = engine.validate_mgg(mgg, ruleset_version="0.1.0")
    json_str = report.model_dump_json()
    parsed = json.loads(json_str)
    assert "overall_valid" in parsed
    assert "layer1_results" in parsed
```

---

## Semantic Layer Acceptance Tests

```python
def test_hinge_cup_classified_correctly():
    mgg = build_mgg("fixtures/panel_hinge_cups.dxf")
    report = engine.validate_mgg(mgg, "0.1.0")
    annotations = semantic_engine.classify(mgg, report)
    hinge_cups = [a for a in annotations.feature_annotations 
                  if a.feature_class == "HINGE_CUP_HOLE"]
    assert len(hinge_cups) == 2
    assert all(a.confidence >= 0.85 for a in hinge_cups)

def test_shelf_pin_grid_detected():
    mgg = build_mgg("fixtures/panel_shelf_pins.dxf")
    report = engine.validate_mgg(mgg, "0.1.0")
    annotations = semantic_engine.classify(mgg, report)
    shelf_pins = [a for a in annotations.feature_annotations 
                  if a.feature_class == "SHELF_PIN_HOLE"]
    assert len(shelf_pins) >= 4
    assert all(a.confidence >= 0.85 for a in shelf_pins)

def test_unknown_feature_not_fatal():
    """Unclassifiable geometry → UNKNOWN_FEATURE, not exception."""
    mgg = build_mgg_with_unknown_feature()
    report = engine.validate_mgg(mgg, "0.1.0")
    annotations = semantic_engine.classify(mgg, report)
    unknowns = [a for a in annotations.feature_annotations 
                if a.feature_class == "UNKNOWN_FEATURE"]
    assert len(unknowns) >= 1

def test_semantic_layer_does_not_mutate_mgg():
    mgg = build_mgg("fixtures/simple_panel.dxf")
    node_count_before = len(list(mgg.query().get_all_nodes()))
    report = engine.validate_mgg(mgg, "0.1.0")
    semantic_engine.classify(mgg, report)
    node_count_after = len(list(mgg.query().get_all_nodes()))
    assert node_count_before == node_count_after
```

---

## Vertical Slice Acceptance Test

```python
def test_vertical_slice():
    """Integration test: one DXF in, five schema-valid files out."""
    result = pipeline.process(
        dxf_path="fixtures/simple_panel.dxf",
        output_dir="test_output/slice_test"
    )
    assert result.success == True
    
    sample_dir = result.export_result.sample_dir
    for filename in ["geometry.dxf", "mgg.json", "validation.json", "labels.json", "provenance.json"]:
        assert os.path.exists(os.path.join(sample_dir, filename))
    
    errors = validate_sample_schema(sample_dir)
    assert errors == [], f"Schema errors: {errors}"
```
