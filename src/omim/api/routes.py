"""API routes for OMIM.

Endpoints:
  POST /parse     — DXF → raw geometry only.
  POST /validate  — DXF → MGG → validation report only.
  POST /analyze   — full pipeline: parse → MGG → validate → classify
                    (+ optional advisory LLM annotations via ?annotate=true).
  POST /annotate  — advisory LLM annotations only (MGG json body or DXF upload).
  POST /generate  — run the synthetic PanelGenerator, return a manifest summary.
  GET  /ontology  — loaded feature classes / operations / constraints / materials.
  GET  /rules     — loaded validation rule definitions.

Authority Hierarchy: Geometry > Validation > Semantic (rule-based) > LLM (Level 6,
advisory). The LLM path is fully guarded and never affects validity or geometry.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from omim.api import llm_service
from omim.api.models import AnnotateRequest, GenerateRequest
from omim.api.resources import ontology_payload, rules_payload
from omim.graph.builder import MGGBuilder
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.graph.serializer import mgg_to_cytoscape
from omim.parser.dxf_parser import DXFParser
from omim.semantic.classifier import FeatureClassifier, SemanticPreconditionError
from omim.synthetic.generator import PanelGenerator
from omim.synthetic.models import PanelGeneratorConfig
from omim.validation.rule_engine import RuleEngine

logger = logging.getLogger(__name__)
router = APIRouter()

# Singletons (stateless, reused across requests)
_parser = DXFParser()
_builder = MGGBuilder()
_validator = RuleEngine()
_classifier = FeatureClassifier()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_dxf(file: UploadFile) -> None:
    if not file.filename or not file.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="File must be a .dxf file")


async def _save_upload(file: UploadFile) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        return Path(tmp.name)


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------


@router.post("/analyze")
async def analyze_dxf(
    file: UploadFile = File(...),
    annotate: bool = Query(
        default=False,
        description="Attach advisory LLM annotations (Authority Level 6) when a "
        "Featherless key is configured. Never affects validity or geometry.",
    ),
) -> dict[str, Any]:
    """Full pipeline: DXF → Parse → MGG → Validate → Classify (+ optional LLM)."""
    _require_dxf(file)
    tmp_path = await _save_upload(file)

    try:
        parse_result = _parser.parse(tmp_path)
        if not parse_result.success or not parse_result.geometry:
            return {
                "success": False,
                "errors": [e.model_dump() for e in parse_result.errors],
            }

        mgg = _builder.build(parse_result.geometry)
        report = _validator.validate(mgg)

        # Classify only when Layer 1 passed (semantic precondition). The
        # classifier itself enforces this; we pass the report so it can refuse
        # gracefully on geometrically invalid graphs.
        annotations = None
        classification_skipped_reason = None
        try:
            annotations = _classifier.classify(mgg, validation_report=report)
        except SemanticPreconditionError as exc:
            classification_skipped_reason = str(exc)

        response: dict[str, Any] = {
            "success": True,
            "graph": mgg_to_cytoscape(mgg),
            "validation": report.model_dump(),
            "annotations": annotations.model_dump() if annotations else None,
            "classification_skipped_reason": classification_skipped_reason,
            "parse_warnings": [
                w.model_dump() for w in parse_result.geometry.warnings
            ],
            "summary": {
                "geometry_nodes": mgg.metadata.geometry_node_count,
                "feature_nodes": mgg.metadata.feature_node_count,
                "constraint_nodes": mgg.metadata.constraint_node_count,
                "edges": mgg.metadata.edge_count,
                "layer1_passed": report.layer1_passed,
                "overall_valid": report.overall_valid,
                "validation_errors": report.severity_summary.get("ERROR", 0),
                "validation_warnings": report.severity_summary.get("WARNING", 0),
                "panel_width_mm": mgg.metadata.panel_width_mm,
                "panel_height_mm": mgg.metadata.panel_height_mm,
            },
        }

        # Optional advisory LLM overlay — fully guarded, never authoritative.
        if annotate and annotations is not None:
            response["llm_annotations"] = await llm_service.annotate(
                mgg, annotations
            )
        elif annotate:
            response["llm_annotations"] = {
                "llm_available": False,
                "advisory": True,
                "annotations": [],
                "note": (
                    "Classification was skipped (Layer 1 did not pass); "
                    "no features to annotate."
                ),
            }

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/parse")
async def parse_dxf(file: UploadFile = File(...)) -> dict[str, Any]:
    """Parse only — return raw geometry without classification or validation."""
    _require_dxf(file)
    tmp_path = await _save_upload(file)
    try:
        result = _parser.parse(tmp_path)
        return result.model_dump()
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/validate")
async def validate_dxf(file: UploadFile = File(...)) -> dict[str, Any]:
    """Parse + Build MGG + Validate only (no classification)."""
    _require_dxf(file)
    tmp_path = await _save_upload(file)
    try:
        parse_result = _parser.parse(tmp_path)
        if not parse_result.success or not parse_result.geometry:
            return {
                "success": False,
                "errors": [e.model_dump() for e in parse_result.errors],
            }

        mgg = _builder.build(parse_result.geometry)
        report = _validator.validate(mgg)
        return {"success": True, "validation": report.model_dump()}
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/nest")
async def nest_dxf(file: UploadFile = File(...)) -> dict[str, Any]:
    """Analyse a DXF for a multi-panel nesting layout.

    Detects whether the file is a nest (a stock sheet carrying several panels),
    which panels exist, how features distribute across them, and layout sanity
    (utilization, overlapping panels, panels outside the sheet).
    """
    from omim.nesting import analyze_nesting

    _require_dxf(file)
    tmp_path = await _save_upload(file)
    try:
        parse_result = _parser.parse(tmp_path)
        if not parse_result.success or not parse_result.geometry:
            return {
                "success": False,
                "errors": [e.model_dump() for e in parse_result.errors],
            }
        mgg = _builder.build(parse_result.geometry)
        layout = analyze_nesting(mgg)
        return {"success": True, "nesting": layout.model_dump()}
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# LLM advisory annotation (Authority Level 6)
# ---------------------------------------------------------------------------


@router.post("/annotate")
async def annotate(request: Request) -> dict[str, Any]:
    """Return advisory LLM annotations only.

    Supply either an MGG JSON body (``{"mgg": {...}}``) or a multipart DXF
    upload. If no Featherless key is configured, returns a 200 response with
    ``llm_available: false`` (graceful — never 500). The output is Level-6
    advisory and never affects geometry or validity.

    The endpoint accepts both ``application/json`` and ``multipart/form-data``;
    we branch on content type because FastAPI cannot cleanly mix a JSON body
    model and a file upload on a single operation.
    """
    content_type = request.headers.get("content-type", "")
    max_features = 20
    mgg: ManufacturingGeometryGraph | None = None
    tmp_path: Path | None = None

    try:
        if content_type.startswith("application/json"):
            try:
                raw = await request.json()
            except Exception:
                raw = {}
            body = AnnotateRequest.model_validate(raw or {})
            max_features = body.max_features
            if body.mgg is None:
                raise HTTPException(
                    status_code=400,
                    detail="Provide either an MGG json body or a DXF file upload.",
                )
            try:
                mgg = ManufacturingGeometryGraph.from_dict(body.mgg)
            except Exception as exc:
                raise HTTPException(
                    status_code=400, detail=f"Invalid MGG payload: {exc}"
                )
        elif content_type.startswith("multipart/form-data"):
            form = await request.form()
            file = form.get("file")
            # Starlette's form returns its own UploadFile, which is not the same
            # class as fastapi.UploadFile — duck-type on the filename instead.
            if not hasattr(file, "filename") or not getattr(file, "filename", None):
                raise HTTPException(
                    status_code=400,
                    detail="Provide either an MGG json body or a DXF file upload.",
                )
            _require_dxf(file)
            tmp_path = await _save_upload(file)
            parse_result = _parser.parse(tmp_path)
            if not parse_result.success or not parse_result.geometry:
                return {
                    "success": False,
                    "errors": [e.model_dump() for e in parse_result.errors],
                }
            mgg = _builder.build(parse_result.geometry)
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either an MGG json body or a DXF file upload.",
            )

        # Classify so we know which features to annotate. Annotation is advisory
        # regardless of classification confidence.
        try:
            annotations = _classifier.classify(mgg)
        except SemanticPreconditionError:
            annotations = None

        if annotations is None:
            return {
                "success": True,
                "llm": {
                    "llm_available": llm_service.llm_configured(),
                    "advisory": True,
                    "annotations": [],
                    "note": "No classifiable features (Layer 1 precondition).",
                },
            }

        llm_result = await llm_service.annotate(
            mgg, annotations, max_features=max_features
        )
        return {"success": True, "llm": llm_result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Annotation failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Synthetic dataset generation
# ---------------------------------------------------------------------------


@router.post("/generate")
def generate(body: GenerateRequest) -> dict[str, Any]:
    """Run the synthetic PanelGenerator to a temp dir; return a manifest summary.

    ``num_samples`` is capped at 50 (enforced by the request model) and the
    output directory is cleaned up after the manifest is read, so the endpoint
    never streams or retains large artifacts.
    """
    config = PanelGeneratorConfig(
        random_seed=body.seed,
        num_samples=body.num_samples,
        invalid_sample_ratio=body.invalid_ratio,
        feature_density=body.density,
    )

    tmp_dir = Path(tempfile.mkdtemp(prefix="omim_gen_"))
    try:
        manifest = PanelGenerator(config).generate_dataset(tmp_dir)
        return {
            "success": True,
            "request": {
                "num_samples": body.num_samples,
                "seed": body.seed,
                "invalid_ratio": body.invalid_ratio,
                "density": body.density,
            },
            "manifest": {
                "dataset_id": manifest.dataset_id,
                "schema_version": manifest.schema_version,
                "generator_version": manifest.generator_version,
                "total_samples": manifest.total_samples,
                "valid_count": manifest.valid_count,
                "invalid_count": manifest.invalid_count,
                "splits": {
                    "train": manifest.train_count,
                    "val": manifest.val_count,
                    "test": manifest.test_count,
                },
                "feature_type_counts": manifest.feature_type_counts,
            },
        }
    except Exception as e:
        logger.exception("Generation failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Knowledge-base introspection
# ---------------------------------------------------------------------------


@router.get("/ontology")
def ontology() -> dict[str, Any]:
    """Return the loaded ontology: feature classes, operations, constraints."""
    return ontology_payload()


@router.get("/rules")
def rules() -> dict[str, Any]:
    """Return the loaded validation rules (ids, names, severities, thresholds)."""
    return rules_payload()
