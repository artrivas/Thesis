# Results index

Which run is current, what each one contains, and what is safe to cite.

## Current run — cite this one

**`runs/2026-07-03_merged/`** is the source of truth for the thesis. Every figure
and table in the results chapter derives from it.

| | |
|---|---|
| Rows | 20,328, all `status=success` |
| Datasets | `erdos_renyi`, `stochastic_block_model`, `barabasi_albert` (synthetic) + `imdb_binary` (real) |
| Workflows | `native_netlsd`, `wl_subtree_kernel_mmd`, `diversity_curves_shortest_path`, `structural_statistics_mmd` |
| Perturbations | `edge_insertion`, `edge_deletion`, `triangle_insertion`, `triangle_deletion`, `community_weakening`, `hub_modification` |
| α grid | 0.0 … 1.0 in steps of 0.1 |
| Seeds | 24 |

It is a merge of two runs, produced with `experimentation.cli merge`; no value was
recomputed. Provenance is recorded in
[`runs/2026-07-03_merged/run_manifest.json`](runs/2026-07-03_merged/run_manifest.json).

### What to read from it

| Path | Contents |
|---|---|
| `results/results.csv.gz` | The raw 20,328-row result table (committed, 1.1 MB). |
| `evaluation/` | `evaluation_summary.csv` (96 rows: 4 workflows × 4 datasets × 6 perturbations), `final_matrix.csv`, `failure_map.csv`. |
| `figures_final/` | **Thesis figures.** Start at [`figures_final/README_figures.md`](runs/2026-07-03_merged/figures_final/README_figures.md), which says which file belongs in the results chapter and which goes to the appendix. |
| `poster_figures/` | **Poster figures**, plus `panel_captions.md`, `hero_analysis_notes.md`, and `interaction_findings/`. |
| `figures/` | Automatic pipeline figures. Internal diagnostics — **do not cite these in the thesis**; `figures_final/` supersedes them. |

### The raw CSV

`results/results.csv` is 23 MB and is not committed. The gzipped copy beside it is,
and the code reads either transparently — `read_result_rows()` and the figure
scripts fall back to `.csv.gz` when the plain `.csv` is absent. To materialize it:

```bash
gunzip -k results/runs/2026-07-03_merged/results/results.csv.gz
```

## Component runs

Kept for traceability. Their manifests are committed; their bulky artifacts are not.

| Run | Config | Rows | Role |
|---|---|---|---|
| `runs/2026-07-01T0519_278e5a7d/` | `278e5a7d` | 19,008 | Full synthetic grid. Shard 1 of the merged run. |
| `runs/2026-07-03T0159_3bb151a6/` | `3bb151a6` | 1,320 | IMDB-BINARY real dataset. Shard 2 of the merged run. |
| `runs/2026-07-01T0437_b502d88d/` | `b502d88d` | 432 | Smoke run (5 graphs × 8 nodes). Not part of the merge; keep for pipeline history, do not cite. |

## Archived

`archive/` (untracked, at the repo root) holds superseded material: the six
pre-traceability `outputs/` trees and two aborted zero-row runs. See
[`../archive/README.md`](../archive/README.md).

## Regenerating the figures

From the repo root, with the `figures` extra installed:

```bash
python scripts/generate_final_figures.py
python scripts/generate_poster_figures.py
python scripts/generate_poster_hero_figures.py
python scripts/generate_interaction_hero_figures.py
```

Each reads only the merged run's `results.csv[.gz]` and `evaluation_summary.csv`;
none of them reads a cached figure.

## Adding a run

New runs land here automatically:

```bash
python -m experimentation.cli run --config full
```

The `.gitignore` policy tracks the `run_manifest.json` and nothing else from a new
run. Promote a run to "current" by merging or citing it here, and update this file.
