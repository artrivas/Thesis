"""Command-line entry points for synthetic experimentation."""

from __future__ import annotations

import argparse
from pathlib import Path

from experimentation.evaluation import evaluate_results
from experimentation.figures import generate_figures
from experimentation.runner import run_debug_experiment, run_full_synthetic_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic graph distribution experimentation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    debug_parser = subparsers.add_parser("run_debug_experiment", help="Run the small debug experiment")
    debug_parser.add_argument("--output-root", default="outputs/debug_experimentation")

    full_parser = subparsers.add_parser("run_full_synthetic_experiment", help="Run the full synthetic experiment")
    full_parser.add_argument("--output-root", default="outputs/experimentation")

    evaluate_parser = subparsers.add_parser("evaluate_results", help="Generate evaluation CSVs")
    evaluate_parser.add_argument("--results", required=True)
    evaluate_parser.add_argument("--output-dir", default=None)

    figures_parser = subparsers.add_parser("generate_figures", help="Generate SVG figures")
    figures_parser.add_argument("--results", required=True)
    figures_parser.add_argument("--output-dir", default=None)

    args = parser.parse_args(argv)
    if args.command == "run_debug_experiment":
        path = run_debug_experiment(Path(args.output_root))
        print(path)
        return 0
    if args.command == "run_full_synthetic_experiment":
        path = run_full_synthetic_experiment(Path(args.output_root))
        print(path)
        return 0
    if args.command == "evaluate_results":
        outputs = evaluate_results(Path(args.results), Path(args.output_dir) if args.output_dir else None)
        for path in outputs.values():
            print(path)
        return 0
    if args.command == "generate_figures":
        outputs = generate_figures(Path(args.results), Path(args.output_dir) if args.output_dir else None)
        for path in outputs.values():
            print(path)
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
