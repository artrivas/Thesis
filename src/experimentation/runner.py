"""Experiment runner and CSV result storage."""

from __future__ import annotations

import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import tracemalloc

from experimentation.config import ExperimentConfig, debug_config, full_synthetic_config
from experimentation.datasets import PairedDistribution, SyntheticDatasetConfig, generate_paired_distribution
from experimentation.workflows import Workflow, acceleration_summary, configure_acceleration, default_workflows


RESULT_COLUMNS = (
    "dataset",
    "dataset_params",
    "perturbation",
    "perturbation_params",
    "alpha",
    "seed",
    "workflow",
    "distribution_score",
    "mean_shift_score",
    "paired_score",
    "runtime_seconds",
    "memory_mb",
    "status",
    "error_message",
)


def run_debug_experiment(output_root: Path | str = Path("outputs/debug_experimentation")) -> Path:
    """Run the debug grid and return the result CSV path."""

    return run_experiment(debug_config(output_root))


def run_full_synthetic_experiment(output_root: Path | str = Path("outputs/experimentation")) -> Path:
    """Run the full synthetic-only grid and return the result CSV path."""

    return run_experiment(full_synthetic_config(output_root))


def run_experiment(
    config: ExperimentConfig,
    output_path: Path | str | None = None,
    workflows: list[Workflow] | None = None,
    *,
    resume: bool = True,
    rerun_failed: bool = False,
    device: str = "auto",
    log_path: Path | str | None = None,
    checkpoint_path: Path | str | None = None,
) -> Path:
    """Execute dataset x perturbation x alpha x seed x workflow and save CSV results."""

    config.outputs.create_directories()
    result_path = Path(output_path) if output_path is not None else config.outputs.results / "results.csv"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = Path(log_path) if log_path is not None else config.outputs.logs / "run.log"
    checkpoint_file = (
        Path(checkpoint_path) if checkpoint_path is not None else config.outputs.logs / "checkpoint.json"
    )
    logger = _experiment_logger(log_file)
    configure_acceleration(device)
    workflow_instances = workflows if workflows is not None else workflows_from_config(config)

    if resume:
        _raise_on_incompatible_resume(result_path, workflow_instances)
    if resume and rerun_failed:
        _drop_failed_rows(result_path)
    completed = _completed_keys(result_path) if resume else set()
    total_rows = _expected_row_count(config, workflow_instances)
    logger.info(
        "run_start result_path=%s resume=%s rerun_failed=%s completed=%d total=%d device=%s",
        result_path,
        resume,
        rerun_failed,
        len(completed),
        total_rows,
        acceleration_summary(),
    )

    append = resume and result_path.exists() and result_path.stat().st_size > 0
    rows_written = 0
    with result_path.open("a" if append else "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        if not append:
            writer.writeheader()
            _flush_checkpoint(handle)

        def persist(row: dict[str, object]) -> None:
            nonlocal rows_written
            writer.writerow({column: _csv_value(row.get(column)) for column in RESULT_COLUMNS})
            rows_written += 1
            completed.add(_row_key(row))
            _flush_checkpoint(handle)
            _write_checkpoint(checkpoint_file, result_path, completed, total_rows)
            logger.info(
                "row_complete %d/%d dataset=%s perturbation=%s alpha=%s seed=%s workflow=%s status=%s",
                len(completed),
                total_rows,
                row.get("dataset"),
                row.get("perturbation"),
                row.get("alpha"),
                row.get("seed"),
                row.get("workflow"),
                row.get("status"),
            )

        for seed in config.seeds:
            for dataset_template in config.resolved_dataset_configs():
                dataset_config = replace(dataset_template, seed=seed)
                for perturbation in config.perturbations.methods:
                    for alpha in config.perturbations.alpha_values:
                        pending_workflows = [
                            workflow
                            for workflow in workflow_instances
                            if _grid_key(dataset_config, perturbation, alpha, seed, workflow.name) not in completed
                        ]
                        if not pending_workflows:
                            logger.info(
                                "grid_skip_completed dataset=%s perturbation=%s alpha=%s seed=%s",
                                dataset_config.family,
                                perturbation,
                                alpha,
                                seed,
                            )
                            continue
                        paired = generate_paired_distribution(dataset_config, perturbation, alpha, seed)
                        for row in _run_workflow_grid(dataset_config, perturbation, alpha, seed, paired, pending_workflows):
                            persist(row)

    logger.info(
        "run_finish result_path=%s rows_written=%d completed=%d total=%d",
        result_path,
        rows_written,
        len(completed),
        total_rows,
    )
    return result_path


def workflows_from_config(config: ExperimentConfig) -> list[Workflow]:
    """Instantiate workflows listed in the experiment config."""

    available = {workflow.name: workflow for workflow in default_workflows()}
    available["diversity_curves_l2"] = available["diversity_curves_shortest_path"]
    workflows = []
    for name in config.workflows.names:
        if name not in available:
            raise ValueError(f"Unknown workflow configured: {name}")
        workflows.append(available[name])
    return workflows


def write_result_rows(rows: list[dict[str, object]], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in RESULT_COLUMNS})
    return path


