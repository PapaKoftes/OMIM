"""Schemas for the auto-labeling + human-review layer.

A ``Label`` is one atomic, reviewable assertion (this node is a HINGE_CUP_HOLE;
this panel is a DOOR; these panels form a CARCASS), each with a confidence, the
source layer that produced it, evidence, and a review status. A ``LabelSet`` is
all labels for one panel/project. The ``ReviewQueue`` persists below-threshold
labels as editable JSONL so a human can confirm/correct them, and feeds the
corrections back as gold ground truth.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class LabelKind(str, Enum):
    FEATURE = "feature"      # a per-node feature classification
    PART = "part"            # a per-panel part type
    ASSEMBLY = "assembly"    # a panel-grouping into a 3D construction
    PROJECT = "project"      # project-level structure


class ReviewStatus(str, Enum):
    AUTO_ACCEPTED = "auto_accepted"   # confidence >= accept threshold
    NEEDS_REVIEW = "needs_review"     # in the review band
    HUMAN_CONFIRMED = "human_confirmed"
    HUMAN_CORRECTED = "human_corrected"
    REJECTED = "rejected"


class Label(BaseModel):
    """One reviewable labeled assertion."""

    label_id: str
    kind: LabelKind
    target_id: str            # node id / panel id / assembly id
    value: str                # the class/type asserted
    confidence: float = 0.0
    source_layer: str = ""    # which identifier produced it
    evidence: list[dict] = Field(default_factory=list)
    alternatives: list[dict] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.NEEDS_REVIEW
    # Populated only after human review.
    corrected_value: str | None = None
    reviewer_note: str = ""

    @property
    def final_value(self) -> str:
        """The authoritative value: a human correction wins over the auto value."""
        if self.review_status == ReviewStatus.HUMAN_CORRECTED and self.corrected_value:
            return self.corrected_value
        return self.value

    @property
    def is_gold(self) -> bool:
        """True when the label is trustworthy ground truth (human-verified)."""
        return self.review_status in (
            ReviewStatus.HUMAN_CONFIRMED,
            ReviewStatus.HUMAN_CORRECTED,
        )


class LabelSet(BaseModel):
    """All labels produced for one panel (or one project rollup)."""

    set_id: str
    source_file: str = ""
    graph_id: str = ""
    labels: list[Label] = Field(default_factory=list)

    def by_kind(self, kind: LabelKind) -> list[Label]:
        return [lab for lab in self.labels if lab.kind == kind]

    @property
    def needs_review_count(self) -> int:
        return sum(1 for lab in self.labels if lab.review_status == ReviewStatus.NEEDS_REVIEW)
