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

    if report.has_errors:
        print(
            f"\n{report.failed} error(s), {report.warnings} warning(s)",
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

    for r in report.results:
        if not r.passed:
            severity = r.severity.value
            print(f"[{severity}] {r.rule_id}: {r.message}")

    print(f"\nTotal: {report.passed} passed, {report.failed} errors, {report.warnings} warnings")
    return 2 if report.has_errors else 0


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
