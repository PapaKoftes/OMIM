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


def _cmd_analyze(args) -> int:
    from omim.graph.builder import MGGBuilder
    from omim.graph.serializer import mgg_to_cytoscape
    from omim.parser.dxf_parser import DXFParser
    from omim.semantic.classifier import FeatureClassifier
    from omim.validation.rule_engine import RuleEngine

    parser = DXFParser()
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
