"""OMIM ML layer — Authority Hierarchy Level 6 (advisory only).

The ML layer is an OPTIONAL, bounded component. It NEVER overrides geometry or
deterministic validation; every output is additive, confidence-bounded, and
carries ``InferenceMethod.ML_GNN`` provenance.

This package imports cleanly even when ``torch`` / ``torch_geometric`` are NOT
installed. The torch-dependent symbols (models, encoders, trainer) are exposed
as factory functions / classes that raise a clear, actionable error only when
*called* without the ``[ml]`` extra.

Pure-numpy, always-available entry points:
  * :func:`extract_node_features` — the 16-dim node feature matrix.
  * :class:`GNNPredictor`         — graceful-degradation inference façade.
  * The :mod:`~omim.ml.results` prediction objects.
"""

from __future__ import annotations

from omim.ml.availability import (
    ML_AVAILABLE,
    PYG_AVAILABLE,
    SKLEARN_AVAILABLE,
    TORCH_AVAILABLE,
    missing_dependencies,
    ml_available,
    require_torch,
)
from omim.ml.features import FEATURE_DIM, FEATURE_NAMES, extract_node_features

# Torch-dependent factories: safe to import (they raise only when called).
from omim.ml.models import (  # noqa: E402  (kept after pure-python exports for clarity)
    ManufacturabilityGNN,
    ManufacturingFeatureGNN,
    VariationalManufacturingEncoder,
    build_vgae,
)
from omim.ml.predictor import GNNPredictor
from omim.ml.results import (
    FEATURE_CLASSES,
    NUM_FEATURE_CLASSES,
    AnomalyPrediction,
    FeatureClassificationPrediction,
    ManufacturabilityPrediction,
    NodeAnomaly,
    NodePrediction,
)

__all__ = [
    # availability
    "TORCH_AVAILABLE",
    "PYG_AVAILABLE",
    "SKLEARN_AVAILABLE",
    "ML_AVAILABLE",
    "ml_available",
    "missing_dependencies",
    "require_torch",
    # features
    "FEATURE_DIM",
    "FEATURE_NAMES",
    "extract_node_features",
    # predictor
    "GNNPredictor",
    # results
    "FEATURE_CLASSES",
    "NUM_FEATURE_CLASSES",
    "NodePrediction",
    "FeatureClassificationPrediction",
    "ManufacturabilityPrediction",
    "NodeAnomaly",
    "AnomalyPrediction",
    # models (factories)
    "ManufacturingFeatureGNN",
    "ManufacturabilityGNN",
    "VariationalManufacturingEncoder",
    "build_vgae",
]
