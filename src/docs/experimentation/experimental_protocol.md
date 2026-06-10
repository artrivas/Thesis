# Experimental Protocol

The high-level pipeline is:

```text
Datasets
  -> Perturbations
  -> Paired graph distributions
  -> Workflows
  -> Evaluation metrics
  -> Tables/Figures
```

## 1. Datasets

Generate synthetic graph distributions only:

- Erdős-Rényi.
- Stochastic Block Model.
- Barabási-Albert.

The number of graphs per distribution is configurable and defaults to `100`.
A smaller debug configuration is available for local smoke runs.

## 2. Perturbations

Apply configurable perturbations to each original graph:

- Edge addition/deletion.
- Triangle injection/removal.
- Community weakening.
- Hub modification.

Perturbation strength is controlled by `alpha`, defaulting to:

```text
0.0, 0.1, 0.2, ..., 1.0
```

Operational alpha definitions:

- Edge addition/deletion: `floor(alpha * |E|)` edge operations are attempted.
  The current default mixes deletions and additions, removing half of the budget
  from existing edges and adding the remaining budget to original non-edges.
- Triangle injection/removal: `floor(alpha * max(1, |E|))` motif operations are
  attempted. The current default first closes open wedges, then removes edges
  that participate in triangles when possible.
- Community weakening: `floor(alpha * number_of_intra_community_edges)`
  rewires are attempted. Each rewire removes one intra-community edge and adds
  one inter-community edge, preserving the edge count when enough candidate
  inter-community non-edges exist.
- Hub modification: `floor(alpha * |E|)` hub-incident edge changes are
  attempted. The current default targets the top 10 percent of nodes by degree,
  removes incident hub edges, and adds replacement hub-incident edges where
  possible.

If `alpha = 0`, the perturbed graph is a separate object that is structurally
equivalent to the original graph.

## 3. Paired Graph Distributions

For each original graph `G_i`, generate a perturbed graph `G_i^alpha`. The
paired relation must be preserved for downstream paired analysis.

For each dataset, perturbation, alpha, and seed, the resulting comparison is:

```text
Original distribution:  {G_1, ..., G_n}
Perturbed distribution: {G_1^alpha, ..., G_n^alpha}
Pairs:                  {(G_i, G_i^alpha)} for i = 1..n
```

## 4. Workflows

Run one representative representation plus discrepancy pipeline per
methodological family:

- `GraphStats+MMD`: structural graph statistics followed by RBF MMD.
- `WLFeatures+MMD`: Weisfeiler-Lehman subtree feature counts followed by
  linear MMD.
- `NativeNetLSD`: NetLSD heat-trace signatures compared by L2 distance between
  mean signatures.
- `DiversityCurveDistance`: shortest-path Diversity Curves followed by L2
  distance between mean curve representations.

Each workflow exposes a common interface:

- `compute_representations(graphs)`.
- `distribution_score(original_graphs, perturbed_graphs)`.
- `mean_shift_score(original_graphs, perturbed_graphs)`.
- `paired_score(original_graphs, perturbed_graphs)`.
- `run(original_graphs, perturbed_graphs)`.

The `run` method records runtime, returns scores in the common result schema,
and reports failures through `status` and `error_message` instead of crashing an
orchestration loop.

## 5. Evaluation Metrics

Each workflow should report:

- `distribution_score`: distribution-level separation.
- `mean_shift_score`: shift in average representation or summary.
- `paired_score`: within-pair change between `G_i` and `G_i^alpha`.
- Runtime and memory measurements.
- Status and error details.

## 6. Tables and Figures

The primary output is a tabular result file following
`docs/experimentation/results_schema.md`. Figures should summarize sensitivity
over `alpha` by dataset, perturbation, workflow, and seed.

## 7. Runner

The runner executes the full synthetic grid:

```text
dataset x perturbation x alpha x seed x workflow
```

For each row, it stores dataset parameters, perturbation parameters,
distribution score, mean-shift score, paired score, runtime, memory if
available, status, and error message. Perturbations that are not applicable,
such as community weakening without community labels, are written as skipped
rows instead of crashing the run.

The debug run writes:

```text
outputs/debug_experimentation/results/results.csv
```

The full synthetic run writes:

```text
outputs/experimentation_native_netlsd/results/results.csv
```

## 8. Evaluation and Figures

Evaluation reads a result CSV and writes:

```text
evaluation_summary.csv
final_matrix.csv
```

Figure generation reads a result CSV and writes SVG files for:

- Score vs alpha.
- Paired distance vs alpha.
- Mean-shift vs paired-shift comparison.
- Granularity heatmap.
- Runtime comparison.

For interactive sanity checks, use the Streamlit dashboard instead of the static
SVGs when labels or dense panels make the figures hard to read.

Supported commands:

```text
python3 -m experimentation.cli run_debug_experiment --output-root outputs/debug_experimentation
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/experimentation_native_netlsd
python3 -m experimentation.cli evaluate_results --results outputs/debug_experimentation/results/results.csv
python3 -m experimentation.cli generate_figures --results outputs/debug_experimentation/results/results.csv
python3 -m pip install -r requirements-dashboard.txt
streamlit run experimentation/dashboard.py
```

## 9. Remote GPU and Resume Behavior

Experiment runs write each completed workflow row to `results.csv` immediately,
then update `logs/checkpoint.json` with completed and remaining row counts.
Rerunning the same command resumes from the existing result file by default and
skips rows that are already present.

The runner also writes a durable progress log to `logs/run.log`. Use this on a
remote server to inspect what the job has completed without waiting for the
full experiment to finish.

GPU acceleration is optional. The NetLSD spectral eigenvalue path uses PyTorch
with CUDA when available under `--device auto`, or fails loudly if CUDA is
explicitly requested but unavailable.

Recommended remote command:

```text
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/experimentation_native_netlsd --device cuda --console-log
```

To intentionally discard an existing checkpoint/result file and start a fresh
CSV, pass:

```text
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/experimentation_native_netlsd --device cuda --no-resume --console-log
```

If a bug or environment issue caused failed rows, pull the fix and recompute
only those failed rows with:

```text
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/experimentation_native_netlsd --device cuda --rerun-failed
```

Use `--console-log` to print the same progress messages written to
`logs/run.log`. Each completed workflow row reports dataset, perturbation, alpha,
seed, workflow, status, and total completed rows.

Use `--workflow` to run one or more workflow families in an isolated output root.
This is the recommended way to parallelize full runs across terminals without
multiple processes writing the same CSV:

```text
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/attempt2_graphstats --workflow structural_statistics_mmd --no-resume --console-log
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/attempt2_wl --workflow wl_subtree_kernel_mmd --no-resume --console-log
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/attempt2_netlsd --workflow native_netlsd --no-resume --console-log --device cuda
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/attempt2_diversity --workflow diversity_curves_shortest_path --no-resume --console-log
```
