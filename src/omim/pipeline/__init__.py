"""OMIM corpus -> labeled dataset pipeline.

  * detect  — auto-detect the delivered DXF layout (per-project / flat / nest)
  * build   — run identify + auto-label over the corpus and emit a labeled
              dataset (per-panel samples, project trees, review queue, manifest)
"""

from omim.pipeline.build import (
    BuildSummary,
    DatasetBuilder,
    apply_review_to_dataset,
    calibrate_from_dataset,
)
from omim.pipeline.detect import CorpusLayout, LayoutDetection, detect_layout
from omim.pipeline.tune import TunedRuleset, tune_ruleset, write_tuned_ruleset

__all__ = [
    "BuildSummary",
    "CorpusLayout",
    "DatasetBuilder",
    "LayoutDetection",
    "TunedRuleset",
    "apply_review_to_dataset",
    "calibrate_from_dataset",
    "detect_layout",
    "tune_ruleset",
    "write_tuned_ruleset",
]
