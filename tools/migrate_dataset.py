#!/usr/bin/env python
"""OMIM dataset migration tool.

Implements the migration framework described in
``docs/02_SCHEMA/Versioning_Policy.md`` ("Migration Policy") and
``docs/02_SCHEMA/Canonical_Sample_Schema.md`` ("Version & Migration Policy").

A dataset's schema version is recorded in ``dataset_metadata.json``
(``schema_version`` field, e.g. ``"v0.1.0"``). Migrations are registered as
single-step transforms keyed on ``(from_version, to_version)``; multi-step
upgrades are composed by chaining adjacent steps.

Design notes
------------
* ``v0.1.0`` is the current frozen schema (see the Hackathon Freeze Rule), so
  the only *active* migration is the **identity** migration ``v0.1.0 ->
  v0.1.0`` (a no-op that simply reports the dataset is already current).
* A **scaffold** for the next breaking bump ``v0.1.0 -> v0.2.0`` is registered
  but marked ``implemented=False``. Attempting it raises a clear
  ``NotImplementedError`` rather than silently mangling data — honouring the
  policy rule "Never silently change field semantics within a version".

Safety
------
The tool is **dry-run by default**: it reports what it *would* do and never
touches files unless ``--apply`` is passed. It is import-safe (no side effects
at import time).

Usage
-----
    python tools/migrate_dataset.py <dataset_dir> --to v0.1.0
    python tools/migrate_dataset.py <dataset_dir> --to v0.2.0 --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

CURRENT_SCHEMA_VERSION = "v0.1.0"
METADATA_FILENAME = "dataset_metadata.json"


# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------


@dataclass
class Migration:
    """A single-step dataset migration ``from_version -> to_version``.

    ``apply`` receives the dataset directory and a ``dry_run`` flag. When
    ``dry_run`` is True it must NOT modify any files; it returns a list of
    human-readable strings describing the changes it would make.
    """

    from_version: str
    to_version: str
    description: str
    implemented: bool = True
    apply: Callable[[Path, bool], list[str]] = field(repr=False, default=None)  # type: ignore[assignment]

    def run(self, dataset_dir: Path, dry_run: bool) -> list[str]:
        if not self.implemented or self.apply is None:
            raise NotImplementedError(
                f"Migration {self.from_version} -> {self.to_version} is not yet "
                f"implemented ({self.description}). This is expected during the "
                f"v0.1.0 hackathon freeze; implement it when the schema bumps."
            )
        return self.apply(dataset_dir, dry_run)


def _identity_migration(dataset_dir: Path, dry_run: bool) -> list[str]:  # noqa: ARG001
    """No-op migration used when the dataset is already at the target version."""
    return []


# The registry maps (from_version, to_version) -> Migration.
MIGRATIONS: dict[tuple[str, str], Migration] = {
    ("v0.1.0", "v0.1.0"): Migration(
        from_version="v0.1.0",
        to_version="v0.1.0",
        description="Identity migration (already current).",
        implemented=True,
        apply=_identity_migration,
    ),
    # Scaffold for the first breaking bump. Not implemented during the freeze.
    # When v0.2.0 lands, set implemented=True and fill in `apply` with the
    # documented field transforms (and update validate_sample_schema to accept
    # both versions, per the Migration Policy).
    ("v0.1.0", "v0.2.0"): Migration(
        from_version="v0.1.0",
        to_version="v0.2.0",
        description="Scaffold: v0.1.0 -> v0.2.0 breaking-change migration.",
        implemented=False,
        apply=None,
    ),
}


def build_migration_path(from_version: str, to_version: str) -> list[Migration]:
    """Return the ordered list of single-step migrations from -> to.

    For the identity case returns the single no-op migration. Otherwise does a
    breadth-first search over the registered single-step migrations so future
    multi-hop upgrades (e.g. v0.1.0 -> v0.2.0 -> v0.3.0) compose automatically.

    Raises ``ValueError`` if no path exists.
    """
    if from_version == to_version:
        ident = MIGRATIONS.get((from_version, to_version))
        return [ident] if ident is not None else []

    # BFS over the migration graph.
    from collections import deque

    queue: deque[tuple[str, list[Migration]]] = deque([(from_version, [])])
    seen = {from_version}
    while queue:
        version, path = queue.popleft()
        for (src, dst), migration in MIGRATIONS.items():
            if src != version or dst == src:
                continue
            new_path = [*path, migration]
            if dst == to_version:
                return new_path
            if dst not in seen:
                seen.add(dst)
                queue.append((dst, new_path))

    raise ValueError(
        f"No migration path from {from_version} to {to_version}. "
        f"Registered steps: {sorted(k for k in MIGRATIONS if k[0] != k[1])}"
    )


# ---------------------------------------------------------------------------
# Dataset version detection
# ---------------------------------------------------------------------------


def detect_schema_version(dataset_dir: Path) -> str:
    """Read ``schema_version`` from a dataset's ``dataset_metadata.json``.

    Raises ``FileNotFoundError`` if the metadata file is missing and
    ``ValueError`` if it lacks a ``schema_version``.
    """
    metadata_path = dataset_dir / METADATA_FILENAME
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"{METADATA_FILENAME} not found in {dataset_dir}; cannot detect "
            f"schema version (is this a dataset directory?)"
        )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    version = metadata.get("schema_version")
    if not version:
        raise ValueError(
            f"{metadata_path} has no 'schema_version' field; cannot migrate."
        )
    return version


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def migrate(dataset_dir: Path, target_version: str, apply: bool) -> int:
    """Run the migration. Returns a process exit code.

    Dry-run by default; pass ``apply=True`` to actually mutate files.
    """
    try:
        current = detect_schema_version(dataset_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Dataset: {dataset_dir}")
    print(f"Current schema version: {current}")
    print(f"Target schema version:  {target_version}")

    if current == target_version:
        print(f"Already current ({current}); nothing to migrate.")
        return 0

    try:
        path = build_migration_path(current, target_version)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    mode = "APPLY" if apply else "DRY-RUN (no files will be modified)"
    print(f"Migration plan ({mode}):")
    for step in path:
        impl = "" if step.implemented else "  [NOT IMPLEMENTED]"
        print(f"  - {step.from_version} -> {step.to_version}: {step.description}{impl}")

    all_changes: list[str] = []
    for step in path:
        try:
            changes = step.run(dataset_dir, dry_run=not apply)
        except NotImplementedError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        all_changes.extend(changes)

    if all_changes:
        verb = "Applied" if apply else "Would apply"
        print(f"{verb} {len(all_changes)} change(s):")
        for change in all_changes:
            print(f"  * {change}")
    else:
        print("No file changes required.")

    if apply:
        print(f"Migration complete: {current} -> {target_version}")
    else:
        print("Dry-run only. Re-run with --apply to write changes.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="migrate_dataset.py",
        description="Migrate an OMIM dataset between schema versions.",
    )
    parser.add_argument("dataset_dir", type=Path, help="Path to the dataset directory")
    parser.add_argument(
        "--to",
        dest="to_version",
        default=CURRENT_SCHEMA_VERSION,
        help=f"Target schema version (default: {CURRENT_SCHEMA_VERSION})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually modify files (default: dry-run only).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return migrate(args.dataset_dir, args.to_version, args.apply)


if __name__ == "__main__":
    sys.exit(main())
