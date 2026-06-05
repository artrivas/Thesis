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

Run one representative workflow per methodological family:

- MMD over structural graph statistics.
- WL subtree kernel with MMD.
- NetLSD spectral signatures.
- Diversity Curves with L2 distance.

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
outputs/experimentation/results/results.csv
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

Supported commands:

```text
python3 -m experimentation.cli run_debug_experiment --output-root outputs/debug_experimentation
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/experimentation
python3 -m experimentation.cli evaluate_results --results outputs/debug_experimentation/results/results.csv
python3 -m experimentation.cli generate_figures --results outputs/debug_experimentation/results/results.csv
```
