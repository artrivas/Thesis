# Implementation Audit Against Method Concepts

Date: 2026-06-10

Status update: this is a historical pre-upgrade audit. For the current
paper-faithful thesis defaults and remaining limitations, see
`src/docs/experimentation/full_fidelity_implementation_netlsd_diversity_wl.md`.

This report audits the local experiment implementation against the main concepts
behind the methods it names. It focuses on whether the code implements the
intended concepts closely enough for the current synthetic perturbation study,
and what remains approximate or unsupported.

## Executive Summary

The implementation is adequate as a controlled synthetic sanity-check pipeline,
but it is not yet a faithful reproduction of all referenced methods. The safest
interpretation is:

- The pipeline correctly runs paired graph perturbation experiments and records
  distribution, mean-shift, paired, runtime, memory, status, and error fields.
- The MMD machinery matches the biased empirical MMD form, but lacks bandwidth
  selection, statistical testing, p-values, and unbiased estimators.
- The WL workflow captures the core 1-WL subtree-count idea, but is a compact
  hand-rolled unlabeled-graph variant rather than a full WL graph-kernel
  implementation.
- The NetLSD workflow captures normalized-Laplacian heat traces, but omits key
  NetLSD details such as heat-trace normalization for size invariance, the paper's
  richer time grid, and scalable spectral approximation.
- The Diversity Curves workflow now uses shortest-path spread inside each graph,
  which addresses the main "shortest path instead of L2" correction. It remains a
  simplified local version of the paper because the coarsening, scale schedule,
  and downstream comparison are simpler.
- The repository should present the workflows honestly: MMD is the discrepancy for
  `GraphStats+MMD` and `WLFeatures+MMD`, while `NativeNetLSD` and
  `DiversityCurveDistance` use L2 distances over valid signatures or curves.
- The evaluation metrics are experiment-specific summary metrics. They are useful
  for this thesis experiment, but they are not themselves claims from the
  original method papers.

## Sources Consulted

- Gretton et al., "A Kernel Two-Sample Test", JMLR 2012:
  https://www.jmlr.org/papers/v13/gretton12a.html
- Shervashidze et al., "Weisfeiler-Lehman Graph Kernels", JMLR 2011:
  https://www.jmlr.org/papers/v12/shervashidze11a.html
- Tsitsulin et al., "NetLSD: Hearing the Shape of a Graph", KDD 2018 / arXiv:
  https://arxiv.org/abs/1805.10712
- Limbeck et al., "Diversity Curves for Graph Representation Learning", arXiv
  2026: https://arxiv.org/abs/2605.06466

## Current Implementation Surface

Main code paths:

- Workflows: `experimentation/workflows.py`
- Experiment orchestration: `experimentation/runner.py`
- Evaluation summary: `experimentation/evaluation.py`
- Perturbations: `experimentation/perturbations.py`
- Dashboard: `experimentation/dashboard.py`

Implemented workflows:

| Internal workflow ID | Recommended presentation name | Representation | Distribution score |
|---|---|---|---|
| `structural_statistics_mmd` | `GraphStats+MMD` | Handcrafted graph statistics | RBF MMD |
| `wl_subtree_kernel_mmd` | `WLFeatures+MMD` | 1-WL subtree feature counts | Linear MMD via squared distance between mean sparse vectors |
| `native_netlsd` | `NativeNetLSD` | Normalized-Laplacian heat traces | L2 distance between mean signatures |
| `diversity_curves_shortest_path` | `DiversityCurveDistance` | Shortest-path spread over coarsened graph scales | L2 distance between mean curve vectors |

Shared per-workflow outputs:

- `distribution_score`
- `mean_shift_score`
- `paired_score`
- `runtime_seconds`
- `memory_mb`
- `status`
- `error_message`

## Naming Audit: Methods vs Pipelines

The repository previously risked presenting all workflows as independent graph
distances. The corrected framing is one classical workflow per methodological
family, with the discrepancy named when it is part of the workflow.

The more accurate framing is:

| Current/internal name | What it really is | Recommended public name |
|---|---|---|
| `structural_statistics_mmd` | Graph statistics representation + RBF MMD discrepancy | `GraphStats+MMD` |
| `wl_subtree_kernel_mmd` | WL feature-count representation + linear MMD discrepancy | `WLFeatures+MMD` |
| `native_netlsd` | NetLSD heat-trace signatures + L2 distance between mean signatures | `NativeNetLSD` |
| `diversity_curves_shortest_path` | Diversity curve representation + L2 distance between mean curves | `DiversityCurveDistance` |

