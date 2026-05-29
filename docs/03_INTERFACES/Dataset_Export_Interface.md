# Dataset Export Interface Contract

Version: v0.1.0  
Section: 03_INTERFACES  

See also: [[02_SCHEMA/Canonical_Sample_Schema]], [[02_SCHEMA/Provenance_Schema]], [[07_SYNTHETIC_GENERATION/Sample_Generation_Flow]]

---

## Contract

```
Input:  ManufacturingGeometryGraph + ValidationReport + SemanticAnnotations + source DXF path
Output: SampleDirectory (5 files on disk)
```

The dataset exporter serializes a fully-processed panel sample to the canonical on-disk format. It does not generate geometry and does not run validation.

---

## Input

```python
class ExportRequest(BaseModel):
    mgg: ManufacturingGeometryGraph
    validation_report: ValidationReport
    semantic_annotations: SemanticAnnotations
    source_dxf_path: str            # original DXF file path
    output_dir: str                 # where to write the sample directory
    sample_id: str | None = None    # auto-generated UUID if None
    split: str = "train"            # "train" | "val" | "test"
```

---

## Output: Sample Directory

```
{output_dir}/{sample_id}/
├── geometry.dxf        # copy of source DXF (unchanged)
├── mgg.json            # serialized ManufacturingGeometryGraph
├── validation.json     # serialized ValidationReport
├── labels.json         # ground-truth labels for benchmark tasks
└── provenance.json     # pipeline provenance record
```

See [[02_SCHEMA/Canonical_Sample_Schema]] for complete field specifications.

---

## Exporter Interface

```python
class DatasetExporter:
    def __init__(self, output_root: str, schema_version: str = "0.1.0"):
        self.output_root = output_root
        self.schema_version = schema_version
    
    def export(self, request: ExportRequest) -> ExportResult:
        """
        Write all 5 sample files to disk.
        Validates output with validate_sample_schema() before returning.
        Raises ExportValidationError if schema check fails.
        """
    
    def export_batch(self, requests: list[ExportRequest]) -> list[ExportResult]:
        """Export multiple samples; collects all errors before raising."""
    
    def validate_export(self, sample_dir: str) -> list[str]:
        """Run validate_sample_schema(); return list of errors (empty = valid)."""
```

---

## ExportResult

```python
class ExportResult(BaseModel):
    success: bool
    sample_id: str
    sample_dir: str
    files_written: list[str]
    schema_valid: bool
    errors: list[str]
    export_time_ms: float
```

---

## Labels Generation

The exporter derives `labels.json` from `SemanticAnnotations`. This is the ground-truth file consumed by benchmark tasks.

```python
def build_labels(
    mgg: ManufacturingGeometryGraph,
    annotations: SemanticAnnotations,
    validation_report: ValidationReport
) -> dict:
    return {
        "schema_version": "0.1.0",
        "sample_id": mgg.metadata.graph_id,
        "is_valid": validation_report.overall_valid,
        "panel_width_mm": mgg.metadata.panel_width_mm,
        "panel_height_mm": mgg.metadata.panel_height_mm,
        "panel_thickness_mm": mgg.metadata.panel_thickness_mm,
        "feature_count": len(annotations.feature_annotations),
        "features": [
            {
                "node_id": ann.node_id,
                "feature_class": ann.feature_class,
                "confidence": ann.confidence,
                "operation": FEATURE_TO_OPERATIONS.get(ann.feature_class, [])
            }
            for ann in annotations.feature_annotations
        ],
        "validation_errors": [
            r.rule_id for r in validation_report.layer1_results + validation_report.layer2_results
            if r.severity == "ERROR"
        ],
        "split": request.split,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
```

---

## Provenance File Generation

```python
def build_provenance_file(
    mgg: ManufacturingGeometryGraph,
    validation_report: ValidationReport,
    annotations: SemanticAnnotations
) -> dict:
    return {
        "schema_version": "0.1.0",
        "sample_id": mgg.metadata.graph_id,
        "pipeline_stages": [
            {
                "stage": "parsing",
                "parser_version": mgg.metadata.parser_version,
                "source_file_hash": mgg.metadata.source_file_hash,
                "timestamp": mgg.metadata.created_at
            },
            {
                "stage": "mgg_build",
                "mgg_builder_version": "0.1.0",
                "node_count": mgg.metadata.node_count,
                "edge_count": mgg.metadata.edge_count
            },
            {
                "stage": "validation",
                "ruleset_version": validation_report.ruleset_version,
                "validation_time_ms": validation_report.validation_time_ms
            },
            {
                "stage": "semantic_annotation",
                "ontology_version": annotations.ontology_version,
                "coverage_ratio": annotations.coverage_ratio,
                "annotation_time_ms": annotations.annotation_time_ms
            }
        ],
        "is_synthetic": mgg.metadata.is_synthetic,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
```

---

## Failure Handling

| Failure | Behavior |
|---------|---------|
| Output directory not writable | Raise `ExportIOError` — fatal for that sample |
| `validate_sample_schema()` fails | Raise `ExportValidationError` with list of failures — do not write partial sample |
| DXF source file not found | Raise `ExportIOError` — fatal |
| Batch partial failure | Collect all errors; raise `BatchExportError` with per-sample results |

**Atomic writes**: All 5 files are written to a temp directory first, then moved atomically. A failed export never leaves a partial sample on disk.

---

## Acceptance Tests

```python
def test_export_writes_five_files():
    """ExportRequest produces exactly 5 files in output directory."""

def test_export_validates_schema():
    """Exported sample passes validate_sample_schema() with no errors."""

def test_export_labels_match_annotations():
    """labels.json feature list matches SemanticAnnotations exactly."""

def test_export_atomic():
    """If export fails mid-write, no partial files remain in output_dir."""

def test_batch_export_collects_errors():
    """Batch with one bad sample reports all errors, succeeds for valid samples."""

def test_provenance_file_has_all_stages():
    """provenance.json contains entries for parsing, mgg_build, validation, semantic_annotation."""
```
