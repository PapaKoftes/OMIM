"""Canonical dataset exporter — writes a fully-processed panel sample to the
frozen 5-file on-disk format.

Spec:
  - docs/03_INTERFACES/Dataset_Export_Interface.md
  - docs/02_SCHEMA/Canonical_Sample_Schema.md  (FROZEN — authoritative)

Resolved spec inconsistencies (frozen Canonical_Sample_Schema wins):
  - schema_version is "v0.1.0" (WITH v-prefix), not "0.1.0"
  - labels.json carries $schema "omim-labels-v0.1.0"
  - provenance.json carries $schema "omim-provenance-v0.1.0"

This module does NOT generate geometry and does NOT run validation; it
serializes already-computed artifacts (MGG, ValidationReport, optional
SemanticAnnotations) to disk and verifies the result against the canonical
schema validation function.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel

SCHEMA_VERSION = "v0.1.0"
ONTOLOGY_VERSION = "v0.1.0"
DATASET_VERSION = "omim-synthetic-v0.1.0"

LABELS_SCHEMA = "omim-labels-v0.1.0"
PROVENANCE_SCHEMA = "omim-provenance-v0.1.0"

SAMPLE_FILES = ["geometry.dxf", "mgg.json", "validation.json", "labels.json", "provenance.json"]

# ---------------------------------------------------------------------------
# Feature -> operation / category fallback maps
#
# The ontology singleton is the authoritative source, but it is not always
# loaded (and there is no global accessor). These maps provide a deterministic
# fallback so the exporter never fails purely because the ontology is absent.
# ---------------------------------------------------------------------------

FEATURE_TO_OPERATIONS: dict[str, list[str]] = {
    "SHELF_PIN_HOLE": ["DRILLING"],
    "HINGE_CUP_HOLE": ["DRILLING"],
    "THROUGH_HOLE": ["DRILLING"],
    "CONFIRMAT_HOLE": ["DRILLING"],
    "DOWEL_HOLE": ["DRILLING"],
    "SYSTEM_HOLE": ["DRILLING"],
    "MINIFIX_HOLE": ["DRILLING"],
    "POCKET": ["CNC_ROUTING"],
    "GROOVE": ["CNC_ROUTING"],
    "DADO": ["CNC_ROUTING"],
    "RABBET": ["CNC_ROUTING"],
    "MILLED_SLOT": ["CNC_ROUTING"],
    "PROFILE_CUT": ["PROFILE_CUTTING"],
    "PANEL_BOUNDARY": ["PROFILE_CUTTING"],
}

# Categories used to compute complexity. "milled" features are anything that
# requires routing rather than simple drilling or profile cutting.
MILLED_CATEGORIES = {"MILLED_FEATURES"}
HOLE_CATEGORIES = {"HOLE_FEATURES"}

MILLED_FEATURE_CLASSES = {
    "POCKET",
    "GROOVE",
    "DADO",
    "RABBET",
    "MILLED_SLOT",
}
HOLE_FEATURE_CLASSES = {
    "SHELF_PIN_HOLE",
    "HINGE_CUP_HOLE",
    "THROUGH_HOLE",
    "CONFIRMAT_HOLE",
    "DOWEL_HOLE",
    "SYSTEM_HOLE",
    "MINIFIX_HOLE",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ExportValidationError(Exception):
    """Raised when an exported sample fails canonical schema validation."""

    def __init__(self, errors: list[str], sample_dir: str | None = None) -> None:
        self.errors = errors
        self.sample_dir = sample_dir
        msg = f"Sample failed schema validation: {errors}"
        if sample_dir:
            msg = f"{sample_dir}: {msg}"
        super().__init__(msg)


class ExportIOError(Exception):
    """Raised on a fatal I/O problem (missing DXF, unwritable output dir)."""


class BatchExportError(Exception):
    """Raised when one or more samples in a batch fail to export."""

    def __init__(self, results: list[ExportResult]) -> None:
        self.results = results
        failed = [r for r in results if not r.success]
        super().__init__(
            f"Batch export had {len(failed)}/{len(results)} failures"
        )


# ---------------------------------------------------------------------------
# Request / result models
# ---------------------------------------------------------------------------


class ExportRequest(BaseModel):
    """A single export request.

    ``mgg`` is a ``ManufacturingGeometryGraph`` and ``validation_report`` is a
    ``ValidationReport``; they are typed as ``object`` here to avoid a circular
    import and to allow ``arbitrary_types_allowed``.
    """

    mgg: object
    validation_report: object
    semantic_annotations: object | None = None
    source_dxf_path: str
    output_dir: str
    sample_id: str | None = None
    split: str = "train"
    # Extra ground-truth from a generation spec (synthetic samples). If present
    # it is the authoritative labels.json content (feature classes etc.).
    labels_override: dict | None = None

    model_config = {"arbitrary_types_allowed": True}


class ExportResult(BaseModel):
    success: bool
    sample_id: str
    sample_dir: str
    files_written: list[str]
    schema_valid: bool
    errors: list[str]
    export_time_ms: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_dump(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _model_dump(obj: Any) -> dict:
    """Return a plain dict for a pydantic model or an already-dict object."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    raise ExportIOError(f"Cannot serialize object of type {type(obj)!r}")


