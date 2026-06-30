# Streamlit Dashboard

An interactive, CPU-only viewer for experiment results. It reads CSVs produced by
the runner/evaluation and **never recomputes graph workflows** — every panel is a
lightweight tabular pass over the result rows (or reads the precomputed
`evaluation/` CSVs from the selected run).

## Running it

```
python -m pip install -r requirements-dashboard.txt   # streamlit, plotly, pandas
streamlit run experimentation/dashboard.py            # from the src/ directory
```

Dependencies are unchanged (`streamlit`, `plotly`, `pandas`); no new packages.

## Run selector (traceable tree)

The sidebar points at the traceable results root (default `results/runs/`) and
lists every run directory containing `results/results.csv`, newest first. Pick a
run to load its `results.csv`; the sidebar shows the path to that run's
`run_manifest.json` for traceability (git commit, config, seeds — see
`traceability.md`). If no runs are found, the sidebar falls back to a CSV uploader
and a manual path box (back-compat with the legacy `outputs/` tree).

## Panels

1. **Score vs Alpha (seed band)** — pick a `(dataset, perturbation)` cell; shows
   each workflow's mean distribution score vs alpha with **mean ± std error bars
   over seeds**. A rising mean that clears its own seed band is the visual answer
   to "it's just randomness" (see `seed_sweep.md`, `alpha_validation.md`).
2. **Failure Map** — the diagnosed-cause grid per `(dataset, perturbation)`,
   colored by cause (`ok` / `perturbation_starved` / `method_blind` / `unstable`
   / `inapplicable`), plus the full `failure_map.csv` table with notes. Prefers
   the run's precomputed `evaluation/failure_map.csv`; derives it from rows only
   as a fallback. Explains WHY a cell behaves as it does (see `failure_map.md`).
3. **Edit-distance Validation** — scatter of `distribution_score` vs the
   importance-weighted edit-distance ground truth, faceted by dataset. A positive
   trend validates that alpha tracks real, weighted structural change (see
   `alpha_validation.md`).
4. **Community: truth vs detected** — `community_weakening` distribution score vs
   alpha, split by `label_source`: SBM uses the planted `ground_truth` partition,
   ER/BA use `detected` communities (the negative control — see
   `community_detection.md`).
5. **Paired Distance**, **Mean Shift vs Paired**, **Evaluation Summary** (with a
   metric heatmap that now includes the edit-distance validation metrics),
   **Final Matrix**, and **Raw Rows** — unchanged tabular/diagnostic views.

## Design notes

- CPU-only and read-only: the UI imports `streamlit`/`plotly`/`pandas` lazily and
  never runs a workflow. Aggregations are pandas/`generate_*` passes over the
  already-computed rows.
- The pure data helpers (`discover_runs`, `seed_band_table`,
  `edit_distance_validation_rows`, `community_label_source_rows`,
  `load_failure_map_rows`) are unit-tested in `tests/test_dashboard.py`; the
  Plotly renderers are thin wrappers over them.
