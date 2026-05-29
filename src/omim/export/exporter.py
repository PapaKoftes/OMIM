"""Export functions for MGG data."""

from __future__ import annotations

import json
from pathlib import Path

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.graph.serializer import mgg_to_cytoscape
from omim.validation.models import ValidationReport


def export_mgg_json(mgg: ManufacturingGeometryGraph, path: str | Path) -> Path:
    """Export full MGG to JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mgg.to_json(), encoding="utf-8")
    return path


def export_validation_report(report: ValidationReport, path: str | Path) -> Path:
    """Export validation report to JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(), indent=2, default=str),
        encoding="utf-8",
    )
    return path


def export_cytoscape(mgg: ManufacturingGeometryGraph, path: str | Path) -> Path:
    """Export MGG in Cytoscape.js JSON format for frontend visualization."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = mgg_to_cytoscape(mgg)
    path.write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8",
    )
    return path