This distinction matters because "WL subtree kernel" and "Diversity Curves" name
representation families or graph-level descriptors, while this experiment
compares graph distributions. The distribution comparison layer is therefore part
of the method actually being evaluated. The corrected NetLSD workflow uses a new
`native_netlsd` ID so old NetLSD+MMD artifacts cannot be silently reused.

## Method Fidelity Assessment

### MMD

Paper concept:

Gretton et al. define MMD as the largest difference in expectations over
functions in the unit ball of an RKHS. The JMLR abstract also emphasizes that
MMD can be computed in quadratic time and can be used for two-sample testing.

Implemented:

- `rbf_mmd()` computes the biased quadratic empirical MMD estimate:
  `E[k(X,X)] + E[k(Y,Y)] - 2E[k(X,Y)]`.
- `sparse_linear_mmd()` computes squared distance between mean sparse feature
  vectors, equivalent to linear-kernel MMD on explicit sparse features.

Covered well:

- The core empirical MMD distance idea is present.
- RBF and linear-kernel variants are sensible for vector and sparse WL features.

Not covered:

- No hypothesis test, permutation test, asymptotic threshold, or p-value.
- No unbiased MMD estimator.
- No bandwidth selection or median heuristic.
- No feature standardization before RBF MMD, which means raw feature scales can
  dominate.

Fidelity: **Medium-high for a descriptive distance; low for a full two-sample
test implementation.**

### Structural Statistics MMD

Paper concept:

This is not a single canonical paper method in the codebase. It is a compact
baseline that uses graph-level statistics and compares their distributions with
MMD.

Implemented:

Each graph is represented by:

- node count
- edge count
- density
- average degree
- degree variance
- average clustering
- triangle count
- transitivity
- connected component count

Covered well:

- Simple, interpretable structural baseline.
- Captures several local and global graph summaries.

Not covered:

- No feature normalization, so edge count, triangle count, and degree variance
  can dominate RBF distances.
- Fixed RBF bandwidth `10.0` is not justified or tuned.
- Not a faithful reproduction of a named graph-kernel/statistical method.

Fidelity: **High as a custom baseline; not applicable as a paper reproduction.**

### Weisfeiler-Lehman Subtree Kernel

Paper concept:

Shervashidze et al. propose efficient graph kernels based on the Weisfeiler-
Lehman test. The key idea is rapid feature extraction through iterative
neighborhood relabeling, producing subtree-like features from the sequence of
WL-refined graphs.

Implemented:

- Initial labels are node degrees.
- At each iteration, a node signature is formed from its current label and sorted
  neighbor labels.
- Graph-level sparse feature counts are accumulated over iterations.
- Distribution comparison uses linear MMD over those feature-count vectors.

Covered well:

- Captures the central 1-WL neighborhood-refinement mechanism.
- Accumulates feature histograms across iterations.
- Uses sparse vectors and linear-kernel MMD, a natural way to compare explicit
  WL histograms across graph distributions.

Not covered:

- No canonical integer compression dictionary shared across a dataset; string
  signatures are deterministic, but this is a simple fallback rather than the
  standard efficient implementation.
- Uses degree labels for unlabeled graphs. That is defensible, but it is a
  modeling choice and not the only unlabeled-WL convention.
- No normalized kernel values.
- No graph-kernel matrix or SVM/classification layer.
- No validation against a reference WL implementation.

Fidelity: **Medium. The core WL subtree idea is present, but the implementation
is a compact feature extractor, not a full WL graph-kernel reproduction.**

### NetLSD

Paper concept:

NetLSD is a permutation- and size-invariant, scale-adaptive graph representation
based on Laplacian spectral signatures. The paper uses heat or wave trace
signatures from the normalized Laplacian spectrum, discusses normalization
against neutral graphs for size invariance, and uses many logarithmically spaced
time scales.

Implemented:

- Computes normalized Laplacian eigenvalues.
- Builds heat trace signatures as `sum(exp(-t * lambda_i))`.
- Uses 16 log-spaced time scales from `1e-2` to `1e2`.
- Uses full eigendecomposition for small graphs, with optional PyTorch
  acceleration.
- Compares graph distributions by L2 distance between mean NetLSD signatures.
- Compares paired graphs by average within-pair signature L2 distance.

Covered well:

