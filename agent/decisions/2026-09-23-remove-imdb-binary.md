---
title: Remove IMDB-BINARY as an experimental dataset
date: 2026-09-23
time_utc: 17:28 UTC
status: done
---

## Decision

Remove IMDB-BINARY entirely as an experimental dataset: the config presets,
the CLI `imdb` target, the generic TU-format loader it was built around
(`real_datasets.py`), the downloaded data files, the fetch script, and the
tests exercising that loader. Historical result rows and one retired doc are
kept for reference.

## Why

The user pointed to
[`docs/2502.02379v3.pdf`](../../docs/2502.02379v3.pdf) — Coupette, Wayland,
Simons & Rieck, *"No Metric to Rule Them All: Toward Principled Evaluations of
Graph-Learning Datasets"* (ICML 2025) — as evidence that IMDB-BINARY is not an
informative graph-learning benchmark.

Specifically, the paper's dataset taxonomy (Section 4.3, page 8) places
IMDB-B (and IMDB-M, COLLAB) in the **Deprecate (‡)** category: datasets with
*high performance separability* but *low structural diversity*. Their
interpretation (page 8): "Although both structure and features may be needed
to achieve state-of-the-art performance, these datasets do not contain
interesting structural variation, and as such, they do little to probe the
capabilities of graph-learning models." This independently corroborates the
project's own prior decision (recorded pre-existing, uncommitted, in
[`docs/experimentation/randomness_rerun_plan.md`](../../docs/experimentation/randomness_rerun_plan.md):
"Exclude IMDB-BINARY. Implement ZINC ... as the real-data experiment") to move
the real-dataset role to ZINC instead.

## Scope

Asked the user how deep to go, since `real_datasets.py` is written as a
generic TU-format loader but IMDB-BINARY was its only registered dataset, and
every doc/script/data file built around it was IMDB-specific. The user chose
**full removal**.

## What changed

- [`src/experimentation/real_datasets.py`](../../src/experimentation/real_datasets.py) — deleted (the generic TU-format loader; nothing else used it).
- [`tests/test_real_datasets.py`](../../tests/test_real_datasets.py) — deleted (tested only that loader).
- [`scripts/fetch_imdb_binary.py`](../../scripts/fetch_imdb_binary.py) — deleted.
- `data/IMDB-BINARY/` — deleted (gitignored, locally downloaded data; not tracked by git).
- [`src/experimentation/config.py`](../../src/experimentation/config.py) — removed `imdb_binary_dataset_config()` and `imdb_config()`.
- [`src/experimentation/cli.py`](../../src/experimentation/cli.py) — removed the `imdb_config` import and the `"imdb"` entry from `CONFIG_BUILDERS`. `--config imdb` is no longer a valid CLI target.
- [`src/experimentation/datasets.py`](../../src/experimentation/datasets.py) — removed the `REAL_DATASET_FAMILIES`/`load_tu_dataset` import, the real-family dispatch branch in `generate_graph_distribution()`, and `_load_real_distribution()`. Reworded the `SyntheticDatasetConfig` comment for `data_root` (still used by the `zinc` family) since it no longer describes a TU loader.
- [`src/experimentation/workflows.py`](../../src/experimentation/workflows.py) — `median_heuristic_bandwidth()` docstring's example dataset changed from IMDB-BINARY to ZINC (both are variable-size real datasets; ZINC is now the only one).
- [`docs/experimentation/community_detection.md`](../../docs/experimentation/community_detection.md) — replaced the IMDB-BINARY complexity-budget example with a generic "real graphs such as ZINC" reference.
- [`docs/experimentation/real_datasets.md`](../../docs/experimentation/real_datasets.md) — kept, but marked **Retired 2026-09-23** at the top with a pointer to this decision; the rest of the document (why IMDB-BINARY was originally chosen, the TU format, usage commands) is preserved for interpreting historical `imdb_binary` result rows.
- [`docs/experimentation/corrected_runs.md`](../../docs/experimentation/corrected_runs.md) — added a "Real datasets" section: kept the pre-existing (uncommitted) ZINC-implementation pointer paragraph that used to live at the bottom of `real_datasets.md`, and added a note on the IMDB-BINARY removal linking to the retired doc and this decision.

## What was deliberately left alone

Historical/point-in-time documents and data-processing code that only
describe or display past runs, not generate new ones:

- [`docs/experimentation/CHANGELOG.md`](../../docs/experimentation/CHANGELOG.md) — "Item 6" entry describing the original IMDB-BINARY loader addition; a changelog records what happened, not current state.
- [`docs/experimentation/final_experimentation_plan.md`](../../docs/experimentation/final_experimentation_plan.md) and [`docs/experimentation/randomness_rerun_plan.md`](../../docs/experimentation/randomness_rerun_plan.md) — superseded/point-in-time planning docs that already discuss excluding IMDB-BINARY in favor of ZINC.
- [`docs/experimentation/seed_sweep.md`](../../docs/experimentation/seed_sweep.md) — mentions the old `--config imdb` CLI value in a sentence about `--seed-count`; historical/descriptive, low value to chase.
- `results/runs/*/code_snapshot/` — frozen snapshots of past runs' source code.
- `archive/stray-logs/imdb_run.log` — an archived log file.
- Analysis scripts under `scripts/` (`analyze_structural_insights.py`,
  `diagnose_mmd_response.py`, `check_distributional_conditions.py`,
  `analyze_statistical_assumptions.py`, `generate_final_figures.py`,
  `generate_interaction_hero_figures.py`, `generate_poster_figures.py`,
  `generate_poster_hero_figures.py`) — these read historical result CSVs that
  may contain `imdb_binary` rows; they don't generate new IMDB-BINARY data,
  so they were left untouched (same rationale as the dashboard/evaluation/
  figures label maps in [[2026-09-23-remove-edge-addition-deletion]]).

## Verification

Ran the full test suite after the change:

```
PYTHONPATH=src python -m unittest discover -s tests
```

Result: `Ran 157 tests ... OK (skipped=15)` — 8 fewer tests than before (the
deleted `tests/test_real_datasets.py`), same pre-existing skips. Also verified
`experimentation.cli`, `.config`, `.datasets`, and `.workflows` still import
cleanly, and grepped `src/` to confirm no remaining references to
`real_datasets`, `REAL_DATASET_FAMILIES`, `load_tu_dataset`,
`imdb_binary_dataset_config`, or `imdb_config`.
