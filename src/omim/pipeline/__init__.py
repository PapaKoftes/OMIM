"""OMIM corpus -> labeled dataset pipeline.

  * detect  — auto-detect the delivered DXF layout (per-project / flat / nest)
  * build   — run identify + auto-label over the corpus and emit a labeled
              dataset (per-panel samples, project trees, review queue, manifest)
"""

from omim.pipeline.build import BuildSummary, DatasetBuilder
from omim.pipeline.detect import CorpusLayout, LayoutDetection, detect_layout

__all__ = [
    "BuildSummary",
    "CorpusLayout",
    "DatasetBuilder",
    "LayoutDetection",
    "detect_layout",
]
