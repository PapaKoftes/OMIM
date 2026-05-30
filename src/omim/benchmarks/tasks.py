"""Benchmark task definitions (BENCH-001 .. BENCH-004).

Each task:

  * loads samples from a dataset directory (the canonical 5-file layout),
  * runs the deterministic OMIM baseline ("model under test") — the
    ``FeatureClassifier`` for per-node feature prediction and the ``RuleEngine``
    for panel validity / violation localization,
  * compares predictions against the synthetic ground truth in ``labels.json``.

Ground truth never comes from inference: feature classes, panel validity and
injected violations all originate from the generation spec stored in
``labels.json``.

The join between a ``labels.json`` feature and an MGG geometry node
-----------------------------------------------------------------
``labels.json`` lists features in the same order they were emitted to the DXF,
which is also the order geometry nodes appear in the MGG. The synthetic
generator writes each feature's ``position_mm`` equal to the corresponding MGG
node ``centroid`` (verified on disk). We therefore join primarily by exact
position match and fall back to positional (index) order. The PROFILE_CUT
boundary feature joins to the unique ``is_outer_boundary`` node.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from omim.graph.mgg import ManufacturingGeometryGraph
from omim.semantic.classifier import FeatureClassifier
from omim.validation.rule_engine import RuleEngine

__all__ = [
    "FEATURE_CLASSES",
    "OPERATION_LABELS",
    "FEATURE_TO_OPERATIONS",
    "compute_operation_ground_truth",
    "BenchmarkSample",
    "load_sample",
    "BaselineModel",
    "Bench001",
    "Bench002",
    "Bench003",
    "Bench004",
    "ALL_TASKS",
]

# ---------------------------------------------------------------------------
# Label spaces (frozen, from docs/09_BENCHMARKS/Benchmark_Tasks.md)
# ---------------------------------------------------------------------------

FEATURE_CLASSES: list[str] = [
    "THROUGH_HOLE",
    "BLIND_HOLE",
    "SHELF_PIN_HOLE",
    "HINGE_CUP_HOLE",
    "CONFIRMAT_HOLE",
    "DOWEL_HOLE",
    "POCKET",
    "GROOVE",
    "DADO",
    "RABBET",
    "OPEN_SLOT",
    "PROFILE_CUT",
    "INTERNAL_CUTOUT",
    "UNKNOWN_FEATURE",
]

OPERATION_LABELS: list[str] = ["DRILLING", "CNC_ROUTING", "PROFILE_CUTTING", "NESTING"]

# Ground-truth feature -> operations mapping (Benchmark_Tasks.md, BENCH-003).
FEATURE_TO_OPERATIONS: dict[str, list[str]] = {
    "THROUGH_HOLE": ["DRILLING"],
    "BLIND_HOLE": ["DRILLING"],
    "SHELF_PIN_HOLE": ["DRILLING"],
    "HINGE_CUP_HOLE": ["DRILLING"],
    "CONFIRMAT_HOLE": ["DRILLING"],
    "DOWEL_HOLE": ["DRILLING"],
    "GROOVE": ["CNC_ROUTING"],
    "POCKET": ["CNC_ROUTING"],
    "RABBET": ["CNC_ROUTING"],
    "DADO": ["CNC_ROUTING"],
    "OPEN_SLOT": ["CNC_ROUTING"],
    "PROFILE_CUT": ["PROFILE_CUTTING"],
    "INTERNAL_CUTOUT": ["PROFILE_CUTTING"],
}


def compute_operation_ground_truth(feature_classes: list[str]) -> set[str]:
    """Operations required for a panel given its ground-truth feature classes.

    NESTING is universal for any panel that has features.
    """
    operations: set[str] = set()
    for fc in feature_classes:
        operations.update(FEATURE_TO_OPERATIONS.get(fc, []))
    if feature_classes:
        operations.add("NESTING")
    return operations


# ---------------------------------------------------------------------------
# Sample loading
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkSample:
    """One loaded benchmark sample (ground truth + MGG)."""

    sample_id: str
    mgg: ManufacturingGeometryGraph
    labels: dict[str, Any]
    # node_id -> ground-truth feature_class (joined from labels.json)
    node_truth: dict[str, str] = field(default_factory=dict)
    # ordered geometry node ids
    geometry_node_ids: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return bool(self.labels.get("is_valid", True))

    @property
    def feature_classes(self) -> list[str]:
        return [self.node_truth[nid] for nid in self.geometry_node_ids if nid in self.node_truth]

    @property
    def violating_node_ids(self) -> list[str]:
        """Ground-truth violating nodes: those whose label feature is is_valid=False."""
        return self._violating


def _join_truth(
    mgg: ManufacturingGeometryGraph,
    labels: dict[str, Any],
) -> tuple[dict[str, str], list[str], list[str]]:
    """Join label features to MGG geometry nodes.

    Returns ``(node_truth, geometry_node_ids, violating_node_ids)``.
    """
    geo_nodes = list(mgg.geometry_nodes())
    geo_ids = [nid for nid, _ in geo_nodes]
    features = labels.get("features", [])

    node_truth: dict[str, str] = {}
    violating: list[str] = []
    used_features: set[int] = set()

    # Identify the outer boundary node (-> PROFILE_CUT feature).
    boundary_id = None
    for nid, data in geo_nodes:
        if data.get("is_outer_boundary"):
            boundary_id = nid
            break

    def _match_feature_by_position(centroid, diameter) -> int | None:
        if centroid is None:
            return None
        best_idx = None
        best_dist = 1e-3  # exact-match tolerance (generator writes identical floats)
        for i, feat in enumerate(features):
            if i in used_features:
                continue
            pos = feat.get("position_mm")
            if pos is None or len(pos) < 2:
                continue
            dx = float(pos[0]) - float(centroid[0])
            dy = float(pos[1]) - float(centroid[1])
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= best_dist:
                # Tie-break with diameter when available.
                fd = feat.get("diameter_mm")
                if diameter is not None and fd is not None and abs(fd - diameter) > 0.5:
                    continue
                best_dist = dist
                best_idx = i
        return best_idx

    # First pass: positional (centroid) match.
    for nid, data in geo_nodes:
        if data.get("is_outer_boundary"):
            continue
        idx = _match_feature_by_position(data.get("centroid"), data.get("diameter_mm"))
        if idx is not None:
            used_features.add(idx)
            feat = features[idx]
            node_truth[nid] = feat.get("feature_class", "UNKNOWN_FEATURE")
            if not feat.get("is_valid", True):
                violating.append(nid)

    # Boundary node -> the (first unused) PROFILE_CUT feature, else PROFILE_CUT.
    if boundary_id is not None:
        prof_idx = None
        for i, feat in enumerate(features):
            if i in used_features:
                continue
            if feat.get("feature_class") == "PROFILE_CUT":
                prof_idx = i
                break
        if prof_idx is not None:
            used_features.add(prof_idx)
            feat = features[prof_idx]
            node_truth[boundary_id] = "PROFILE_CUT"
            if not feat.get("is_valid", True):
                violating.append(boundary_id)
        else:
            node_truth[boundary_id] = "PROFILE_CUT"

    # Fallback: any unmatched geometry node joins to the next unused feature by
    # order (same emission order on disk).
    if len(node_truth) < len(geo_ids):
        unused = [i for i in range(len(features)) if i not in used_features]
        ui = 0
        for nid in geo_ids:
            if nid in node_truth:
                continue
            if ui < len(unused):
                feat = features[unused[ui]]
                ui += 1
                node_truth[nid] = feat.get("feature_class", "UNKNOWN_FEATURE")
                if not feat.get("is_valid", True):
                    violating.append(nid)
            else:
                node_truth[nid] = "UNKNOWN_FEATURE"

    return node_truth, geo_ids, violating


def load_sample(sample_dir: str | Path) -> BenchmarkSample:
    """Load a canonical 5-file sample directory into a ``BenchmarkSample``."""
    sample_dir = Path(sample_dir)
    labels = json.loads((sample_dir / "labels.json").read_text(encoding="utf-8"))
    mgg = ManufacturingGeometryGraph.from_json(
        (sample_dir / "mgg.json").read_text(encoding="utf-8")
    )
    node_truth, geo_ids, violating = _join_truth(mgg, labels)
    sample = BenchmarkSample(
        sample_id=labels.get("sample_id", sample_dir.name),
        mgg=mgg,
        labels=labels,
        node_truth=node_truth,
        geometry_node_ids=geo_ids,
    )
    sample._violating = violating  # type: ignore[attr-defined]
    return sample


# ---------------------------------------------------------------------------
# Baseline model under test (deterministic OMIM pipeline)
# ---------------------------------------------------------------------------


class BaselineModel:
    """The deterministic OMIM baseline: semantic classifier + rule engine.

    This is the "model under evaluation". It runs ONLY on the MGG (geometry),
    never on labels.json or the on-disk validation.json, satisfying the
    leakage-prevention rules in Train_Test_Policy.md.
    """

    def __init__(self) -> None:
        self.classifier = FeatureClassifier()
        self.rule_engine = RuleEngine()

    # -- BENCH-001 ----------------------------------------------------------

    def predict_node_classes(self, sample: BenchmarkSample) -> dict[str, str]:
        """node_id -> predicted feature_class (and a confidence map alongside)."""
        annotations = self.classifier.classify(sample.mgg.copy())
        return {a.node_id: a.feature_class for a in annotations.feature_annotations}

    def predict_node_classes_with_conf(
        self, sample: BenchmarkSample
    ) -> tuple[dict[str, str], dict[str, float]]:
        annotations = self.classifier.classify(sample.mgg.copy())
        preds = {a.node_id: a.feature_class for a in annotations.feature_annotations}
        confs = {a.node_id: a.confidence for a in annotations.feature_annotations}
        return preds, confs

    # -- BENCH-002 ----------------------------------------------------------

    def predict_validity(self, sample: BenchmarkSample) -> tuple[bool, list[str], float]:
        """Return ``(is_valid, violating_node_ids, confidence)``.

        Confidence is a deterministic monotone function of the error count
        (more failed nodes -> more confident the panel is invalid).
        """
        report = self.rule_engine.validate(sample.mgg.copy(), annotate_graph=False)
        is_valid = bool(report.overall_valid)
        violating = list(report.failed_node_ids)
        n_err = report.severity_summary.get("ERROR", 0) + report.severity_summary.get(
            "SYSTEM_ERROR", 0
        )
        # Confidence in the *positive (manufacturable)* class.
        conf_valid = 1.0 / (1.0 + n_err)
        return is_valid, violating, conf_valid

    # -- BENCH-003 ----------------------------------------------------------

    def predict_operations(self, sample: BenchmarkSample) -> set[str]:
        """Multi-label operation set inferred from predicted feature classes."""
        preds = self.predict_node_classes(sample)
        return compute_operation_ground_truth(list(preds.values()))

    # -- BENCH-004 ----------------------------------------------------------

    def anomaly_score(self, sample: BenchmarkSample) -> float:
        """Panel-level anomaly score in [0, 1].

        Uses the rule-based validation error count as the anomaly signal
        (Train_Test_Policy.md: "Validation error count as anomaly score").
        UNKNOWN_FEATURE predictions add to the score (unusual geometry).
        """
        report = self.rule_engine.validate(sample.mgg.copy(), annotate_graph=False)
        n_err = report.severity_summary.get("ERROR", 0) + report.severity_summary.get(
            "SYSTEM_ERROR", 0
        )
        n_warn = report.severity_summary.get("WARNING", 0)
        preds = self.predict_node_classes(sample)
        n_unknown = sum(1 for v in preds.values() if v == "UNKNOWN_FEATURE")
        raw = n_err + 0.25 * n_warn + 0.5 * n_unknown
        # Squash to (0, 1) deterministically.
        return raw / (1.0 + raw)


# ---------------------------------------------------------------------------
# Task wrappers — collect (y_true, y_pred) materials for the evaluator
# ---------------------------------------------------------------------------


class Bench001:
    """Feature Classification — per-node multi-class."""

    task_id = "BENCH-001"
    name = "Feature Classification"
    primary_metric = "macro_f1"
    pass_threshold = 0.80

    def collect(
        self, samples: list[BenchmarkSample], model: BaselineModel
    ) -> dict[str, Any]:
        y_true: list[str] = []
        y_pred: list[str] = []
        for s in samples:
            preds = model.predict_node_classes(s)
            for nid in s.geometry_node_ids:
                if nid not in s.node_truth:
                    continue
                y_true.append(s.node_truth[nid])
                y_pred.append(preds.get(nid, "UNKNOWN_FEATURE"))
        return {"y_true": y_true, "y_pred": y_pred, "labels": FEATURE_CLASSES}


class Bench002:
    """Validity Prediction — panel-level binary + violation localization."""

    task_id = "BENCH-002"
    name = "Validity Prediction"
    primary_metric = "binary_f1"
    pass_threshold = 0.85
    critical_metric = "fnr"
    critical_threshold = 0.10

    def collect(
        self, samples: list[BenchmarkSample], model: BaselineModel
    ) -> dict[str, Any]:
        y_true: list[bool] = []
        y_pred: list[bool] = []
        conf_valid: list[float] = []
        ious: list[float] = []
        for s in samples:
            pred_valid, pred_viol, conf = model.predict_validity(s)
            y_true.append(s.is_valid)
            y_pred.append(pred_valid)
            conf_valid.append(conf)
            # Violation localization only meaningful on truly-invalid panels.
            if not s.is_valid:
                from omim.benchmarks.metrics import iou as _iou

                ious.append(_iou(pred_viol, s.violating_node_ids))
        return {
            "y_true": y_true,
            "y_pred": y_pred,
            "conf_valid": conf_valid,
            "localization_iou": ious,
        }


class Bench003:
    """Operation Inference — panel-level multi-label."""

    task_id = "BENCH-003"
    name = "Operation Inference"
    primary_metric = "macro_f1"
    pass_threshold = 0.85

    def collect(
        self, samples: list[BenchmarkSample], model: BaselineModel
    ) -> dict[str, Any]:
        y_true: list[set[str]] = []
        y_pred: list[set[str]] = []
        for s in samples:
            true_ops = compute_operation_ground_truth(s.feature_classes)
            pred_ops = model.predict_operations(s)
            y_true.append(true_ops)
            y_pred.append(pred_ops)
        return {"y_true": y_true, "y_pred": y_pred, "labels": OPERATION_LABELS}


class Bench004:
    """Anomaly Detection — panel-level scoring (invalid = anomalous)."""

    task_id = "BENCH-004"
    name = "Anomaly Detection"
    primary_metric = "auroc"
    pass_threshold = 0.80

    def collect(
        self, samples: list[BenchmarkSample], model: BaselineModel
    ) -> dict[str, Any]:
        y_true: list[bool] = []  # True = anomalous (invalid)
        scores: list[float] = []
        for s in samples:
            y_true.append(not s.is_valid)
            scores.append(model.anomaly_score(s))
        return {"y_true": y_true, "scores": scores}


ALL_TASKS: dict[str, Any] = {
    "BENCH-001": Bench001,
    "BENCH-002": Bench002,
    "BENCH-003": Bench003,
    "BENCH-004": Bench004,
}