- Uses the normalized Laplacian.
- Uses heat trace signatures over logarithmic time scales.
- Full eigendecomposition is acceptable for the current 50-node synthetic graphs.

Not covered:

- No NetLSD heat-trace normalization against empty/complete neutral graphs.
  Therefore the current signature is not fully size-invariant. This matters less
  for the current fixed-size 50-node experiment, but it matters for general graph
  comparison.
- Uses 16 time scales, while the NetLSD paper reports a richer default grid.
- Does not implement wave signatures.
- Does not implement the paper's scalable spectral approximation strategy for
  large graphs.
- If all graphs have the same fixed size, lack of size normalization is less
  confounding; variable-size datasets still need an explicit normalization policy.

Fidelity: **Medium-high for the intended NativeNetLSD classical representative on
small fixed-size synthetic graphs; incomplete for full NetLSD as published.**

### Diversity Curves

Paper concept:

The Diversity Curves paper tracks structural diversity of a graph across
coarsening levels. The paper describes graph spread as an isometry-invariant
measure of metric diversity and uses edge contraction coarsening. It identifies
shortest-path distance as the default graph distance for diversity computations,
with diffusion and resistance distances studied as alternatives.

Implemented:

- Computes all-pairs shortest-path distances in each graph.
- Computes spread as a sum over node-wise inverse heat-kernel-like denominators.
- Computes diversity curves across deterministic edge-contraction scales.
- Averages across deterministic pseudo-random contraction repetitions.
- Names the workflow `diversity_curves_shortest_path`.

Covered well:

- The previous `diversity_curves_l2` naming has been replaced in the fixed run.
- The graph-internal metric is shortest-path distance, not L2.
- The implementation uses spread over coarsened graphs, matching the core
  conceptual structure.

Important distinction:

- Shortest-path distance is used inside the graph when computing spread.
- L2 is still used later to compare two completed curve vectors. That is not the
  same as using L2 as the Diversity Curves graph metric.

Not covered:

- Coarsening is simplified: deterministic hash-priority edge contraction rather
  than the full edge-scoring/randomized framework described in the paper.
- Only 4 scales are used by default, which is coarse compared with richer
  cardinality schedules.
- No upsampling.
- No diffusion, resistance, heat-kernel, or feature-space distance alternatives.
- Disconnected-graph handling is local and pragmatic: infinite distances are
  ignored in the spread denominator, and unreachable lower scales are
  interpolated.
- No validation against the authors' implementation.

Fidelity: **Medium. The major shortest-path correction is correct, but this is
still a simplified Diversity Curves variant.**

## Evaluation Metrics Implemented

The evaluation layer summarizes experiment behavior, not original paper claims.

Implemented metrics:

- `sensitivity`: Spearman correlation between `alpha` and `distribution_score`.
- `monotonicity`: fraction of adjacent alpha means where score decreases.
- `paired_detectability`: Spearman correlation between `alpha` and
  `paired_score`.
- `mean_shift_detectability`: Spearman correlation between `alpha` and
  `mean_shift_score`.
- `robustness_cv`: coefficient of variation across seed-level mean distribution
  scores.
- `ranking_stability_tau`: Kendall tau comparing workflow rankings across seeds.
- `relative_runtime`: workflow runtime divided by fastest workflow runtime for
  the same dataset, perturbation, alpha, and seed.
- `interpretability_score`: manual fixed score.
- `granularity_label`: inherited from perturbation type.

Covered well:

- Useful for checking whether scores increase as perturbation strength
  increases.
- Separates distribution-level, mean-shift, and paired behavior.
- Runtime comparison is normalized within matched experiment settings.

Concerns:

- `ranking_stability_tau` ranks workflows using raw score magnitudes across
  methods with very different scales. This can be misleading unless scores are
  normalized first.
- Interpretability scores are subjective.
- Correlation labels use fixed thresholds; they are convenient summaries, not
  statistical confidence statements.
- Skipped rows are excluded from evaluation summaries, so missing
  dataset/perturbation coverage must be reported separately.

## Sanity Checks Currently Covered

Automated tests:

- `tests/test_workflows.py`
  - Each workflow runs and returns finite numeric scores.
  - `paired_score(original, original) == 0`.
  - Distribution and mean-shift scores run without errors.
  - WL iteration labels are deterministic/canonical for a small case.
  - Diversity Curves uses shortest-path spread at the original scale.
  - Default workflow set includes `diversity_curves_shortest_path`.
