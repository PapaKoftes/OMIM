"""ReviewQueue — human-in-the-loop correction of low-confidence labels.

Below-threshold labels are written to an editable JSONL file (one label per
line). A human opens it, sets ``review_status`` to ``human_confirmed`` or
``human_corrected`` (with ``corrected_value``), and the queue reads it back and
applies the decisions to the in-memory LabelSets — turning silver labels into
gold ground truth that the dataset exporter can then trust.

JSONL is deliberate: it diffs cleanly in git, is trivial to edit by hand or feed
to a labeling UI, and supports partial review (confirm some, leave others).
"""

from __future__ import annotations

import json
from pathlib import Path

from omim.labeling.models import Label, LabelSet, ReviewStatus


class ReviewQueue:
    """Export labels needing review to JSONL and re-apply human decisions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def export(self, label_sets: list[LabelSet]) -> int:
        """Write every NEEDS_REVIEW label to the JSONL queue. Returns the count.

        Each line carries the label plus its source set so a reviewer (or UI) has
        full context. Deterministic order (by set then label id).
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for ls in label_sets:
            for lab in ls.labels:
                if lab.review_status == ReviewStatus.NEEDS_REVIEW:
                    row = {
                        "set_id": ls.set_id,
                        "source_file": ls.source_file,
                        "label": lab.model_dump(mode="json"),
                        # Reviewer fills these in:
                        "decision": "",           # "confirm" | "correct" | "reject"
                        "corrected_value": "",
                        "note": "",
                    }
                    lines.append(json.dumps(row, sort_keys=True))
        lines.sort()
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return len(lines)

    def load_decisions(self) -> dict[str, dict]:
        """Read reviewer decisions from the JSONL queue, keyed by label_id.

        Skips rows with no decision (un-reviewed). Tolerant of blank lines.
        """
        decisions: dict[str, dict] = {}
        if not self.path.exists():
            return decisions
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            decision = (row.get("decision") or "").strip().lower()
            if not decision:
                continue
            label_id = row.get("label", {}).get("label_id")
            if label_id:
                decisions[label_id] = {
                    "decision": decision,
                    "corrected_value": (row.get("corrected_value") or "").strip(),
                    "note": (row.get("note") or "").strip(),
                }
        return decisions

    def apply_decisions(
        self, label_sets: list[LabelSet], decisions: dict[str, dict] | None = None
    ) -> int:
        """Apply human decisions to the label sets in place. Returns #labels updated.

        decision == "confirm" -> HUMAN_CONFIRMED (auto value is correct)
        decision == "correct" -> HUMAN_CORRECTED + corrected_value
        decision == "reject"  -> REJECTED (excluded from the dataset)
        """
        if decisions is None:
            decisions = self.load_decisions()
        updated = 0
        for ls in label_sets:
            for lab in ls.labels:
                d = decisions.get(lab.label_id)
                if not d:
                    continue
                updated += _apply_one(lab, d)
        return updated


def _apply_one(label: Label, decision: dict) -> int:
    kind = decision["decision"]
    if kind == "confirm":
        label.review_status = ReviewStatus.HUMAN_CONFIRMED
    elif kind == "correct":
        cv = decision.get("corrected_value")
        if not cv:
            return 0  # a correction with no value is a no-op
        label.review_status = ReviewStatus.HUMAN_CORRECTED
        label.corrected_value = cv
    elif kind == "reject":
        label.review_status = ReviewStatus.REJECTED
    else:
        return 0
    label.reviewer_note = decision.get("note", "")
    return 1