def _mgg_dict(mgg: Any) -> dict:
    if hasattr(mgg, "to_dict"):
        return mgg.to_dict()
    if hasattr(mgg, "to_json"):
        return json.loads(mgg.to_json())
    raise ExportIOError("mgg object has neither to_dict() nor to_json()")


def _operations_for_feature(feature_class: str) -> list[str]:
    return FEATURE_TO_OPERATIONS.get(feature_class, [])


def _is_milled(feature_class: str, category: str = "") -> bool:
    return feature_class in MILLED_FEATURE_CLASSES or category in MILLED_CATEGORIES


def _is_hole(feature_class: str, category: str = "") -> bool:
    return feature_class in HOLE_FEATURE_CLASSES or category in HOLE_CATEGORIES


def _compute_complexity(features: list[dict]) -> str:
    """simple / medium / complex per Canonical_Sample_Schema heuristic.

    - simple:  <= 3 feature types AND <= 5 features AND no milled features
    - complex: > 5 feature types OR > 15 features OR (has holes AND has milled)
    - medium:  everything else
    """
    n_features = len(features)
    feature_types = {f.get("feature_class") for f in features}
    n_types = len(feature_types)

    has_milled = any(
        _is_milled(f.get("feature_class", ""), f.get("_category", "")) for f in features
    )
    has_holes = any(
        _is_hole(f.get("feature_class", ""), f.get("_category", "")) for f in features
    )

    if n_types > 5 or n_features > 15 or (has_holes and has_milled):
        return "complex"
    if n_types <= 3 and n_features <= 5 and not has_milled:
        return "simple"
    return "medium"


def _panel_block(mgg: Any, override_panel: dict | None = None) -> dict:
    """Build the labels.json ``panel`` block from MGG metadata + overrides."""
    meta = getattr(mgg, "metadata", None)
    width = getattr(meta, "panel_width_mm", None)
    height = getattr(meta, "panel_height_mm", None)

    panel: dict[str, Any] = {
        "width_mm": width,
        "height_mm": height,
        "thickness_mm": 18.0,
        "area_mm2": (width * height) if (width is not None and height is not None) else None,
        "material": "MDF",
    }
    if override_panel:
        panel.update({k: v for k, v in override_panel.items() if v is not None})
        # Recompute area if width/height supplied but area not explicitly given.
        if "area_mm2" not in override_panel:
            w = panel.get("width_mm")
            h = panel.get("height_mm")
            if w is not None and h is not None:
                panel["area_mm2"] = w * h
    return panel


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


