"""API routes for OMIM."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from omim.graph.builder import MGGBuilder
from omim.graph.serializer import mgg_to_cytoscape
from omim.parser.dxf_parser import DXFParser
from omim.semantic.classifier import FeatureClassifier
from omim.validation.rule_engine import RuleEngine

logger = logging.getLogger(__name__)
router = APIRouter()

# Singletons
_parser = DXFParser()
_builder = MGGBuilder()
_validator = RuleEngine()
_classifier = FeatureClassifier()


@router.post("/analyze")
async def analyze_dxf(file: UploadFile = File(...)) -> dict[str, Any]:
    """Full pipeline: DXF → Parse → MGG → Classify → Validate → Response."""
    if not file.filename or not file.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="File must be a .dxf file")

    # Save upload to temp file
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Parse
        parse_result = _parser.parse(tmp_path)
        if not parse_result.success or not parse_result.geometry:
            return {
                "success": False,
                "errors": [e.model_dump() for e in parse_result.errors],
            }

        # Build MGG
        mgg = _builder.build(parse_result.geometry)

        # Classify features
        classifications = _classifier.classify(mgg)

        # Validate
        report = _validator.validate(mgg)

        # Return results
        return {
            "success": True,
            "graph": mgg_to_cytoscape(mgg),
            "validation": report.model_dump(),
            "classifications": [c.model_dump() for c in classifications],
            "parse_warnings": [
                w.model_dump() for w in parse_result.geometry.warnings
            ],
            "summary": {
                "geometry_nodes": mgg.metadata.geometry_node_count,
                "feature_nodes": mgg.metadata.feature_node_count,
                "constraint_nodes": mgg.metadata.constraint_node_count,
                "edges": mgg.metadata.edge_count,
                "validation_errors": report.failed,
                "validation_warnings": report.warnings,
                "panel_width_mm": mgg.metadata.panel_width_mm,
                "panel_height_mm": mgg.metadata.panel_height_mm,
            },
        }
    except Exception as e:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/parse")
async def parse_dxf(file: UploadFile = File(...)) -> dict[str, Any]:
    """Parse only — return raw geometry without classification or validation."""
    if not file.filename or not file.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="File must be a .dxf file")

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = _parser.parse(tmp_path)
        return result.model_dump()
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/validate")
async def validate_dxf(file: UploadFile = File(...)) -> dict[str, Any]:
    """Parse + Build MGG + Validate only (no classification)."""
    if not file.filename or not file.filename.lower().endswith(".dxf"):
        raise HTTPException(status_code=400, detail="File must be a .dxf file")

    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        parse_result = _parser.parse(tmp_path)
        if not parse_result.success or not parse_result.geometry:
            return {
                "success": False,
                "errors": [e.model_dump() for e in parse_result.errors],
            }

        mgg = _builder.build(parse_result.geometry)
        report = _validator.validate(mgg)

        return {
            "success": True,
            "validation": report.model_dump(),
        }
    finally:
        tmp_path.unlink(missing_ok=True)
