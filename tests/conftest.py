"""Shared test fixtures."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from omim.graph.builder import MGGBuilder
from omim.graph.models import GraphMetadata
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.parser.models import RawEntity, RawGeometry


DATA_DIR = Path(__file__).parent.parent / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"


@pytest.fixture
def sample_raw_geometry() -> RawGeometry:
    """A simple panel with 4 shelf-pin holes and a boundary rectangle."""
    # Panel: 600 x 400 mm rectangle
    panel_pts = [(0, 0), (600, 0), (600, 400), (0, 400)]

    entities = [
        # Panel boundary (closed polyline)
        RawEntity(
            entity_id="100",
            entity_type="LWPOLYLINE",
            layer="cut",
            inferred_layer_type="cut",
            points=panel_pts,
            is_closed=True,
            bbox=(0, 0, 600, 400),
        ),
        # Shelf pin holes: 5mm diameter at 32mm spacing
        RawEntity(
            entity_id="201",
            entity_type="CIRCLE",
            layer="drill",
            inferred_layer_type="drill",
            center=(37, 100),
            radius_mm=2.5,
            is_closed=True,
            bbox=(34.5, 97.5, 39.5, 102.5),
        ),
        RawEntity(
            entity_id="202",
            entity_type="CIRCLE",
            layer="drill",
            inferred_layer_type="drill",
            center=(37, 132),
            radius_mm=2.5,
            is_closed=True,
            bbox=(34.5, 129.5, 39.5, 134.5),
        ),
        RawEntity(
            entity_id="203",
            entity_type="CIRCLE",
            layer="drill",
            inferred_layer_type="drill",
            center=(37, 164),
            radius_mm=2.5,
            is_closed=True,
            bbox=(34.5, 161.5, 39.5, 166.5),
        ),
        RawEntity(
            entity_id="204",
            entity_type="CIRCLE",
            layer="drill",
            inferred_layer_type="drill",
            center=(37, 196),
            radius_mm=2.5,
            is_closed=True,
            bbox=(34.5, 193.5, 39.5, 198.5),
        ),
        # 35mm hinge cup hole
        RawEntity(
            entity_id="301",
            entity_type="CIRCLE",
            layer="drill",
            inferred_layer_type="drill",
            center=(500, 50),
            radius_mm=17.5,
            is_closed=True,
            bbox=(482.5, 32.5, 517.5, 67.5),
        ),
    ]

    return RawGeometry(
        source_file="test_panel.dxf",
        source_file_hash="sha256:test",
        dxf_version="AC1027",
        entities=entities,
        panel_boundary_detected=True,
        panel_boundary_entity_id="100",
    )


@pytest.fixture
def sample_mgg(sample_raw_geometry: RawGeometry) -> ManufacturingGeometryGraph:
    """Build an MGG from the sample raw geometry."""
    builder = MGGBuilder()
    return builder.build(sample_raw_geometry)
