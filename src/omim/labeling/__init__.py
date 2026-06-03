"""OMIM auto-labeling + human review layer.

Turns identification output into confidence-scored, reviewable labels:

  * AutoLabeler  — MGG -> LabelSet (feature + part labels, confidence-banded)
  * ReviewQueue  — export below-threshold labels to editable JSONL, apply the
                   human decisions back as gold ground truth
"""

from omim.labeling.autolabeler import AutoLabeler
from omim.labeling.models import Label, LabelKind, LabelSet, ReviewStatus
from omim.labeling.review import ReviewQueue

__all__ = [
    "AutoLabeler",
    "Label",
    "LabelKind",
    "LabelSet",
    "ReviewQueue",
    "ReviewStatus",
]
