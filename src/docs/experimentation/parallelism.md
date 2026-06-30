# Parallel Execution, Crash-Safe Resume, and Seed-Range Sharding

This document explains how the runner executes the experiment grid in parallel
on a CPU-only machine without compromising the validity of the timing/memory
metrics, the crash-safety of the result CSV, or determinism.

## Unit of parallel work: one grid cell

A **grid cell** is one `(seed, dataset_config, perturbation, alpha)` combination.
A worker:

1. generates the `PairedDistribution` for that cell once, and
2. runs **all pending workflows on it serially**, returning the result rows.

Workers never write to disk. They only compute and return rows. The **parent
process is the sole writer**.

```
parent: enumerate cells ──▶ ProcessPoolExecutor (N workers)
           ▲                      │  each worker = one cell
           │  rows                │  workflows run SERIALLY inside the cell
           └──────────────────────┘
parent: persist(row)  =  CSV append + flush + os.fsync + checkpoint.json
```

## Why parallelize across cells but keep workflows serial within a cell

Two metrics are only meaningful under **controlled core contention**:

- `relative_runtime` compares each workflow's `runtime_seconds` against the
  fastest workflow *for the same `(dataset, perturbation, alpha, seed)`*. That
  comparison is only fair if the four workflows in a cell ran one-at-a-time on
  the same uncontended core.
- `memory_mb` comes from `tracemalloc`, which measures the Python allocations of
  a single workflow. Running workflows concurrently would not corrupt the number
  (tracemalloc is per-process) but running them on a contended core would distort
  the paired `runtime_seconds`.

Therefore the design is:

- **Across cells → parallel.** Different cells are independent; running them on
  different cores changes nothing about within-cell comparisons.
- **Within a cell → serial.** The four workflows are timed against each other, so
  they must run sequentially on one core.
- **Each worker is single-threaded.** The pool initializer sets
  `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` (plus
  `NUMEXPR_NUM_THREADS`/`VECLIB_MAXIMUM_THREADS`) and calls
  `torch.set_num_threads(1)` when torch is present. A workflow therefore cannot
  spawn its own threads and steal cores from sibling cells, which would make the
  relative-runtime numbers irreproducible.

`--workers 1` keeps the original serial code path and is byte-for-byte identical
to the historical behavior; use it for debugging. `--workers N` (default
`os.cpu_count() - 1`) matches `--workers 1` on every score column and is
materially faster on multi-core.

## Start method: forkserver

The pool uses the `forkserver` start method on POSIX (falling back to `spawn`).
`forkserver` forks each worker from a clean, single-threaded server process, so:

- the thread-cap environment variables in the initializer take effect *before*
  any numeric library is imported in the worker, and
- we avoid the fork-from-a-multithreaded-parent deadlock hazard that the default
  `fork` method warns about on modern Python.

## Crash-safe resume (unchanged durability contract)

The parent keeps the existing per-row durability mechanism and only extends it:

- every persisted row is written, `flush()`ed, and `os.fsync()`ed before the next
  row is computed;
- `checkpoint.json` is rewritten atomically (`*.tmp` then `replace`) after each
  row;
- on restart, `_completed_keys` reads the existing CSV and the run skips any cell
  whose workflows are all already present.

Because the parent is the only writer and persists one fsync'd row at a time, an
abrupt kill (lost connectivity, SIGKILL) can lose at most the handful of cells
that were *in flight* in workers; those cells are simply recomputed on the next
resume. The CSV never contains a partially written or duplicated row.

`KeyboardInterrupt`/SIGTERM shut the pool down (`cancel_futures=True`) and
re-raise after the last fsync'd row, leaving a consistent CSV for the next
resume.

**Single resume command** (see `traceability.md`):

```
python -m experimentation.cli run --resume --results-root results/runs --run-id <id> --workers N
```

### Bounded submission

The parent keeps about `2 × workers` cells in flight at once instead of
submitting the whole grid. This keeps parent memory flat for large sweeps and
minimizes the number of in-flight (recomputed-on-resume) cells if the process
dies.

## Failed cells do not kill the run

If a worker raises while computing a cell (e.g. a malformed dataset), the parent
catches it, logs `cell_failed`, and writes a `failed` row for each pending
workflow in that cell (full row key, no scores). The run continues. On resume,
`--rerun-failed` drops `failed` rows and recomputes them. (Per-workflow
exceptions are still caught inside `Workflow.run` and recorded as `failed`
status, exactly as before — this cell-level guard is for catastrophic errors
that escape a workflow.)

## Seed-range sharding for multi-machine runs

The resolved seed list is **globally deterministic and machine-independent**
(see `seed_sweep.md`): `seed_count` expands to `[base, base+1, …]`. This lets a
replication sweep be split across machines by **index slice**:

- `--seed-range A:B` restricts a run to `resolved_seeds[A:B]` (half-open).
- Each shard writes to its **own run directory**, tagged with the slice, e.g.
  `results/runs/<id>_shard-0-10/`. Because shards write to different directories,
  there is **no cross-process or cross-machine write contention**, and each shard
  is independently crash-safe and resumable.

Because the slices are disjoint by construction and the seed list is
deterministic, the shards are non-overlapping and reproducible.

### Merging shards

```
python -m experimentation.cli merge \
    --shard results/runs/<id>_shard-0-10 \
    --shard results/runs/<id>_shard-10-20 \
    --output results/runs/<id>_merged --evaluate --figures
```

`merge` concatenates the shard `results.csv` files, **de-duplicating on the row
key**, writes one combined `results.csv`, and (optionally) runs
evaluation/figures on it. The de-duplication makes the merge idempotent and
tolerant of accidental shard overlap.

**Guarantee:** two disjoint `--seed-range` shards run on separate
processes/machines and then `merge`d produce a combined results directory
numerically identical to a single unsharded run over the same seeds, with no
duplicate rows. This is verified in `tests/test_runner_parallel.py`.

## Tests

`tests/test_runner_parallel.py` covers:

- **determinism** — parallel scores equal serial scores for the same seeds;
- **resume-after-kill** — a truncated CSV plus a resume yields the complete,
  de-duplicated CSV with no recomputation of completed cells;
- **failed-cell handling** — a worker exception produces `failed` rows and does
  not kill the run; `--rerun-failed` re-picks them without duplication;
- **seed-range sharding** — two disjoint shards plus a merge equal one unsharded
  run, numerically identical and de-duplicated.
