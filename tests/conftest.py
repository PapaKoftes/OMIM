"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from omim.graph.builder import MGGBuilder
from omim.graph.mgg import ManufacturingGeometryGraph
from omim.parser.models import PanelBoundary, RawEntity, RawGeometry

DATA_DIR = Path(__file__).parent.parent / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"


@pytest.fixture
def sample_raw_geometry() -> RawGeometry:
    """A simple panel with 4 shelf-pin holes and a boundary rectangle."""
    # Panel: 600 x 400 mm rectangle
    panel_pts = [[0, 0], [600, 0], [600, 400], [0, 400]]

    entities = [
        # Panel boundary (closed polyline)
        RawEntity(
            entity_id="100",
            ezdxf_handle="h100",
            entity_type="LWPOLYLINE",
            layer="cut",
            inferred_layer_type="cut",
            coordinates=panel_pts,
            is_closed=True,
            bounding_box=[0, 0, 600, 400],
            centroid=[300.0, 200.0],
            area_mm2=240000.0,
            perimeter_mm=2000.0,
        ),
        # Shelf pin holes: 5mm diameter at 32mm spacing
        RawEntity(
            entity_id="201",
            ezdxf_handle="h201",
            entity_type="CIRCLE",
            layer="drill",
            inferred_layer_type="drill",
            coordinates=[37, 100, 2.5],
            is_closed=True,
            bounding_box=[34.5, 97.5, 39.5, 102.5],
            centroid=[37, 100],
            area_mm2=19.635,
            perimeter_mm=15.708,
            diameter_mm=5.0,
            radius_mm=2.5,
        ),
        RawEntity(
            entity_id="202",
            ezdxf_handle="h202",
            entity_type="CIRCLE",
            layer="drill",
            inferred_layer_type="drill",
            coordinates=[37, 132, 2.5],
            is_closed=True,
            bounding_box=[34.5, 129.5, 39.5, 134.5],
            centroid=[37, 132],
            area_mm2=19.635,
            perimeter_mm=15.708,
            diameter_mm=5.0,
            radius_mm=2.5,
        ),
        RawEntity(
            entity_id="203",
            ezdxf_handle="h203",
            entity_type="CIRCLE",
            layer="drill",
            inferred_layer_type="drill",
            coordinates=[37, 164, 2.5],
            is_closed=True,
            bounding_box=[34.5, 161.5, 39.5, 166.5],
            centroid=[37, 164],
            area_mm2=19.635,
            perimeter_mm=15.708,
            diameter_mm=5.0,
            radius_mm=2.5,
        ),
        RawEntity(
            entity_id="204",
            ezdxf_handle="h204",
            entity_type="CIRCLE",
            layer="drill",
            inferred_layer_type="drill",
            coordinates=[37, 196, 2.5],
            is_closed=True,
            bounding_box=[34.5, 193.5, 39.5, 198.5],
            centroid=[37, 196],
            area_mm2=19.635,
            perimeter_mm=15.708,
            diameter_mm=5.0,
            radius_mm=2.5,
        ),
        # 35mm hinge cup hole
        RawEntity(
            entity_id="301",
            ezdxf_handle="h301",
            entity_type="CIRCLE",
            layer="drill",
            inferred_layer_type="drill",
            coordinates=[500, 50, 17.5],
            is_closed=True,
            bounding_box=[482.5, 32.5, 517.5, 67.5],
            centroid=[500, 50],
            area_mm2=962.1128,
            perimeter_mm=109.9557,
            diameter_mm=35.0,
            radius_mm=17.5,
        ),
    ]

    return RawGeometry(
        source_file="test_panel.dxf",
        source_file_hash="sha256:test",
        dxf_version="AC1027",
        entities=entities,
        panel_boundary=PanelBoundary(
            entity_id="100",
            coordinates=panel_pts,
            bounding_box=[0, 0, 600, 400],
            area_mm2=240000.0,
            inferred=False,
        ),
        panel_boundary_inferred=False,
        entity_counts={"LWPOLYLINE": 1, "CIRCLE": 5},
    )


@pytest.fixture
def sample_mgg(sample_raw_geometry: RawGeometry) -> ManufacturingGeometryGraph:
    """Build an MGG from the sample raw geometry."""
    builder = MGGBuilder()
    return builder.build(sample_raw_geometry)