def build_labels(
    mgg: Any,
    annotations: Any,
    validation_report: Any,
    split: str,
    labels_override: dict | None = None,
) -> dict:
    """Build the canonical ``labels.json`` content.

    If ``labels_override`` is provided (synthetic ground truth), its feature
    list is authoritative (ground_truth_source="synthetic_generator",
    confidence 1.0). Otherwise features are derived from
    ``semantic_annotations`` (ground_truth_source="semantic_inference").
    """
    meta = getattr(mgg, "metadata", None)
    sample_id = getattr(meta, "graph_id", None)
    overall_valid = bool(getattr(validation_report, "overall_valid", True))

    override = labels_override or {}

    # ---- Features ---------------------------------------------------------
    features: list[dict] = []
    if "features" in override:
        # Authoritative synthetic ground truth.
        for feat in override["features"]:
            f = dict(feat)
            f.setdefault("ontology_version", ONTOLOGY_VERSION)
            f.setdefault("ground_truth_source", "synthetic_generator")
            f.setdefault("confidence", 1.0)
            # Keep an internal category hint for complexity (stripped later).
            f["_category"] = f.get("feature_category", "")
            features.append(f)
    else:
        # Derive from semantic annotations.
        feature_anns = getattr(annotations, "feature_annotations", []) if annotations else []
        for i, ann in enumerate(feature_anns):
            feature_class = getattr(ann, "feature_class", None)
            node_id = getattr(ann, "node_id", None)
            confidence = getattr(ann, "confidence", 0.0)
            features.append(
                {
                    "feature_id": node_id or f"feat_{i:03d}",
                    "feature_class": feature_class,
                    "ontology_version": ONTOLOGY_VERSION,
                    "diameter_mm": None,
                    "depth_mm": None,
                    "is_through": None,
                    "position_mm": None,
                    "group_id": None,
                    "geometry_entity_id": node_id,
                    "ground_truth_source": "semantic_inference",
                    "confidence": confidence,
                    "_category": "",
                }
            )

    # ---- Feature counts & operations -------------------------------------
    feature_counts: dict[str, int] = {}
    operations: set[str] = set()
    for f in features:
        fc = f.get("feature_class")
        if fc:
            feature_counts[fc] = feature_counts.get(fc, 0) + 1
            operations.update(_operations_for_feature(fc))

    complexity = _compute_complexity(features)

    # Strip internal hint key before emitting.
    for f in features:
        f.pop("_category", None)

    labels: dict[str, Any] = {
        "$schema": LABELS_SCHEMA,
        "sample_id": override.get("sample_id", sample_id),
        "schema_version": SCHEMA_VERSION,
        "is_valid": override.get("is_valid", overall_valid),
        "injected_violations": override.get("injected_violations", []),
        "panel": _panel_block(mgg, override.get("panel")),
        "features": features,
        "feature_counts": override.get("feature_counts", feature_counts),
        "operations": override.get("operations", sorted(operations)),
        "complexity": override.get("complexity", complexity),
        "split": split,
    }
    return labels


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def build_provenance_file(
    mgg: Any,
    validation_report: Any,
    annotations: Any,
    is_synthetic: bool = False,
) -> dict:
    """Build the canonical ``provenance.json`` content."""
    meta = getattr(mgg, "metadata", None)
    sample_id = getattr(meta, "graph_id", None)
    source_file_hash = getattr(meta, "source_file_hash", None)
    ruleset_version = getattr(validation_report, "ruleset_version", SCHEMA_VERSION)

    stages: list[dict] = []

    if is_synthetic:
        stages.append(
            {
                "stage": "synthetic_generator",
                "inference_method": "synthetic",
                "confidence": 1.0,
            }
        )

    stages.append(
        {
            "stage": "parser",
            "inference_method": "deterministic",
            "confidence": 1.0,
            "source_file_hash": source_file_hash,
        }
    )
    stages.append(
        {
            "stage": "graph_builder",
            "inference_method": "deterministic",
            "confidence": 1.0,
        }
    )
    stages.append(
        {
            "stage": "validation",
            "inference_method": "deterministic",
            "confidence": 1.0,
            "ruleset_version": ruleset_version,
        }
    )

    if annotations is not None:
        # Use coverage_ratio as a coarse confidence signal when available.
        coverage = getattr(annotations, "coverage_ratio", None)
        confidence = coverage if isinstance(coverage, (int, float)) else 1.0
        stages.append(
            {
                "stage": "semantic",
                "inference_method": "heuristic",
                "confidence": confidence,
            }
        )

    return {
        "$schema": PROVENANCE_SCHEMA,
        "sample_id": sample_id,
        "schema_version": SCHEMA_VERSION,
        "pipeline_stages": stages,
        "dataset_version": DATASET_VERSION,
    }


# ---------------------------------------------------------------------------
# Schema validation (canonical — mirrors Canonical_Sample_Schema.md)
# ---------------------------------------------------------------------------


