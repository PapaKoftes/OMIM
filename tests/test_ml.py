"""Tests for the OMIM ML layer (Authority Hierarchy Level 6, advisory only).

Two tiers:

  * ALWAYS-RUN (no torch needed): clean import, availability flags, the pure
    numpy 16-dim feature extractor, and graceful degradation of GNNPredictor.
  * GUARDED by ``@pytest.mark.skipif(not ML_AVAILABLE)``: model forward pass,
    graph encoding shape, and a tiny overfit sanity check. These require the
    full torch + torch_geometric stack and skip cleanly when it is absent.
"""

from __future__ import annotations

import numpy as np
import pytest

import omim.ml as ml
from omim.ml.availability import ML_AVAILABLE
from omim.ml.features import FEATURE_DIM, FEATURE_NAMES, extract_node_features
from omim.ml.predictor import GNNPredictor
from omim.ml.results import (
    NUM_FEATURE_CLASSES,
    AnomalyPrediction,
    FeatureClassificationPrediction,
    ManufacturabilityPrediction,
)
from omim.provenance.models import InferenceMethod

_SKIP_REASON = "requires torch + torch_geometric ([ml] extra)"


# ===========================================================================
# Tier 1: ALWAYS RUN (no torch required)
# ===========================================================================


def test_package_imports_cleanly():
    """The ML package must import without torch installed."""
    assert hasattr(ml, "extract_node_features")
    assert hasattr(ml, "GNNPredictor")
    assert hasattr(ml, "ManufacturingFeatureGNN")


def test_availability_flags_are_bools():
    assert isinstance(ml.TORCH_AVAILABLE, bool)
    assert isinstance(ml.PYG_AVAILABLE, bool)
    assert isinstance(ml.ML_AVAILABLE, bool)
    assert isinstance(ml.ml_available(), bool)
    # ML_AVAILABLE implies both sub-deps.
    assert ml.ML_AVAILABLE == (ml.TORCH_AVAILABLE and ml.PYG_AVAILABLE)


def test_feature_metadata_consistent():
    assert FEATURE_DIM == 16
    assert len(FEATURE_NAMES) == 16
    assert NUM_FEATURE_CLASSES == 13


def test_extract_node_features_shape(sample_mgg):
    node_ids, feat = extract_node_features(sample_mgg)
    n_geometry = len(list(sample_mgg.geometry_nodes()))
    assert feat.shape == (n_geometry, 16)
    assert len(node_ids) == n_geometry
    assert feat.dtype == np.float32


