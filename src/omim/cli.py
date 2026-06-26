"""OMIM CLI — command-line interface for manufacturing geometry analysis."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from omim import __version__

    parser = argparse.ArgumentParser(
        prog="omim",
        description="Open Manufacturing Intelligence Middleware",
    )
    parser.add_argument(
        "--version", action="version", version=f"omim {__version__}"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    sub = parser.add_subparsers(dest="command")

    # --- analyze ---
    analyze_p = sub.add_parser("analyze", help="Full DXF analysis pipeline")
    analyze_p.add_argument("file", type=Path, help="Path to DXF file")
    analyze_p.add_argument(
        "-o", "--output", type=Path, default=None, help="Output JSON path"
    )
    analyze_p.add_argument(
        "--cytoscape", action="store_true", help="Output in Cytoscape.js format"
    )
    analyze_p.add_argument(
        "--profile", default=None,
        help="Layer profile: a built-in name (e.g. 'cabinet') or a path to a "
             "customer profile YAML (maps the shop's layer dialect to OMIM types)",
    )

    # --- validate ---
    validate_p = sub.add_parser("validate", help="Validate a DXF file")
    validate_p.add_argument("file", type=Path, help="Path to DXF file")

    # --- generate ---
    gen_p = sub.add_parser("generate", help="Generate a synthetic panel dataset")
    gen_p.add_argument("output_dir", type=Path, help="Output dataset directory")
    gen_p.add_argument("-n", "--num-samples", type=int, default=100, help="Number of samples")
    gen_p.add_argument("--seed", type=int, default=42, help="Random seed (reproducible)")
    gen_p.add_argument(
        "--invalid-ratio", type=float, default=0.30,
        help="Fraction of intentionally-invalid samples",
    )
    gen_p.add_argument(
        "--density", choices=["sparse", "medium", "dense"], default="medium",
        help="Feature density per panel",
    )

    # --- nest ---
    nest_p = sub.add_parser("nest", help="Analyse a DXF for multi-panel nesting layout")
    nest_p.add_argument("file", type=Path, help="Path to DXF file")
    nest_p.add_argument("-o", "--output", type=Path, default=None, help="Output JSON path")

    # --- build-dataset ---
    bd_p = sub.add_parser(
        "build-dataset",
        help="Auto-detect a DXF corpus layout, identify+auto-label every panel, "
             "and emit a labeled dataset + review queue",
    )
    bd_p.add_argument("corpus_dir", type=Path, help="Directory of delivered DXFs")
    bd_p.add_argument("output_dir", type=Path, help="Where to write the dataset")
    bd_p.add_argument(
        "--accept-threshold", type=float, default=0.75,
        help="Confidence >= this is auto-accepted; below goes to the review queue",
    )
    bd_p.add_argument(
        "--profile", default=None,
        help="Layer profile: a built-in name (e.g. 'cabinet') or a path to a "
             "customer profile YAML. The shop's layer dialect -> OMIM types.",
    )

    # --- profiles ---
    sub.add_parser("profiles", help="List built-in layer profiles (agnostic-middleware adapters)")

    # --- layer-blind ---
    lb_p = sub.add_parser(
        "layer-blind",
        help="Re-classify a DXF with all layer names deleted, to show how much "
             "OMIM infers from geometry alone (the 'is it really inference?' test)",
    )
    lb_p.add_argument("file", type=Path, help="Path to DXF file")
    lb_p.add_argument(
        "--profile", default=None,
        help="Layer profile for the layer-aware baseline",
    )

    # --- calibrate ---
    cal_p = sub.add_parser(
        "calibrate",
        help="Fit a confidence calibrator from a reviewed dataset's gold labels "
             "(turns hand-set confidences into measured ones)",
    )
    cal_p.add_argument("dataset_dir", type=Path, help="A reviewed dataset directory")
    cal_p.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Calibrator JSON path (default: <dataset_dir>/calibrator.json)",
    )

    # --- apply-review ---
    ar_p = sub.add_parser(
        "apply-review",
        help="Fold a filled-in review_sheet.csv (edited by a carpenter/expert) "
             "back into a built dataset — corrections become gold labels",
    )
    ar_p.add_argument("dataset_dir", type=Path, help="The built dataset directory")
    ar_p.add_argument(
        "--sheet", type=Path, default=None,
        help="The filled review CSV (default: <dataset_dir>/review_sheet.csv)",
    )

    # --- domains ---
    dom_p = sub.add_parser(
        "domains",
        help="List every fabrication domain OMIM can apply to (status + datasets)",
    )
    dom_p.add_argument("--status", default=None,
                       help="Filter by status (production|experimental|stub|planned)")
    dom_p.add_argument("--key", default=None, help="Show full detail for one domain key")

    # --- tune-ruleset ---
    tune_p = sub.add_parser(
        "tune-ruleset",
        help="Measure a real DXF corpus and emit an identification ruleset tuned to it",
    )
    tune_p.add_argument("corpus_dir", type=Path, help="Directory of delivered DXFs")
    tune_p.add_argument("-o", "--output", type=Path, required=True, help="Tuned ruleset YAML path")
    tune_p.add_argument(
        "--min-samples", type=int, default=5,
        help="Minimum corpus samples before a threshold is tuned (else keep catalog default)",
    )

    # --- verify ---
    verify_p = sub.add_parser("verify", help="Verify a dataset or sample for integrity/schema")
    verify_p.add_argument("path", type=Path, help="Dataset dir or single sample dir")

    # --- benchmark ---
    bench_p = sub.add_parser("benchmark", help="Run benchmark tasks on a dataset")
    bench_p.add_argument("dataset_dir", type=Path, help="Dataset directory")
    bench_p.add_argument("--split", default="test", help="Split to evaluate (train|val|test)")
    bench_p.add_argument("--task", default=None, help="Single task id (e.g. BENCH-001)")
    bench_p.add_argument("-o", "--output", type=Path, default=None, help="Write JSON report")

    # --- ingest / ground ---
    ingest_p = sub.add_parser("ingest", help="Ingest a directory of real DXFs and report stats")
    ingest_p.add_argument("dxf_dir", type=Path, help="Directory of .dxf files")

    ground_p = sub.add_parser(
        "ground", help="Ingest real DXFs, extract distributions, validate vs catalog"
    )
    ground_p.add_argument("dxf_dir", type=Path, help="Directory of .dxf files")
    ground_p.add_argument(
        "--profile-out", type=Path, default=None, help="Write a grounding profile JSON"
    )

    # --- train / predict (ML, optional [ml] extra) ---
    train_p = sub.add_parser("train", help="Train a GNN model (requires [ml] extra)")
    train_p.add_argument("--dataset", type=Path, required=True, help="Canonical samples dir")
    train_p.add_argument("--checkpoint-dir", type=Path, required=True, help="Output dir")
    train_p.add_argument("--epochs", type=int, default=50)
    train_p.add_argument("--lr", type=float, default=1e-3)
    train_p.add_argument("--patience", type=int, default=10)

    predict_p = sub.add_parser("predict", help="Run advisory GNN prediction (requires [ml] extra)")
    predict_p.add_argument("file", type=Path, help="DXF file or mgg.json")
    predict_p.add_argument("--feature-checkpoint", type=Path, default=None)

    # --- serve ---
    serve_p = sub.add_parser("serve", help="Start the API server")
    serve_p.add_argument("--host", default="0.0.0.0", help="Bind host")
    serve_p.add_argument("--port", type=int, default=8000, help="Bind port")
    serve_p.add_argument("--reload", action="store_true", help="Auto-reload")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.command == "analyze":
        return _cmd_analyze(args)
    elif args.command == "validate":
        return _cmd_validate(args)
    elif args.command == "generate":
        return _cmd_generate(args)
    elif args.command == "nest":
        return _cmd_nest(args)
    elif args.command == "build-dataset":
        return _cmd_build_dataset(args)
    elif args.command == "apply-review":
        return _cmd_apply_review(args)
    elif args.command == "domains":
        return _cmd_domains(args)
    elif args.command == "profiles":
        return _cmd_profiles(args)
    elif args.command == "calibrate":
        return _cmd_calibrate(args)
    elif args.command == "layer-blind":
        return _cmd_layer_blind(args)
    elif args.command == "tune-ruleset":
        return _cmd_tune_ruleset(args)
    elif args.command == "verify":
        return _cmd_verify(args)
    elif args.command == "benchmark":
        return _cmd_benchmark(args)
    elif args.command == "ingest":
        return _cmd_ingest(args)
    elif args.command == "ground":
        return _cmd_ground(args)
    elif args.command == "train":
        return _cmd_train(args)
    elif args.command == "predict":
        return _cmd_predict(args)
    elif args.command == "serve":
        return _cmd_serve(args)
    else:
        parser.print_help()
        return 0


def _resolve_profile(args):
    """Resolve a --profile flag (built-in name or YAML path) to a LayerProfile."""
    name = getattr(args, "profile", None)
    if not name:
        return None
    from omim.profiles import load_profile
    return load_profile(name)


def _cmd_analyze(args) -> int:
    from omim.graph.builder import MGGBuilder
    from omim.graph.serializer import mgg_to_cytoscape
    from omim.parser.dxf_parser import DXFParser
    from omim.semantic.classifier import FeatureClassifier
    from omim.validation.rule_engine import RuleEngine

    parser = DXFParser(profile=_resolve_profile(args))
    result = parser.parse(args.file)

    if not result.success or not result.geometry:
        for err in result.errors:
            print(f"ERROR [{err.error_code}]: {err.message}", file=sys.stderr)
        return 1

    mgg = MGGBuilder().build(result.geometry)
    FeatureClassifier().classify(mgg)
    report = RuleEngine().validate(mgg)

    if args.cytoscape:
        output = mgg_to_cytoscape(mgg)
    else:
        output = {
            "graph": mgg.to_dict(),
            "validation": report.model_dump(),
        }

    text = json.dumps(output, indent=2, default=str)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Written to {args.output}")
    else:
        print(text)

    if not report.overall_valid:
        err_count = report.severity_summary.get("ERROR", 0)
        warn_count = report.severity_summary.get("WARNING", 0)
        print(
            f"\n{err_count} error(s), {warn_count} warning(s)",
            file=sys.stderr,
        )
        return 2  # Errors found but analysis succeeded

    return 0


def _cmd_validate(args) -> int:
    from omim.graph.builder import MGGBuilder
    from omim.parser.dxf_parser import DXFParser
    from omim.validation.rule_engine import RuleEngine

    parser = DXFParser()
    result = parser.parse(args.file)

    if not result.success or not result.geometry:
        for err in result.errors:
            print(f"ERROR [{err.error_code}]: {err.message}", file=sys.stderr)
        return 1

    mgg = MGGBuilder().build(result.geometry)
    report = RuleEngine().validate(mgg)

    all_results = report.layer1_results + report.layer2_results
    for r in all_results:
        if not r.passed:
            print(f"[{r.severity}] {r.rule_id}: {r.message}")

    err_count = report.severity_summary.get("ERROR", 0)
    warn_count = report.severity_summary.get("WARNING", 0)
    passed_count = sum(1 for r in all_results if r.passed)
    print(f"\nTotal: {passed_count} passed, {err_count} errors, {warn_count} warnings")
    return 2 if not report.overall_valid else 0


def _cmd_nest(args) -> int:
    from omim.graph.builder import MGGBuilder
    from omim.nesting import analyze_nesting
    from omim.parser.dxf_parser import DXFParser

    result = DXFParser().parse(args.file)
    if not result.success or not result.geometry:
        for err in result.errors:
            print(f"ERROR [{err.error_code}]: {err.message}", file=sys.stderr)
        return 1

    mgg = MGGBuilder().build(result.geometry)
    layout = analyze_nesting(mgg)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(layout.model_dump(), indent=2, default=str), encoding="utf-8"
        )
        print(f"Written to {args.output}")
    else:
        print(f"Nested: {layout.is_nested}  |  panels: {layout.panel_count}  "
              f"|  sheet: {layout.sheet_source}")
        if layout.utilization is not None:
            print(f"Sheet utilization: {layout.utilization:.1%}")
        for p in layout.panels:
            print(f"  panel {p.panel_id}: {p.width_mm:.0f}x{p.height_mm:.0f} mm, "
                  f"{p.feature_count} feature(s)")
        for w in layout.warnings:
            print(f"  WARNING: {w}", file=sys.stderr)
    # Exit 2 if the layout has physical problems (overlap / out-of-sheet).
    if layout.overlapping_panel_pairs or layout.panels_outside_sheet:
        return 2
    return 0


def _cmd_domains(args) -> int:
    from omim.domains import DomainStatus, build_registry

    reg = build_registry()

    if args.key:
        d = reg.get(args.key)
        if d is None:
            print(f"Unknown domain key: {args.key}", file=sys.stderr)
            print(f"Known: {', '.join(reg.keys())}", file=sys.stderr)
            return 1
        print(f"{d.key}  [{d.status.value}]\n  {d.title}\n  {d.summary}")
        print(f"\n  Fit: {d.fit}")
        if d.maturity_note:
            print(f"  Maturity: {d.maturity_note}")
        if d.feature_vocabulary:
            print(f"  Features: {', '.join(d.feature_vocabulary)}")
        if d.part_types:
            print(f"  Parts: {', '.join(d.part_types)}")
        if d.join_types:
            print(f"  Joins: {', '.join(d.join_types)}")
        if d.datasets:
            print("  Datasets:")
            for ds in d.datasets:
                print(f"    - {ds.name} [{ds.license.value}] {ds.url}".rstrip())
        if d.tools:
            print("  Reuse (open source):")
            for t in d.tools:
                print(f"    - {t.name} [{t.license.value}] — {t.reuse_for}")
        if d.blockers:
            print("  Blockers:")
            for b in d.blockers:
                print(f"    - {b}")
        return 0

    want = None
    if args.status:
        try:
            want = DomainStatus(args.status.lower())
        except ValueError:
            print(f"Unknown status: {args.status}", file=sys.stderr)
            return 1
    domains = reg.by_status(want) if want else reg.all()
    print(f"{len(domains)} domain(s)"
          + (f" with status={want.value}" if want else f" (of {len(reg)} total)") + ":\n")
    for d in domains:
        data = "real-data" if d.has_real_data else "no-data"
        print(f"  {d.status.value:12s} {data:9s} {d.key:22s} {d.title}")
    if not want:
        print("\nUse  omim domains --key <key>  for full detail.")
    return 0


def _cmd_tune_ruleset(args) -> int:
    from omim.pipeline import write_tuned_ruleset

    tuned = write_tuned_ruleset(args.corpus_dir, args.output, min_samples=args.min_samples)
    print(f"Tuned ruleset written to {args.output}")
    print(f"Corpus files measured: {tuned.corpus_files}")
    measured = [k for k, v in tuned.sources.items() if v == "corpus_measured"]
    defaulted = [k for k, v in tuned.sources.items() if v == "catalog_default"]
    print(f"Tuned from corpus ({len(measured)}): {', '.join(measured) or 'none'}")
    print(f"Kept catalog default ({len(defaulted)}): {', '.join(defaulted) or 'none'}")
    for note in tuned.notes:
        print(f"  note: {note}")
    return 0


def _cmd_apply_review(args) -> int:
    from omim.pipeline import apply_review_to_dataset

    sheet = args.sheet or (args.dataset_dir / "review_sheet.csv")
    if not sheet.exists():
        print(f"Review sheet not found: {sheet}", file=sys.stderr)
        return 1
    result = apply_review_to_dataset(args.dataset_dir, sheet)
    print(f"Decisions in sheet : {result['decisions_in_sheet']}")
    print(f"Labels updated     : {result['labels_updated']}")
    print(f"Gold labels now    : {result['gold_labels_now']}")
    print(f"Label files        : {result['label_files']}")
    print("\nCorrections folded in. Confirmed/corrected labels are now gold "
          "ground truth in the dataset.")
    return 0


def _cmd_layer_blind(args) -> int:
    from omim.graph.builder import MGGBuilder
    from omim.parser.dxf_parser import DXFParser
    from omim.semantic.layer_blind import layer_blind_report

    result = DXFParser(profile=_resolve_profile(args)).parse(args.file)
    if not result.success or not result.geometry:
        for err in result.errors:
            print(f"ERROR [{err.error_code}]: {err.message}", file=sys.stderr)
        return 1
    mgg = MGGBuilder().build(result.geometry)
    rep = layer_blind_report(mgg)
    print(f"Total features         : {rep.total_features}")
    print(f"Classified (with layers): {rep.aware_known}")
    print(f"Classified (NO layers)  : {rep.blind_known} ({rep.blind_known_ratio:.0%})")
    print(f"Agreement (geometry won): {rep.agreement_ratio:.0%}")
    print(f"Recovered layer-blind   : {rep.per_class_blind}")
    print("\nHigh agreement => the classification is real geometric inference, "
          "not just reading the shop's layer names.")
    return 0


def _cmd_calibrate(args) -> int:
    from omim.pipeline import calibrate_from_dataset

    out = args.output or (args.dataset_dir / "calibrator.json")
    result = calibrate_from_dataset(args.dataset_dir, out)
    print(f"Gold (human-reviewed) pairs : {result['gold_pairs']}")
    print(f"Calibrator fitted           : {result['fitted']}")
    if result["raw_ece"] is not None:
        print(f"Raw ECE (pre-calibration)   : {result['raw_ece']}")
    print(f"Calibrator written          : {result['calibrator_path']}")
    if result["gold_pairs"] == 0:
        print("\nNo gold labels yet — wrote an identity calibrator. Run "
              "'apply-review' first so a human's answers become gold, then "
              "re-run calibrate to get a measured mapping.")
    return 0


def _cmd_profiles(args) -> int:
    from omim.profiles import CANONICAL_LAYER_TYPES, builtin_profile_names, get_builtin_profile

    print("OMIM canonical layer types:", ", ".join(CANONICAL_LAYER_TYPES))
    print("\nBuilt-in profiles (one default adapter each, not 'the' convention):")
    for name in builtin_profile_names():
        prof = get_builtin_profile(name)
        print(f"  {name}:")
        for ltype, prefixes in prof.as_conventions().items():
            print(f"    {ltype:9s} <- {', '.join(prefixes)}")
    print("\nCustomer dialects load from a YAML path (kept out-of-tree):")
    print("  omim build-dataset <corpus> <out> --profile path/to/customer.yaml")
    return 0


def _cmd_build_dataset(args) -> int:
    from omim.pipeline import DatasetBuilder

    builder = DatasetBuilder(
        accept_threshold=args.accept_threshold, profile=_resolve_profile(args)
    )
    summary = builder.build(args.corpus_dir, args.output_dir)
    print(f"Layout detected : {summary.layout}")
    print(f"DXF files       : {summary.dxf_files}")
    print(f"Panels          : {summary.panels}")
    print(f"Projects        : {summary.projects}")
    print(f"Labels (total)  : {summary.labels_total}")
    print(f"Need review     : {summary.labels_needing_review}")
    print(f"Output          : {summary.output_dir}")
    if summary.failures:
        print(f"\n{len(summary.failures)} file(s) skipped:", file=sys.stderr)
        for f in summary.failures[:10]:
            print(f"  - {f}", file=sys.stderr)
    print(f"\nReview the low-confidence labels in {summary.output_dir}/review_queue.jsonl,")
    print("set each row's 'decision' (confirm|correct|reject), then re-import to finalize.")
    return 0


def _cmd_generate(args) -> int:
    from omim.synthetic.generator import PanelGenerator
    from omim.synthetic.models import PanelGeneratorConfig

    config = PanelGeneratorConfig(
        random_seed=args.seed,
        num_samples=args.num_samples,
        invalid_sample_ratio=args.invalid_ratio,
        feature_density=args.density,
    )
    print(
        f"Generating {config.num_samples} samples "
        f"(seed={config.random_seed}, invalid_ratio={config.invalid_sample_ratio}) "
        f"-> {args.output_dir}"
    )
    manifest = PanelGenerator(config).generate_dataset(str(args.output_dir))
    print(
        f"Done: {manifest.total_samples} samples "
        f"({manifest.valid_count} valid, {manifest.invalid_count} invalid) | "
        f"splits: train={manifest.train_count} val={manifest.val_count} test={manifest.test_count}"
    )
    print(f"Manifest + dataset_metadata written to {args.output_dir}")
    return 0


def _cmd_verify(args) -> int:
    from omim.integrity import check_dataset_consistency, validate_sample_schema

    path = args.path
    # A sample dir has the 5 canonical files; a dataset dir has samples/ + splits/.
    if (path / "samples").is_dir() or (path / "dataset_metadata.json").exists():
        violations = check_dataset_consistency(str(path))
        label = "dataset"
    else:
        violations = validate_sample_schema(str(path))
        label = "sample"
    if violations:
        print(f"{label} INVALID — {len(violations)} violation(s):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 2
    print(f"{label} OK: no integrity/schema violations")
    return 0


def _cmd_benchmark(args) -> int:
    from omim.benchmarks.runner import run_benchmarks

    tasks = [args.task] if args.task else None
    report = run_benchmarks(str(args.dataset_dir), tasks=tasks, split=args.split)
    md = report.get("markdown_table") if isinstance(report, dict) else None
    print(md or json.dumps(report, indent=2, default=str))
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"\nReport written to {args.output}")
    return 0


def _cmd_ingest(args) -> int:
    from omim.corpus.ingest import CorpusIngestor

    stats = CorpusIngestor().ingest_directory(str(args.dxf_dir))
    print(stats.summary() if hasattr(stats, "summary") else stats)
    return 0


def _cmd_ground(args) -> int:
    from omim.corpus.distribution_extractor import extract_distributions
    from omim.corpus.ingest import CorpusIngestor
    from omim.corpus.validator import validate_against_catalog

    stats = CorpusIngestor().ingest_directory(str(args.dxf_dir))
    dist = extract_distributions(stats)
    report = validate_against_catalog(stats)
    print(
        f"Conformant: {report.overall_conformant} "
        f"({report.n_passed} passed, {report.n_failed} failed)"
    )
    if args.profile_out:
        args.profile_out.write_text(json.dumps(dist, indent=2, default=str), encoding="utf-8")
        print(f"Grounding profile written to {args.profile_out}")
    return 0


def _cmd_train(args) -> int:
    from omim.ml.availability import ML_AVAILABLE, missing_dependencies

    if not ML_AVAILABLE:
        print(
            "ML extra not installed (missing: "
            f"{', '.join(missing_dependencies())}). Install with: pip install 'omim[ml]'",
            file=sys.stderr,
        )
        return 1
    from torch_geometric.loader import DataLoader

    from omim.ml.trainer import CanonicalSampleDataset, GNNTrainer

    ds = CanonicalSampleDataset(str(args.dataset))
    samples = ds.all()
    if not samples:
        print("No trainable samples found in dataset.", file=sys.stderr)
        return 1
    # Simple 85/15 train/val split for the CLI path.
    split = max(1, int(len(samples) * 0.85))
    train_loader = DataLoader(samples[:split], batch_size=16, shuffle=True)
    val_loader = DataLoader(samples[split:], batch_size=16) if samples[split:] else None
    weights = ds.compute_class_weights() if hasattr(ds, "compute_class_weights") else None
    trainer = GNNTrainer(
        optimizer_lr=args.lr,
        max_epochs=args.epochs,
        early_stopping_patience=args.patience,
        class_weights=weights,
    )
    trainer.train(train_loader, val_loader, checkpoint_dir=str(args.checkpoint_dir))
    print(f"Training complete. Checkpoints in {args.checkpoint_dir}")
    return 0


def _cmd_predict(args) -> int:
    from omim.ml.predictor import GNNPredictor

    # Build an MGG from a DXF or load mgg.json.
    if str(args.file).lower().endswith(".dxf"):
        from omim.graph.builder import MGGBuilder
        from omim.parser.dxf_parser import DXFParser

        result = DXFParser().parse(args.file)
        if not result.success or not result.geometry:
            print("Failed to parse DXF", file=sys.stderr)
            return 1
        mgg = MGGBuilder().build(result.geometry)
    else:
        from omim.graph.mgg import ManufacturingGeometryGraph

        mgg = ManufacturingGeometryGraph.from_dict(
            json.loads(args.file.read_text(encoding="utf-8"))
        )

    predictor = GNNPredictor(feature_checkpoint=str(args.feature_checkpoint)
                             if args.feature_checkpoint else None)
    prediction = predictor.predict(mgg)
    payload = prediction if isinstance(prediction, dict) else getattr(
        prediction, "__dict__", prediction
    )
    print(json.dumps(payload, indent=2, default=str))
    return 0


def _cmd_serve(args) -> int:
    import uvicorn

    uvicorn.run(
        "omim.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
