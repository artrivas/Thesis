# Traceable Run Directories and the Run Manifest

Experiment outputs are isolated from source code and organized so that any result
can be traced back to the exact code, config, and seeds that produced it.

## Layout

Every run lives in its own directory under a results root (default
`results/runs/`), named with a timestamp and a short config hash:

```
results/runs/2026-06-29T1530_1a2b3c4d/
├── run_manifest.json        # reproducibility record (tracked in git)
├── results/
│   └── results.csv          # the result rows (git-ignored, bulky)
├── logs/
│   ├── run.log
│   └── checkpoint.json      # crash-safe resume state (inside the run dir)
├── evaluation/
│   ├── evaluation_summary.csv
│   ├── final_matrix.csv
│   └── failure_map.csv
└── figures/
    └── figure_*.svg
```

Seed-range shards get a suffixed sibling directory, e.g.
`results/runs/2026-06-29T1530_1a2b3c4d_shard-0-10/` (see `parallelism.md`).

- The **config hash** is `sha1` of the seed-normalized resolved config (dataset
  params with the per-graph seed zeroed out, perturbation methods + alphas,
  workflow names, and the swept seed list), truncated to 8 chars. It is
  machine-independent and stable, so the same experiment yields the same hash on
  any machine and across shards.
- Results **never** go into the source tree. `outputs/` still works for
  back-compat (`--output-root`), but new runs default to the traceable
  `results/runs/` tree.

## `run_manifest.json`

Written by the parent process at run start (`status: running`) and rewritten
atomically at the end (`status: finished`, with `ended_at`). It records:

- `git_commit` — `git rev-parse HEAD` at run time (or `null` if unavailable);
- `config` + `config_hash` — the full seed-normalized resolved config;
- `seeds` — the **resolved** seed list actually used (after any `--seed-range`
  slice), plus `seed_range`;
- `workflows` — the workflow list;
- `hostname`;
- `started_at` / `ended_at` — UTC timestamps;
- `library_versions` — python/platform plus numpy/torch/streamlit/plotly/pandas
  when installed;
- `result_path`, `output_root`, and `checkpoint_path`.

Together these let anyone reproduce a run: check out `git_commit`, re-run with the
recorded config + seeds, and expect bit-identical results (the seed list is
deterministic — see `seed_sweep.md`).

## The single resume command

The `checkpoint.json` lives inside the run directory, so a run is fully
self-describing. Resuming after a crash targets an existing run directory by id:

```
python -m experimentation.cli run --resume \
    --results-root results/runs --run-id <id> --workers N
```

When `--run-id` is given, the run directory name is exactly `<id>` (no new
timestamp), so re-issuing the command continues the same run with zero
recomputation of completed cells and zero CSV corruption (the parent is the sole
writer; each row is fsync'd; see `parallelism.md`). `--resume` is the default;
the flag is accepted explicitly for clarity. `--run-id` is also how shards on
different machines agree on a directory name.

## Git tracking (`results/.gitignore`)

`results/.gitignore` keeps the run **structure and manifests** tracked while
ignoring bulky artifacts:

- ignored: `runs/*/results/`, `runs/*/logs/`, `runs/*/figures/`,
  `runs/*/evaluation/`;
- tracked: `runs/*/run_manifest.json` (the only committable file inside a run
  dir).

So you can commit a manifest to record that a run happened — and exactly how —
without ever committing a large CSV.

## Tests

`tests/test_traceability.py`: run-directory layout, auto run-id format, manifest
required fields, manifest records the sharded seed subset, and resume-by-run-id
targets the same directory without duplication.
