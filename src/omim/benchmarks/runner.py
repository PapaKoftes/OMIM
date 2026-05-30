"""Benchmark harness — orchestrates all tasks and renders a report.

``run_benchmarks(dataset_dir, tasks=None, split="test")`` returns a
JSON-serializable dict and can also render a markdown results table.

Deterministic: no timestamps or wall-clock fields are included, so the report
is byte-stable across runs over the same dataset.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omim.benchmarks.evaluator import BenchmarkEvaluator, BenchmarkResult

__all__ = ["run_benchmarks", "render_markdown_table", "report_to_json"]


def run_benchmarks(
    dataset_dir: str | Path,
    tasks: list[str] | None = None,
    split: str = "test",
) -> dict[str, Any]:
    """Run the benchmark suite over ``dataset_dir`` and return a report dict.

    The report has the shape::

        {
          "dataset_dir": str,
          "split": str,
          "split_counts": {"train": int, "val": int, "test": int},
          "baseline": "omim-deterministic-v0.1.0",
          "results": {task_id: <BenchmarkResult dict>, ...},
          "summary": {task_id: {"primary_metric", "value", "passed"}, ...},
          "markdown_table": str,
        }
    """
    evaluator = BenchmarkEvaluator(dataset_dir)
    results: dict[str, BenchmarkResult] = evaluator.run_all(split=split, tasks=tasks)

    summary = {
        tid: {
            "primary_metric": r.primary_metric,
            "value": r.primary_value,
            "passed": r.passed,
        }
        for tid, r in results.items()
    }
    table = render_markdown_table(results)

    return {
        "dataset_dir": str(Path(dataset_dir)),
        "split": split,
        "split_counts": evaluator.splits().counts(),
        "baseline": "omim-deterministic-v0.1.0",
        "results": {tid: r.to_dict() for tid, r in results.items()},
        "summary": summary,
        "markdown_table": table,
    }


def render_markdown_table(results: dict[str, BenchmarkResult]) -> str:
    """Render a compact markdown results table for the baseline run."""
    lines = [
        "| Task | Name | Split | N | Primary metric | Value | Pass |",
        "|------|------|-------|---|----------------|-------|------|",
    ]
    for tid in sorted(results.keys()):
        r = results[tid]
        lines.append(
            f"| {r.task_id} | {r.task_name} | {r.split} | {r.n_units} | "
            f"{r.primary_metric} | {r.primary_value:.4f} | "
            f"{'PASS' if r.passed else 'FAIL'} |"
        )
    return "\n".join(lines)


def report_to_json(report: dict[str, Any], indent: int = 2) -> str:
    """Serialize a report dict to stable JSON (sorted keys)."""
    return json.dumps(report, indent=indent, sort_keys=True, default=str)