def validate_sample_schema(sample_dir: str | Path) -> list[str]:
    """Return a list of schema violations (empty list = valid).

    Mirrors the reference implementation in
    docs/02_SCHEMA/Canonical_Sample_Schema.md.
    """
    sample_dir = Path(sample_dir)
    errors: list[str] = []

    for fname in SAMPLE_FILES:
        if not (sample_dir / fname).exists():
            errors.append(f"MISSING FILE: {fname}")

    labels_path = sample_dir / "labels.json"
    if labels_path.exists():
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        if labels.get("$schema") != LABELS_SCHEMA:
            errors.append("labels.json: wrong $schema version")
        for i, feat in enumerate(labels.get("features", [])):
            for req in [
                "feature_id",
                "feature_class",
                "position_mm",
                "ground_truth_source",
                "confidence",
            ]:
                # feature_id may be supplied as node_id per spec note.
                if req == "feature_id" and ("feature_id" in feat or "node_id" in feat):
                    continue
                if req not in feat:
                    errors.append(f"features[{i}]: missing '{req}'")

    mgg_path = sample_dir / "mgg.json"
    if mgg_path.exists():
        mgg = json.loads(mgg_path.read_text(encoding="utf-8"))
        for node in mgg.get("nodes", []):
            if "provenance" not in node.get("data", {}):
                node_id = node.get("id", "?")
                errors.append(f"mgg.json node {node_id}: missing provenance")

    return errors


# ---------------------------------------------------------------------------
# Dataset-level consistency
# ---------------------------------------------------------------------------


def _load_split_ids(path: Path) -> list[str]:
    """Load sample IDs from a .jsonl split file.

    Each line is either a bare string id or a JSON object with a
    ``sample_id``/``id`` key.
    """
    if not path.exists():
        return []
    ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            ids.append(line)
            continue
        if isinstance(obj, str):
            ids.append(obj)
        elif isinstance(obj, dict):
            sid = obj.get("sample_id") or obj.get("id")
            if sid is not None:
                ids.append(sid)
    return ids


def check_dataset_consistency(dataset_dir: str | Path) -> list[str]:
    """Verify all samples in a dataset directory are schema-valid and consistent.

    Checks:
      - Train/val/test splits are disjoint (no sample in two splits)
      - Every sample validates against the canonical schema
      - Total sample count matches dataset_metadata.json statistics.total_samples
    """
    dataset_dir = Path(dataset_dir)
    violations: list[str] = []

    train_ids = set(_load_split_ids(dataset_dir / "splits" / "train.jsonl"))
    val_ids = set(_load_split_ids(dataset_dir / "splits" / "val.jsonl"))
    test_ids = set(_load_split_ids(dataset_dir / "splits" / "test.jsonl"))

    overlap = train_ids & val_ids
    if overlap:
        violations.append(f"SPLIT_OVERLAP train/val: {sorted(overlap)[:5]}...")
    overlap = train_ids & test_ids
    if overlap:
        violations.append(f"SPLIT_OVERLAP train/test: {sorted(overlap)[:5]}...")
    overlap = val_ids & test_ids
    if overlap:
        violations.append(f"SPLIT_OVERLAP val/test: {sorted(overlap)[:5]}...")

    for sample_id in train_ids | val_ids | test_ids:
        sample_errors = validate_sample_schema(dataset_dir / "samples" / sample_id)
        violations.extend(sample_errors)

    metadata_path = dataset_dir / "dataset_metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        expected_total = metadata.get("statistics", {}).get("total_samples")
        actual_total = len(train_ids) + len(val_ids) + len(test_ids)
        if expected_total is not None and expected_total != actual_total:
            violations.append(
                f"SAMPLE_COUNT_MISMATCH: metadata says {expected_total}, "
                f"splits contain {actual_total}"
            )
    else:
        violations.append("MISSING FILE: dataset_metadata.json")

    return violations


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


