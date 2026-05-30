"""omim.domains.pid — Piping & Instrumentation Diagram domain (ISA-5.1).

A v0 adapter that proves OMIM's core (typed graph + provenance + deterministic
rule contracts) is domain-agnostic: it ingests an externally-annotated P&ID graph
(graphml) into the core MGG and validates ISA-5.1 compliance (tag grammar,
connectivity, control-loop completeness) — reusing ``omim.core`` with no
panel-specific imports.

See docs/10_IMPLEMENTATION/PID_Expansion_Scope.md.
"""

from omim.domains.pid.ingest import FieldMap, PIDIngestResult, ingest_graphml, ingest_nx_graph
from omim.domains.pid.isa_ontology import ParsedTag, parse_tag
from omim.domains.pid.models import PIDValidationReport
from omim.domains.pid.rules import (
    check_connectivity,
    check_loop_completeness,
    check_tag_grammar,
    validate_pid,
)

__all__ = [
    "ingest_graphml",
    "ingest_nx_graph",
    "FieldMap",
    "PIDIngestResult",
    "parse_tag",
    "ParsedTag",
    "validate_pid",
    "PIDValidationReport",
    "check_tag_grammar",
    "check_connectivity",
    "check_loop_completeness",
]
