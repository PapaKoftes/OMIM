"""Byte-reproducibility of the synthetic generation pipeline.

The GENERATION path (``omim generate`` / ``PanelGenerator.generate_dataset``)
must be byte-reproducible from (seed, config, code): generating twice with the
same seed must produce identical bytes for every per-sample data artifact
(geometry.dxf, mgg.json, validation.json, labels.json, provenance.json), and a
different seed must produce different geometry (so the determinism is real, not
a frozen bug).

These run the generator in SEPARATE subprocesses so that PYTHONHASHSEED differs
between runs — that is the condition under which the original pipeline was
non-deterministic (ezdxf emits its CLASSES section in set-iteration order).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

SAMPLE_FILES = [
    "geometry.dxf",
    "mgg.json",
    "validation.json",
    "labels.json",
    "provenance.json",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _generate(out_dir: Path, *, n: int, seed: int) -> None:
    """Run the CLI generator in a fresh subprocess (distinct PYTHONHASHSEED)."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "omim.cli",
            "generate",
            str(out_dir),
            "-n",
            str(n),
            "--seed",
            str(seed),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"generate failed (seed={seed}):\n{result.stdout}\n{result.stderr}"
    )


def _sample_hashes(dataset_dir: Path) -> dict[str, str]:
    """Map "<sample_id>/<file>" -> sha256 for every data artifact."""
    hashes: dict[str, str] = {}
    samples_dir = dataset_dir / "samples"
    for sample_dir in sorted(samples_dir.iterdir()):
        if not sample_dir.is_dir():
            continue
        for fname in SAMPLE_FILES:
            fpath = sample_dir / fname
            assert fpath.exists(), f"missing artifact {fpath}"
            hashes[f"{sample_dir.name}/{fname}"] = _sha256(fpath)
    return hashes


def test_same_seed_is_byte_identical(tmp_path: Path) -> None:
    """Two runs with the same seed produce byte-identical artifacts."""
    d1 = tmp_path / "run1"
    d2 = tmp_path / "run2"
    _generate(d1, n=6, seed=42)
    _generate(d2, n=6, seed=42)

    h1 = _sample_hashes(d1)
    h2 = _sample_hashes(d2)

    assert h1, "no samples were generated"
    assert set(h1) == set(h2), "the two runs produced different sample sets"

    mismatches = {k: (h1[k], h2[k]) for k in h1 if h1[k] != h2[k]}
    assert not mismatches, f"non-reproducible artifacts: {sorted(mismatches)}"


def test_dataset_level_files_are_byte_identical(tmp_path: Path) -> None:
    """manifest.json and dataset_metadata.json are reproducible too."""
    d1 = tmp_path / "run1"
    d2 = tmp_path / "run2"
    _generate(d1, n=4, seed=123)
    _generate(d2, n=4, seed=123)

    for fname in ("manifest.json", "dataset_metadata.json"):
        assert _sha256(d1 / fname) == _sha256(d2 / fname), (
            f"{fname} is not byte-reproducible"
        )


def test_different_seed_changes_geometry(tmp_path: Path) -> None:
    """A different seed must change the geometry (determinism is not a frozen bug)."""
    d_a = tmp_path / "seed_a"
    d_b = tmp_path / "seed_b"
    _generate(d_a, n=6, seed=42)
    _generate(d_b, n=6, seed=7)

    ha = _sample_hashes(d_a)
    hb = _sample_hashes(d_b)

    a_dxf = sorted(v for k, v in ha.items() if k.endswith("geometry.dxf"))
    b_dxf = sorted(v for k, v in hb.items() if k.endswith("geometry.dxf"))
    assert a_dxf, "no geometry produced for seed 42"
    assert b_dxf, "no geometry produced for seed 7"
    # The two seeds must not yield an identical multiset of geometry files.
    assert a_dxf != b_dxf, "different seeds produced identical geometry"


@pytest.mark.parametrize("seed", [1, 1000])
def test_dxf_writer_is_hashseed_independent(tmp_path: Path, seed: int) -> None:
    """The DXF writer alone is byte-stable regardless of PYTHONHASHSEED.

    Runs the writer in two subprocesses with explicitly different hash seeds —
    this directly targets the ezdxf CLASSES-section set-ordering issue.
    """
    code = (
        "from omim.synthetic.dxf_writer import DXFWriter\n"
        "from omim.synthetic.models import PanelSpec, FeatureSpec\n"
        "panel = PanelSpec(width_mm=600, height_mm=400, thickness_mm=18,"
        " boundary_points=[(0,0),(600,0),(600,400),(0,400)], panel_type='shelf')\n"
        "feats = [FeatureSpec(feature_class='SHELF_PIN_HOLE', entity_type='CIRCLE',"
        " center=(50,50), radius_mm=2.5)]\n"
        "import sys; DXFWriter().write_panel(panel, feats, sys.argv[1])\n"
    )

    out1 = tmp_path / "a.dxf"
    out2 = tmp_path / "b.dxf"
    import os

    env1 = dict(os.environ, PYTHONHASHSEED="0")
    env2 = dict(os.environ, PYTHONHASHSEED="424242")
    subprocess.run([sys.executable, "-c", code, str(out1)], env=env1, check=True)
    subprocess.run([sys.executable, "-c", code, str(out2)], env=env2, check=True)

    assert _sha256(out1) == _sha256(out2), "DXF bytes depend on PYTHONHASHSEED"
