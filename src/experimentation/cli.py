"""Command-line entry points for synthetic experimentation."""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from experimentation.config import ExperimentConfig, WorkflowConfig, debug_config, full_synthetic_config
from experimentation.evaluation import evaluate_results
from experimentation.figures import generate_figures
from experimentation.runner import run_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic graph distribution experimentation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    debug_parser = subparsers.add_parser("run_debug_experiment", help="Run the small debug experiment")
    debug_parser.add_argument("--output-root", default="outputs/debug_experimentation")
    debug_parser.add_argument("--device", default="auto", help="Acceleration device: auto, cpu, cuda, or cuda:N")
    debug_parser.add_argument("--no-resume", action="store_true", help="Start a fresh result CSV instead of resuming")
    debug_parser.add_argument("--rerun-failed", action="store_true", help="Drop failed rows and recompute them")
    debug_parser.add_argument("--log-file", default=None, help="Optional run log path")
    debug_parser.add_argument("--console-log", action="store_true", help="Print progress logs to the terminal")
    debug_parser.add_argument(
        "--workflow",
        action="append",
        default=None,
        help="Workflow ID to run. Repeat to run multiple workflows.",
    )

    full_parser = subparsers.add_parser("run_full_synthetic_experiment", help="Run the full synthetic experiment")
    full_parser.add_argument("--output-root", default="outputs/experimentation_native_netlsd")
    full_parser.add_argument("--device", default="auto", help="Acceleration device: auto, cpu, cuda, or cuda:N")
    full_parser.add_argument("--no-resume", action="store_true", help="Start a fresh result CSV instead of resuming")
    full_parser.add_argument("--rerun-failed", action="store_true", help="Drop failed rows and recompute them")
    full_parser.add_argument("--log-file", default=None, help="Optional run log path")
    full_parser.add_argument("--console-log", action="store_true", help="Print progress logs to the terminal")
    full_parser.add_argument(
        "--workflow",
        action="append",
        default=None,
        help="Workflow ID to run. Repeat to run multiple workflows.",
    )

    evaluate_parser = subparsers.add_parser("evaluate_results", help="Generate evaluation CSVs")
    evaluate_parser.add_argument("--results", required=True)
    evaluate_parser.add_argument("--output-dir", default=None)

    figures_parser = subparsers.add_parser("generate_figures", help="Generate SVG figures")
    figures_parser.add_argument("--results", required=True)
    figures_parser.add_argument("--output-dir", default=None)

    args = parser.parse_args(argv)
    if args.command == "run_debug_experiment":
        path = run_experiment(
            _with_workflows(debug_config(Path(args.output_root)), args.workflow),
            resume=not args.no_resume,
            rerun_failed=args.rerun_failed,
            device=args.device,
            log_path=Path(args.log_file) if args.log_file else None,
            console_log=args.console_log,
        )
        print(path)
        return 0
    if args.command == "run_full_synthetic_experiment":
        path = run_experiment(
            _with_workflows(full_synthetic_config(Path(args.output_root)), args.workflow),
            resume=not args.no_resume,
            rerun_failed=args.rerun_failed,
            device=args.device,
            log_path=Path(args.log_file) if args.log_file else None,
            console_log=args.console_log,
        )
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


def _with_workflows(config: ExperimentConfig, workflow_names: list[str] | None) -> ExperimentConfig:
    if not workflow_names:
        return config
    return replace(config, workflows=WorkflowConfig(names=tuple(workflow_names)))


if __name__ == "__main__":
    raise SystemExit(main())
