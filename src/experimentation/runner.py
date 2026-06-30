"""Experiment runner and CSV result storage."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import logging
import multiprocessing
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import tracemalloc

from experimentation.config import (
    ExperimentConfig,
    config_hash,
    debug_config,
    full_synthetic_config,
    resolved_config_payload,
)
from experimentation.datasets import PairedDistribution, SyntheticDatasetConfig, generate_paired_distribution
from experimentation.ground_truth import cell_edit_distances
from experimentation.workflows import (
    DIVERSITY_CURVES_WORKFLOW,
    LEGACY_NETLSD_MMD_WORKFLOW,
    NATIVE_NETLSD_WORKFLOW,
    Workflow,
    acceleration_summary,
    configure_acceleration,
    default_workflows,
)


# Environment variables that force single-threaded numeric libraries in each
# worker. Keeping every worker single-threaded is what preserves the validity of
# the relative_runtime and tracemalloc memory metrics: we parallelize ACROSS grid
# cells and keep the workflows serial WITHIN a cell, so each measured workflow
# runs under the same controlled, single-core contention as the serial path.
_WORKER_THREAD_CAP_VARS = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


def _apply_thread_caps() -> None:
    for variable in _WORKER_THREAD_CAP_VARS:
        os.environ[variable] = "1"


def _init_worker(device: str = "cpu") -> None:
    """ProcessPool initializer: pin each worker to a single CPU thread."""

    _apply_thread_caps()
    try:  # torch stays optional and CPU-only inside workers.
        import torch  # type: ignore[import-not-found]

        torch.set_num_threads(1)
    except ImportError:
        pass
    configure_acceleration(device)


def _multiprocessing_context():
    """Pick a safe start method for CPU workers.

    ``forkserver`` forks every worker from a clean, single-threaded server
    process, so the thread-cap initializer runs before any heavy import and we
    avoid the fork-from-multithreaded-parent deadlock hazard. We fall back to
    ``spawn`` where ``forkserver`` is unavailable (e.g. Windows).
    """

    available = multiprocessing.get_all_start_methods()
    for method in ("forkserver", "spawn"):
        if method in available:
            return multiprocessing.get_context(method)
    return multiprocessing.get_context()


def _compute_cell_rows(
    dataset_config: SyntheticDatasetConfig,
    perturbation: str,
    alpha: float,
    seed: int,
    workflows: list[Workflow],
) -> list[dict[str, object]]:
    """Compute every workflow row for one grid cell (worker entry point).

    A "cell" is one ``(seed, dataset_config, perturbation, alpha)`` combination.
    The worker generates the PairedDistribution once and runs ALL pending
    workflows on it SERIALLY, returning the rows for the parent to persist. The
    worker never touches the result files; only the parent process writes.
    """

    paired = generate_paired_distribution(dataset_config, perturbation, alpha, seed)
    return _run_workflow_grid(dataset_config, perturbation, alpha, seed, paired, workflows)


RESULT_COLUMNS = (
    "dataset",
    "dataset_params",
    "perturbation",
    "perturbation_params",
    "alpha",
    "seed",
    "workflow",
    "implementation_mode",
    "workflow_params",
    "perturbation_family",
    "perturbation_direction",
    "label_source",
    "graph_count",
    "node_count_min",
    "node_count_max",
    "edge_count_min",
    "edge_count_max",
    "distribution_score",
    "mean_shift_score",
    "paired_score",
    "edit_distance_raw",
    "edit_distance_weighted",
    "runtime_seconds",
    "memory_mb",
    "status",
    "error_message",
)


def run_debug_experiment(output_root: Path | str = Path("outputs/debug_experimentation")) -> Path:
    """Run the debug grid and return the result CSV path."""

    return run_experiment(debug_config(output_root))


def run_full_synthetic_experiment(output_root: Path | str = Path("outputs/experimentation_native_netlsd")) -> Path:
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
    console_log: bool = False,
    workers: int = 1,
    seed_range: tuple[int, int] | None = None,
    run_id: str | None = None,
    write_manifest: bool = True,
) -> Path:
    """Execute dataset x perturbation x alpha x seed x workflow and save CSV results.

    With ``workers == 1`` the run is serial and byte-for-byte identical to the
    historical behavior. With ``workers > 1`` the grid is executed in parallel,
    one CPU process per grid cell, while the parent process remains the sole
    writer so the append + fsync + checkpoint crash-safety story is unchanged.

    ``seed_range`` is a half-open ``(start, stop)`` index slice into the resolved
    seed list, used to shard a replication sweep across machines.
    """

    config.outputs.create_directories()
    result_path = Path(output_path) if output_path is not None else config.outputs.results / "results.csv"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = Path(log_path) if log_path is not None else config.outputs.logs / "run.log"
    checkpoint_file = (
        Path(checkpoint_path) if checkpoint_path is not None else config.outputs.logs / "checkpoint.json"
    )
    logger = _experiment_logger(log_file, console=console_log)
    configure_acceleration(device)
    workflow_instances = workflows if workflows is not None else workflows_from_config(config)
    seeds = _resolve_seeds(config.seeds, seed_range)

    if resume:
        _raise_on_incompatible_resume(result_path, workflow_instances)
    if resume and rerun_failed:
        _drop_failed_rows(result_path)
    completed = _completed_keys(result_path) if resume else set()
    total_rows = _expected_row_count(config, workflow_instances, len(seeds))
    started_at = datetime.now(timezone.utc).isoformat()
    resolved_run_id = run_id or config.outputs.root.name
    manifest_kwargs = dict(
        run_id=resolved_run_id,
        seeds=seeds,
        workflows=workflow_instances,
        result_path=result_path,
        checkpoint_path=checkpoint_file,
        started_at=started_at,
        seed_range=seed_range,
        workers=workers,
    )
    if write_manifest:
        write_run_manifest(config, status="running", **manifest_kwargs)
    logger.info(
        "run_start result_path=%s resume=%s rerun_failed=%s workers=%d seed_range=%s "
        "seeds=%d completed=%d total=%d device=%s",
        result_path,
        resume,
        rerun_failed,
        workers,
        seed_range,
        len(seeds),
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

        pending_cells = _pending_cells(config, workflow_instances, seeds, completed, logger)
        if workers <= 1:
            _run_serial(pending_cells, persist)
        else:
            _run_parallel(pending_cells, persist, workers=workers, logger=logger)

    if write_manifest:
        write_run_manifest(
            config,
            status="finished",
            ended_at=datetime.now(timezone.utc).isoformat(),
            **manifest_kwargs,
        )
    logger.info(
        "run_finish result_path=%s rows_written=%d completed=%d total=%d",
        result_path,
        rows_written,
        len(completed),
        total_rows,
    )
    return result_path


Cell = tuple[SyntheticDatasetConfig, str, float, int]


def _resolve_seeds(seeds: tuple[int, ...], seed_range: tuple[int, int] | None) -> tuple[int, ...]:
    if seed_range is None:
        return tuple(seeds)
    start, stop = seed_range
    if start < 0 or stop < start:
        raise ValueError(f"seed_range must be a half-open (start, stop) with 0 <= start <= stop, got {seed_range}")
    return tuple(seeds)[start:stop]


def _iter_cells(config: ExperimentConfig, seeds: tuple[int, ...]):
    """Yield grid cells in the historical serial order for deterministic output."""

    for seed in seeds:
        for dataset_template in config.resolved_dataset_configs():
            dataset_config = replace(dataset_template, seed=seed)
            for perturbation in config.perturbations.methods:
                for alpha in config.perturbations.alpha_values:
                    yield (dataset_config, perturbation, alpha, seed)


def _pending_cells(
    config: ExperimentConfig,
    workflow_instances: list[Workflow],
    seeds: tuple[int, ...],
    completed: set[RowKey],
    logger: logging.Logger,
) -> list[tuple[Cell, list[Workflow]]]:
    pending: list[tuple[Cell, list[Workflow]]] = []
    for cell in _iter_cells(config, seeds):
        dataset_config, perturbation, alpha, seed = cell
        pending_workflows = [
            workflow
            for workflow in workflow_instances
            if _grid_key(dataset_config, perturbation, alpha, seed, workflow) not in completed
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
        pending.append((cell, pending_workflows))
    return pending


def _run_serial(pending_cells: list[tuple[Cell, list[Workflow]]], persist) -> None:
    for (dataset_config, perturbation, alpha, seed), pending_workflows in pending_cells:
        rows = _compute_cell_rows(dataset_config, perturbation, alpha, seed, pending_workflows)
        for row in rows:
            persist(row)


def _run_parallel(
    pending_cells: list[tuple[Cell, list[Workflow]]],
    persist,
    *,
    workers: int,
    logger: logging.Logger,
) -> None:
    """Run cells across a CPU process pool; the parent stays the sole writer.

    Submission is bounded (about two cells per worker in flight) so memory stays
    flat and an abrupt kill loses at most a handful of in-flight cells, which the
    next resume simply recomputes. A worker crash records ``failed`` rows for the
    cell instead of killing the whole run.
    """

    context = _multiprocessing_context()
    cell_iterator = iter(pending_cells)
    inflight: dict[object, tuple[Cell, list[Workflow]]] = {}
    max_inflight = max(1, workers * 2)
    executor = ProcessPoolExecutor(
        max_workers=workers,
        mp_context=context,
        initializer=_init_worker,
        initargs=("cpu",),
    )
    try:
        def submit_next() -> bool:
            item = next(cell_iterator, None)
            if item is None:
                return False
            cell, pending_workflows = item
            future = executor.submit(_compute_cell_rows, *cell, pending_workflows)
            inflight[future] = (cell, pending_workflows)
            return True

        for _ in range(max_inflight):
            if not submit_next():
                break

        while inflight:
            done, _ = wait(list(inflight), return_when=FIRST_COMPLETED)
            for future in done:
                cell, pending_workflows = inflight.pop(future)
                try:
                    rows = future.result()
                except Exception as exc:  # pragma: no cover - exercised via failing-cell test.
                    rows = _failed_cell_rows(cell, pending_workflows, exc)
                    logger.warning(
                        "cell_failed dataset=%s perturbation=%s alpha=%s seed=%s error=%s",
                        cell[0].family,
                        cell[1],
                        cell[2],
                        cell[3],
                        exc,
                    )
                for row in rows:
                    persist(row)
                submit_next()
    except KeyboardInterrupt:
        logger.warning("run_interrupted flushing and shutting down workers")
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)


def _failed_cell_rows(
    cell: Cell,
    workflows: list[Workflow],
    exc: Exception,
) -> list[dict[str, object]]:
    """Synthesize ``failed`` rows for a cell whose worker raised.

    These rows carry the full row key so resume recognizes them and
    ``--rerun-failed`` can re-pick them, but they hold no scores.
    """

    dataset_config, perturbation, alpha, seed = cell
    dataset_params = json.dumps(asdict(dataset_config), sort_keys=True)
    rows = []
    for workflow in workflows:
        parameters = workflow.parameters()
        rows.append(
            {
                "dataset": dataset_config.family,
                "dataset_params": dataset_params,
                "perturbation": perturbation,
                "perturbation_params": "",
                "perturbation_family": None,
                "perturbation_direction": None,
                "label_source": None,
                "edit_distance_raw": None,
                "edit_distance_weighted": None,
                "graph_count": 0,
                "node_count_min": 0,
                "node_count_max": 0,
                "edge_count_min": 0,
                "edge_count_max": 0,
                "alpha": alpha,
                "seed": seed,
                "workflow": workflow.name,
                "implementation_mode": parameters.get("implementation_mode", "paper_faithful"),
                "workflow_params": parameters,
                "distribution_score": None,
                "mean_shift_score": None,
                "paired_score": None,
                "runtime_seconds": 0.0,
                "memory_mb": None,
                "status": "failed",
                "error_message": f"cell_execution_failed: {exc}",
            }
        )
    return rows


def workflows_from_config(config: ExperimentConfig) -> list[Workflow]:
    """Instantiate workflows listed in the experiment config."""

    available = {workflow.name: workflow for workflow in default_workflows()}
    available["diversity_curves_l2"] = available[DIVERSITY_CURVES_WORKFLOW]
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


def _shard_result_csv(path: Path) -> Path:
    """Resolve a shard pointer (results.csv, a run dir, or a results dir)."""

    path = Path(path)
    if path.is_file():
        return path
    for candidate in (path / "results.csv", path / "results" / "results.csv"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"No results.csv found for shard {path}")


def merge_runs(shard_paths: list[Path | str], output_path: Path | str) -> Path:
    """Concatenate shard result CSVs into one, de-duplicating on the row key.

    Each shard owns its own crash-safe results.csv; merging simply unions the
    rows. Because the global seed list is deterministic and shards slice disjoint
    index ranges, two disjoint shards plus a merge reproduce a single unsharded
    run exactly. De-duplication on the row key makes the merge idempotent and
    tolerant of accidental shard overlap.
    """

    seen: set[RowKey] = set()
    merged: list[dict[str, object]] = []
    for shard in shard_paths:
        for row in read_result_rows(_shard_result_csv(Path(shard))):
            key = _row_key(row)
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    merged.sort(key=_row_key)
    return write_result_rows(merged, output_path)


RowKey = tuple[str, str, str, str, str, str, str]


def _completed_keys(path: Path) -> set[RowKey]:
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
    legacy_by_current = {
        DIVERSITY_CURVES_WORKFLOW: {"diversity_curves_l2"},
        NATIVE_NETLSD_WORKFLOW: {LEGACY_NETLSD_MMD_WORKFLOW},
    }
    incompatible = set()
    existing_workflows = {str(row.get("workflow")) for row in read_result_rows(path)}
    for current, legacy_names in legacy_by_current.items():
        if current in expected_workflows:
            incompatible.update(existing_workflows & legacy_names)
    legacy_workflows = incompatible
    if legacy_workflows:
        legacy = ", ".join(sorted(legacy_workflows))
        raise ValueError(
            f"Existing result file contains legacy workflow rows ({legacy}). "
            "Start a fresh CSV with --no-resume or use a new output root before running fixed experiments."
        )


def _row_key(row: dict[str, object]) -> RowKey:
    return (
        str(row.get("dataset", "")),
        str(row.get("dataset_params", "")),
        str(row.get("perturbation", "")),
        str(row.get("alpha", "")),
        str(row.get("seed", "")),
        str(row.get("workflow", "")),
        _canonical_jsonish(row.get("workflow_params", "")),
    )


def _grid_key(
    dataset_config: SyntheticDatasetConfig,
    perturbation: str,
    alpha: float,
    seed: int,
    workflow: Workflow,
) -> RowKey:
    return (
        dataset_config.family,
        json.dumps(asdict(dataset_config), sort_keys=True),
        perturbation,
        str(alpha),
        str(seed),
        workflow.name,
        json.dumps(workflow.parameters(), sort_keys=True),
    )


def _canonical_jsonish(value: object) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _expected_row_count(config: ExperimentConfig, workflows: list[Workflow], num_seeds: int | None = None) -> int:
    seed_count = len(config.seeds) if num_seeds is None else num_seeds
    return (
        seed_count
        * len(config.resolved_dataset_configs())
        * len(config.perturbations.methods)
        * len(config.perturbations.alpha_values)
        * len(workflows)
    )


def _write_checkpoint(
    path: Path,
    result_path: Path,
    completed: set[RowKey],
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


MANIFEST_FILENAME = "run_manifest.json"


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(Path(__file__).resolve().parent),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _library_versions() -> dict[str, str | None]:
    from importlib.metadata import PackageNotFoundError, version

    versions: dict[str, str | None] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    for package in ("numpy", "torch", "streamlit", "plotly", "pandas"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
        except Exception:  # pragma: no cover - metadata backend quirks
            versions[package] = None
    return versions


def write_run_manifest(
    config: ExperimentConfig,
    *,
    run_id: str,
    seeds: tuple[int, ...],
    workflows: list[Workflow],
    result_path: Path,
    checkpoint_path: Path,
    started_at: str,
    ended_at: str | None = None,
    status: str = "running",
    seed_range: tuple[int, int] | None = None,
    workers: int = 1,
    manifest_path: Path | None = None,
) -> Path:
    """Write the per-run manifest for reproducibility/traceability (atomic).

    Records the git commit, the full resolved config, the resolved seed list,
    the workflow list, hostname, start/end timestamps, library versions, and the
    checkpoint path, all inside the run directory.
    """

    path = manifest_path if manifest_path is not None else config.outputs.root / MANIFEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "status": status,
        "git_commit": _git_commit(),
        "hostname": socket.gethostname(),
        "started_at": started_at,
        "ended_at": ended_at,
        "config_hash": config_hash(config),
        "config": resolved_config_payload(config),
        "seeds": [int(seed) for seed in seeds],
        "seed_range": list(seed_range) if seed_range is not None else None,
        "workers": workers,
        "workflows": [workflow.name for workflow in workflows],
        "output_root": str(config.outputs.root),
        "result_path": str(result_path),
        "checkpoint_path": str(checkpoint_path),
        "library_versions": _library_versions(),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)
    return path


def _experiment_logger(log_path: Path, console: bool = False) -> logging.Logger:
    logger = logging.getLogger("experimentation.runner")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    resolved = log_path.resolve()
    has_file_handler = False
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == resolved:
            has_file_handler = True
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) != resolved:
            logger.removeHandler(handler)
            handler.close()
        elif getattr(handler, "_experiment_console_handler", False) and not console:
            logger.removeHandler(handler)
            handler.close()
    if not has_file_handler:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    has_console_handler = any(
        getattr(handler, "_experiment_console_handler", False)
        for handler in logger.handlers
    )
    if console and not has_console_handler:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler._experiment_console_handler = True  # type: ignore[attr-defined]
        console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(console_handler)
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
    perturbation_summary = _summarize_perturbations(paired)
    perturbation_params = json.dumps(perturbation_summary, sort_keys=True)
    size_summary = _graph_size_summary(paired)
    skip_error = _skip_error(paired)
    edit_distance_raw, edit_distance_weighted = cell_edit_distances(paired)

    rows = []
    for workflow in workflows:
        workflow_params = workflow.parameters()
        if skip_error is not None:
            result = {
                "workflow": workflow.name,
                "implementation_mode": workflow_params.get("implementation_mode", "paper_faithful"),
                "workflow_params": workflow_params,
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
                "perturbation_family": perturbation_summary.get("perturbation_family"),
                "perturbation_direction": perturbation_summary.get("perturbation_direction"),
                "label_source": perturbation_summary.get("label_source"),
                "edit_distance_raw": edit_distance_raw,
                "edit_distance_weighted": edit_distance_weighted,
                **size_summary,
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
        "perturbation_family": paired.metadata.get("perturbation_family"),
        "perturbation_direction": paired.metadata.get("perturbation_direction"),
        "label_source": None,
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
        summary["perturbation_family"] = summary["perturbation_family"] or item.get("perturbation_family")
        summary["perturbation_direction"] = summary["perturbation_direction"] or item.get("perturbation_direction")
        summary["label_source"] = summary["label_source"] or item.get("label_source")
    return summary


def _graph_size_summary(paired: PairedDistribution) -> dict[str, object]:
    graphs = paired.original_graphs + paired.perturbed_graphs
    if not graphs:
        return {
            "graph_count": 0,
            "node_count_min": 0,
            "node_count_max": 0,
            "edge_count_min": 0,
            "edge_count_max": 0,
        }
    node_counts = [graph.num_nodes for graph in graphs]
    edge_counts = [graph.number_of_edges() for graph in graphs]
    return {
        "graph_count": len(paired.original_graphs),
        "node_count_min": min(node_counts),
        "node_count_max": max(node_counts),
        "edge_count_min": min(edge_counts),
        "edge_count_max": max(edge_counts),
    }


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
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True)
    return value
