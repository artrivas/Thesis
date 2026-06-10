# Theoretical Motivation

This experimentation module compares distributions of graphs, not only
individual graph pairs. The scientific question is whether representative graph
comparison workflows can detect controlled changes in synthetic graph
generating processes as perturbation strength increases.

The experiment is paired. For each original graph `G_i`, the pipeline generates
a perturbed graph `G_i^alpha` using the same base graph and a configurable
perturbation strength `alpha`. This preserves the relation between each source
graph and its perturbed counterpart while still allowing distribution-level
comparisons between the original sample and the perturbed sample.

Evaluation should expose four complementary behaviors:

- Distribution-level behavior: whether the workflow separates the original
  graph distribution from the perturbed graph distribution.
- Mean-shift behavior: whether average workflow representations shift
  monotonically or detectably as `alpha` increases.
- Paired behavior: whether each `(G_i, G_i^alpha)` relation shows consistent
  within-pair change.
- Granular behavior: whether sensitivity differs across dataset families,
  perturbation types, seeds, and perturbation strengths.

For feasibility, the initial implementation uses one representation plus
discrepancy pipeline per methodological family:

- `GraphStats+MMD`: structural graph statistics followed by RBF MMD.
- `WLFeatures+MMD`: Weisfeiler-Lehman subtree feature counts followed by
  linear MMD.
- `NativeNetLSD`: NetLSD heat-trace signatures compared by L2 distance between
  mean signatures.
- `DiversityCurveDistance`: shortest-path Diversity Curves followed by L2
  distance between mean curve representations.

Only synthetic graph families are in scope for this phase: Erdős-Rényi,
Stochastic Block Model, and Barabási-Albert. Real datasets are intentionally
excluded until the synthetic protocol and result schema are stable.

## Synthetic Dataset Rationale

The three synthetic graph families are selected because they isolate different
structural regimes:

- Erdős-Rényi controls random density and noise through an independent edge
  probability. It is useful as a baseline where structure is mostly explained
  by graph size and density.
- Stochastic Block Model controls community and mesoscopic structure through
  within-block and between-block edge probabilities. It gives a direct setting
  for testing whether workflows detect weakened communities.
- Barabási-Albert controls hubs and heavy-tail degree behavior through
  preferential attachment. It gives a direct setting for testing sensitivity to
  hub and degree-distribution perturbations.

## Perturbation Rationale

Perturbations are grouped by the structural scale they primarily affect:

- Local perturbations: edge addition/deletion changes the adjacency relation
  directly while preserving the graph family and paired source graph.
- Motif and clustering perturbations: triangle injection/removal changes local
  closure and clustering by closing open wedges or deleting triangle edges.
- Mesoscopic perturbations: community weakening rewires intra-community edges
  into inter-community edges, primarily for SBM graphs with community labels.
- Hub and global perturbations: hub modification targets high-degree nodes,
  primarily for BA graphs, and changes the role of central attachment points.

Every perturbation returns a new graph object. The original graph is not mutated
in place, and metadata records the number of edges added, edges removed,
rewires, and triangles affected when available.

## Workflow Rationale

`GraphStats+MMD` represents each graph with a compact
feature vector containing node count, edge count, density, average degree,
degree variance, average clustering, triangle count, transitivity, and connected
component count. An RBF-kernel MMD score then compares the original and
perturbed graph distributions.

`WLFeatures+MMD` uses iterative neighborhood relabeling to create
graph-level counts of rooted subtree features. The current implementation uses
degree labels at initialization and a deterministic manual relabeling fallback.
Distribution separation is measured by the squared distance between mean WL
feature count vectors, equivalent to a linear-kernel MMD.

`NativeNetLSD` represents each graph with heat-trace signatures over log-spaced
time scales. The current fallback computes eigenvalues of the normalized
Laplacian with a small Jacobi eigensolver and evaluates the heat trace from
those eigenvalues. Distribution separation is the L2 distance between the mean
NetLSD signatures of the two graph samples, and paired behavior is the average
within-pair signature L2 distance. This is suitable for small synthetic smoke
runs; larger experiments should eventually use NumPy/SciPy or a dedicated
NetLSD package.

`DiversityCurveDistance` computes graph structural diversity as spread over
shortest-path distances. The workflow evaluates spread across deterministic
edge-contraction scales and compares the resulting curve representations with
L2 distance between mean curves. This matches the default graph metric described
in the Diversity Curves paper while keeping the local experiment runner
reproducible.

## Evaluation Metrics

Sensitivity measures whether a workflow's distribution-level score increases as
the perturbation strength increases. It is computed as the Spearman correlation
between `alpha` and `distribution_score`.

Monotonicity measures whether scores avoid decreases as `alpha` increases. It is
computed as the fraction of adjacent alpha steps where the mean score decreases.
Lower values are better.

Paired detectability measures whether within-pair changes increase with
perturbation strength. It is computed as the Spearman correlation between
`alpha` and `paired_score`.

Mean-shift detectability measures whether the average representation of the
perturbed distribution moves away from the original distribution as `alpha`
increases. It is computed as the Spearman correlation between `alpha` and
`mean_shift_score`.

Robustness measures stability across seeds. The primary statistic is the
coefficient of variation, `CV = sigma / mean`, computed over seed-level mean
distribution scores. Ranking stability is also estimated with Kendall tau by
comparing workflow rankings across seeds for the same dataset and perturbation.

Efficiency is measured as relative runtime:

```text
workflow_runtime / fastest_runtime_for_same_dataset_perturbation_alpha_seed
```

Interpretability is assigned as a fixed qualitative score for this phase:

- `GraphStats+MMD`: `3`.
- `WLFeatures+MMD`: `2`.
- `NativeNetLSD`: `2`.
- `DiversityCurveDistance`: `3`.

Granularity maps perturbations to their main structural scale:

- Edge addition/deletion: local.
- Triangle injection/removal: local/mesoscopic.
- Community weakening: mesoscopic.
- Hub modification: global.

The final matrix converts metric values into labels. Correlation-based metrics
use Very high for values at least `0.90`, High for `0.75` to `0.89`, Medium for
`0.50` to `0.74`, and Low below `0.50`. Monotonicity uses the violation
fraction, where Very high is at most `0.05`, High at most `0.15`, Medium at most
`0.30`, and Low above `0.30`. Robustness uses CV, where Very high is at most
`0.10`, High at most `0.20`, Medium at most `0.35`, and Low above `0.35`.
