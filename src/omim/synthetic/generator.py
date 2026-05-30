"""PanelGenerator — the synthetic dataset orchestrator.

Pipeline philosophy:

    Manufacturing Standards -> Generator -> Geometry
        -> (deterministic validator is the GATEKEEPER)
        -> keep if valid-matches-intent, discard otherwise.

Ground-truth labels come from the GENERATION SPEC (PanelSpec / FeatureSpec),
never from inference. Every sample is run through the FULL OMIM pipeline
(parse -> build -> validate) and only kept when its validation outcome matches
its intended validity:

    valid sample   -> validator overall_valid must be True   (else E-005, skip)
    invalid sample -> validator overall_valid must be False  (else skip)

Determinism: a per-sample RNG is seeded as ``random_seed + sample_index``.
Provenance for the generation stage uses InferenceMethod.SYNTHETIC, confidence
1.0.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from omim.export import (
    DatasetExporter,
    ExportRequest,
    ExportValidationError,
    build_dataset_metadata,
)
from omim.graph.builder import MGGBuilder
from omim.parser.dxf_parser import DXFParser
from omim.synthetic import distributions as dist
from omim.synthetic.dxf_writer import DXFWriter
from omim.synthetic.feature_generators import (
    SINGLE_FEATURE_GENERATORS,
    generate_confirmat_pair,
    generate_profile_cut,
    generate_shelf_pin_group,
)
from omim.synthetic.invalidation import inject_violations
from omim.synthetic.models import (
    DatasetManifest,
    FeatureSpec,
    GeneratedSample,
    PanelGeneratorConfig,
    PanelSpec,
)
from omim.validation.rule_engine import RuleEngine

logger = logging.getLogger(__name__)

GENERATOR_VERSION = "v0.1.0"

# Feature classes that come in groups / pairs rather than single placements.
_GROUP_GENERATORS = {
    "SHELF_PIN_HOLE": generate_shelf_pin_group,
    "CONFIRMAT_HOLE": generate_confirmat_pair,
}


class PanelGenerator:
    """Generate synthetic cabinet-panel DXFs grounded in manufacturing standards."""

    def __init__(self, config: PanelGeneratorConfig | None = None) -> None:
        self.config = config or PanelGeneratorConfig()
        self.rng = np.random.default_rng(self.config.random_seed)

        # Pipeline components (re-used across samples).
        self.parser = DXFParser()
        self.builder = MGGBuilder()
        self.rule_engine = RuleEngine()
        self.dxf_writer = DXFWriter(dxf_version=self.config.dxf_version)

        # Ontology is optional for generation (standards are encoded directly),
        # but load it if available so the builder can use it.
        self.ontology = None

    # ------------------------------------------------------------------
    # Single-sample generation (pure spec -> GeneratedSample)
    # ------------------------------------------------------------------

    def generate_sample(self, sample_index: int) -> GeneratedSample:
        """Generate a single deterministic sample for *sample_index*."""
        sample_rng = np.random.default_rng(self.config.random_seed + sample_index)

        # --- Panel spec from realistic distributions ---
        panel = self._sample_panel(sample_rng)

        is_invalid = bool(sample_rng.random() < self.config.invalid_sample_ratio)

        # --- Features ---
        features: list[FeatureSpec] = [generate_profile_cut(panel)]
        features.extend(self._generate_features(panel, sample_rng))

        # --- Ensure shelf-pin rows are complete (>= 3) ---
        features = self._complete_shelf_pin_rows(features)

        # --- Generation-side validation (constraint grammar pre-check) ---
        # Drop any feature that slipped past the per-generator checks. The
        # profile cut is always retained.
        features = self._grammar_filter(panel, features)

        injected: list[str] = []
        if is_invalid:
            n_violations = int(
                sample_rng.integers(1, self.config.max_violations_per_invalid + 1)
            )
            features, injected = inject_violations(
                panel, features, n_violations, sample_rng
            )
            # If nothing could be injected, demote to a valid sample so the
            # ground-truth label still matches the validator outcome.
            if not injected:
                is_invalid = False

        sample_id = f"sample_{sample_index:06d}"
        return GeneratedSample(
            sample_id=sample_id,
            panel=panel,
            features=features,
            is_invalid=is_invalid,
            injected_violations=injected,
        )

    # ------------------------------------------------------------------
    # Panel + feature sampling
    # ------------------------------------------------------------------

    def _sample_panel(self, rng: np.random.Generator) -> PanelSpec:
        panel_type = dist.sample_panel_type(rng)
        width = dist.sample_width(rng)
        height = dist.sample_height(rng)
        thickness = dist.sample_thickness(rng)

        # Clamp to configured bounds (keeps GEO-004 coord range happy too).
        width = float(
            min(max(width, self.config.min_panel_width_mm), self.config.max_panel_width_mm)
        )
        height = float(
            min(max(height, self.config.min_panel_height_mm), self.config.max_panel_height_mm)
        )

        boundary = [
            (0.0, 0.0),
            (width, 0.0),
            (width, height),
            (0.0, height),
        ]
        return PanelSpec(
            width_mm=width,
            height_mm=height,
            thickness_mm=thickness,
            boundary_points=boundary,
            panel_type=panel_type,
        )

    def _generate_features(
        self, panel: PanelSpec, rng: np.random.Generator
    ) -> list[FeatureSpec]:
        """Generate features per the panel's allowed classes and hole count."""
        allowed = dist.allowed_feature_classes(panel.panel_type)
        target_count = dist.sample_hole_count(panel.panel_type, rng)
        if target_count <= 0 or not allowed:
            return []

        features: list[FeatureSpec] = []
        # Cap attempts so a constrained small panel cannot loop forever.
        attempts = 0
        max_attempts = target_count * 4 + 8

        def _circle_count() -> int:
            return sum(1 for f in features if f.entity_type == "CIRCLE")

        while _circle_count() < target_count and attempts < max_attempts:
            attempts += 1
            feature_class = allowed[int(rng.integers(0, len(allowed)))]

            if feature_class in _GROUP_GENERATORS:
                group = _GROUP_GENERATORS[feature_class](panel, rng)
                features.extend(group)
            elif feature_class in SINGLE_FEATURE_GENERATORS:
                feat = SINGLE_FEATURE_GENERATORS[feature_class](panel, rng)
                if feat is not None:  # E-001: placement may fail -> skip feature
                    features.append(feat)
            # else: unknown class for this panel type -> ignore

        return features

    def _complete_shelf_pin_rows(self, features: list[FeatureSpec]) -> list[FeatureSpec]:
        """Drop any shelf-pin group that ended up with fewer than 3 holes.

        The group generator already enforces >= 3, but a later grammar filter
        could thin a group; this guarantees the System-32 pattern invariant.
        """
        # Count members per shelf-pin group.
        counts: dict[str, int] = {}
        for f in features:
            if f.feature_class == "SHELF_PIN_HOLE" and f.group_id:
                counts[f.group_id] = counts.get(f.group_id, 0) + 1

        keep: list[FeatureSpec] = []
        for f in features:
            if (
                f.feature_class == "SHELF_PIN_HOLE"
                and f.group_id
                and counts.get(f.group_id, 0) < 3
            ):
                continue
            keep.append(f)
        return keep

    def _grammar_filter(
        self, panel: PanelSpec, features: list[FeatureSpec]
    ) -> list[FeatureSpec]:
        """Pre-validation grammar check: keep the profile cut + valid features."""
        from omim.synthetic.constraint_grammar import (
            satisfies_edge_clearance,
            satisfies_wall_thickness,
            within_panel,
        )

        kept: list[FeatureSpec] = []
        circles_so_far: list[FeatureSpec] = []
        for f in features:
            if f.feature_class == "PROFILE_CUT":
                kept.append(f)
                continue
            if f.entity_type == "CIRCLE":
                if (
                    within_panel(f, panel)
                    and satisfies_edge_clearance(f, panel)
                    and satisfies_wall_thickness(f, circles_so_far)
                ):
                    kept.append(f)
                    circles_so_far.append(f)
            else:
                if within_panel(f, panel):
                    kept.append(f)
        return self._complete_shelf_pin_rows(kept)

    # ------------------------------------------------------------------
    # Dataset generation (the gatekeeper loop)
    # ------------------------------------------------------------------

    def generate_dataset(self, output_dir: str | Path) -> DatasetManifest:
        """Generate the full dataset under *output_dir* and return its manifest.

        Layout (canonical):
            <output_dir>/samples/<sample_id>/{geometry.dxf,mgg.json,
                                              validation.json,labels.json,
                                              provenance.json}
            <output_dir>/splits/{train,val,test}.jsonl
            <output_dir>/manifest.json
            <output_dir>/_work/<sample_id>.dxf   (intermediate DXF inputs)
        """
        output_dir = Path(output_dir)
        samples_dir = output_dir / "samples"
        splits_dir = output_dir / "splits"
        work_dir = output_dir / "_work"
        for d in (samples_dir, splits_dir, work_dir):
            d.mkdir(parents=True, exist_ok=True)

        exporter = DatasetExporter(output_root=samples_dir)

        manifest = DatasetManifest(
            dataset_id=f"omim-synthetic-{self.config.schema_version}-{uuid.uuid4().hex[:8]}",
            generated_at=datetime.now(UTC).isoformat(),
            generator_version=GENERATOR_VERSION,
            schema_version=self.config.schema_version,
        )

        feature_type_counts: dict[str, int] = {}
        split_ids: dict[str, list[str]] = {"train": [], "val": [], "test": []}
        kept_samples = 0

        for idx in range(self.config.num_samples):
            sample = self.generate_sample(idx)

            # --- Write the candidate DXF ---
            dxf_path = work_dir / f"{sample.sample_id}.dxf"
            self.dxf_writer.write_panel(sample.panel, sample.features, dxf_path)

            # --- Run the FULL pipeline: parse -> build -> validate ---
            parse_result = self.parser.parse(dxf_path)
            if not parse_result.success or parse_result.geometry is None:
                logger.warning(
                    "E-001 parse failed for %s; skipping", sample.sample_id
                )
                continue

            mgg = self.builder.build(parse_result.geometry)
            report = self.rule_engine.validate(mgg)

            # --- THE VALIDATOR IS THE GATEKEEPER ---
            if not sample.is_invalid:
                # Valid sample MUST pass validation.
                if not report.overall_valid:
                    failing = [
                        r.rule_id
                        for r in (report.layer1_results + report.layer2_results)
                        if not r.passed and r.severity in ("ERROR", "SYSTEM_ERROR")
                    ]
                    logger.error(
                        "E-005 generation bug: valid sample %s failed validation "
                        "(%s); skipping",
                        sample.sample_id,
                        ", ".join(sorted(set(failing))) or "unknown",
                    )
                    continue
            else:
                # Invalid sample MUST fail validation (intent must land).
                if report.overall_valid:
                    logger.warning(
                        "Invalid sample %s passed validation (injection did not "
                        "produce an ERROR); skipping",
                        sample.sample_id,
                    )
                    continue

            # --- Assign split deterministically ---
            split = self._assign_split(idx)
            sample.split = split

            # --- Build synthetic ground-truth labels override ---
            labels_override = self._build_labels_override(sample)

            # --- Export via the canonical DatasetExporter ---
            request = ExportRequest(
                mgg=mgg,
                validation_report=report,
                semantic_annotations=None,
                source_dxf_path=str(dxf_path),
                output_dir=str(samples_dir),
                sample_id=sample.sample_id,
                split=split,
                labels_override=labels_override,
            )
            try:
                exporter.export(request)
            except ExportValidationError as exc:
                logger.error(
                    "Export schema validation failed for %s: %s; skipping",
                    sample.sample_id,
                    exc.errors,
                )
                continue

            # --- Accumulate manifest statistics ---
            kept_samples += 1
            split_ids[split].append(sample.sample_id)
            manifest.sample_ids[sample.sample_id] = split
            if sample.is_invalid:
                manifest.invalid_count += 1
            else:
                manifest.valid_count += 1
            for feat in sample.features:
                feature_type_counts[feat.feature_class] = (
                    feature_type_counts.get(feat.feature_class, 0) + 1
                )

        # --- Finalize manifest ---
        manifest.total_samples = kept_samples
        manifest.train_count = len(split_ids["train"])
        manifest.val_count = len(split_ids["val"])
        manifest.test_count = len(split_ids["test"])
        manifest.feature_type_counts = feature_type_counts

        # --- Write split files (.jsonl) ---
        for split_name, ids in split_ids.items():
            split_file = splits_dir / f"{split_name}.jsonl"
            split_file.write_text(
                "".join(f"{sid}\n" for sid in ids), encoding="utf-8"
            )

        # --- Write manifest.json ---
        (output_dir / "manifest.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )

        # --- Write canonical dataset_metadata.json (enables consistency check) ---
        metadata = build_dataset_metadata(
            config={
                "seed": self.config.random_seed,
                "n_samples": self.config.num_samples,
                "feature_density": self.config.feature_density,
                "invalid_ratio": self.config.invalid_sample_ratio,
                "panel_width_range_mm": [
                    self.config.min_panel_width_mm,
                    self.config.max_panel_width_mm,
                ],
                "panel_height_range_mm": [
                    self.config.min_panel_height_mm,
                    self.config.max_panel_height_mm,
                ],
                "panel_thickness_options_mm": self.config.panel_thickness_options_mm,
                "dataset_id": manifest.dataset_id,
            },
            statistics={
                "total_samples": manifest.total_samples,
                "valid_samples": manifest.valid_count,
                "invalid_samples": manifest.invalid_count,
                "train_samples": manifest.train_count,
                "val_samples": manifest.val_count,
                "test_samples": manifest.test_count,
                "feature_counts": feature_type_counts,
            },
        )
        import json as _json

        (output_dir / "dataset_metadata.json").write_text(
            _json.dumps(metadata, indent=2, default=str), encoding="utf-8"
        )

        logger.info(
            "Generated dataset %s: %d kept (%d valid, %d invalid) "
            "[train=%d, val=%d, test=%d]",
            manifest.dataset_id,
            manifest.total_samples,
            manifest.valid_count,
            manifest.invalid_count,
            manifest.train_count,
            manifest.val_count,
            manifest.test_count,
        )
        return manifest

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _assign_split(self, sample_index: int) -> str:
        """Deterministically assign a split by index position in the ratio bands."""
        n = max(self.config.num_samples, 1)
        train_cut = self.config.train_ratio
        val_cut = self.config.train_ratio + self.config.val_ratio
        frac = (sample_index % n) / n
        if frac < train_cut:
            return "train"
        if frac < val_cut:
            return "val"
        return "test"

    def _build_labels_override(self, sample: GeneratedSample) -> dict:
        """Build the authoritative synthetic labels.json content for a sample.

        Every feature carries position_mm (required by the canonical schema),
        its ground-truth feature_class, and any injected violations.
        """
        features: list[dict] = []
        feature_counts: dict[str, int] = {}
        for i, feat in enumerate(sample.features):
            if feat.center is not None:
                position = [float(feat.center[0]), float(feat.center[1])]
            elif feat.points:
                xs = [p[0] for p in feat.points]
                ys = [p[1] for p in feat.points]
                position = [float(sum(xs) / len(xs)), float(sum(ys) / len(ys))]
            else:
                position = None

            diameter = (feat.radius_mm * 2.0) if feat.radius_mm is not None else None
            features.append(
                {
                    "feature_id": f"{sample.sample_id}_feat_{i:03d}",
                    "feature_class": feat.feature_class,
                    "diameter_mm": diameter,
                    "depth_mm": feat.depth_mm,
                    "position_mm": position,
                    "group_id": feat.group_id,
                    "is_valid": feat.is_valid,
                    "violations": list(feat.violations),
                    "ground_truth_source": "synthetic_generator",
                    "confidence": 1.0,
                }
            )
            feature_counts[feat.feature_class] = (
                feature_counts.get(feat.feature_class, 0) + 1
            )

        return {
            "sample_id": sample.sample_id,
            "is_valid": not sample.is_invalid,
            "injected_violations": list(sample.injected_violations),
            "panel": {
                "width_mm": sample.panel.width_mm,
                "height_mm": sample.panel.height_mm,
                "thickness_mm": sample.panel.thickness_mm,
                "panel_type": sample.panel.panel_type,
            },
            "features": features,
            "feature_counts": feature_counts,
        }
