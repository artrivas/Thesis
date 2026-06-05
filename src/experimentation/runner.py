"""Experiment runner and CSV result storage."""

from __future__ import annotations

import csv
from dataclasses import asdict, replace
import json
from pathlib import Path
import tracemalloc

from experimentation.config import ExperimentConfig, debug_config, full_synthetic_config
from experimentation.datasets import PairedDistribution, SyntheticDatasetConfig, generate_paired_distribution
from experimentation.workflows import Workflow, default_workflows


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
) -> Path:
    """Execute dataset x perturbation x alpha x seed x workflow and save CSV results."""

    config.outputs.create_directories()
    result_path = Path(output_path) if output_path is not None else config.outputs.results / "results.csv"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_instances = workflows if workflows is not None else workflows_from_config(config)

    rows: list[dict[str, object]] = []
    for seed in config.seeds:
        for dataset_template in config.resolved_dataset_configs():
            dataset_config = replace(dataset_template, seed=seed)
            for perturbation in config.perturbations.methods:
                for alpha in config.perturbations.alpha_values:
                    paired = generate_paired_distribution(dataset_config, perturbation, alpha, seed)
                    rows.extend(_run_workflow_grid(dataset_config, perturbation, alpha, seed, paired, workflow_instances))

    write_result_rows(rows, result_path)
    return result_path


def workflows_from_config(config: ExperimentConfig) -> list[Workflow]:
    """Instantiate workflows listed in the experiment config."""

    available = {workflow.name: workflow for workflow in default_workflows()}
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
