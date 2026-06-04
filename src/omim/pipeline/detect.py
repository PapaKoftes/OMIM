"""Auto-detect how a delivered DXF corpus is organised.

Three layouts are supported (the user said "mixed / not sure yet"):

  * PER_PROJECT_FOLDERS — subdirectories each holding the panel DXFs of one
    3D construction. Detected when DXFs live in >1 subdirectory.
  * NEST_FILES — each DXF is a nested sheet carrying many panels. Detected when
    a sampled DXF parses to a multi-panel nest (>1 panel via the nesting layer).
  * FLAT_PILE — many single-panel DXFs in one directory.

Detection samples a few files rather than parsing the whole corpus, so it stays
cheap on large deliveries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CorpusLayout(str, Enum):
    PER_PROJECT_FOLDERS = "per_project_folders"
    NEST_FILES = "nest_files"
    FLAT_PILE = "flat_pile"


@dataclass
class LayoutDetection:
    layout: CorpusLayout
    dxf_count: int
    subdir_count: int
    sampled_nest: bool = False
    reason: str = ""
    project_dirs: list[Path] = field(default_factory=list)


def _dxf_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.dxf"))


def detect_layout(root: str | Path, sample: int = 3) -> LayoutDetection:
    """Detect the corpus layout under *root* by structure + a small parse sample."""
    root = Path(root)
    dxfs = _dxf_files(root)
    if not dxfs:
        return LayoutDetection(
            layout=CorpusLayout.FLAT_PILE, dxf_count=0, subdir_count=0,
            reason="no .dxf files found",
        )

    # Subdirectories that directly contain DXFs.
    project_dirs = sorted({
        p.parent for p in dxfs if p.parent != root
    })

    # Sample a few files and see whether any is a multi-panel nest.
    sampled_nest = _sample_is_nest(dxfs[: max(1, sample)])

    if sampled_nest:
        return LayoutDetection(
            layout=CorpusLayout.NEST_FILES, dxf_count=len(dxfs),
            subdir_count=len(project_dirs), sampled_nest=True,
            reason="sampled DXF parsed to a multi-panel nest",
            project_dirs=project_dirs,
        )
    if len(project_dirs) > 1:
        return LayoutDetection(
            layout=CorpusLayout.PER_PROJECT_FOLDERS, dxf_count=len(dxfs),
            subdir_count=len(project_dirs),
            reason=f"DXFs split across {len(project_dirs)} subdirectories",
            project_dirs=project_dirs,
        )
    return LayoutDetection(
        layout=CorpusLayout.FLAT_PILE, dxf_count=len(dxfs),
        subdir_count=len(project_dirs),
        reason="single directory of DXFs, none nested",
        project_dirs=project_dirs,
    )


def _sample_is_nest(paths: list[Path]) -> bool:
    """True if any sampled DXF parses to >1 panel (a nest). Import-local to keep
    detection cheap and avoid a hard import cycle."""
    from omim.graph.builder import MGGBuilder
    from omim.nesting import analyze_nesting
    from omim.parser.dxf_parser import DXFParser

    parser = DXFParser()
    builder = MGGBuilder()
    for p in paths:
        try:
            result = parser.parse(p)
            if not result.success or not result.geometry:
                continue
            mgg = builder.build(result.geometry)
            if analyze_nesting(mgg).panel_count > 1:
                return True
        except Exception:  # noqa: BLE001 — detection must never crash the run
            continue
    return False
