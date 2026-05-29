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
    """Read an MGG from a JSON file."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    return ManufacturingGeometryGraph.from_dict(data)


def mgg_to_cytoscape(mgg: ManufacturingGeometryGraph) -> dict[str, Any]:
    """Convert an MGG to Cytoscape.js JSON format for the frontend."""
    elements: list[dict] = []

    for nid, data in mgg.graph.nodes(data=True):
        node_data = {"id": nid, **data}
        # Add position from centroid if available
        position = None
        centroid = data.get("centroid")
        if centroid:
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