class DatasetExporter:
    """Writes fully-processed panel samples to the canonical 5-file format."""

    def __init__(self, output_root: str | Path, schema_version: str = SCHEMA_VERSION) -> None:
        self.output_root = Path(output_root)
        self.schema_version = schema_version

    # -- single export ------------------------------------------------------

    def export(self, request: ExportRequest) -> ExportResult:
        start = time.perf_counter()

        sample_id = request.sample_id or str(uuid.uuid4())

        # output_dir is the directory under which {sample_id}/ is created.
        base_dir = Path(request.output_dir) if request.output_dir else self.output_root
        sample_dir = base_dir / sample_id

        source_dxf = Path(request.source_dxf_path)
        if not source_dxf.exists():
            raise ExportIOError(f"Source DXF not found: {source_dxf}")

        is_synthetic = request.labels_override is not None

        # Build all file contents up front (cheap, no I/O).
        try:
            mgg_data = _mgg_dict(request.mgg)
            validation_data = _model_dump(request.validation_report)
            labels_data = build_labels(
                request.mgg,
                request.semantic_annotations,
                request.validation_report,
                request.split,
                request.labels_override,
            )
            provenance_data = build_provenance_file(
                request.mgg,
                request.validation_report,
                request.semantic_annotations,
                is_synthetic=is_synthetic,
            )
        except ExportIOError:
            raise
        except Exception as exc:  # noqa: BLE001 — surface as IO error per contract
            raise ExportIOError(f"Failed to assemble sample content: {exc}") from exc

        # ---- ATOMIC WRITE -------------------------------------------------
        # Write everything to a sibling temp dir, validate, then move into
        # place. A failed export never leaves a partial sample behind.
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ExportIOError(f"Output directory not writable: {base_dir} ({exc})") from exc

        tmp_dir = base_dir / f".{sample_id}.tmp"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

        try:
            tmp_dir.mkdir(parents=True, exist_ok=False)

            shutil.copy(source_dxf, tmp_dir / "geometry.dxf")
            (tmp_dir / "mgg.json").write_text(_json_dump(mgg_data), encoding="utf-8")
            (tmp_dir / "validation.json").write_text(
                _json_dump(validation_data), encoding="utf-8"
            )
            (tmp_dir / "labels.json").write_text(_json_dump(labels_data), encoding="utf-8")
            (tmp_dir / "provenance.json").write_text(
                _json_dump(provenance_data), encoding="utf-8"
            )

            # Validate the temp directory before committing.
            errors = validate_sample_schema(tmp_dir)
            schema_valid = len(errors) == 0
            if not schema_valid:
                raise ExportValidationError(errors, sample_dir=str(sample_dir))

            # Commit: replace any existing sample dir atomically-ish.
            if sample_dir.exists():
                shutil.rmtree(sample_dir)
            tmp_dir.replace(sample_dir)
        except ExportValidationError:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
        except OSError as exc:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ExportIOError(f"Failed writing sample {sample_id}: {exc}") from exc
        finally:
            # Defensive: never leave the temp dir around.
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        files_written = [str(sample_dir / f) for f in SAMPLE_FILES]

        return ExportResult(
            success=True,
            sample_id=sample_id,
            sample_dir=str(sample_dir),
            files_written=files_written,
            schema_valid=True,
            errors=[],
            export_time_ms=elapsed_ms,
        )

    # -- batch export -------------------------------------------------------

    def export_batch(self, requests: list[ExportRequest]) -> list[ExportResult]:
        """Export multiple samples, collecting all errors.

        Each failure becomes a non-success ExportResult; successful samples are
        still written. If any sample fails, ``BatchExportError`` is raised after
        all samples have been attempted.
        """
        results: list[ExportResult] = []
        any_failure = False

        for request in requests:
            start = time.perf_counter()
            try:
                results.append(self.export(request))
            except (ExportValidationError, ExportIOError) as exc:
                any_failure = True
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                errors = getattr(exc, "errors", None) or [str(exc)]
                sid = request.sample_id or ""
                sample_dir = ""
                if request.output_dir and sid:
                    sample_dir = str(Path(request.output_dir) / sid)
                results.append(
                    ExportResult(
                        success=False,
                        sample_id=sid,
                        sample_dir=sample_dir,
                        files_written=[],
                        schema_valid=False,
                        errors=errors,
                        export_time_ms=elapsed_ms,
                    )
                )

        if any_failure:
            raise BatchExportError(results)
        return results

    # -- validation helper --------------------------------------------------

    def validate_export(self, sample_dir: str | Path) -> list[str]:
        """Run validate_sample_schema(); return list of errors (empty = valid)."""
        return validate_sample_schema(sample_dir)
