"""OMIM CLI — command-line interface for manufacturing geometry analysis."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omim",
        description="Open Manufacturing Intelligence Middleware",
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
    annotations = FeatureClassifier().classify(mgg)
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
