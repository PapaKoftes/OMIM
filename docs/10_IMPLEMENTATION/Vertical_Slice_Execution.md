# Vertical Slice Execution

Version: v0.1.0  
Section: 10_IMPLEMENTATION  

See also: [[10_IMPLEMENTATION/Hackathon_Execution_Order]], [[10_IMPLEMENTATION/Definition_of_Done]], [[10_IMPLEMENTATION/Acceptance_Tests]]

---

## The Minimum Viable Slice

The vertical slice is the thinnest path through the entire system that produces a complete, schema-valid sample. Everything beyond this slice is optional until the slice works end-to-end.

```
DXF file → Parser → MGG Builder → Validation Engine → Export
                                                          ↓
                                                  sample_dir/
                                                  ├── geometry.dxf
                                                  ├── mgg.json
                                                  ├── validation.json
                                                  ├── labels.json (minimal)
                                                  └── provenance.json
```

**The slice is done when this test passes:**

```python
def test_vertical_slice():
    """One DXF in → five valid files out."""
    result = pipeline.process("fixtures/simple_panel.dxf", output_dir="test_output")
    
    assert result.success == True
    assert os.path.exists("test_output/sample_001/geometry.dxf")
    assert os.path.exists("test_output/sample_001/mgg.json")
    assert os.path.exists("test_output/sample_001/validation.json")
    assert os.path.exists("test_output/sample_001/labels.json")
    assert os.path.exists("test_output/sample_001/provenance.json")
    
    errors = validate_sample_schema("test_output/sample_001")
    assert errors == []
```

---

## Build Order Invariant

```
Parser BEFORE MGG Builder
MGG Builder BEFORE Validation Engine
Validation Engine BEFORE Semantic Layer
Semantic Layer BEFORE Dataset Export
```

This is not a preference — it is an architectural law. Building these out of order will require rework.

---

## Allowed vs. Forbidden During Slice Implementation

### Allowed

```python
# Hardcode configuration during slice — make it configurable later
RULES_DIR = "data/rules/"
OUTPUT_DIR = "output/"

# Return minimal/stub implementations as placeholders
def execute_layer2(mgg):
    return []  # Stub: implement MFG rules after slice works

# Use dataclasses instead of Pydantic during initial prototyping
@dataclass
class GeometryNode:  # Upgrade to Pydantic after slice works
    ...
```

### Forbidden

```python
# FORBIDDEN: Build the semantic layer before the slice works
# (Semantic layer requires working MGG + validation — build those first)

# FORBIDDEN: Optimize performance during the slice
# Profile later; get it working first

# FORBIDDEN: Add features not needed for the slice
# No multi-panel processing until single-panel slice passes

# FORBIDDEN: Add error handling beyond what prevents crashes
# Structured error handling comes after the slice
```

---

## Anti-Perfectionism Gate

If you spend more than 2 hours on any single component before the slice works end-to-end, stop and ask:

1. Can I hardcode this value to unblock the slice?
2. Can I return a stub that satisfies the interface contract?
3. Is this component actually required for the minimum slice?

The slice unblocks everything. Perfect components before the slice are a trap.

---

## Slice Verification Fixtures

The slice must pass against these fixtures (minimum required):

| Fixture | What It Tests |
|---------|--------------|
| `simple_panel.dxf` | Minimal valid: one rectangle + 4 circles |
| `panel_with_violations.dxf` | Invalid: circles too close to edge |
| `panel_no_boundary.dxf` | No explicit boundary; infer from bounding box |

See [[10_IMPLEMENTATION/Acceptance_Tests]] for complete fixture list.

---

## Post-Slice Additions (In Order)

Once the slice passes:

1. Implement all Layer 1 rules (GEO-001 to GEO-006)
2. Implement all Layer 2 rules (MFG-001 to MFG-010)
3. Implement semantic inference engine
4. Implement synthetic generator
5. Implement batch processing
6. Implement benchmark evaluation script
7. Optimize performance (if needed — profile first)
