"""OMIM identification layer.

Read-only inference that builds on the geometry/feature layers to identify, in
separate properly-layered modules:

  * parts     — classify each panel as a furniture part type
  * assembly  — group panels into a single 3D construction (+ how they join)
  * project   — assemble the full project tree (project -> assemblies -> panels)

Every identification carries confidence, ranked alternatives, evidence, and
provenance, and never mutates the MGG.
"""

from omim.identify.assembly import identify_assemblies
from omim.identify.models import (
    PART_TYPES,
    AssemblyIdentification,
    PanelRef,
    PartIdentification,
    ProjectStructure,
)
from omim.identify.parts import identify_part
from omim.identify.project import build_project_structure

__all__ = [
    "PART_TYPES",
    "AssemblyIdentification",
    "PanelRef",
    "PartIdentification",
    "ProjectStructure",
    "build_project_structure",
    "identify_assemblies",
    "identify_part",
]
