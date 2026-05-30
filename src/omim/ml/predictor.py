"""GNNPredictor — public entry point for the ML layer with graceful degradation.

This is the class the pipeline calls. It NEVER raises on missing dependencies
or missing checkpoints; instead it returns an *additive* prediction object
flagged ``fallback=True`` with a clear ``ml_unavailable`` note (Failure_Modes
D-003). The caller is expected to fall back to deterministic heuristics.

Authority Hierarchy Level 6: every result is advisory, confidence-bounded, and
never mutates the MGG or any validation report.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omim.ml.availability import ML_AVAILABLE, missing_dependencies
from omim.ml.results import (
    AnomalyPrediction,
    FeatureClassificationPrediction,
    ManufacturabilityPrediction,
    unavailable_anomaly,
    unavailable_classification,
    unavailable_manufacturability,
)

if TYPE_CHECKING:
    from omim.graph.mgg import ManufacturingGeometryGraph

logger = logging.getLogger(__name__)


class GNNPredictor:
    """Advisory GNN predictor with graceful degradation.

    Parameters
    ----------
    feature_checkpoint, manufacturability_checkpoint, vgae_checkpoint:
        Optional paths to trained model state_dicts. If a checkpoint is absent
        (or torch is unavailable), the corresponding ``predict_*`` method
        returns a fallback result instead of raising.
    anomaly_threshold:
        Per-node reconstruction-error threshold for the VGAE.
    """

    def __init__(
        self,
        feature_checkpoint: str | Path | None = None,
        manufacturability_checkpoint: str | Path | None = None,
        vgae_checkpoint: str | Path | None = None,
        anomaly_threshold: float = 1.0,
    ) -> None:
        self.feature_checkpoint = Path(feature_checkpoint) if feature_checkpoint else None
        self.manufacturability_checkpoint = (
            Path(manufacturability_checkpoint) if manufacturability_checkpoint else None
        )
        self.vgae_checkpoint = Path(vgae_checkpoint) if vgae_checkpoint else None
        self.anomaly_threshold = anomaly_threshold

        # Lazily built / loaded models (only when ML is available).
        self._feature_model: Any = None
        self._manufacturability_model: Any = None
        self._vgae: Any = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Whether the full GNN stack is importable."""
        return ML_AVAILABLE

    def _unavailable_reason(self) -> str:
        missing = missing_dependencies()
        if missing:
            return f"missing dependencies: {', '.join(missing)}"
        return "unknown"

    @staticmethod
    def _graph_id(mgg: ManufacturingGeometryGraph) -> str | None:
        return getattr(getattr(mgg, "metadata", None), "graph_id", None)

    # ------------------------------------------------------------------
    # Model loading helpers (only reached when ML_AVAILABLE)
    # ------------------------------------------------------------------

    @staticmethod
    def _load_state_into(model: Any, checkpoint: Path | None) -> None:
        """Load a checkpoint into *model* if one was requested.

        Honesty rule (Failure_Modes D-003 / 'no silent failure'): if a checkpoint
        path was *explicitly provided* but does not exist, raise — the caller's
        try/except converts this into a flagged ``fallback=True`` result rather
        than silently predicting with random weights. ``None`` means 'no trained
        model requested' and is left as an (untrained) fresh model intentionally.
        """
        if checkpoint is None:
            return
        if not checkpoint.exists():
            raise FileNotFoundError(f"checkpoint not found: {checkpoint}")
        import torch

        state = torch.load(checkpoint, map_location="cpu", weights_only=False)
        model.load_state_dict(state.get("model_state", state))

    def _load_feature_model(self) -> Any:
        if self._feature_model is not None:
            return self._feature_model

        from omim.ml.models import ManufacturingFeatureGNN

        model = ManufacturingFeatureGNN()
        self._load_state_into(model, self.feature_checkpoint)
        model.eval()
        self._feature_model = model
        return model

    def _load_manufacturability_model(self) -> Any:
        if self._manufacturability_model is not None:
            return self._manufacturability_model

        from omim.ml.models import ManufacturabilityGNN

        model = ManufacturabilityGNN()
        self._load_state_into(model, self.manufacturability_checkpoint)
        model.eval()
        self._manufacturability_model = model
        return model

    def _load_vgae(self) -> Any:
        if self._vgae is not None:
            return self._vgae

        from omim.ml.models import build_vgae

        vgae = build_vgae()
        self._load_state_into(vgae, self.vgae_checkpoint)
        vgae.eval()
        self._vgae = vgae
        return vgae

    # ------------------------------------------------------------------
    # Public prediction API (graceful degradation everywhere)
    # ------------------------------------------------------------------

    def predict_features(
        self,
        mgg: ManufacturingGeometryGraph,
        validation_report: Any = None,
    ) -> FeatureClassificationPrediction:
        """Per-node feature classification (additive). Falls back if unavailable."""
        if not ML_AVAILABLE:
            reason = self._unavailable_reason()
            logger.warning("ML unavailable; using heuristics only (%s)", reason)
            return unavailable_classification(self._graph_id(mgg), reason)
        try:
            model = self._load_feature_model()
            return model.predict(mgg, validation_report)
        except Exception as exc:  # noqa: BLE001 — never break the pipeline (D-003)
            logger.warning("GNN feature prediction failed; falling back: %s", exc)
            return unavailable_classification(self._graph_id(mgg), f"runtime error: {exc}")

    def predict_manufacturability(
        self,
        mgg: ManufacturingGeometryGraph,
        validation_report: Any = None,
    ) -> ManufacturabilityPrediction:
        """Graph-level manufacturability score (advisory). Never overrides validation."""
        if not ML_AVAILABLE:
            reason = self._unavailable_reason()
            logger.warning("ML unavailable; using heuristics only (%s)", reason)
            return unavailable_manufacturability(self._graph_id(mgg), reason)
        try:
            model = self._load_manufacturability_model()
            return model.predict(mgg, validation_report)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GNN manufacturability prediction failed; falling back: %s", exc)
            return unavailable_manufacturability(
                self._graph_id(mgg), f"runtime error: {exc}"
            )

    def predict_anomaly(
        self, mgg: ManufacturingGeometryGraph
    ) -> AnomalyPrediction:
        """VGAE anomaly scan (advisory). Falls back if unavailable."""
        if not ML_AVAILABLE:
            reason = self._unavailable_reason()
            logger.warning("ML unavailable; using heuristics only (%s)", reason)
            return unavailable_anomaly(self._graph_id(mgg), reason)
        try:
            vgae = self._load_vgae()
            return vgae.predict_anomaly(mgg, threshold=self.anomaly_threshold)
        except Exception as exc:  # noqa: BLE001
            logger.warning("VGAE anomaly prediction failed; falling back: %s", exc)
            return unavailable_anomaly(self._graph_id(mgg), f"runtime error: {exc}")

    def predict(
        self,
        mgg: ManufacturingGeometryGraph,
        validation_report: Any = None,
    ) -> dict[str, Any]:
        """Run all three advisory predictions and return them as a dict overlay."""
        return {
            "features": self.predict_features(mgg, validation_report),
            "manufacturability": self.predict_manufacturability(mgg, validation_report),
            "anomaly": self.predict_anomaly(mgg),
            "ml_available": ML_AVAILABLE,
            "fallback": not ML_AVAILABLE,
        }
