"""GNNTrainer — training harness for the OMIM feature-classification GNN.

Torch-guarded: importing this module is always safe, but :class:`GNNTrainer`
construction calls :func:`require_torch`. Includes:

  * :class:`CanonicalSampleDataset` — reads canonical sample dirs (mgg.json +
    labels.json) into torch_geometric ``Data`` objects with per-node labels.
  * :class:`GNNTrainer` — Adam + weight decay, ReduceLROnPlateau on val macro
    F1, cross-entropy with inverse-frequency class weights (class-imbalance
    handling per ML_Integration.md), early stopping, checkpoint save/load.

The trainer has NO meaningful heuristic fallback, so it raises (rather than
degrades) when torch is absent — unlike the inference-time GNNPredictor.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from pydantic import BaseModel

from omim.ml.availability import require_torch
from omim.ml.results import FEATURE_CLASSES, NUM_FEATURE_CLASSES

if TYPE_CHECKING:
    from omim.graph.mgg import ManufacturingGeometryGraph

logger = logging.getLogger(__name__)

#: Maps a labels.json feature_class to its index in the GNN output space.
CLASS_TO_INDEX: dict[str, int] = {name: i for i, name in enumerate(FEATURE_CLASSES)}
_UNKNOWN_INDEX = CLASS_TO_INDEX["UNKNOWN_FEATURE"]


class TrainingResult(BaseModel):
    """Summary returned by :meth:`GNNTrainer.train`."""

    epochs_run: int = 0
    best_epoch: int = 0
    best_val_macro_f1: float = 0.0
    final_train_loss: float = 0.0
    history: list[dict] = []  # per-epoch {epoch, train_loss, val_macro_f1}
    checkpoint_path: str | None = None
    stopped_early: bool = False


# ---------------------------------------------------------------------------
# Label resolution: map labels.json feature ids -> per-geometry-node class idx
# ---------------------------------------------------------------------------


def _node_labels_from_sample(
    node_ids: list[str],
    labels: dict,
    mgg: Any,
    position_tol_mm: float = 0.5,
) -> np.ndarray:
    """Build a per-node int label array aligned with ``node_ids``.

    The canonical ``labels.json`` features carry ``feature_class`` and
    ``position_mm`` but NOT a geometry-node id (the generator writes each
    feature's ``position_mm`` equal to the corresponding MGG node ``centroid``).
    We therefore join by position (mirroring ``omim.benchmarks.tasks._join_truth``):

      1. The outer-boundary geometry node maps to PROFILE_CUT.
      2. Every other geometry node matches the nearest unused label feature whose
         ``position_mm`` is within ``position_tol_mm`` of the node ``centroid``.
      3. Unmatched nodes -> UNKNOWN_FEATURE.

    Greedy one-to-one assignment prevents a single label from labelling two nodes.
    """
    feats = [
        (f.get("feature_class"), f.get("position_mm"))
        for f in labels.get("features", [])
        if f.get("feature_class")
    ]
    used = [False] * len(feats)

    out = np.full(len(node_ids), _UNKNOWN_INDEX, dtype=np.int64)
    for i, nid in enumerate(node_ids):
        data = mgg.get_node(nid) or {}

        # Rule 1: the outer profile cut is the panel boundary.
        if data.get("is_outer_boundary"):
            out[i] = CLASS_TO_INDEX.get("PROFILE_CUT", _UNKNOWN_INDEX)
            continue

        centroid = data.get("centroid")
        if not centroid:
            continue

        # Rule 2: nearest unused label within tolerance.
        best_j, best_d = None, position_tol_mm
        for j, (fc, pos) in enumerate(feats):
            if used[j] or not pos or fc == "PROFILE_CUT":
                continue
            d = ((float(pos[0]) - float(centroid[0])) ** 2
                 + (float(pos[1]) - float(centroid[1])) ** 2) ** 0.5
            if d <= best_d:
                best_d, best_j = d, j
        if best_j is not None:
            used[best_j] = True
            out[i] = CLASS_TO_INDEX.get(feats[best_j][0], _UNKNOWN_INDEX)
    return out


def load_sample_as_data(sample_dir: str | Path) -> Any:
    """Load one canonical sample dir (mgg.json + labels.json) into a PyG ``Data``.

    Requires torch. Returns a ``Data`` with ``x`` (N,16), ``edge_index``, and
    per-node ``y``. Also attaches ``graph_y`` (1.0 if labels.json is_valid).
    """
    require_torch("Loading a canonical sample for training")

    from omim.graph.mgg import ManufacturingGeometryGraph
    from omim.ml.graph_encoding import mgg_to_data

    sample_dir = Path(sample_dir)
    mgg_data = json.loads((sample_dir / "mgg.json").read_text(encoding="utf-8"))
    labels = json.loads((sample_dir / "labels.json").read_text(encoding="utf-8"))

    mgg: ManufacturingGeometryGraph = ManufacturingGeometryGraph.from_dict(mgg_data)
    from omim.ml.features import extract_node_features

    node_ids, _ = extract_node_features(mgg)
    y = _node_labels_from_sample(node_ids, labels, mgg)
    graph_y = 1.0 if labels.get("is_valid", True) else 0.0
    return mgg_to_data(mgg, y=y, graph_label=graph_y)


class CanonicalSampleDataset:
    """Adapter reading canonical sample dirs into a list of PyG ``Data`` objects.

    Parameters
    ----------
    root:
        Either a directory containing sample subdirs, or a dataset root with a
        ``samples/`` subdir. Each sample dir must contain ``mgg.json`` +
        ``labels.json``.
    sample_ids:
        Optional explicit list of sample IDs (subdir names) to load. If omitted,
        every subdir containing an ``mgg.json`` is used.
    """

    def __init__(
        self,
        root: str | Path,
        sample_ids: list[str] | None = None,
    ) -> None:
        require_torch("Building a training dataset")
        self.root = Path(root)
        self._base = self.root / "samples" if (self.root / "samples").is_dir() else self.root
        if sample_ids is None:
            sample_ids = sorted(
                p.name for p in self._base.iterdir() if (p / "mgg.json").exists()
            )
        self.sample_ids = sample_ids
        self._data: list[Any] = []
        for sid in self.sample_ids:
            try:
                self._data.append(load_sample_as_data(self._base / sid))
            except Exception as exc:  # noqa: BLE001 — skip malformed samples, keep training
                logger.warning("Skipping sample %s: %s", sid, exc)

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, idx: int) -> Any:
        return self._data[idx]

    def all(self) -> list[Any]:
        return list(self._data)

    def compute_class_weights(self) -> Any:
        """Inverse-frequency class weights over all node labels (handles imbalance).

        Uses sklearn's balanced weighting when available; otherwise a manual
        inverse-frequency computation. Returns a torch FloatTensor of length 13.
        """
        import torch

        if self._data:
            all_y = np.concatenate([d.y.numpy() for d in self._data])
        else:
            all_y = np.array([], dtype=np.int64)
        weights = np.ones(NUM_FEATURE_CLASSES, dtype=np.float32)
        if all_y.size > 0:
            present = np.unique(all_y)
            try:
                from sklearn.utils.class_weight import compute_class_weight

                cw = compute_class_weight(
                    class_weight="balanced", classes=present, y=all_y
                )
                for cls, w in zip(present, cw):
                    weights[int(cls)] = float(w)
            except Exception:  # noqa: BLE001 — fall back to manual inverse-frequency
                counts = np.bincount(all_y, minlength=NUM_FEATURE_CLASSES).astype(np.float32)
                nonzero = counts > 0
                weights[nonzero] = all_y.size / (present.size * counts[nonzero])
        return torch.from_numpy(weights)


class GNNTrainer:
    """Train a :func:`ManufacturingFeatureGNN` for node feature classification."""

    def __init__(
        self,
        model: Any = None,
        optimizer_lr: float = 0.001,
        weight_decay: float = 1e-4,
        max_epochs: int = 100,
        early_stopping_patience: int = 15,
        class_weights: Any = None,
        device: str = "auto",
    ) -> None:
        require_torch("Training a GNN")
        import torch

        from omim.ml.models import ManufacturingFeatureGNN

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)

        self.model = (model if model is not None else ManufacturingFeatureGNN()).to(self.device)
        self.optimizer = torch.optim.Adam(
            self.model.parameters(), lr=optimizer_lr, weight_decay=weight_decay
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="max", factor=0.5, patience=5
        )
        self.max_epochs = max_epochs
        self.early_stopping_patience = early_stopping_patience
        if class_weights is not None:
            class_weights = class_weights.to(self.device)
        self.criterion = torch.nn.CrossEntropyLoss(weight=class_weights)

    # -- metrics ------------------------------------------------------------

    @staticmethod
    def _macro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        try:
            from sklearn.metrics import f1_score

            return float(
                f1_score(y_true, y_pred, average="macro", zero_division=0)
            )
        except Exception:  # noqa: BLE001 — manual macro-F1 fallback
            classes = np.unique(np.concatenate([y_true, y_pred]))
            f1s = []
            for c in classes:
                tp = int(np.sum((y_pred == c) & (y_true == c)))
                fp = int(np.sum((y_pred == c) & (y_true != c)))
                fn = int(np.sum((y_pred != c) & (y_true == c)))
                denom = 2 * tp + fp + fn
                f1s.append((2 * tp / denom) if denom else 0.0)
            return float(np.mean(f1s)) if f1s else 0.0

    # -- train/eval steps ---------------------------------------------------

    def _epoch(self, batches: list[Any], train: bool) -> tuple[float, float]:
        import torch

        self.model.train(train)
        total_loss = 0.0
        all_true: list[np.ndarray] = []
        all_pred: list[np.ndarray] = []
        ctx = torch.enable_grad() if train else torch.no_grad()
        with ctx:
            for data in batches:
                data = data.to(self.device)
                if train:
                    self.optimizer.zero_grad()
                logits = self.model(data.x, data.edge_index)
                loss = self.criterion(logits, data.y)
                if train:
                    loss.backward()
                    self.optimizer.step()
                total_loss += float(loss.item())
                all_true.append(data.y.cpu().numpy())
                all_pred.append(logits.argmax(dim=-1).cpu().numpy())
        n = max(1, len(batches))
        y_true = np.concatenate(all_true) if all_true else np.array([])
        y_pred = np.concatenate(all_pred) if all_pred else np.array([])
        macro_f1 = self._macro_f1(y_true, y_pred) if y_true.size else 0.0
        return total_loss / n, macro_f1

    def train(
        self,
        train_loader: Any,
        val_loader: Any | None = None,
        checkpoint_dir: str | Path | None = None,
    ) -> TrainingResult:
        """Run the training loop with early stopping on val macro F1.

        ``train_loader`` / ``val_loader`` may be any iterable of PyG ``Data``
        objects (a list, a ``CanonicalSampleDataset.all()``, or a DataLoader).
        """
        train_batches = list(train_loader)
        val_batches = list(val_loader) if val_loader is not None else []

        history: list[dict] = []
        best_f1 = -1.0
        best_epoch = 0
        epochs_no_improve = 0
        stopped_early = False
        ckpt_path: str | None = None
        final_train_loss = 0.0

        for epoch in range(1, self.max_epochs + 1):
            train_loss, _ = self._epoch(train_batches, train=True)
            final_train_loss = train_loss
            if val_batches:
                _, val_f1 = self._epoch(val_batches, train=False)
            else:
                _, val_f1 = self._epoch(train_batches, train=False)
            self.scheduler.step(val_f1)
            history.append(
                {"epoch": epoch, "train_loss": train_loss, "val_macro_f1": val_f1}
            )
            logger.info(
                "epoch %d | train_loss=%.4f | val_macro_f1=%.4f", epoch, train_loss, val_f1
            )

            if val_f1 > best_f1:
                best_f1 = val_f1
                best_epoch = epoch
                epochs_no_improve = 0
                if checkpoint_dir is not None:
                    ckpt_path = self.save_checkpoint(checkpoint_dir, epoch, val_f1)
            else:
                epochs_no_improve += 1
                if epochs_no_improve >= self.early_stopping_patience:
                    stopped_early = True
                    logger.info("Early stopping at epoch %d", epoch)
                    break

        return TrainingResult(
            epochs_run=len(history),
            best_epoch=best_epoch,
            best_val_macro_f1=max(best_f1, 0.0),
            final_train_loss=final_train_loss,
            history=history,
            checkpoint_path=ckpt_path,
            stopped_early=stopped_early,
        )

    # -- checkpoints --------------------------------------------------------

    def save_checkpoint(
        self, checkpoint_dir: str | Path, epoch: int, val_macro_f1: float
    ) -> str:
        import torch

        checkpoint_dir = Path(checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        path = checkpoint_dir / "feature_gnn_best.pt"
        torch.save(
            {
                "model_state": self.model.state_dict(),
                "epoch": epoch,
                "val_macro_f1": val_macro_f1,
                "feature_classes": FEATURE_CLASSES,
            },
            path,
        )
        return str(path)

    def load_checkpoint(self, path: str | Path) -> None:
        import torch

        state = torch.load(Path(path), map_location=self.device)
        self.model.load_state_dict(state.get("model_state", state))
        self.model.to(self.device)
