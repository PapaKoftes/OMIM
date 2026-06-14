"""Carpenter-friendly review sheet (CSV) for the human-in-the-loop labelling.

The JSONL review queue (``review.py``) is correct but engineer-facing. This module
exports the SAME below-confidence labels as a plain CSV a non-technical expert
(a carpenter, a cabinet maker) can open in Excel / Google Sheets, understand, and
fill in — then imports their answers back through the exact same decision logic
(confirm / correct / reject) so their corrections become gold ground truth.

The sheet speaks plain English, not code:

  file | what OMIM thinks this is | how sure | is it right? (yes/no) |
  if no, what is it? | notes

The reviewer only touches two columns: "is it right?" and (when wrong) "what is
it?". Everything else is context. A companion glossary CSV explains every term.
"""

from __future__ import annotations

import csv
from pathlib import Path

from omim.labeling.models import Label, LabelSet, ReviewStatus

# Plain-English names for the internal label kinds + classes a reviewer sees.
_KIND_PLAIN = {
    "feature": "hole / cut detail",
    "part": "whole panel type",
    "assembly": "group of panels",
    "project": "whole project",
}

# Plain-English glossary for the machine class names (extend freely; unknown
# values pass through as-is so the sheet is never blank).
_CLASS_PLAIN: dict[str, str] = {
    "SHELF_PIN_HOLE": "shelf-pin hole (5mm, holds a shelf peg)",
    "HINGE_CUP_HOLE": "hinge cup (35mm bore for a concealed hinge)",
    "CONFIRMAT_HOLE": "Confirmat / Euro-screw hole (7mm)",
    "DOWEL_HOLE": "dowel hole (8mm)",
    "DOWEL_HOLE_LIGHT": "dowel hole (6mm)",
    "DOWEL_HOLE_HEAVY": "dowel hole (10mm)",
    "CAM_HOLE": "cam fitting hole (Minifix, 15mm)",
    "HARDWARE_HOLE": "hardware mounting hole (handle/lock, 20-50mm)",
    "THROUGH_HOLE": "plain drilled through-hole",
    "POCKET": "pocket / recess (milled, not all the way through)",
    "GROOVE": "groove / channel (long narrow milled slot)",
    "INTERNAL_CUTOUT": "internal cut-out (hole through the panel)",
    "PROFILE_CUT": "outline / profile cut (the panel edge)",
    "SIDE_PANEL": "cabinet side",
    "TOP_PANEL": "cabinet top",
    "BOTTOM_PANEL": "cabinet bottom",
    "SHELF": "shelf",
    "DOOR": "door",
    "DRAWER_FRONT": "drawer front",
    "BACK_PANEL": "back panel",
    "DIVIDER": "divider / partition",
    "UNKNOWN_PART": "not sure / other",
    "UNKNOWN_FEATURE": "not sure / other",
    "ENGRAVING": "engraving / marking",
}

_HEADER = [
    "row_id",                    # opaque id — DO NOT EDIT (links the answer back)
    "file",
    "picture",                   # relative path to an SVG thumbnail of the panel
    "what OMIM thinks this is",
    "how sure (%)",
    "other guesses",
    "is it right? (yes/no)",     # reviewer fills this
    "if no, what is it?",        # reviewer fills this (when 'no')
    "notes",                     # optional
]


def plain_class(value: str) -> str:
    """Human phrasing for a machine class name (passes unknowns through)."""
    return _CLASS_PLAIN.get(value, value.replace("_", " ").lower())


def _alts_plain(label: Label) -> str:
    out = []
    for a in label.alternatives[:3]:
        v = a.get("part_type") or a.get("feature_class")
        if v:
            out.append(plain_class(str(v)))
    return "; ".join(out)


def export_review_sheet(
    label_sets: list[LabelSet],
    path: str | Path,
    thumbnails: dict[str, str] | None = None,
) -> int:
    """Write below-confidence labels to a carpenter-friendly CSV. Returns #rows.

    Only NEEDS_REVIEW labels are written (the auto-accepted ones don't need a
    human). ``row_id`` is the opaque label_id so answers re-link on import.
    *thumbnails* maps a LabelSet.graph_id to a relative SVG path, filled into the
    "picture" column so the reviewer can see the panel.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    thumbnails = thumbnails or {}
    rows: list[list[str]] = []
    for ls in label_sets:
        fname = Path(ls.source_file).name or ls.source_file or ls.graph_id
        pic = thumbnails.get(ls.graph_id, "")
        for lab in ls.labels:
            if lab.review_status != ReviewStatus.NEEDS_REVIEW:
                continue
            kind = _KIND_PLAIN.get(lab.kind.value, lab.kind.value)
            rows.append([
                lab.label_id,
                fname,
                pic,
                f"{plain_class(lab.value)}  ({kind})",
                f"{round(lab.confidence * 100)}",
                _alts_plain(lab),
                "",   # is it right?
                "",   # if no, what is it?
                "",   # notes
            ])
    rows.sort(key=lambda r: (r[1], r[0]))
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(_HEADER)
        w.writerows(rows)
    return len(rows)


def write_glossary(path: str | Path) -> None:
    """Write a companion glossary CSV so a reviewer knows what each term means."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["term", "plain meaning"])
        for code, plain in sorted(_CLASS_PLAIN.items()):
            w.writerow([code, plain])


def _normalise_yes_no(text: str) -> str | None:
    t = (text or "").strip().lower()
    if t in ("y", "yes", "right", "correct", "true", "1", "ok", "✓"):
        return "yes"
    if t in ("n", "no", "wrong", "incorrect", "false", "0", "✗", "x"):
        return "no"
    return None


def _plain_to_class(text: str) -> str:
    """Map a reviewer's plain answer back to a machine class when possible.

    Accepts either a known plain phrase, a raw class name, or free text (kept
    verbatim so nothing is lost — an unknown correction is still a real label).
    """
    t = (text or "").strip()
    if not t:
        return ""
    upper = t.upper().replace(" ", "_")
    if upper in _CLASS_PLAIN:
        return upper
    # reverse-lookup the plain phrasing
    for code, plain in _CLASS_PLAIN.items():
        if t.lower() == plain.lower() or t.lower() in plain.lower():
            return code
    return t  # free text — preserved as-is


def import_review_sheet(path: str | Path) -> dict[str, dict]:
    """Read a filled-in review CSV into decisions keyed by label_id.

    Maps the carpenter's plain answers onto the same decision shape the JSONL
    queue uses: ``{"decision": confirm|correct|reject, "corrected_value", "note"}``.
    Blank / unanswered rows are skipped (left for a later pass).
    """
    path = Path(path)
    decisions: dict[str, dict] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            label_id = (row.get("row_id") or "").strip()
            if not label_id:
                continue
            yn = _normalise_yes_no(row.get("is it right? (yes/no)", ""))
            note = (row.get("notes") or "").strip()
            if yn == "yes":
                decisions[label_id] = {"decision": "confirm", "corrected_value": "",
                                       "note": note}
            elif yn == "no":
                corrected = _plain_to_class(row.get("if no, what is it?", ""))
                if corrected:
                    decisions[label_id] = {"decision": "correct",
                                           "corrected_value": corrected, "note": note}
                else:
                    # marked wrong but no replacement given -> reject (drop it)
                    decisions[label_id] = {"decision": "reject", "corrected_value": "",
                                           "note": note or "marked wrong, no value given"}
            # blank answer -> skip (un-reviewed)
    return decisions
