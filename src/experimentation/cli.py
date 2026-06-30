"""Command-line entry points for synthetic experimentation."""

from __future__ import annotations

import argparse
from dataclasses import replace
import os
from pathlib import Path

from experimentation.config import (
    ExperimentConfig,
    WorkflowConfig,
    build_run_output_config,
    debug_config,
    full_synthetic_config,
    imdb_config,
    output_config_for_root,
)
from experimentation.evaluation import evaluate_results
from experimentation.figures import generate_figures
from experimentation.runner import merge_runs, run_experiment


CONFIG_BUILDERS = {
    "debug": debug_config,
    "full": full_synthetic_config,
    "imdb": imdb_config,
}
DEFAULT_RESULTS_ROOT = "results/runs"


def default_workers() -> int:
    """Default to one process per core, leaving a core for the parent writer."""

    return max(1, (os.cpu_count() or 2) - 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic graph distribution experimentation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_legacy_run_parser(subparsers, "run_debug_experiment", "outputs/debug_experimentation")
    _add_legacy_run_parser(subparsers, "run_full_synthetic_experiment", "outputs/experimentation_native_netlsd")
    _add_run_parser(subparsers)
    _add_merge_parser(subparsers)

    evaluate_parser = subparsers.add_parser("evaluate_results", help="Generate evaluation CSVs")
    evaluate_parser.add_argument("--results", required=True)
    evaluate_parser.add_argument("--output-dir", default=None)

    figures_parser = subparsers.add_parser("generate_figures", help="Generate SVG figures")
    figures_parser.add_argument("--results", required=True)
    figures_parser.add_argument("--output-dir", default=None)

    args = parser.parse_args(argv)
    if args.command in ("run_debug_experiment", "run_full_synthetic_experiment"):
        return _run_legacy(args)
    if args.command == "run":
        return _run(args)
    if args.command == "merge":
        return _merge(args)
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


def _add_legacy_run_parser(subparsers, name: str, default_output_root: str) -> None:
    legacy = subparsers.add_parser(name, help=f"Run the {name.replace('_', ' ')} (legacy outputs/ tree)")
    legacy.add_argument("--output-root", default=default_output_root)
    legacy.add_argument("--device", default="auto", help="Acceleration device: auto, cpu, cuda, or cuda:N")
    legacy.add_argument("--no-resume", action="store_true", help="Start a fresh result CSV instead of resuming")
    legacy.add_argument("--rerun-failed", action="store_true", help="Drop failed rows and recompute them")
    legacy.add_argument("--log-file", default=None, help="Optional run log path")
    legacy.add_argument("--console-log", action="store_true", help="Print progress logs to the terminal")
    legacy.add_argument(
        "--workflow",
        action="append",
        default=None,
        help="Workflow ID to run. Repeat to run multiple workflows.",
    )


def _add_run_parser(subparsers) -> None:
    run = subparsers.add_parser("run", help="Run an experiment into a traceable results/runs/<id>/ directory")
    run.add_argument("--config", choices=sorted(CONFIG_BUILDERS), default="full", help="Named base config")
    run.add_argument("--results-root", default=DEFAULT_RESULTS_ROOT, help="Root for traceable run directories")
    run.add_argument("--run-id", default=None, help="Resume/target an existing run directory by id")
    run.add_argument("--output-root", default=None, help="Legacy: write directly into this directory")
    run.add_argument("--workers", type=int, default=default_workers(), help="CPU worker processes (1 = serial)")
    run.add_argument("--seed-range", default=None, help="Half-open index slice A:B into the resolved seed list")
    run.add_argument("--device", default="cpu", help="Acceleration device (CPU-only target): cpu, auto, cuda:N")
    run.add_argument("--resume", action="store_true", help="Resume an existing run dir (default; explicit for clarity)")
    run.add_argument("--no-resume", action="store_true", help="Start a fresh result CSV instead of resuming")
    run.add_argument("--rerun-failed", action="store_true", help="Drop failed rows and recompute them")
    run.add_argument("--console-log", action="store_true", help="Print progress logs to the terminal")
    run.add_argument("--evaluate", action="store_true", help="Generate evaluation CSVs after the run")
    run.add_argument("--figures", action="store_true", help="Generate SVG figures after the run")
    run.add_argument(
        "--workflow",
        action="append",
        default=None,
        help="Workflow ID to run. Repeat to run multiple workflows.",
    )


def _add_merge_parser(subparsers) -> None:
    merge = subparsers.add_parser("merge", help="Merge seed-range shard results into one combined run")
    merge.add_argument("--shard", action="append", required=True, help="Shard run dir or results.csv. Repeat per shard.")
    merge.add_argument("--output", required=True, help="Combined run directory")
    merge.add_argument("--evaluate", action="store_true", help="Generate evaluation CSVs on the merged CSV")
    merge.add_argument("--figures", action="store_true", help="Generate SVG figures on the merged CSV")


def _run_legacy(args) -> int:
    builder = debug_config if args.command == "run_debug_experiment" else full_synthetic_config
    path = run_experiment(
        _with_workflows(builder(Path(args.output_root)), args.workflow),
        resume=not args.no_resume,
        rerun_failed=args.rerun_failed,
        device=args.device,
        log_path=Path(args.log_file) if args.log_file else None,
        console_log=args.console_log,
    )
    print(path)
    return 0


def _run(args) -> int:
    config = _with_workflows(CONFIG_BUILDERS[args.config](), args.workflow)
    seed_range = _parse_seed_range(args.seed_range)
    if args.output_root:
        outputs = output_config_for_root(Path(args.output_root))
        run_id = args.run_id or Path(args.output_root).name
    else:
        run_id, outputs = build_run_output_config(
            args.results_root, config, run_id=args.run_id, seed_range=seed_range
        )
    config = replace(config, outputs=outputs)
    result_path = run_experiment(
        config,
        resume=not args.no_resume,
        rerun_failed=args.rerun_failed,
        device=args.device,
        console_log=args.console_log,
        workers=args.workers,
        seed_range=seed_range,
        run_id=run_id,
    )
    print(f"run_id={run_id}")
    print(result_path)
    if args.evaluate:
        for path in evaluate_results(result_path, config.outputs.evaluation).values():
            print(path)
    if args.figures:
        for path in generate_figures(result_path, config.outputs.figures).values():
            print(path)
    return 0


def _merge(args) -> int:
    output_dir = Path(args.output)
    outputs = output_config_for_root(output_dir)
    outputs.create_directories()
    merged = merge_runs(list(args.shard), outputs.results / "results.csv")
    print(merged)
    if args.evaluate:
        for path in evaluate_results(merged, outputs.evaluation).values():
            print(path)
    if args.figures:
        for path in generate_figures(merged, outputs.figures).values():
            print(path)
    return 0


def _parse_seed_range(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    if ":" not in value:
        raise SystemExit("--seed-range must be A:B (half-open index slice)")
    start_text, stop_text = value.split(":", 1)
    return (int(start_text), int(stop_text))


def _with_workflows(config: ExperimentConfig, workflow_names: list[str] | None) -> ExperimentConfig:
    if not workflow_names:
        return config
    return replace(config, workflows=WorkflowConfig(names=tuple(workflow_names)))


if __name__ == "__main__":
    raise SystemExit(main())
