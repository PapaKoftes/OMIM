"""Project-structure identification: the full tree.

Builds a ``ProjectStructure`` (project -> assemblies -> panels -> features) from a
set of identified panels. This is the top of the identification stack: it calls
the assembly grouper and packages the result as a navigable project tree.

Separate from :mod:`omim.identify.assembly` by design — assembly answers "which
panels form one 3D piece", project answers "how is the whole delivery organised".
"""

from __future__ import annotations

from typing import Any

from omim.identify.assembly import identify_assemblies
from omim.identify.models import PanelRef, ProjectStructure
from omim.identify.parts import PartIdentification


def build_project_structure(
    panels: list[tuple[PartIdentification, str]],
    project_id: str,
    name: str = "",
    **params: Any,
) -> ProjectStructure:
    """Assemble identified panels into a project tree.

    Parameters
    ----------
    panels:
        ``(PartIdentification, source_file)`` for every panel in the project.
    project_id, name:
        Identity for the project node.

    Assemblies with >= 2 panels are kept as assemblies; confident-but-singleton
    groups are surfaced under ``ungrouped_panels`` so the tree honestly separates
    "grouped into a construction" from "standalone part".
    """
    assemblies = identify_assemblies(panels, **params)

    grouped = [a for a in assemblies if a.panel_count >= 2]
    singles = [a for a in assemblies if a.panel_count < 2]
    ungrouped: list[PanelRef] = [p for a in singles for p in a.panels]

    total_panels = sum(a.panel_count for a in assemblies)

    return ProjectStructure(
        project_id=project_id,
        name=name,
        assemblies=grouped,
        assembly_count=len(grouped),
        panel_count=total_panels,
        ungrouped_panels=ungrouped,
        provenance={
            "inference_method": "heuristic",
            "pipeline_stage": "project_identification",
            "module": "omim.identify.project",
        },
    )
