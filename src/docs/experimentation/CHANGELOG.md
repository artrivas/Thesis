# Experimentation Changelog

Running log of changes to the `src/experimentation/` module and its docs. Newest
entries first. Each entry corresponds to one committed work item.

## Item 8 — Seed-sweep config knob

**Modules:** `config.py`, `runner.py`, `cli.py`, `tests/test_seed_sweep.py`,
`docs/experimentation/seed_sweep.md`.

- `seeds_from_count(n, base_seed=0)` expands a seed COUNT into a deterministic,
  machine-independent seed list `(base_seed, …, base_seed+n-1)`.
- `ExperimentConfig` gains `seed_count` and a `resolved_seeds()` method:
  `seed_count` takes precedence over an explicit `seeds` list when both are set;
  an explicit list is used otherwise; **neither** raises a clear error. The
  `seeds` field default is now `None`.
- Named configs: `debug_config` uses `seed_count=2`; new `replication_config`
  uses `seed_count=24` (20–30 band). CLI: `--config {debug,full,replication,imdb}`
  and `--seed-count N` (deterministic override).
- Runner and `resolved_config_payload`/manifest now use `resolved_seeds()`, so the
  resolved list drives the sweep, the config hash, the manifest, and
  `--seed-range` slicing. `--seed-count 30` resolves to a 30-seed list recorded
  in `run_manifest.json`.
- Test helpers that build on `debug_config` and want an explicit `seeds` list now
  pass `seed_count=None` (documented contract).
- Tests: `seeds_from_count` determinism/correctness, precedence, missing-both
  error, debug/replication resolved lists, `seed_count=30`, `--seed-range` slice
  equals the sublist and disjoint shards partition the list.

## Item 7 — Streamlit dashboard updates

**Modules:** `dashboard.py`, `tests/test_dashboard.py`,
`docs/experimentation/dashboard.md`.

- Sidebar **run selector**: scans the traceable `results/runs/` tree (default)
  for run dirs with `results/results.csv`, newest first, and surfaces the run's
  `run_manifest.json` path. Falls back to upload / manual path for legacy
  `outputs/`.
- New panels: **alpha-vs-score with a per-seed band** (mean ± std over seeds),
  the **failure map** (colored by diagnosed cause; prefers the run's precomputed
  `failure_map.csv`), the **edit-distance-vs-score validation** scatter, and the
  **ground_truth-vs-detected community** comparison.
- Evaluation-summary heatmap metric list now includes
  `edit_distance_validation` / `paired_edit_distance_validation`; numeric
  coercion covers the edit-distance columns.
- CPU-only and read-only: no graph recompute in the UI; panels are tabular
  passes / read the precomputed evaluation CSVs. `requirements-dashboard.txt`
  unchanged (streamlit/plotly/pandas).
- Tests: `discover_runs`, `seed_band_table`, `edit_distance_validation_rows`,
  `community_label_source_rows`, `load_failure_map_rows`; renderers smoke-tested
  against a real run.

## Item 6 — Real dataset loader (IMDB-BINARY)

**Modules:** new `real_datasets.py`, `datasets.py`, `config.py`, `cli.py`,
`workflows.py`, `scripts/fetch_imdb_binary.py`, `tests/fixtures/TINYTU/`,
`tests/test_real_datasets.py`, `src/.gitignore`,
`docs/experimentation/real_datasets.md`.

- New `real_datasets.py`: dependency-free TUDataset text-format loader
  (`_A.txt`, `_graph_indicator.txt`, `_graph_labels.txt`, optional
  `_node_labels.txt`) into the repo's `Graph` objects, targeting IMDB-BINARY.
- Integrated as a dataset family `imdb_binary`: `SyntheticDatasetConfig` gains
  `data_root` / `dataset_name`; `generate_graph_distribution` dispatches to the
  loader (seed-dependent subsample for replication). All perturbations,
  workflows, edit-distance ground truth, and the failure map apply unchanged;
  community_weakening uses detected labels (unlabeled data).
- `config.imdb_config` / `imdb_binary_dataset_config`; `--config imdb` in the CLI.
- `scripts/fetch_imdb_binary.py` downloads + unzips into `src/data/IMDB-BINARY/`
  (stdlib only); `src/.gitignore` ignores `data/` so the real dataset is never
  committed. Only the tiny `tests/fixtures/TINYTU/` is tracked.
- `workflows.median_heuristic_bandwidth` added for variable-size auto-bandwidth
  (not wired into defaults, to preserve synthetic reproducibility); documented
  MMD-bandwidth and NetLSD-normalization sensitivity for variable graph sizes.
- Tests: fixture structure/labels, missing-data error, real family through
  `generate_graph_distribution` and a full run, median-heuristic bandwidth.

## Item 5 — Traceable run directories + run manifest

**Modules:** `runner.py`, `cli.py`, `config.py` (item 1 helpers),
`results/.gitignore`, `results/runs/.gitkeep`,
`tests/test_traceability.py`, `docs/experimentation/traceability.md`.

- `run_experiment` writes `run_manifest.json` into the run directory at start
  (`status=running`) and end (`status=finished`), atomically. It records git
  commit, full resolved config + config hash, the **resolved** seed list (after
  any `--seed-range`), workflow list, hostname, start/end UTC timestamps, library
  versions, result path, and checkpoint path.
