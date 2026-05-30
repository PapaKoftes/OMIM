"""GNN model architectures for the OMIM ML layer (Authority Level 6).

Three models, all per docs/10_IMPLEMENTATION/ML_Integration.md:

  * :func:`ManufacturingFeatureGNN`  -- GraphSAGE node classifier (13 classes).
  * :func:`ManufacturabilityGNN`     -- graph-level binary classifier.
  * :func:`VariationalManufacturingEncoder` -- VGAE encoder for anomaly detection.

GRACEFUL IMPORT: ``import omim.ml.models`` must succeed even without torch. We
therefore do NOT define ``torch.nn.Module`` subclasses at module scope. Instead
each public name is a *factory function* that lazily builds and returns a model
instance, calling :func:`require_torch` first. The actual ``nn.Module`` classes
are defined inside :func:`_define_models`, memoized on first use.

Every model exposes a ``predict(...)`` method returning an *additive* Level-6
prediction object (see :mod:`omim.ml.results`); ``predict`` NEVER mutates the
MGG or any validation report.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from omim.ml.availability import require_torch
from omim.ml.results import (
    FEATURE_CLASSES,
    NUM_FEATURE_CLASSES,
    AnomalyPrediction,
    FeatureClassificationPrediction,
    ManufacturabilityPrediction,
    NodeAnomaly,
    NodePrediction,
)

if TYPE_CHECKING:
    from omim.graph.mgg import ManufacturingGeometryGraph

__all__ = [
    "ManufacturingFeatureGNN",
    "ManufacturabilityGNN",
    "VariationalManufacturingEncoder",
    "build_vgae",
]


@lru_cache(maxsize=1)
def _define_models() -> dict[str, type]:
    """Define and return the torch nn.Module classes. Memoized.

    All heavy imports live here so module import never needs torch.
    """
    require_torch("Constructing a GNN model")

    import torch
    import torch.nn.functional as F
    from torch_geometric.nn import (
        BatchNorm,
        GCNConv,
        SAGEConv,
        global_max_pool,
        global_mean_pool,
    )

    from omim.ml.graph_encoding import mgg_to_data

    class _ManufacturingFeatureGNN(torch.nn.Module):
        """GraphSAGE node classifier. Reference: Hamilton et al., NeurIPS 2017."""

        def __init__(
            self,
            in_channels: int = 16,
            hidden_channels: int = 128,
            out_channels: int = NUM_FEATURE_CLASSES,
            num_layers: int = 3,
            dropout: float = 0.3,
        ) -> None:
            super().__init__()
            self.num_layers = num_layers
            self.dropout = dropout
            self.convs = torch.nn.ModuleList()
            self.norms = torch.nn.ModuleList()

            self.convs.append(SAGEConv(in_channels, hidden_channels))
            self.norms.append(BatchNorm(hidden_channels))
            for _ in range(max(0, num_layers - 2)):
                self.convs.append(SAGEConv(hidden_channels, hidden_channels))
                self.norms.append(BatchNorm(hidden_channels))
            self.convs.append(SAGEConv(hidden_channels, out_channels))

        def forward(self, x, edge_index):
            for conv, norm in zip(self.convs[:-1], self.norms):
                x = conv(x, edge_index)
                x = norm(x)
                x = F.relu(x)
                x = F.dropout(x, p=self.dropout, training=self.training)
            return self.convs[-1](x, edge_index)  # raw logits

        def predict_proba(self, x, edge_index):
            return F.softmax(self.forward(x, edge_index), dim=-1)

        @torch.no_grad()
        def predict(
            self,
            mgg: ManufacturingGeometryGraph,
            validation_report: Any = None,  # noqa: ARG002 — read-only, never mutated
        ) -> FeatureClassificationPrediction:
            """Return an additive per-node classification overlay. No mutation."""
            self.eval()
            data = mgg_to_data(mgg)
            graph_id = getattr(getattr(mgg, "metadata", None), "graph_id", None)
            if data.num_nodes == 0:
                return FeatureClassificationPrediction(graph_id=graph_id)

            proba = self.predict_proba(data.x, data.edge_index)
            conf, idx = proba.max(dim=-1)
            preds: list[NodePrediction] = []
            for i, nid in enumerate(data.node_ids):
                class_idx = int(idx[i].item())
                dist = {
                    FEATURE_CLASSES[c]: float(proba[i, c].item())
                    for c in range(proba.shape[1])
                }
                preds.append(
                    NodePrediction(
                        node_id=nid,
                        feature_class=FEATURE_CLASSES[class_idx],
                        confidence=float(conf[i].item()),
                        proba=dist,
                    )
                )
            return FeatureClassificationPrediction(
                graph_id=graph_id, node_predictions=preds
            )

    class _ManufacturabilityGNN(torch.nn.Module):
        """Graph-level binary classifier (mean+max global pooling)."""

        def __init__(self, in_channels: int = 16, hidden_channels: int = 128) -> None:
            super().__init__()
            self.conv1 = SAGEConv(in_channels, hidden_channels)
            self.conv2 = SAGEConv(hidden_channels, hidden_channels)
            self.conv3 = SAGEConv(hidden_channels, hidden_channels)
            self.classifier = torch.nn.Sequential(
                torch.nn.Linear(hidden_channels * 2, hidden_channels),
                torch.nn.ReLU(),
                torch.nn.Dropout(0.3),
                torch.nn.Linear(hidden_channels, 1),
            )

        def forward(self, x, edge_index, batch):
            x = F.relu(self.conv1(x, edge_index))
            x = F.relu(self.conv2(x, edge_index))
            x = self.conv3(x, edge_index)
            x_mean = global_mean_pool(x, batch)
            x_max = global_max_pool(x, batch)
            x_global = torch.cat([x_mean, x_max], dim=1)
            return self.classifier(x_global).squeeze(-1)  # raw logit(s)

        @torch.no_grad()
        def predict(
            self,
            mgg: ManufacturingGeometryGraph,
            validation_report: Any = None,  # noqa: ARG002 — read-only, never mutated
        ) -> ManufacturabilityPrediction:
            """Return an additive, advisory manufacturability score. No mutation.

            NOTE: this NEVER overrides a deterministic validation verdict.
            """
            self.eval()
            data = mgg_to_data(mgg)
            graph_id = getattr(getattr(mgg, "metadata", None), "graph_id", None)
            batch = torch.zeros(data.num_nodes, dtype=torch.long)
            logit = self.forward(data.x, data.edge_index, batch)
            p = float(torch.sigmoid(logit).item())
            return ManufacturabilityPrediction(
                graph_id=graph_id,
                p_manufacturable=p,
                predicted_manufacturable=p >= 0.5,
                confidence=abs(p - 0.5) * 2.0,
            )

    class _VariationalManufacturingEncoder(torch.nn.Module):
        """VGAE encoder. Reference: Kipf & Welling, NIPS Workshop 2016."""

        def __init__(
            self,
            in_channels: int = 16,
            hidden_channels: int = 64,
            out_channels: int = 32,
        ) -> None:
            super().__init__()
            self.conv1 = GCNConv(in_channels, hidden_channels)
            self.conv_mu = GCNConv(hidden_channels, out_channels)
            self.conv_logstd = GCNConv(hidden_channels, out_channels)

        def forward(self, x, edge_index):
            x = F.relu(self.conv1(x, edge_index))
            return self.conv_mu(x, edge_index), self.conv_logstd(x, edge_index)

    return {
        "ManufacturingFeatureGNN": _ManufacturingFeatureGNN,
        "ManufacturabilityGNN": _ManufacturabilityGNN,
        "VariationalManufacturingEncoder": _VariationalManufacturingEncoder,
    }


# ---------------------------------------------------------------------------
# Public factory functions (callable without torch -> raises a clear error)
# ---------------------------------------------------------------------------


def ManufacturingFeatureGNN(*args: Any, **kwargs: Any):  # noqa: N802 — factory mimics class
    """Build a GraphSAGE node-classifier model instance.

    Requires torch + torch_geometric (raises a clear ImportError otherwise).
    """
    return _define_models()["ManufacturingFeatureGNN"](*args, **kwargs)


def ManufacturabilityGNN(*args: Any, **kwargs: Any):  # noqa: N802 — factory mimics class
    """Build a graph-level binary manufacturability classifier instance."""
    return _define_models()["ManufacturabilityGNN"](*args, **kwargs)


def VariationalManufacturingEncoder(*args: Any, **kwargs: Any):  # noqa: N802
    """Build the VGAE *encoder* module.

    Usually wrapped in a torch_geometric ``VGAE``; see :func:`build_vgae`.
    """
    return _define_models()["VariationalManufacturingEncoder"](*args, **kwargs)


def build_vgae(
    in_channels: int = 16, hidden_channels: int = 64, out_channels: int = 32
):
    """Build a ready-to-train ``torch_geometric.nn.VGAE`` for anomaly detection.

    Trained on VALID panels only; at inference, high reconstruction error =>
    anomaly candidate. Returns an object whose ``.predict_anomaly(mgg)`` yields
    an additive :class:`AnomalyPrediction` (attached below).
    """
    require_torch("Building a VGAE anomaly detector")

    import torch
    from torch_geometric.nn import VGAE

    from omim.ml.graph_encoding import mgg_to_data

    encoder = VariationalManufacturingEncoder(in_channels, hidden_channels, out_channels)
    vgae = VGAE(encoder)

    @torch.no_grad()
    def predict_anomaly(
        mgg: ManufacturingGeometryGraph, threshold: float = 1.0
    ) -> AnomalyPrediction:
        vgae.eval()
        data = mgg_to_data(mgg)
        graph_id = getattr(getattr(mgg, "metadata", None), "graph_id", None)
        if data.num_nodes == 0:
            return AnomalyPrediction(graph_id=graph_id, threshold=threshold)

        z = vgae.encode(data.x, data.edge_index)
        # Per-node anomaly = mean BCE recon error of its incident edges' logits.
        # Approximation: node anomaly = -mean log-prob of reconstructing self &
        # neighbor links. We use the latent norm deviation as a cheap, stable proxy.
        recon = torch.sigmoid(torch.matmul(z, z.t()))
        # Reconstruction error per node: how poorly its row matches adjacency.
        adj = torch.zeros((data.num_nodes, data.num_nodes))
        ei = data.edge_index
        adj[ei[0], ei[1]] = 1.0
        node_err = torch.nn.functional.binary_cross_entropy(
            recon.clamp(1e-6, 1 - 1e-6), adj, reduction="none"
        ).mean(dim=1)

        anomalies: list[NodeAnomaly] = []
        for i, nid in enumerate(data.node_ids):
            score = float(node_err[i].item())
            anomalies.append(
                NodeAnomaly(node_id=nid, anomaly_score=score, is_anomaly=score > threshold)
            )
        graph_score = float(node_err.mean().item())
        return AnomalyPrediction(
            graph_id=graph_id,
            node_anomalies=anomalies,
            graph_anomaly_score=graph_score,
            threshold=threshold,
        )

    # Attach the convenience predictor without subclassing VGAE.
    vgae.predict_anomaly = predict_anomaly  # type: ignore[attr-defined]
    return vgae
