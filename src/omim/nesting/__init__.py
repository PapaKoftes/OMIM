"""Multi-panel nesting comprehension for OMIM.

Understands a DXF that contains a whole nest (a stock sheet carrying many panels),
not just a single panel: panel/sheet detection, per-panel feature assignment, and
layout sanity (utilization, overlaps, out-of-sheet).
"""

from omim.nesting.analyzer import analyze_nesting
from omim.nesting.models import NestedPanel, NestingLayout

__all__ = ["NestedPanel", "NestingLayout", "analyze_nesting"]
