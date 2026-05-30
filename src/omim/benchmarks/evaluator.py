"""Benchmark evaluator — runs a task over a split and computes metrics.

Produces a deterministic, JSON-serializable ``BenchmarkResult`` (no timestamps,
no wall-clock fields — so that two runs over the same data are byte-identical).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from omim.benchmarks import metrics as M
from omim.benchmarks.splitter import BenchmarkSplitter, DatasetSplits
from omim.benchmarks.tasks import (
    ALL_TASKS,
    BaselineModel,
    BenchmarkSample,
    load_sample,
)

__all__ = ["BenchmarkResult", "BenchmarkEvaluator"]


def _round(value: Any, ndigits: int = 6) -> Any:
    """Round floats (incl. numpy) for stable, comparable output."""
    if isinstance(value, (float, np.floating)):
        return round(float(value), ndigits)
    if isinstance(value, dict):
        return {k: _round(v, ndigits) for k, v in value.items()}
    if isinstance(value, list):
        return [_round(v, ndigits) for v in value]
    if isinstance(value, (int, np.integer)):
        return int(value)
    return value


class BenchmarkResult(BaseModel):
    """Deterministic result of one benchmark task on one split."""

    task_id: str
    task_name: str
    split: str
    n_samples: int
    n_units: int  # nodes (BENCH-001), panels (002/003/004)
    primary_metric: str
    primary_value: float
    passed: bool
    metrics: dict[str, Any] = Field(default_factory=dict)
    per_class: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class BenchmarkEvaluator:
    """Run benchmark tasks against an on-disk dataset directory."""

    def __init__(self, dataset_dir: str | Path, model: BaselineModel | None = None) -> None:
        self.dataset_dir = Path(dataset_dir)
        self.model = model or BaselineModel()
        self.splitter = BenchmarkSplitter()
        self._splits: DatasetSplits | None = None
        self._sample_cache: dict[str, BenchmarkSample] = {}

    # ------------------------------------------------------------------
    # Sample / split access
    # ------------------------------------------------------------------

    def splits(self) -> DatasetSplits:
        if self._splits is None:
            self._splits = self.splitter.resolve(self.dataset_dir)
        return self._splits

    def _load(self, sample_id: str) -> BenchmarkSample:
        if sample_id not in self._sample_cache:
            self._sample_cache[sample_id] = load_sample(
                self.dataset_dir / "samples" / sample_id
            )
        return self._sample_cache[sample_id]

    def samples_for_split(self, split: str) -> list[BenchmarkSample]:
        ids = self.splits().get(split)
        samples: list[BenchmarkSample] = []
        for sid in ids:
            sample_path = self.dataset_dir / "samples" / sid
            if (sample_path / "labels.json").exists():
                samples.append(self._load(sid))
        return samples

    # ------------------------------------------------------------------
    # Single-task evaluation
    # ------------------------------------------------------------------

    def run_task(self, task_id: str, split: str = "test") -> BenchmarkResult:
        task_id = task_id.upper().replace("BENCH", "BENCH").replace("_", "-")
        if task_id not in ALL_TASKS:
            # Accept short forms like "bench001".
            for key in ALL_TASKS:
                if key.replace("-", "").lower() == task_id.replace("-", "").lower():
                    task_id = key
                    break
        if task_id not in ALL_TASKS:
            raise ValueError(f"Unknown task {task_id!r}; known: {list(ALL_TASKS)}")

        task = ALL_TASKS[task_id]()
        samples = self.samples_for_split(split)
        collected = task.collect(samples, self.model)

        if task_id == "BENCH-001":
            return self._eval_bench001(task, split, samples, collected)
        if task_id == "BENCH-002":
            return self._eval_bench002(task, split, samples, collected)
        if task_id == "BENCH-003":
            return self._eval_bench003(task, split, samples, collected)
        return self._eval_bench004(task, split, samples, collected)

    # -- BENCH-001 ----------------------------------------------------------

    def _eval_bench001(self, task, split, samples, collected) -> BenchmarkResult:
        y_true = collected["y_true"]
        y_pred = collected["y_pred"]
        labels = collected["labels"]
        macro = M.macro_f1(y_true, y_pred, labels)
        macro_present = M.macro_f1_present(y_true, y_pred, labels)
        micro = M.micro_f1(y_true, y_pred, labels)
        acc = M.accuracy(y_true, y_pred)
        per_class = M.precision_recall_f1_per_class(y_true, y_pred, labels)
        cm_labels, cm = M.confusion_matrix(y_true, y_pred, labels)
        metrics = {
            "macro_f1": macro,
            "macro_f1_present": macro_present,
            "micro_f1": micro,
            "accuracy": acc,
            "confusion_matrix": {
                "labels": cm_labels,
                "matrix": cm.tolist(),
            },
        }
        return BenchmarkResult(
            task_id=task.task_id,
            task_name=task.name,
            split=split,
            n_samples=len(samples),
            n_units=len(y_true),
            primary_metric="macro_f1",
            primary_value=_round(macro),
            passed=macro >= task.pass_threshold,
            metrics=_round(metrics),
            per_class=_round({k: per_class[k] for k in per_class}),
        )

    # -- BENCH-002 ----------------------------------------------------------

    def _eval_bench002(self, task, split, samples, collected) -> BenchmarkResult:
        y_true = collected["y_true"]  # True = manufacturable
        y_pred = collected["y_pred"]
        conf_valid = collected["conf_valid"]
        ious = collected["localization_iou"]

        # F1 for the "manufacturable" positive class.
        rates_valid = M.binary_rates(y_true, y_pred, pos_label=True)
        # Spec FNR = invalid predicted as valid -> treat INVALID as positive.
        rates_invalid = M.binary_rates(
            [not v for v in y_true], [not v for v in y_pred], pos_label=True
        )
        binary_f1 = rates_valid["f1"]
        # AUROC for the binary prediction using validity confidence.
        auroc = M.roc_auc(y_true, conf_valid)
        loc_iou = float(np.mean(ious)) if ious else 1.0

        metrics = {
            "binary_f1": binary_f1,
            "fpr": rates_invalid["fpr"],  # valid predicted invalid
            "fnr": rates_invalid["fnr"],  # invalid predicted valid (safety)
            "accuracy": rates_valid["accuracy"],
            "auroc": auroc,
            "violation_localization_iou": loc_iou,
            "confusion": {
                "tp_valid": rates_valid["tp"],
                "fp_valid": rates_valid["fp"],
                "fn_valid": rates_valid["fn"],
                "tn_valid": rates_valid["tn"],
            },
        }
        passed = (
            binary_f1 >= task.pass_threshold
            and rates_invalid["fnr"] <= task.critical_threshold
        )
        return BenchmarkResult(
            task_id=task.task_id,
            task_name=task.name,
            split=split,
            n_samples=len(samples),
            n_units=len(y_true),
            primary_metric="binary_f1",
            primary_value=_round(binary_f1),
            passed=passed,
            metrics=_round(metrics),
            per_class={},
        )

    # -- BENCH-003 ----------------------------------------------------------

    def _eval_bench003(self, task, split, samples, collected) -> BenchmarkResult:
        y_true = collected["y_true"]
        y_pred = collected["y_pred"]
        labels = collected["labels"]
        ml = M.multilabel_macro_f1(y_true, y_pred, labels)
        h_loss = M.hamming_loss(y_true, y_pred, labels)
        subset = M.subset_accuracy(y_true, y_pred)
        metrics = {
            "macro_f1": ml["macro_f1"],
            "micro_f1": ml["micro_f1"],
            "hamming_loss": h_loss,
            "subset_accuracy": subset,
        }
        return BenchmarkResult(
            task_id=task.task_id,
            task_name=task.name,
            split=split,
            n_samples=len(samples),
            n_units=len(y_true),
            primary_metric="macro_f1",
            primary_value=_round(ml["macro_f1"]),
            passed=ml["macro_f1"] >= task.pass_threshold,
            metrics=_round(metrics),
            per_class=_round(ml["per_label"]),
        )

    # -- BENCH-004 ----------------------------------------------------------

    def _eval_bench004(self, task, split, samples, collected) -> BenchmarkResult:
        y_true = collected["y_true"]  # True = anomalous
        scores = collected["scores"]
        auroc = M.roc_auc(y_true, scores)

        # F1 at the threshold that maximizes F1 over a fixed grid.
        best_f1 = 0.0
        best_thr = 0.0
        for thr in np.linspace(0.0, 1.0, 101):
            preds = [s >= thr for s in scores]
            rates = M.binary_rates(y_true, preds, pos_label=True)
            if rates["f1"] > best_f1:
                best_f1 = rates["f1"]
                best_thr = float(thr)

        metrics = {
            "auroc": auroc,
            "f1_optimal": best_f1,
            "f1_optimal_threshold": best_thr,
            "n_anomalous": int(sum(1 for v in y_true if v)),
            "n_normal": int(sum(1 for v in y_true if not v)),
        }
        return BenchmarkResult(
            task_id=task.task_id,
            task_name=task.name,
            split=split,
            n_samples=len(samples),
            n_units=len(y_true),
            primary_metric="auroc",
            primary_value=_round(auroc),
            passed=auroc >= task.pass_threshold,
            metrics=_round(metrics),
            per_class={},
        )

    # ------------------------------------------------------------------
    # Run-all
    # ------------------------------------------------------------------

    def run_all(
        self, split: str = "test", tasks: list[str] | None = None
    ) -> dict[str, BenchmarkResult]:
        task_ids = tasks or list(ALL_TASKS.keys())
        return {tid: self.run_task(tid, split) for tid in task_ids}
