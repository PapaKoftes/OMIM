"""MGG JSON serialization / deserialization utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omim.graph.mgg import ManufacturingGeometryGraph


def save_mgg(mgg: ManufacturingGeometryGraph, path: str | Path) -> Path:
    """Write an MGG to a JSON file. Returns the resolved path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mgg.to_json(), encoding="utf-8")
    return path


def load_mgg(path: str | Path) -> ManufacturingGeometryGraph:
    """Read an MGG from a JSON file.

    Raises a clear :class:`ValueError` (chaining the underlying cause) when the
    file is missing, is not valid JSON, or lacks the expected MGG structure —
    rather than leaking a raw ``JSONDecodeError``/``KeyError`` with no context.
    """
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read MGG file {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed MGG JSON at {path}: {exc}") from exc
    if not isinstance(data, dict) or "metadata" not in data:
        raise ValueError(
            f"Invalid MGG document at {path}: expected a JSON object with a "
            f"'metadata' key (got {type(data).__name__})"
        )
    try:
        return ManufacturingGeometryGraph.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Could not reconstruct MGG from {path}: {exc}") from exc


def mgg_to_cytoscape(mgg: ManufacturingGeometryGraph) -> dict[str, Any]:
    """Convert an MGG to Cytoscape.js JSON format for the frontend."""
    elements: list[dict] = []

    for nid, data in mgg.graph.nodes(data=True):
        node_data = {"id": nid, **data}
        # Add position from centroid if available (list[float])
        position = None
        centroid = data.get("centroid")
        if centroid and len(centroid) >= 2:
            position = {"x": centroid[0], "y": centroid[1]}
        entry: dict[str, Any] = {"data": node_data, "group": "nodes"}
        if position:
            entry["position"] = position
        elements.append(entry)

    for u, v, data in mgg.graph.edges(data=True):
        edge_data = {"source": u, "target": v, **data}
        elements.append({"data": edge_data, "group": "edges"})

    return {
        "metadata": mgg.metadata.model_dump(),
        "elements": elements,
    }
