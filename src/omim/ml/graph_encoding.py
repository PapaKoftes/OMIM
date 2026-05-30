"""Convert an MGG into a torch_geometric ``Data`` object.

Guarded by ML availability: importing this module is always safe, but calling
:func:`mgg_to_data` requires ``torch`` + ``torch_geometric`` (it calls
:func:`omim.ml.availability.require_torch`).

Node features come from the pure-numpy :func:`omim.ml.features.extract_node_features`
(the testable core). Edges are built from the MGG's directed edges, then
symmetrized (GraphSAGE / GCN expect undirected adjacency).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from omim.ml.availability import require_torch
from omim.ml.features import extract_node_features

if TYPE_CHECKING:
    from omim.graph.mgg import ManufacturingGeometryGraph


def _build_edge_index(
    node_ids: list[str], mgg: ManufacturingGeometryGraph
) -> np.ndarray:
    """Build a ``(2, E)`` int64 edge_index over the geometry-node subgraph.

    Only edges whose *both* endpoints are geometry nodes (i.e. present in
    ``node_ids``) are kept. Edges are symmetrized so adjacency is undirected.
    Self-loops are added to guarantee every node has at least one edge (avoids
    isolated-node issues in message passing).
    """
    index = {nid: i for i, nid in enumerate(node_ids)}
    src: list[int] = []
    dst: list[int] = []

    g = mgg.graph
    for u, v in g.edges():
        if u in index and v in index:
            iu, iv = index[u], index[v]
            # symmetrize
            src.extend([iu, iv])
            dst.extend([iv, iu])

    # self-loops
    for i in range(len(node_ids)):
        src.append(i)
        dst.append(i)

    if not src:
        return np.zeros((2, 0), dtype=np.int64)
    return np.asarray([src, dst], dtype=np.int64)


def mgg_to_data(
    mgg: ManufacturingGeometryGraph,
    y: Any = None,
    graph_label: Any = None,
) -> Any:
    """Convert an MGG to a ``torch_geometric.data.Data`` object.

    Parameters
    ----------
    mgg:
        The graph to encode.
    y:
        Optional per-node integer labels (length N) for node classification.
    graph_label:
        Optional graph-level label (e.g. manufacturable 0/1) for graph tasks.

    Returns
    -------
    torch_geometric.data.Data
        With ``x`` (N, 16) float tensor, ``edge_index`` (2, E) long tensor, and
        an attached ``node_ids`` list. Carries ``y`` / ``graph_y`` when provided.

    Raises
    ------
    ImportError
        If torch / torch_geometric are not installed.
    """
    require_torch("Encoding an MGG to a torch_geometric Data object")

    import torch  # local, guarded
    from torch_geometric.data import Data

    node_ids, feat = extract_node_features(mgg)
    x = torch.from_numpy(np.ascontiguousarray(feat)).float()
    edge_index = torch.from_numpy(_build_edge_index(node_ids, mgg)).long()

    data = Data(x=x, edge_index=edge_index)
    data.node_ids = node_ids
    data.num_nodes = len(node_ids)

    if y is not None:
        data.y = torch.as_tensor(y, dtype=torch.long)
    if graph_label is not None:
        data.graph_y = torch.as_tensor([float(graph_label)], dtype=torch.float)

    return data