def read_result_rows(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _completed_keys(path: Path) -> set[tuple[str, str, str, str, str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return set()
    return {_row_key(row) for row in read_result_rows(path)}


def _drop_failed_rows(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    rows = [row for row in read_result_rows(path) if row.get("status") != "failed"]
    write_result_rows(rows, path)


def _raise_on_incompatible_resume(path: Path, workflows: list[Workflow]) -> None:
    if not path.exists() or path.stat().st_size == 0:
        return
    expected_workflows = {workflow.name for workflow in workflows}
    if "diversity_curves_shortest_path" not in expected_workflows:
        return
    legacy_workflows = {
        str(row.get("workflow"))
        for row in read_result_rows(path)
        if row.get("workflow") == "diversity_curves_l2"
    }
    if legacy_workflows:
        legacy = ", ".join(sorted(legacy_workflows))
        raise ValueError(
            f"Existing result file contains legacy workflow rows ({legacy}). "
            "Start a fresh CSV with --no-resume or use a new output root before running fixed experiments."
        )


def _row_key(row: dict[str, object]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("dataset", "")),
        str(row.get("dataset_params", "")),
        str(row.get("perturbation", "")),
        str(row.get("alpha", "")),
        str(row.get("seed", "")),
        str(row.get("workflow", "")),
    )


def _grid_key(
    dataset_config: SyntheticDatasetConfig,
    perturbation: str,
    alpha: float,
    seed: int,
    workflow_name: str,
) -> tuple[str, str, str, str, str, str]:
    return (
        dataset_config.family,
        json.dumps(asdict(dataset_config), sort_keys=True),
        perturbation,
        str(alpha),
        str(seed),
        workflow_name,
    )


def _expected_row_count(config: ExperimentConfig, workflows: list[Workflow]) -> int:
    return (
        len(config.seeds)
        * len(config.resolved_dataset_configs())
        * len(config.perturbations.methods)
        * len(config.perturbations.alpha_values)
        * len(workflows)
    )


def _write_checkpoint(
    path: Path,
    result_path: Path,
    completed: set[tuple[str, str, str, str, str, str]],
    total_rows: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "result_path": str(result_path),
        "completed_rows": len(completed),
        "total_rows": total_rows,
        "remaining_rows": max(0, total_rows - len(completed)),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)


def _flush_checkpoint(handle) -> None:
    handle.flush()
    os.fsync(handle.fileno())


def _experiment_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("experimentation.runner")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    resolved = log_path.resolve()
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == resolved:
            return logger
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            handler.close()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def _run_workflow_grid(
    dataset_config: SyntheticDatasetConfig,
    perturbation: str,
    alpha: float,
    seed: int,
    paired: PairedDistribution,
    workflows: list[Workflow],
) -> list[dict[str, object]]:
    dataset_params = json.dumps(asdict(dataset_config), sort_keys=True)
    perturbation_params = json.dumps(_summarize_perturbations(paired), sort_keys=True)
    skip_error = _skip_error(paired)

    rows = []
    for workflow in workflows:
        if skip_error is not None:
            result = {
                "workflow": workflow.name,
                "distribution_score": None,
                "mean_shift_score": None,
                "paired_score": None,
                "runtime_seconds": 0.0,
                "memory_mb": None,
                "status": "skipped",
                "error_message": skip_error,
            }
        else:
            result = _run_workflow_with_memory(workflow, paired)

        rows.append(
            {
                "dataset": dataset_config.family,
                "dataset_params": dataset_params,
                "perturbation": perturbation,
                "perturbation_params": perturbation_params,
                "alpha": alpha,
                "seed": seed,
                **result,
            }
        )
    return rows


def _run_workflow_with_memory(workflow: Workflow, paired: PairedDistribution) -> dict[str, object]:
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()
    tracemalloc.reset_peak()
    result = workflow.run(paired.original_graphs, paired.perturbed_graphs)
    _, peak = tracemalloc.get_traced_memory()
    result["memory_mb"] = peak / (1024 * 1024)
    if not was_tracing:
        tracemalloc.stop()
    return result


def _summarize_perturbations(paired: PairedDistribution) -> dict[str, object]:
    metadata = paired.metadata.get("perturbations", [])
    summary: dict[str, object] = {
        "method": paired.metadata.get("perturbation"),
        "alpha": paired.metadata.get("alpha"),
        "graphs": len(metadata),
        "graphs_success": 0,
        "graphs_skipped": 0,
        "edges_added": 0,
        "edges_removed": 0,
        "rewires": 0,
        "triangles_affected": 0,
    }
    for item in metadata:
        if item.get("status") == "skipped":
            summary["graphs_skipped"] = int(summary["graphs_skipped"]) + 1
        else:
            summary["graphs_success"] = int(summary["graphs_success"]) + 1
        for key in ("edges_added", "edges_removed", "rewires", "triangles_affected"):
            summary[key] = int(summary[key]) + int(item.get(key, 0) or 0)
    return summary


def _skip_error(paired: PairedDistribution) -> str | None:
    metadata = paired.metadata.get("perturbations", [])
    if not metadata:
        return None
    if all(item.get("status") == "skipped" for item in metadata):
        messages = sorted({str(item.get("error_message")) for item in metadata if item.get("error_message")})
        return "; ".join(messages) if messages else "perturbation skipped"
    return None


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    return value
