"""Corpus -> labeled dataset pipeline.

Point this at a delivered folder of panel DXFs; it auto-detects the layout,
runs the full identify + auto-label stack over every panel, groups panels into
projects/assemblies, and writes:

  * ``samples/<panel>/`` — per-panel record: mgg.json, labels.json, depth/nesting
  * ``projects/<project>.json`` — the project tree (assemblies -> panels)
  * ``review_queue.jsonl`` — every below-threshold label, ready for human review
  * ``dataset_manifest.json`` — counts, layout, label/gold statistics

Designed to scale to a large delivery: each panel is independent, failures are
isolated (a bad DXF is logged and skipped, never fatal).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from omim.graph.builder import MGGBuilder
from omim.identify.parts import identify_part
from omim.identify.project import build_project_structure
from omim.labeling import AutoLabeler, LabelSet, ReviewQueue
from omim.labeling.autolabeler import labelset_from_project
from omim.nesting import analyze_nesting, split_raw_geometry_by_panels
from omim.parser.dxf_parser import DXFParser
from omim.pipeline.detect import CorpusLayout, detect_layout
from omim.semantic.classifier import FeatureClassifier

# Fixed timestamp for byte-reproducible dataset artifacts. The builder accepts an
# injectable creation_timestamp precisely so output does not embed wall-clock time;
# the dataset pipeline pins it so two runs over identical input produce identical
# mgg.json files (mirrors the synthetic generator's determinism guarantee).
_PINNED_TIMESTAMP = "2000-01-01T00:00:00+00:00"

logger = logging.getLogger(__name__)


@dataclass
class PanelRecord:
    panel_id: str
    source_file: str
    project: str
    label_set: LabelSet
    part_type: str
    mgg_dict: dict


@dataclass
class BuildSummary:
    layout: str
    dxf_files: int
    panels: int
    projects: int
    labels_total: int
    labels_needing_review: int
    failures: list[str] = field(default_factory=list)
    output_dir: str = ""


class DatasetBuilder:
    """Build a labeled dataset from a corpus directory."""

    def __init__(
        self,
        accept_threshold: float = 0.75,
        reject_threshold: float = 0.30,
    ) -> None:
        self._accept_threshold = accept_threshold
        self._parser = DXFParser()
        self._builder = MGGBuilder()
        self._classifier = FeatureClassifier()
        self._labeler = AutoLabeler(
            accept_threshold=accept_threshold,
            reject_threshold=reject_threshold,
            classifier=self._classifier,
        )

    # -- panel enumeration -------------------------------------------------

    def _panels_from_file(self, path: Path, project: str) -> list[PanelRecord]:
        """Parse one DXF into one or more panel records, genuinely splitting nests.

        A multi-panel nest is split into one independent RawGeometry per panel
        (omim.nesting.split), and each is built + labeled as its own panel — so a
        sheet of N panels yields N records, not 1. Single-panel files yield 1.
        Uses a pinned creation_timestamp for byte-reproducible mgg.json output.
        """
        result = self._parser.parse(path)
        if not result.success or not result.geometry:
            raise ValueError(f"parse failed: {[e.error_code for e in result.errors]}")

        sub_geometries = split_raw_geometry_by_panels(result.geometry)
        records: list[PanelRecord] = []
        for raw in sub_geometries:
            mgg = self._builder.build(raw, creation_timestamp=_PINNED_TIMESTAMP)
            annotations = self._classifier.classify(mgg)
            ls = self._labeler.label_panel(mgg)
            part = identify_part(mgg, annotations)
            mgg_dict = mgg.to_dict()
            # Record the nesting view of this (now single-panel) graph for context.
            mgg_dict["_nesting"] = analyze_nesting(mgg).model_dump()
            records.append(PanelRecord(
                panel_id=mgg.metadata.graph_id,
                source_file=str(path),
                project=project,
                label_set=ls,
                part_type=part.part_type,
                mgg_dict=mgg_dict,
            ))
        return records

    # -- main build --------------------------------------------------------

    def build(self, corpus_dir: str | Path, output_dir: str | Path) -> BuildSummary:
        corpus_dir = Path(corpus_dir)
        output_dir = Path(output_dir)
        (output_dir / "samples").mkdir(parents=True, exist_ok=True)
        (output_dir / "projects").mkdir(parents=True, exist_ok=True)

        detection = detect_layout(corpus_dir)
        logger.info("Detected corpus layout: %s (%s)", detection.layout, detection.reason)

        # Map each DXF file to a project name based on the detected layout.
        dxfs = sorted(corpus_dir.rglob("*.dxf"))
        file_project: dict[Path, str] = {}
        for p in dxfs:
            if detection.layout == CorpusLayout.PER_PROJECT_FOLDERS:
                file_project[p] = p.parent.name
            else:
                # Flat pile / nest files: each file is its own project unit.
                file_project[p] = p.stem

        all_records: list[PanelRecord] = []
        failures: list[str] = []
        for p in dxfs:
            try:
                all_records.extend(self._panels_from_file(p, file_project[p]))
            except Exception as exc:  # noqa: BLE001 — isolate per-file failures
                logger.warning("Skipping %s: %s", p, exc)
                failures.append(f"{p}: {exc}")

        # --- write per-panel samples ---
        label_sets: list[LabelSet] = []
        for rec in all_records:
            sample_dir = output_dir / "samples" / _safe(rec.panel_id)
            sample_dir.mkdir(parents=True, exist_ok=True)
            (sample_dir / "mgg.json").write_text(
                json.dumps(rec.mgg_dict, indent=2, default=str), encoding="utf-8"
            )
            (sample_dir / "labels.json").write_text(
                rec.label_set.model_dump_json(indent=2), encoding="utf-8"
            )
            label_sets.append(rec.label_set)

        # --- group panels into projects + write project trees ---
        by_project: dict[str, list[PanelRecord]] = {}
        for rec in all_records:
            by_project.setdefault(rec.project, []).append(rec)

        for project, recs in sorted(by_project.items()):
            # Reconstruct a PartIdentification per panel from its stored record.
            panel_inputs = [
                (_part_id_from_record(r), r.source_file) for r in recs
            ]
            structure = build_project_structure(
                panel_inputs, project_id=project, name=project,
            )
            (output_dir / "projects" / f"{_safe(project)}.json").write_text(
                structure.model_dump_json(indent=2), encoding="utf-8"
            )
            # Assembly + project identifications are heuristic -> they go through
            # the SAME review queue as feature/part labels (not written unreviewed).
            label_sets.append(
                labelset_from_project(structure, accept_threshold=self._accept_threshold)
            )

        # --- review queue ---
        review_path = output_dir / "review_queue.jsonl"
        n_review = ReviewQueue(review_path).export(label_sets)

        labels_total = sum(len(ls.labels) for ls in label_sets)
        summary = BuildSummary(
            layout=detection.layout.value,
            dxf_files=len(dxfs),
            panels=len(all_records),
            projects=len(by_project),
            labels_total=labels_total,
            labels_needing_review=n_review,
            failures=failures,
            output_dir=str(output_dir),
        )
        (output_dir / "dataset_manifest.json").write_text(
            json.dumps(summary.__dict__, indent=2), encoding="utf-8"
        )
        return summary


def _safe(name: str) -> str:
    """Filesystem-safe id."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)


def _part_id_from_record(rec: PanelRecord):
    """Reconstruct a PartIdentification from a stored panel record (cheap)."""
    from omim.identify.models import PartIdentification

    meta = rec.mgg_dict.get("metadata", {})
    return PartIdentification(
        panel_id=rec.panel_id,
        part_type=rec.part_type,
        confidence=next(
            (lab.confidence for lab in rec.label_set.labels if lab.kind.value == "part"),
            0.0,
        ),
        width_mm=meta.get("panel_width_mm"),
        height_mm=meta.get("panel_height_mm"),
        thickness_mm=_max_depth(rec.mgg_dict),
    )


def _max_depth(mgg_dict: dict) -> float | None:
    depths = [
        n.get("depth_mm")
        for n in mgg_dict.get("nodes", [])
        if isinstance(n, dict) and n.get("depth_mm") is not None
    ]
    return max(depths) if depths else None
