"""Tests for the OMIM benchmark harness (BENCH-001..004).

These tests generate a small real dataset with the synthetic ``PanelGenerator``
(fixed seed), then run every benchmark task through ``BenchmarkEvaluator`` and
assert:

  * metrics fall in valid ranges,
  * runs are deterministic (run twice -> byte-identical results),
  * the deterministic baseline scores reasonably on feature classification,
  * the splitter produces disjoint splits.

No numbers are hard-coded as "expected" — every assertion is a range / property
check or a determinism check, so the test reflects real measured behaviour.
"""

from __future__ import annotations

import pytest

from omim.benchmarks import (
    BenchmarkEvaluator,
    BenchmarkSplitter,
    metrics,
    run_benchmarks,
)
from omim.benchmarks.metrics import iou, macro_f1, roc_auc
from omim.synthetic.generator import PanelGenerator
from omim.synthetic.models import PanelGeneratorConfig

# Evaluate on the train split (the largest band) so per-class F1 is stable on a
# small generated dataset. The split machinery itself is exercised separately.
EVAL_SPLIT = "train"


@pytest.fixture(scope="module")
def dataset_dir(tmp_path_factory) -> str:
    """Generate a small, deterministic dataset once for the whole module."""
    d = tmp_path_factory.mktemp("omim_bench_ds")
    cfg = PanelGeneratorConfig(
        random_seed=123,
        num_samples=30,
        invalid_sample_ratio=0.4,
    )
    PanelGenerator(cfg).generate_dataset(d)
    return str(d)


# ---------------------------------------------------------------------------
# Pure metric unit tests (no dataset needed)
# ---------------------------------------------------------------------------


def test_macro_f1_perfect_and_zero():
    yt = ["A", "A", "B", "B"]
    assert macro_f1(yt, yt, ["A", "B"]) == pytest.approx(1.0)
    flipped = ["B", "B", "A", "A"]
    assert macro_f1(yt, flipped, ["A", "B"]) == pytest.approx(0.0)


def test_roc_auc_perfect_and_random():
    # Perfectly separable -> 1.0
    assert roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == pytest.approx(1.0)
    # Reversed -> 0.0
    assert roc_auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == pytest.approx(0.0)
    # All ties -> 0.5
    assert roc_auc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) == pytest.approx(0.5)
    # Single class -> chance
    assert roc_auc([1, 1, 1], [0.1, 0.5, 0.9]) == pytest.approx(0.5)