- `tests/test_evaluation.py`
  - Spearman sensitivity for monotonic data.
  - Monotonicity violation counting.
  - Label threshold behavior.
  - Evaluation output file generation.
- `tests/test_runner.py`
  - End-to-end debug run.
  - Failed workflows are recorded without crashing the full experiment.
  - Resume behavior skips completed rows.
  - Checkpoint file records completion.
  - Failed rows can be rerun.
  - Legacy `diversity_curves_l2` resume is rejected when shortest-path diversity
    is configured.
- `tests/test_dashboard.py`
  - Fixed results path is preferred when present.
  - Legacy diversity rows are detected.
  - Dashboard labels and normalized chart values behave as expected.

Latest local verification:

```text
.venv/bin/python -m unittest discover -s tests
Ran 52 tests in 0.416s
OK
```

Legacy fixed result-file sanity before NativeNetLSD regeneration:

```text
outputs/experimentation_fixed/results/results.csv
rows: 2640
status: success=2200, skipped=440
workflows: 660 rows each
skipped reason: community_weakening requires community_labels metadata
finite successful distribution_score rows: 2200
finite successful mean_shift_score rows: 2200
finite successful paired_score rows: 2200
```

The 440 skipped rows are expected:

```text
2 datasets without community labels
x 1 community_weakening perturbation
x 11 alpha values
x 5 seeds
x 4 workflows
= 440 skipped rows
```

## Sanity Checks Not Yet Covered

Highest-value missing checks:

- Reference-output comparison against known libraries:
  - WL kernel implementation.
  - NetLSD implementation.
  - Diversity Curves implementation, if available.
- MMD known-value tests on tiny manually constructed vectors.
- Broader RBF bandwidth sensitivity tests.
- Feature standardization tests for structural statistics.
- NetLSD heat-trace normalization tests for graphs with different sizes.
- Distribution-level tests showing `alpha=0` scores are exactly or nearly zero
  for every workflow/dataset/seed.
- Monotonic trend checks over the full fixed CSV, with failures reported by
  workflow/dataset/perturbation.
- Normalized ranking-stability checks to replace or supplement raw-score
  Kendall tau.

## What The Implementation Can Support Today

Reasonable claims:

- The experiment compares four graph-distribution descriptors under controlled
  synthetic perturbations.
- The descriptors are implemented consistently across the same paired datasets.
- Diversity Curves uses shortest-path spread in the graph metric sense.
- NativeNetLSD no longer uses RBF MMD as the main distribution score.
- The fixed run no longer contains legacy `diversity_curves_l2` rows.
- The dashboard and evaluation can reveal relative sensitivity trends within
  each workflow.

Claims to avoid or qualify:

- "This is a faithful NetLSD implementation."
- "This is a full WL subtree graph kernel implementation."
- "This reproduces the Diversity Curves paper."
- "The final matrix is statistically significant."
- "Raw workflow scores are directly comparable across methods."

Better phrasing:

> We implement lightweight, self-contained versions of structural-statistics
> MMD, WL-subtree feature MMD, native NetLSD heat-trace signature distance, and
> shortest-path Diversity Curves. These are used as controlled descriptors for a
> paired synthetic perturbation study. The implementation captures the core
> representation ideas, but several paper-specific details are simplified.

## Recommended Next Fixes

Priority 1:

- Normalize scores before computing `ranking_stability_tau`, or remove that
  metric from the final matrix.
- Add MMD known-value tests.
- Make structural-statistics features standardized before RBF MMD, or document
  that raw features are intentionally used.

Priority 2:

- Add NetLSD heat-trace normalization against neutral graphs.
- Increase NetLSD time samples or make time-grid size configurable.
- Add a reference comparison for NetLSD on small graphs.

Priority 3:

- Make Diversity Curves scale schedule configurable.
- Add a richer coarsening strategy or expose the current hash-priority
  contraction as a simplified deterministic approximation.
- Add optional diffusion/resistance distances only if needed for ablation.

## Bottom Line

The current implementation is coherent for exploratory thesis experimentation,
but it should be described as a self-contained approximation of the method
families. The strongest implemented pieces are the paired experiment runner, MMD
distance computation, WL-style subtree feature extraction, and the corrected
shortest-path Diversity Curves graph metric. The weakest pieces relative to the
papers are NetLSD size-invariance, full Diversity Curves coarsening/scaling, and
cross-workflow ranking based on raw score magnitudes.
