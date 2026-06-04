"""Domain registry — the map of every sheet/panel-fabrication domain OMIM can
apply to, as declarative specs rather than (over-claimed) working classifiers.

OMIM's core (parser → graph → features → validation → nesting → dataset pipeline)
is domain-agnostic: a domain is mostly *data* — a feature/part vocabulary, a
ruleset, the real datasets to train/benchmark against, and the open-source tools
worth reusing. This registry records all of that for every candidate domain, each
tagged with an honest :class:`DomainStatus` so nothing pretends to be more mature
than it is.

A domain here being PLANNED/STUB does NOT mean any inference works yet — it means
the vocabulary + datasets + reuse targets have been scoped so the work is
shovel-ready. Only PRODUCTION/EXPERIMENTAL domains have real code behind them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DomainStatus(str, Enum):
    """How mature a domain's OMIM support actually is (no over-claiming)."""

    PRODUCTION = "production"        # real, validated, well-tested code path
    EXPERIMENTAL = "experimental"    # real code, heuristics not yet calibrated on real data
    STUB = "stub"                    # vocabulary + datasets scoped; no inference yet
    PLANNED = "planned"              # researched + specced; not started


class LicenseClass(str, Enum):
    """Coarse license bucket for an external asset (vs OMIM's Apache-2.0)."""

    PERMISSIVE = "permissive"        # MIT/BSD/Apache/CC0/CC-BY — safe to use/vendor
    COPYLEFT = "copyleft"            # GPL/AGPL — do NOT vendor
    WEAK_COPYLEFT = "weak_copyleft"  # LGPL — OK as unmodified dependency only
    NONCOMMERCIAL = "noncommercial"  # CC-*-NC / research-only — eval only, don't ship
    SHAREALIKE = "sharealike"        # CC-BY-SA — usable, derivatives stay SA
    UNKNOWN = "unknown"              # not yet verified — treat as do-not-ship


@dataclass(frozen=True)
class DatasetRef:
    """A real external dataset relevant to a domain."""

    name: str
    what: str
    license: LicenseClass
    url: str
    note: str = ""


@dataclass(frozen=True)
class ToolRef:
    """An open-source tool/library worth reusing instead of reinventing."""

    name: str
    what: str
    license: LicenseClass
    url: str
    reuse_for: str = ""  # which OMIM capability it would back


@dataclass(frozen=True)
class DomainSpec:
    """Everything OMIM knows about applying to one fabrication domain."""

    key: str                         # registry id, e.g. "panel_furniture"
    title: str
    status: DomainStatus
    summary: str
    # What the domain's inference would recognize.
    feature_vocabulary: tuple[str, ...] = ()
    part_types: tuple[str, ...] = ()
    join_types: tuple[str, ...] = ()
    # Real-world grounding.
    datasets: tuple[DatasetRef, ...] = ()
    tools: tuple[ToolRef, ...] = ()
    # Honest notes: what's done, what's blocked, what's a stretch.
    fit: str = ""                    # one-line: why this fits (or is a stretch)
    blockers: tuple[str, ...] = ()
    module: str | None = None        # implementing module if any code exists

    @property
    def has_real_data(self) -> bool:
        """True if at least one usably-licensed real dataset exists for it."""
        usable = {LicenseClass.PERMISSIVE, LicenseClass.SHAREALIKE}
        return any(d.license in usable for d in self.datasets)


class DomainRegistry:
    """In-memory registry of all domain specs, with query helpers."""

    def __init__(self, specs: list[DomainSpec]) -> None:
        self._specs: dict[str, DomainSpec] = {}
        for s in specs:
            if s.key in self._specs:
                raise ValueError(f"duplicate domain key: {s.key}")
            self._specs[s.key] = s

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, key: str) -> bool:
        return key in self._specs

    def get(self, key: str) -> DomainSpec | None:
        return self._specs.get(key)

    def all(self) -> list[DomainSpec]:
        return list(self._specs.values())

    def by_status(self, status: DomainStatus) -> list[DomainSpec]:
        return [s for s in self._specs.values() if s.status == status]

    def with_real_data(self) -> list[DomainSpec]:
        return [s for s in self._specs.values() if s.has_real_data]

    def keys(self) -> list[str]:
        return list(self._specs.keys())