def test_iou_semantics():
    assert iou(set(), set()) == pytest.approx(1.0)
    assert iou({"a"}, {"a"}) == pytest.approx(1.0)
    assert iou({"a"}, {"b"}) == pytest.approx(0.0)
    assert iou({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


def test_hamming_and_subset_accuracy():
    space = ["DRILLING", "CNC_ROUTING", "PROFILE_CUTTING", "NESTING"]
    yt = [{"DRILLING", "NESTING"}, {"PROFILE_CUTTING", "NESTING"}]
    assert metrics.subset_accuracy(yt, yt) == pytest.approx(1.0)
    assert metrics.hamming_loss(yt, yt, space) == pytest.approx(0.0)
    yp = [{"DRILLING", "NESTING"}, {"DRILLING", "NESTING"}]
    # second sample differs in 2 of 4 slots -> 2/8 total
    assert metrics.hamming_loss(yt, yp, space) == pytest.approx(0.25)
    assert metrics.subset_accuracy(yt, yp) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Splitter
# ---------------------------------------------------------------------------


def test_splitter_disjoint_from_disk(dataset_dir):
    splits = BenchmarkSplitter().resolve(dataset_dir)
    assert splits.is_disjoint()
    counts = splits.counts()
    assert sum(counts.values()) > 0


def test_splitter_deterministic_derivation():
    splitter = BenchmarkSplitter()
    ids = [f"sample_{i:06d}" for i in range(200)]
    a = splitter.create_splits(ids)
    b = splitter.create_splits(ids)
    assert a == b
    assert a.is_disjoint()
    # Every id assigned exactly once.
    assert len(a.train) + len(a.val) + len(a.test) == len(ids)
    # Banding roughly matches 70/15/15.
    assert len(a.train) > len(a.val)
    assert len(a.train) > len(a.test)


def test_splitter_repairs_overlap():
    from omim.benchmarks.splitter import DatasetSplits

    overlapping = DatasetSplits(
        train=["s1", "s2"], val=["s2", "s3"], test=["s3", "s4"]
    )
    repaired = BenchmarkSplitter()._dedupe(overlapping)
    assert repaired.is_disjoint()
    assert repaired.train == ["s1", "s2"]
    assert repaired.val == ["s3"]
    assert repaired.test == ["s4"]


# ---------------------------------------------------------------------------
# Benchmark tasks — ranges + baseline quality
# ---------------------------------------------------------------------------


def test_bench001_feature_classification(dataset_dir):
    r = BenchmarkEvaluator(dataset_dir).run_task("BENCH-001", EVAL_SPLIT)
    assert r.task_id == "BENCH-001"
    assert r.n_units > 0
    assert 0.0 <= r.metrics["macro_f1"] <= 1.0
    assert 0.0 <= r.metrics["macro_f1_present"] <= 1.0
    assert 0.0 <= r.metrics["accuracy"] <= 1.0
    # Standards-grounded valid samples plant exact standard diameters the
    # deterministic classifier recognises -> macro F1 over observed classes
    # should be comfortably above the "noteworthy" threshold.
    assert r.metrics["macro_f1_present"] > 0.5, r.per_class
    # Per-class F1 reported for every feature class in the frozen space.
    from omim.benchmarks.tasks import FEATURE_CLASSES

    for fc in FEATURE_CLASSES:
        assert fc in r.per_class
        assert 0.0 <= r.per_class[fc]["f1"] <= 1.0


def test_bench002_validity_prediction(dataset_dir):
    r = BenchmarkEvaluator(dataset_dir).run_task("BENCH-002", EVAL_SPLIT)
    assert r.task_id == "BENCH-002"
    assert r.n_units > 0
    for key in ("binary_f1", "fpr", "fnr", "accuracy", "auroc", "violation_localization_iou"):
        assert 0.0 <= r.metrics[key] <= 1.0
    # The rule engine IS the gatekeeper that generated the labels, so on
    # synthetic data its FNR must be 0 (it never misses an injected violation).
    assert r.metrics["fnr"] == pytest.approx(0.0)
    assert r.metrics["binary_f1"] > 0.85


def test_bench003_operation_inference(dataset_dir):
    r = BenchmarkEvaluator(dataset_dir).run_task("BENCH-003", EVAL_SPLIT)
    assert r.task_id == "BENCH-003"
    assert r.n_units > 0
    assert 0.0 <= r.metrics["macro_f1"] <= 1.0
    assert 0.0 <= r.metrics["hamming_loss"] <= 1.0
    assert 0.0 <= r.metrics["subset_accuracy"] <= 1.0
    # Operation inference is bounded by feature classification but should still
    # be reasonable given drilling/profile features dominate.
    assert r.metrics["macro_f1"] > 0.5


def test_bench004_anomaly_detection(dataset_dir):
    r = BenchmarkEvaluator(dataset_dir).run_task("BENCH-004", EVAL_SPLIT)
    assert r.task_id == "BENCH-004"
    assert r.n_units > 0
    assert 0.0 <= r.metrics["auroc"] <= 1.0
    assert 0.0 <= r.metrics["f1_optimal"] <= 1.0
    # Validation error count is a strong anomaly signal on synthetic data.
    assert r.metrics["auroc"] >= 0.80


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_results_are_deterministic(dataset_dir):
    ev1 = BenchmarkEvaluator(dataset_dir)
    ev2 = BenchmarkEvaluator(dataset_dir)
    for tid in ("BENCH-001", "BENCH-002", "BENCH-003", "BENCH-004"):
        r1 = ev1.run_task(tid, EVAL_SPLIT)
        r2 = ev2.run_task(tid, EVAL_SPLIT)
        assert r1.to_dict() == r2.to_dict(), f"{tid} not deterministic"


def test_run_benchmarks_report(dataset_dir):
    report = run_benchmarks(dataset_dir, split=EVAL_SPLIT)
    assert set(report["results"].keys()) == {
        "BENCH-001",
        "BENCH-002",
        "BENCH-003",
        "BENCH-004",
    }
    assert "markdown_table" in report
    assert "| Task |" in report["markdown_table"]
    assert report["baseline"] == "omim-deterministic-v0.1.0"
    # No timestamp keys leak into the (deterministic) report.
    assert "timestamp" not in report

    # Whole report is reproducible.
    report2 = run_benchmarks(dataset_dir, split=EVAL_SPLIT)
    assert report["results"] == report2["results"]
