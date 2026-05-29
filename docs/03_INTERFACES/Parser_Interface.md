# Parser Interface Contract

Version: v0.1.0  
Section: 03_INTERFACES  

See also: [[02_SCHEMA/MGG_Schema]], [[05_VALIDATION/Failure_Modes]]

---

## Contract

```
Input:  DXF file path (string)
Output: RawGeometry | ParseResult (with error)
```

**The parser is the only module that reads DXF.** No other module may call ezdxf directly.

---

## Input Specification

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `filepath` | string | yes | Absolute or relative path to .dxf file |
| `config` | ParserConfig | no | Optional; defaults loaded from config |

```python
class ParserConfig(BaseModel):
    supported_dxf_versions: list[str] = ["AC1015", "AC1018", "AC1021", "AC1024", "AC1027", "AC1032"]
    max_file_size_bytes: int = 50 * 1024 * 1024  # 50MB
    target_units: str = "mm"                     # normalize to mm
    layer_conventions: dict = DEFAULT_LAYER_MAP  # CUT, DRILL, POCKET, BORDER
    spline_approximation_segments: int = 50
```

---

## Output Specification

### Success Path: `RawGeometry`

```python
class RawGeometry(BaseModel):
    source_file: str
    source_file_hash: str           # SHA256
    dxf_version: str                # e.g., "AC1024" (R2010)
    units_original: str             # "mm" | "inches" | "unknown"
    units_normalized_to: str        # always "mm"
    
    entities: list[RawEntity]
    
    # Inferred panel context
    panel_boundary: PanelBoundary | None   # None if not detected
    panel_boundary_inferred: bool          # True if from bounding box
    
    # Stats
    entity_counts: dict[str, int]   # {"CIRCLE": 8, "LWPOLYLINE": 3, ...}
    
    # Warnings (non-fatal issues)
    warnings: list[ParseWarning]
    
    # Provenance
    parse_timestamp: str
    parser_version: str


class RawEntity(BaseModel):
    entity_id: str                  # UUID
    ezdxf_handle: str               # Original ezdxf entity handle (for provenance)
    entity_type: str                # "CIRCLE" | "LWPOLYLINE" | "ARC" | "LINE" | "SPLINE"
    layer: str                      # DXF layer name (preserved verbatim)
    inferred_layer_type: str        # "cut" | "drill" | "pocket" | "engrave" | "border" | "unknown"
    
    # Geometry
    coordinates: list               # Type-dependent; see below
    is_closed: bool | None
    
    # Derived (computed by Shapely at parse time)
    bounding_box: list[float]       # [xmin, ymin, xmax, ymax] in mm
    centroid: list[float] | None    # [cx, cy] in mm
    area_mm2: float | None
    perimeter_mm: float | None
    diameter_mm: float | None       # Only for CIRCLE entities
    radius_mm: float | None
    
    is_approximated: bool           # True if SPLINE was approximated as polyline
```

### Failure Path: `ParseResult`

```python
class ParseResult(BaseModel):
    success: bool
    geometry: RawGeometry | None    # None if success=False
    errors: list[ParseError]
    warnings: list[ParseWarning]

class ParseError(BaseModel):
    error_code: str  # "DXF_NOT_FOUND" | "DXF_CORRUPT" | "DXF_VERSION_UNSUPPORTED" | "DXF_TOO_LARGE"
    message: str
    recoverable: bool

class ParseWarning(BaseModel):
    warning_code: str  # "units_converted" | "no_panel_boundary" | "no_cuttable_entities" | ...
    message: str
    entity_id: str | None
```

---

## Entity Coordinate Formats

| Entity Type | Coordinate Format | Example |
|-------------|------------------|---------|
| CIRCLE | `[cx, cy, r]` | `[50.0, 32.0, 2.5]` |
| LWPOLYLINE | `[[x1,y1], [x2,y2], ...]` | `[[0,0],[800,0],[800,600],[0,600]]` |
| LINE | `[[x1,y1], [x2,y2]]` | `[[10.0, 0.0], [50.0, 0.0]]` |
| ARC | `[cx, cy, r, start_angle_deg, end_angle_deg]` | `[30.0, 30.0, 5.0, 0, 90]` |
| SPLINE | `[[x1,y1], ...]` (approximated) | same as polyline |

All coordinates are in **mm**, normalized from source units.

---

## Supported Entity Types

| Priority | Entity | Processing |
|----------|--------|-----------|
| P0 | LWPOLYLINE | Full support; most common panel outline entity |
| P0 | CIRCLE | Full support; holes |
| P0 | ARC | Full support; corner radii |
| P1 | LINE | Full support; individual edges |
| P1 | POLYLINE | Full support; legacy polylines |
| P2 | SPLINE | Approximated as polyline (50 segments default) |
| SKIP | TEXT | Annotation; not included |
| SKIP | DIMENSION | Annotation; not included |
| SKIP | HATCH | Fill; not included |
| SKIP | INSERT | Block reference; exploded to entities if simple |

---

## Layer Classification Convention

```yaml
layer_conventions:
  CUT: ["CUT", "CUT_", "PROFILE", "OUTLINE", "OUTER"]
  DRILL: ["DRILL", "HOLE", "BORE", "PUNCH"]
  POCKET: ["POCKET", "GROOVE", "SLOT", "DADO", "RABBET"]
  BORDER: ["BORDER", "SHEET", "STOCK", "MATERIAL"]
  ENGRAVE: ["ENGRAVE", "ETCH", "SCORE"]
  # Unknown: any layer not matching above
```

Layer matching is case-insensitive and prefix-matched.

---

## Failure Handling

| Failure | Behavior |
|---------|---------|
| File not found | Raise `FileNotFoundError` |
| DXF corrupt | Return `ParseResult(success=False, error_code="DXF_CORRUPT")` |
| DXF version unsupported | Return `ParseResult(success=False, error_code="DXF_VERSION_UNSUPPORTED")` |
| File too large (>50MB) | Return `ParseResult(success=False, error_code="DXF_TOO_LARGE")` |
| Empty DXF | Return `RawGeometry` with empty `entities`, `warning="empty_file"` |
| Inches detected | Convert to mm; add `warning="units_converted"` |
| No panel boundary | Infer from bounding box + 10mm margin; set `panel_boundary_inferred=True` |

---

## Acceptance Tests

```python
def test_parser_circle_extraction():
    """Parser extracts circles with correct center and radius."""

def test_parser_units_normalization():
    """Parser converts inches to mm when $INSUNITS=1."""

def test_parser_handles_malformed_dxf():
    """Parser returns ParseResult with error code, not stack trace."""

def test_parser_preserves_entity_handle():
    """Parser stores ezdxf entity handle in RawEntity.ezdxf_handle."""

def test_parser_layer_classification():
    """DRILL layer circles get inferred_layer_type='drill'."""
```
