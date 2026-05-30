"""OMIM benchmarks — evaluable ML tasks over the synthetic dataset.

Four tasks (BENCH-001..004) evaluate the deterministic OMIM baseline
(``FeatureClassifier`` + ``RuleEngine``) against synthetic ground truth from
``labels.json``. Everything here is deterministic and depends only on numpy
(no sklearn, no torch / GPU).

See docs/09_BENCHMARKS/ for task definitions, metrics, and the train/test
policy.
"""

from __future__ import annotations

from omim.benchmarks import metrics
from omim.benchmarks.evaluator import BenchmarkEvaluator, BenchmarkResult
from omim.benchmarks.runner import (
    render_markdown_table,
    report_to_json,
    run_benchmarks,
)
from omim.benchmarks.splitter import BenchmarkSplitter, DatasetSplits
from omim.benchmarks.tasks import (
    ALL_TASKS,
    FEATURE_CLASSES,
    FEATURE_TO_OPERATIONS,
    OPERATION_LABELS,
    BaselineModel,
    Bench001,
    Bench002,
    Bench003,
    Bench004,
    BenchmarkSample,
    compute_operation_ground_truth,
    load_sample,
)

__all__ = [
    "metrics",
    "BenchmarkEvaluator",
    "BenchmarkResult",
    "BenchmarkSplitter",
    "DatasetSplits",
    "run_benchmarks",
    "render_markdown_table",
    "report_to_json",
    "ALL_TASKS",
    "BaselineModel",
    "BenchmarkSample",
    "load_sample",
    "Bench001",
    "Bench002",
    "Bench003",
    "Bench004",
    "FEATURE_CLASSES",
    "OPERATION_LABELS",
    "FEATURE_TO_OPERATIONS",
    "compute_operation_ground_truth",
]