def test_extract_node_features_finite_and_bounded(sample_mgg):
    _ids, feat = extract_node_features(sample_mgg)
    assert np.isfinite(feat).all(), "all features must be finite"
    # Normalized / binary columns must stay within [0, 1] (or near it).
    # cols: area, perim, circularity, is_*, centroid_x/y, layer one-hot,
    #       n_contained, dist_to_edge are all in [0,1].
    bounded_cols = [0, 1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    sub = feat[:, bounded_cols]
    assert sub.min() >= -1e-6
    assert sub.max() <= 1.0 + 1e-6
    # aspect ratio (col 2) is log-scaled and clamped to [-2, 2].
    assert feat[:, 2].min() >= -2.0 - 1e-6
    assert feat[:, 2].max() <= 2.0 + 1e-6


def test_layer_onehot_sums_to_one(sample_mgg):
    _ids, feat = extract_node_features(sample_mgg)
    onehot = feat[:, 10:14]
    assert np.allclose(onehot.sum(axis=1), 1.0)


def test_extract_features_empty_graph():
    """An MGG with no geometry nodes yields a (0, 16) matrix, not an error."""
    from omim.graph.mgg import ManufacturingGeometryGraph
    from omim.graph.models import GraphMetadata

    mgg = ManufacturingGeometryGraph(GraphMetadata(graph_id="empty"))
    node_ids, feat = extract_node_features(mgg)
    assert node_ids == []
    assert feat.shape == (0, 16)


def test_predictor_features_graceful_when_unavailable(sample_mgg, caplog):
    """GNNPredictor must NEVER raise when ML deps/checkpoint are absent (D-003)."""
    pred = GNNPredictor()  # no checkpoints
    result = pred.predict_features(sample_mgg)
    assert isinstance(result, FeatureClassificationPrediction)
    assert result.inference_method == InferenceMethod.ML_GNN
    if not ML_AVAILABLE:
        assert result.fallback is True
        assert result.ml_available is False
        assert "ml_unavailable" in result.note


def test_predictor_manufacturability_graceful(sample_mgg):
    pred = GNNPredictor()
    result = pred.predict_manufacturability(sample_mgg)
    assert isinstance(result, ManufacturabilityPrediction)
    assert result.inference_method == InferenceMethod.ML_GNN
    if not ML_AVAILABLE:
        assert result.fallback is True


def test_predictor_anomaly_graceful(sample_mgg):
    pred = GNNPredictor()
    result = pred.predict_anomaly(sample_mgg)
    assert isinstance(result, AnomalyPrediction)
    if not ML_AVAILABLE:
        assert result.fallback is True


def test_predictor_predict_all_keys(sample_mgg):
    pred = GNNPredictor()
    out = pred.predict(sample_mgg)
    assert set(out) >= {"features", "manufacturability", "anomaly", "ml_available", "fallback"}


def test_ml_prediction_provenance_is_level6(sample_mgg):
    """Even a fallback manufacturability result builds a valid Level-6 record."""
    result = ManufacturabilityPrediction(graph_id="g", p_manufacturable=0.8, confidence=0.6)
    rec = result.to_provenance()
    assert rec.inference_method == InferenceMethod.ML_GNN
    # Authority invariant: Level-6 (authority > 4) must have confidence < 1.0.
    assert rec.confidence < 1.0


def test_require_torch_raises_clearly_when_unavailable():
    if ML_AVAILABLE:
        pytest.skip("ML stack present; require_torch is a no-op")
    with pytest.raises(ImportError) as exc:
        ml.require_torch("unit test")
    assert "omim[ml]" in str(exc.value)


def test_model_factory_raises_without_stack():
    if ML_AVAILABLE:
        pytest.skip("ML stack present; factory succeeds")
    with pytest.raises(ImportError):
        ml.ManufacturingFeatureGNN()


# ===========================================================================
# Tier 2: GUARDED — require torch + torch_geometric (skip cleanly otherwise)
# ===========================================================================


@pytest.mark.skipif(not ML_AVAILABLE, reason=_SKIP_REASON)
def test_graph_encoding_shape(sample_mgg):
    from omim.ml.graph_encoding import mgg_to_data

    data = mgg_to_data(sample_mgg)
    n = len(list(sample_mgg.geometry_nodes()))
    assert data.x.shape == (n, 16)
    assert data.edge_index.shape[0] == 2
    assert data.num_nodes == n
    assert len(data.node_ids) == n


@pytest.mark.skipif(not ML_AVAILABLE, reason=_SKIP_REASON)
def test_feature_gnn_forward_pass(sample_mgg):
    from omim.ml.graph_encoding import mgg_to_data

    model = ml.ManufacturingFeatureGNN()
    data = mgg_to_data(sample_mgg)
    proba = model.predict_proba(data.x, data.edge_index)
    assert proba.shape == (data.num_nodes, NUM_FEATURE_CLASSES)
    # softmax rows sum to 1
    import torch

    assert torch.allclose(proba.sum(dim=-1), torch.ones(data.num_nodes), atol=1e-4)


@pytest.mark.skipif(not ML_AVAILABLE, reason=_SKIP_REASON)
def test_feature_gnn_predict_returns_additive(sample_mgg):
    model = ml.ManufacturingFeatureGNN()
    result = model.predict(sample_mgg)
    assert isinstance(result, FeatureClassificationPrediction)
    assert result.inference_method == InferenceMethod.ML_GNN
    assert len(result.node_predictions) == len(list(sample_mgg.geometry_nodes()))
    for np_ in result.node_predictions:
        assert 0.0 <= np_.confidence <= 1.0
        assert np_.feature_class in ml.FEATURE_CLASSES


@pytest.mark.skipif(not ML_AVAILABLE, reason=_SKIP_REASON)
def test_manufacturability_gnn_forward(sample_mgg):
    result = ml.ManufacturabilityGNN().predict(sample_mgg)
    assert isinstance(result, ManufacturabilityPrediction)
    assert 0.0 <= result.p_manufacturable <= 1.0


@pytest.mark.skipif(not ML_AVAILABLE, reason=_SKIP_REASON)
def test_vgae_anomaly_forward(sample_mgg):
    vgae = ml.build_vgae()
    result = vgae.predict_anomaly(sample_mgg)
    assert isinstance(result, AnomalyPrediction)
    assert len(result.node_anomalies) == len(list(sample_mgg.geometry_nodes()))


@pytest.mark.skipif(not ML_AVAILABLE, reason=_SKIP_REASON)
def test_overfit_tiny_batch_sanity(sample_mgg):
    """2-epoch sanity check: trainer runs end-to-end and loss is finite."""
    import torch

    from omim.ml.graph_encoding import mgg_to_data
    from omim.ml.trainer import GNNTrainer

    # Build a tiny labeled batch: assign deterministic node labels.
    data = mgg_to_data(sample_mgg)
    n = data.num_nodes
    data.y = torch.zeros(n, dtype=torch.long)  # all class 0 -> trivially learnable

    trainer = GNNTrainer(max_epochs=2, early_stopping_patience=10)
    result = trainer.train([data], val_loader=[data])
    assert result.epochs_run >= 1
    assert np.isfinite(result.final_train_loss)
    assert 0.0 <= result.best_val_macro_f1 <= 1.0
