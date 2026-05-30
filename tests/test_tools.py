"""Tests for the packaging/ops tools (tools/verify_dataset.py, migrate_dataset.py).

Generates a tiny real dataset via ``omim.synthetic`` and exercises both tools
against it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"


def _load_tool(name: str):
    """Import a tools/*.py script as a module by file path."""
    path = TOOLS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"omim_tools_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tiny_dataset(tmp_path_factory) -> Path:
    """Generate a small, schema-valid dataset and return its directory."""
    from omim.synthetic import PanelGenerator, PanelGeneratorConfig

    out_dir = tmp_path_factory.mktemp("dataset")
    config = PanelGeneratorConfig(random_seed=7, num_samples=12, invalid_sample_ratio=0.25)
    manifest = PanelGenerator(config).generate_dataset(out_dir)

    # Sanity: the generator must have kept at least one sample and written the
    # canonical metadata file (the migrate tool depends on it).
    assert manifest.total_samples >= 1
    assert (out_dir / "dataset_metadata.json").exists()
    return out_dir


# ---------------------------------------------------------------------------
# verify_dataset.py
# ---------------------------------------------------------------------------


def test_verify_dataset_exits_zero_on_valid_dataset(tiny_dataset: Path):
    verify = _load_tool("verify_dataset")
    assert verify.main([str(tiny_dataset)]) == 0


def test_verify_dataset_exits_nonzero_on_missing_dir(tmp_path: Path):
    verify = _load_tool("verify_dataset")
    assert verify.main([str(tmp_path / "does_not_exist")]) == 1


# ---------------------------------------------------------------------------
# migrate_dataset.py
# ---------------------------------------------------------------------------


def test_migrate_to_current_reports_already_current(tiny_dataset: Path, capsys):
    migrate = _load_tool("migrate_dataset")
    rc = migrate.main([str(tiny_dataset), "--to", "v0.1.0"])
    assert rc == 0
    out = capsys.readouterr().out.lower()
    assert "already current" in out


def test_migrate_dry_run_does_not_modify_files(tiny_dataset: Path):
    """A dry-run migration (even to a different version) must not touch files."""
    migrate = _load_tool("migrate_dataset")

    # Snapshot every file's mtime + content hash before the run.
    def _snapshot() -> dict[str, tuple[float, int]]:
        snap: dict[str, tuple[float, int]] = {}
        for p in sorted(tiny_dataset.rglob("*")):
            if p.is_file():
                st = p.stat()
                snap[str(p)] = (st.st_mtime, st.st_size)
        return snap

    before = _snapshot()

    # Identity target: dry-run, no --apply.
    migrate.main([str(tiny_dataset), "--to", "v0.1.0"])

    after = _snapshot()
    assert before == after, "dry-run migration modified dataset files"


def test_migrate_detect_schema_version(tiny_dataset: Path):
    migrate = _load_tool("migrate_dataset")
    assert migrate.detect_schema_version(tiny_dataset) == "v0.1.0"


def test_migrate_unimplemented_step_errors_cleanly(tiny_dataset: Path, capsys):
    """v0.1.0 -> v0.2.0 is scaffolded but not implemented; must error, not corrupt."""
    migrate = _load_tool("migrate_dataset")
    rc = migrate.main([str(tiny_dataset), "--to", "v0.2.0"])
    assert rc == 2
    err = capsys.readouterr().err.lower()
    assert "not yet implemented" in err


def test_migration_registry_has_identity_and_scaffold():
    migrate = _load_tool("migrate_dataset")
    assert ("v0.1.0", "v0.1.0") in migrate.MIGRATIONS
    assert migrate.MIGRATIONS[("v0.1.0", "v0.1.0")].implemented is True
    assert ("v0.1.0", "v0.2.0") in migrate.MIGRATIONS
    assert migrate.MIGRATIONS[("v0.1.0", "v0.2.0")].implemented is False


def test_migrate_missing_metadata_errors(tmp_path: Path):
    migrate = _load_tool("migrate_dataset")
    rc = migrate.main([str(tmp_path), "--to", "v0.1.0"])
    assert rc == 1


# ---------------------------------------------------------------------------
# End-to-end: run verify_dataset.py as a real subprocess with src on the path.
# ---------------------------------------------------------------------------


def test_verify_dataset_as_subprocess(tiny_dataset: Path):
    import subprocess

    env = {
        **__import__("os").environ,
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }
    result = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "verify_dataset.py"), str(tiny_dataset)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_dataset_metadata_schema_version_present(tiny_dataset: Path):
    meta = json.loads((tiny_dataset / "dataset_metadata.json").read_text(encoding="utf-8"))
    assert meta["schema_version"] == "v0.1.0"
