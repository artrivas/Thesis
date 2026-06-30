# Experimentation Changelog

Running log of changes to the `src/experimentation/` module and its docs. Newest
entries first. Each entry corresponds to one committed work item.

## Item 1 — Grid-cell parallel runner + seed-range sharding

**Modules:** `runner.py`, `config.py`, `cli.py`,
`tests/test_runner_parallel.py`, `docs/experimentation/parallelism.md`.

- Added a CPU-only parallel execution path to `run_experiment` via
  `ProcessPoolExecutor`. The unit of parallel work is one **grid cell**
  `(seed, dataset_config, perturbation, alpha)`; a worker generates the paired
  distribution once and runs all pending workflows **serially**, returning rows.
  The **parent process remains the sole writer**, so the per-row append +
  `os.fsync` + `checkpoint.json` crash-safety contract is unchanged.
- `--workers N` (default `os.cpu_count() - 1`). `--workers 1` keeps the original
  serial path, byte-for-byte identical to previous behavior.
- Each worker is pinned single-threaded (`OMP/MKL/OPENBLAS/NUMEXPR/VECLIB
  _NUM_THREADS=1`, `torch.set_num_threads(1)`) via the pool initializer, run
  under the `forkserver` start method (falls back to `spawn`). This preserves the
  validity of `relative_runtime` and `tracemalloc` `memory_mb`, which require
  controlled single-core contention.
- **Seed-range sharding:** `--seed-range A:B` restricts a run to a half-open
  index slice of the resolved seed list; each shard writes to its own
  shard-tagged run directory (no cross-machine write contention). A new `merge`
  CLI subcommand and `merge_runs()` concatenate shard CSVs, de-duplicating on the
  row key, then optionally evaluate/figure the merged CSV.
- Robustness: a worker exception records `failed` rows for the cell (run keeps
  going); `KeyboardInterrupt`/SIGTERM flush and shut workers down cleanly so the
  next resume is consistent.
- `config.py`: added `OutputConfig.evaluation`, `output_config_for_root`,
  `config_hash` (seed-normalized, machine-independent), `run_id_for_config`,
  `shard_suffix`, and `build_run_output_config` for the traceable
  `results/runs/<id>[_shard-A-B]/` layout.
- `cli.py`: added `run` (traceable run dirs, `--workers`, `--seed-range`,
  `--config`, `--results-root`, `--run-id`, `--evaluate`, `--figures`) and
  `merge` subcommands; kept legacy `run_debug_experiment` /
  `run_full_synthetic_experiment` for back-compat.
- Tests: determinism (parallel == serial), resume-after-kill, failed-cell
  handling + `--rerun-failed`, seed-range sharding + merge, config-hash
  stability. Full suite: 84 tests passing.
