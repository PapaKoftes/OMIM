"""omim.domains — domain adapters over the domain-agnostic ``omim.core``.

Each subpackage adapts a specific engineering domain onto the shared core
(typed graph + provenance + deterministic rule contracts):

- ``omim.domains.panel`` — cabinet/panel CNC from DXF (the original domain).
- ``omim.domains.pid``   — Piping & Instrumentation Diagrams (ISA-5.1).

The full map of every domain OMIM can apply to (with honest status, vocabulary,
researched datasets, and open-source tools to reuse) lives in the *registry* —
declarative specs, not over-claimed code:

    from omim.domains import build_registry
    reg = build_registry()
    reg.by_status(DomainStatus.PRODUCTION)   # what actually works
    reg.with_real_data()                     # where real datasets exist
"""

from omim.domains.catalog import build_registry
from omim.domains.registry import (
    DatasetRef,
    DomainRegistry,
    DomainSpec,
    DomainStatus,
    LicenseClass,
    ToolRef,
)

__all__ = [
    "DatasetRef",
    "DomainRegistry",
    "DomainSpec",
    "DomainStatus",
    "LicenseClass",
    "ToolRef",
    "build_registry",
]
