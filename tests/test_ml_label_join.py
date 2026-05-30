"""Regression tests for ML training-label resolution.

Guards the bug where canonical-sample labels (which carry ``position_mm`` but no
geometry-node id) failed to join to MGG nodes, so every training label collapsed
to UNKNOWN_FEATURE and the GNN "learned" a single degenerate class
(val_macro_f1 == 1.0 by predicting UNKNOWN for everything).
"""

from __future__ import annotations

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.graph.models import GeometryNode, GraphMetadata
from omim.ml.results import FEATURE_CLASSES
from omim.ml.trainer import _node_labels_from_sample

_UNKNOWN = FEATURE_CLASSES.index("UNKNOWN_FEATURE")


def _mgg_with(nodes):
    mgg = ManufacturingGeometryGraph(GraphMetadata(graph_id="t"))
    for n in nodes:
        mgg.add_geometry_node(n)
    return mgg


def test_labels_join_by_position():
    """A 5mm hole at (37,100) and 35mm at (500,50) get their real classes,
    matched by position_mm <-> centroid (no id keys exist on labels)."""
    nodes = [
        GeometryNode(
            node_id="geom-a", geometry_type="circle", layer="DRILL",
            inferred_layer_type="drill", coordinates=[37, 100, 2.5],
            centroid=[37.0, 100.0], diameter_mm=5.0, radius_mm=2.5,
            source_entity_id="h1",
        ),
        GeometryNode(
            node_id="geom-b", geometry_type="circle", layer="DRILL",
            inferred_layer_type="drill", coordinates=[500, 50, 17.5],
            centroid=[500.0, 50.0], diameter_mm=35.0, radius_mm=17.5,
            source_entity_id="h2",
        ),
    ]
    mgg = _mgg_with(nodes)
    node_ids = ["geom-a", "geom-b"]
    labels = {
        "features": [
            {"feature_class": "SHELF_PIN_HOLE", "position_mm": [37.0, 100.0]},
            {"feature_class": "HINGE_CUP_HOLE", "position_mm": [500.0, 50.0]},
        ]
    }
    y = _node_labels_from_sample(node_ids, labels, mgg)
    assert FEATURE_CLASSES[y[0]] == "SHELF_PIN_HOLE"
    assert FEATURE_CLASSES[y[1]] == "HINGE_CUP_HOLE"
    # The whole point of the regression: NOT all UNKNOWN.
    assert not all(v == _UNKNOWN for v in y)


def test_outer_boundary_maps_to_profile_cut():
    node = GeometryNode(
        node_id="geom-panel", geometry_type="lwpolyline", layer="BORDER",
        inferred_layer_type="border", coordinates=[[0, 0], [600, 0], [600, 400], [0, 400]],
        centroid=[300.0, 200.0], is_outer_boundary=True, is_closed=True,
        source_entity_id="p1",
    )
    mgg = _mgg_with([node])
    y = _node_labels_from_sample(["geom-panel"], {"features": []}, mgg)
    assert FEATURE_CLASSES[y[0]] == "PROFILE_CUT"


def test_unmatched_node_is_unknown_not_crash():
    node = GeometryNode(
        node_id="geom-x", geometry_type="circle", layer="DRILL",
        inferred_layer_type="drill", coordinates=[10, 10, 1.0],
        centroid=[10.0, 10.0], diameter_mm=2.0, radius_mm=1.0,
        source_entity_id="h9",
    )
    mgg = _mgg_with([node])
    # label is far away -> no positional match -> UNKNOWN, no exception
    labels = {"features": [{"feature_class": "SHELF_PIN_HOLE", "position_mm": [999.0, 999.0]}]}
    y = _node_labels_from_sample(["geom-x"], labels, mgg)
    assert FEATURE_CLASSES[y[0]] == "UNKNOWN_FEATURE"


def test_one_label_does_not_label_two_nodes():
    """Greedy one-to-one: a single label must not be assigned to two nodes."""
    nodes = [
        GeometryNode(
            node_id=f"geom-{i}", geometry_type="circle", layer="DRILL",
            inferred_layer_type="drill", coordinates=[37, 100, 2.5],
            centroid=[37.0, 100.0], diameter_mm=5.0, radius_mm=2.5,
            source_entity_id=f"h{i}",
        )
        for i in range(2)
    ]
    mgg = _mgg_with(nodes)
    labels = {"features": [{"feature_class": "SHELF_PIN_HOLE", "position_mm": [37.0, 100.0]}]}
    y = _node_labels_from_sample(["geom-0", "geom-1"], labels, mgg)
    matched = [v for v in y if v != _UNKNOWN]
    assert len(matched) == 1  # only one node consumes the single label
