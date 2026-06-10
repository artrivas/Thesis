# Final Experimentation Plan

## 1. Objective

Evaluate how four representative graph distribution comparison workflows detect
controlled perturbations in synthetic graph distributions.

The experiment compares graph distributions, not only individual graph pairs.
For each original graph `G_i`, the pipeline generates a paired perturbed graph
`G_i^alpha`.

## 2. Real Dataset Scope

Real datasets are excluded in this version. The current goal is to stabilize the
synthetic protocol, perturbation definitions, scoring outputs, and evaluation
tables before adding external dataset variability.

## 3. Synthetic Datasets

The synthetic families are:

- Erdos-Renyi: controls random density and noise.
- Stochastic Block Model: controls community and mesoscopic structure.
- Barabasi-Albert: controls hubs and heavy-tail degree behavior.

## 4. Perturbations

Perturbations are:

- Edge addition/deletion: attempts `floor(alpha * |E|)` edge operations.
- Triangle injection/removal: attempts `floor(alpha * max(1, |E|))` motif
  operations.
- Community weakening: rewires an alpha fraction of intra-community edges into
  inter-community edges when community labels are available.
- Hub modification: modifies an alpha fraction of edges incident to top-degree
  nodes where possible.

`alpha` defaults to:

```text
0.0, 0.1, 0.2, ..., 1.0
```

## 5. Workflows

The workflows are representation plus discrepancy pipelines:

- `GraphStats+MMD`: structural graph statistics followed by RBF MMD.
- `WLFeatures+MMD`: Weisfeiler-Lehman subtree feature counts followed by
  linear MMD.
- `NativeNetLSD`: NetLSD heat-trace signatures compared by L2 distance between
  mean signatures.
- `DiversityCurveDistance`: shortest-path Diversity Curves followed by L2
  distance between mean curve representations.

## 6. Measurement Levels

The experiment reports:

- Distribution-level behavior through `distribution_score`.
- Mean-shift behavior through `mean_shift_score`.
- Paired behavior through `paired_score`.
- Granular behavior by dataset, perturbation, alpha, seed, and workflow.

## 7. Evaluation Metrics

Metrics are:

- Sensitivity: Spearman correlation between alpha and distribution score.
- Monotonicity: fraction of adjacent alpha steps where the score decreases.
- Paired detectability: Spearman correlation between alpha and paired score.
- Mean-shift detectability: Spearman correlation between alpha and mean-shift
  score.
- Robustness: coefficient of variation across seeds and Kendall tau ranking
  stability when multiple seeds are present.
- Efficiency: workflow runtime divided by the fastest runtime for the same
  dataset, perturbation, alpha, and seed.
- Interpretability: fixed score, with statistics MMD and Diversity Curves rated
  highest in this version.
- Granularity: local, local/mesoscopic, mesoscopic, global, or multiscale
  detection summary.

## 8. Result Table Schemas

Raw result rows contain:

```text
dataset, dataset_params, perturbation, perturbation_params, alpha, seed,
workflow, distribution_score, mean_shift_score, paired_score,
runtime_seconds, memory_mb, status, error_message
```

Evaluation summary rows contain:

```text
workflow, dataset, perturbation, sensitivity, monotonicity,
paired_detectability, mean_shift_detectability, robustness_cv,
ranking_stability_tau, relative_runtime, interpretability_score,
granularity_label
```

Final matrix rows contain:

```text
workflow, sensitivity_label, monotonicity_label, paired_label,
mean_shift_label, granularity_label, robustness_label, efficiency_label,
interpretability_label
```

## 9. Expected Figures

The figure utilities generate:

- Figure 1: score vs alpha.
- Figure 2: paired distance vs alpha.
- Figure 3: mean-shift vs paired-shift comparison.
- Figure 4: granularity heatmap.
- Figure 5: runtime comparison.

Figures are saved as SVG files.

## 10. How To Run

Run the debug experiment:

```bash
python3 -m experimentation.cli run_debug_experiment --output-root outputs/debug_experimentation
```

Run the full synthetic experiment:

```bash
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/experimentation_native_netlsd --console-log
```

Evaluate results:

```bash
python3 -m experimentation.cli evaluate_results --results outputs/debug_experimentation/results/results.csv
```

Generate figures:

```bash
python3 -m experimentation.cli generate_figures --results outputs/debug_experimentation/results/results.csv
```

Debug results are saved under:

```text
outputs/debug_experimentation/results/
```

Full synthetic results are saved under:

```text
outputs/experimentation_native_netlsd/results/
```

Figures are saved under:

```text
outputs/debug_experimentation/figures/
outputs/experimentation_native_netlsd/figures/
```

Run the interactive dashboard for sanity checks:

```bash
python3 -m pip install -r requirements-dashboard.txt
streamlit run experimentation/dashboard.py
```

## 11. Limitations

Current limitations:

- No real datasets are included yet.
- Diversity Curves use shortest-path spread over deterministic edge-contraction
  scales; external implementations may still differ in coarsening choices.
- WL and NetLSD use standard-library fallback implementations. External
  dependencies may change speed or exact representations in future versions.
- Full synthetic runs can be slow with the fallback NetLSD eigensolver.

## 12. Future Work

Planned extensions:

- Add PROTEINS, ENZYMES, ZINC, or IMDB-BINARY.
- Add a second representative workflow per methodological family.
- Add degree-preserving rewiring.
- Add mode dropping.
- Add attribute noise.