- The traceable layout `results/runs/<timestamp>_<cfghash>[_shard-A-B]/` (helpers
  from item 1) is the default for the `run` subcommand via `--results-root`
  (default `results/runs`); `checkpoint.json` lives inside the run dir. `outputs/`
  still works for back-compat.
- Resume targets an existing run dir by id:
  `run --resume --results-root results/runs --run-id <id>`. Added the explicit
  `--resume` flag and threaded `run_id` into the manifest.
- `results/.gitignore` keeps run structure + `run_manifest.json` tracked while
  ignoring bulky `results/`, `logs/`, `figures/`, `evaluation/` artifacts.
- Tests: run-dir layout, auto run-id format, manifest fields, sharded seed
  subset recorded, resume-by-run-id targets the same directory.

## Item 4 — Seed-replication band + failure map

**Modules:** `evaluation.py`, `figures.py`, `tests/test_failure_map.py`,
`tests/test_runner_parallel.py`, `docs/experimentation/failure_map.md`.

- `figure_1_score_vs_alpha` now overlays a per-seed dispersion band: shaded
  mean ± std plus a deterministic bootstrap 95% CI envelope over seeds, so the
  "it's just randomness" objection is visible. Added `polygon`, dashed
  `polyline`, `_std`, `_bootstrap_ci` (deterministic), `_dispersion_band`.
- New `figure_6_failure_map.svg` and machine-readable `failure_map.csv`
  (written by `evaluate_results`). `generate_failure_map` diagnoses each
  `(dataset, perturbation)` cell with a cause: `inapplicable`,
  `perturbation_starved`, `method_blind`, `unstable`, or `ok`, derived from
  logged `edit_distance_raw` + sensitivity/monotonicity/CV, in that precedence
  order. The map explains WHY a cell behaves as it does (e.g.
  triangle_deletion-on-ER = `perturbation_starved`).
- Verified the multi-seed path yields non-degenerate CV (the old CV=0/tau=1 was a
  single-seed artifact); added a regression test.
- `failure_map.md` documents the causes, precedence, and the
  triangle_deletion-on-ER worked example.
- Tests: each cause label is triggered by synthetic rows; SVG renders;
  multi-seed CV is non-zero.

## Item 3 — Edit-distance ground truth + alpha validation

**Modules:** new `ground_truth.py`, `perturbations.py`, `runner.py`,
`evaluation.py`, `tests/test_ground_truth.py`,
`docs/experimentation/alpha_validation.md`.

- New `ground_truth.py`: exact per-pair edit distance from logged operations
  (never NP-hard GED). `raw` = symmetric-difference size of the edge sets;
  `weighted` = sum of edited-edge importances on the **original** graph. Importance
  weighting is pluggable: dependency-free Brandes `brandes_betweenness`,
  `edge_betweenness`, `node_betweenness`; default `betweenness_product_weight`
  (`1 + cb[u]·cb[v]`, defined for added and removed edges).
- `perturb_graph` now records the exact net `edited_edges` (symmetric difference,
  so add-then-remove cancels) in every perturbation's metadata.
- Runner computes per-cell mean `edit_distance_raw` and `edit_distance_weighted`
  (new result columns) once per cell and attaches them to every workflow row.
- Evaluation adds `edit_distance_validation` (Spearman of `distribution_score` vs
  `edit_distance_weighted`) and `paired_edit_distance_validation` (vs
  `paired_score`) to `evaluation_summary.csv`.
- `alpha_validation.md`: alpha is a nominal control validated empirically by
  (a) replication over seeds and (b) monotone correlation with the
  importance-weighted edit-distance ground truth; explicitly flags paired
  analysis as a synthetic-only diagnostic, not a distribution distance.
- Tests: known raw counts, hub-vs-leaf weighting ordering, bridge edge
  betweenness peak, cell-mean edit distance scaling with alpha.

## Item 2 — Detected-community fallback (Clauset–Newman–Moore)

**Modules:** `perturbations.py`, `runner.py`, `tests/test_perturbations.py`,
`docs/experimentation/community_detection.md`, `docs/experimentation/theory.md`.

- `_community_weakening` no longer skips when `community_labels` are missing.
  Added `detect_communities`, a dependency-free deterministic greedy modularity
  maximizer (CNM agglomerative; merge gain `B_cd/m - D_c·D_d/(2m²)`, ties to the
  lowest ids). Ground-truth labels (SBM) are used when present and tagged
  `label_source=ground_truth`; otherwise communities are detected and tagged
  `label_source=detected`.
- New result column `label_source` (empty for non-community perturbations),
  propagated through `_summarize_perturbations` → `_run_workflow_grid`. Also
  records `num_communities` in metadata.
- Documented the algorithm, the ER negative-control interpretation (a detected
  partition of a structureless graph is noise → low sensitivity is expected),
  and the ground_truth-vs-detected distinction; updated theory.md.
- Tests: SBM ground_truth path unchanged; ER/BA produce non-skipped `detected`
  rows; detector recovers a planted two-community graph; edgeless graph handled.

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
