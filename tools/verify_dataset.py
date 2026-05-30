#!/usr/bin/env python
"""OMIM dataset verifier.

Thin CLI wrapper around ``omim.integrity.check_dataset_consistency`` (the
single integrity entry point, which re-exports the canonical check from
``omim.export.dataset_exporter``). Runs the dataset-level consistency check
described in ``docs/02_SCHEMA/Canonical_Sample_Schema.md`` and exits non-zero
when any violation is found.

Usage
-----
    python tools/verify_dataset.py <dataset_dir>

Exit codes
----------
    0  dataset is consistent (no violations)
    1  bad invocation / dataset directory not found
    2  one or more consistency violations
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Prefer the consolidated integrity surface; fall back to the exporter if the
# integrity module is unavailable for any reason.
try:
    from omim.integrity import check_dataset_consistency
except ImportError:  # pragma: no cover - defensive fallback
    from omim.export.dataset_exporter import check_dataset_consistency


def verify(dataset_dir: Path) -> int:
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        print(f"ERROR: dataset directory not found: {dataset_dir}", file=sys.stderr)
        return 1

    violations = check_dataset_consistency(dataset_dir)

    if violations:
        print(f"FAIL: {len(violations)} consistency violation(s) in {dataset_dir}:")
        for v in violations:
            print(f"  - {v}")
        return 2

    print(f"OK: {dataset_dir} is consistent (no violations).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify_dataset.py",
        description="Verify an OMIM dataset's consistency (exit non-zero on violations).",
    )
    parser.add_argument("dataset_dir", type=Path, help="Path to the dataset directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return verify(args.dataset_dir)


if __name__ == "__main__":
    sys.exit(main())
