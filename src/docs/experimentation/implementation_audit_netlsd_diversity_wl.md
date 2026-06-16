# Implementation Audit: NetLSD, Diversity Curves, and WL

Date: 2026-06-16

Status update: this report documents the pre-upgrade audit. The implementation
has since been upgraded; see
`src/docs/experimentation/full_fidelity_implementation_netlsd_diversity_wl.md`
for the current paper-faithful defaults, remaining deviations, tests, and
regenerated debug outputs.

## Executive Summary

This audit checks whether the repository implementations of `NativeNetLSD`,
`DiversityCurveDistance`, and `WLFeatures+MMD` are mathematically faithful to
their source papers and suitable for thesis-grade high-fidelity experiments.

Bottom line: the implementations are coherent lightweight descriptors for the
current fixed-size synthetic perturbation study, but they are not faithful
reproductions of the original papers. They should not be presented as full
NetLSD, full Diversity Curves, or full Weisfeiler-Lehman subtree kernel
implementations without qualification.

The most important limitations are:

- NetLSD omits neutral-graph heat-trace normalization for size invariance and
  uses 16 time scales rather than the paper's 250 log-spaced samples.
- Diversity Curves uses shortest-path spread, but only four default scales and
  a deterministic hash/structure-driven contraction order rather than the
  paper's all-cardinality schedule with random edge contraction repetitions and
  upsampling support.
- WL captures the core 1-WL subtree-count feature idea for unlabeled graphs, but
  it is used as a mean-feature linear-MMD distribution descriptor, not as the
  paper's full graph-kernel matrix method over labeled graphs.
- Result rows log only workflow names, not method hyperparameters such as WL
  iterations, NetLSD time grid, NetLSD normalization, Diversity Curves scales, or
  contraction policy. This is a reproducibility gap for custom runs.

One clear robustness issue was patched: dense vector distances now reject
different-length vectors instead of silently truncating with `zip`. This matters
because variable-size Diversity Curve representations could otherwise be
compared incorrectly.

## Source Material Inspected

Documentation in `src/docs`:

- `src/docs/experimentation/theory.md`
- `src/docs/experimentation/experimental_protocol.md`
- `src/docs/experimentation/final_experimentation_plan.md`
- `src/docs/experimentation/implementation_audit.md`
- `src/docs/experimentation/implementation_log.md`
- `src/docs/experimentation/results_schema.md`

No PDFs are present under `src/docs`. To compare against original papers while
staying within the local repository, these local PDFs were also inspected:

- `papers/NetLSD.pdf`
- `papers/DiversityCurves.pdf`
- `papers/shervashidze11a.pdf`

## Implementation Files Reviewed

Core implementations:

- `src/experimentation/workflows.py`
- `src/experimentation/graph.py`
- `src/experimentation/runner.py`
- `src/experimentation/config.py`
- `src/experimentation/datasets.py`
- `src/experimentation/perturbations.py`

Callers, result processing, and labels:

- `src/experimentation/evaluation.py`
- `src/experimentation/figures.py`
- `src/experimentation/dashboard.py`
- `src/experimentation/cli.py`

Tests reviewed and extended:

- `src/tests/test_workflows.py`
- `src/tests/test_runner.py`
- `src/tests/test_evaluation.py`
- `src/tests/test_dashboard.py`
- `src/tests/test_experimentation_baseline.py`

## Finding Summary

| Method | Finding | Severity | Code changed |
| --- | --- | --- | --- |
| NetLSD | No neutral-graph heat-trace normalization; not size-invariant as published | HIGH, CRITICAL for variable-size graph comparisons | No |
| NetLSD | Default uses 16 log-spaced time scales, paper uses 250 over `[1e-2, 1e2]` | HIGH | No |
| NetLSD | Full eigendecomposition is used; scalable approximation is absent | MEDIUM for current 50-node graphs, HIGH for large graphs | No |
| NetLSD | Heat signature only; wave signature variants absent | MEDIUM | No |
| Diversity Curves | Default uses 4 evaluation scales, not all integer cardinalities | HIGH | No |
| Diversity Curves | No upsampling to common dataset cardinality for variable-size graphs | HIGH, CRITICAL for variable-size graph comparisons | Partial guard only |
| Diversity Curves | Deterministic contraction differs from random edge scores/repetitions | HIGH | No |
| Diversity Curves | Only shortest-path metric implemented | MEDIUM | No |
| WL | Core 1-WL subtree counts are present for unlabeled graphs | LOW concern | No |
| WL | No support for original discrete node labels or edge labels | HIGH if labeled graph benchmarks are used | No |
| WL | Distribution comparison is linear MMD over mean features, not the paper's kernel matrix workflow | MEDIUM | No |
| WL | Raw feature counts are size-sensitive | MEDIUM | No |
| All dense-vector methods | Length mismatch could silently truncate vector distances | HIGH | Yes |
| All workflows | Workflow hyperparameters are not written to result CSVs | HIGH for reproducibility | No |

## NetLSD Audit

### Expected Algorithm

According to `src/docs/experimentation/theory.md`,
`experimental_protocol.md`, and the local NetLSD paper:

- Use an undirected graph and the normalized Laplacian.
- Compute a heat trace signature from eigenvalues:
  `h_t = sum_j exp(-t * lambda_j)`.
- Compare graph signatures with an L2-type distance over sampled time scales.
- Use a logarithmic time grid. The paper reports 250 values on `[1e-2, 1e2]`.
- For size-invariance, normalize heat or wave traces against neutral graphs
  such as the empty or complete graph.
- For large graphs, use spectral approximation rather than full dense
  eigendecomposition.

### Actual Behavior

Implemented in `src/experimentation/workflows.py`:

- `normalized_laplacian_eigenvalues()` builds a normalized Laplacian with
  diagonal 1 for non-isolated nodes and 0 for isolated nodes.
- `netlsd_signature()` computes raw heat traces by summing
  `exp(-t * lambda)` over all eigenvalues.
- `NetLSDWorkflow` compares two graph distributions using L2 distance between
  mean raw signatures.
- `paired_score` is the average within-pair L2 distance between raw signatures.
- Default time grid has 16 log-spaced values from `1e-2` to `1e2`.
- Optional PyTorch acceleration computes a full dense eigendecomposition on
  CPU/GPU; no truncated or interpolated approximation is implemented.

### Mismatches

1. No neutral-graph normalization.
   Severity: HIGH, CRITICAL if graphs have different sizes.

   The current raw heat trace contains graph size information. This is less
   confounding in the current fixed-size synthetic experiment, where every graph
   has 50 nodes, but it violates the size-invariance goal of NetLSD and would
   materially bias variable-size comparisons.

   Recommended fix: add explicit normalization modes such as `none`,
   `empty_graph`, and `complete_graph`, record the mode in result metadata, and
   rerun experiments when variable-size datasets are introduced.

2. Default time grid is much smaller than the paper default.
   Severity: HIGH.

   The paper reports 250 log-spaced time samples on `[1e-2, 1e2]`; the code uses
   16. This can miss scale-dependent differences and changes the representation.

   Recommended fix: expose a named paper-default grid and use it for thesis
   high-fidelity runs, or document the 16-point grid as a computational
   approximation and run a sensitivity analysis.

3. No wave signature variants.
   Severity: MEDIUM.

   The paper evaluates heat and wave signatures. The repository implements only
   heat traces.

   Recommended fix: add wave-trace support only if the thesis compares against
   those paper variants.

4. No scalable approximation.
   Severity: MEDIUM for current 50-node graphs; HIGH for large graphs.

   Full eigendecomposition is mathematically exact for small graphs, so this is
   acceptable for the current 50-node synthetic setup. It is not the large-graph
   NetLSD algorithm.

   Recommended fix: either keep full eigendecomposition and state the graph-size
   limitation, or add a documented approximation strategy before large-graph
   experiments.

### Code Changes

No NetLSD algorithmic behavior was changed. Tests were added for known
normalized-Laplian eigenvalues, known heat-trace values, isolated nodes, and
determinism.

## Diversity Curves Audit

### Expected Algorithm

According to `src/docs/experimentation/theory.md`,
`final_experimentation_plan.md`, and the local Diversity Curves paper:

- Treat each graph as a finite metric space.
- Use shortest-path distance as the default graph metric.
- Compute spread:
  `Div(G) = sum_x 1 / sum_y exp(-d(x, y))`.
- Compute a curve over graph cardinalities after edge contraction coarsening:
  `DivCurve(G)_i = Div(G_i)`.
- Default cardinality schedule is all integers from 1 to the maximum graph size
  in the dataset, unless a cheaper schedule is explicitly chosen.
- Use random edge contraction repetitions and average the resulting curves.
- Upsample smaller graphs to common cardinalities when comparing variable-size
  datasets.
- For disconnected graphs, interpolate below the number of connected components
  and set `DivCurve(G)_1 = 1`.

### Actual Behavior

Implemented in `src/experimentation/workflows.py`:

- `shortest_path_spread()` uses BFS shortest-path distances and ignores
  infinite distances in the exponential denominator, equivalent to
  `exp(-inf) = 0`.
- `diversity_curve()` computes spread over coarsened graphs and averages over
  `repetitions=3`.
- Default `max_scales=4`, so a 50-node graph is evaluated at only four
  cardinalities.
- `_selected_contraction_edge()` chooses edges by structural signature and a
  deterministic SHA-256 priority, not by sampled random edge scores.
- No node upsampling is implemented.
- Distribution and paired comparisons use L2 distances between curve vectors or
  their means.

### Mismatches

1. The default scale schedule is too sparse for paper-level fidelity.
   Severity: HIGH.

   Four scales are a coarse summary, not the default Diversity Curves
   representation over all cardinalities.

   Recommended fix: for thesis-grade Diversity Curves, compute curves over all
   cardinalities `1..nmax` or explicitly justify a reduced schedule with a
   sensitivity analysis.

2. No upsampling to common cardinalities.
   Severity: HIGH, CRITICAL for variable-size graph comparisons.

   The current synthetic configs use fixed-size graphs, so this does not affect
   existing rows. For variable-size datasets, the current workflow cannot
   reproduce the paper's size-aware comparison protocol.

   Recommended fix: add dataset-level curve construction with a common
   cardinality interval and node upsampling for smaller graphs, or restrict the
   thesis claim to fixed-size graph distributions.

3. Deterministic contraction is not the paper's random edge scoring.
   Severity: HIGH.

   The code favors structural signatures before hash priority. That makes the
   method reproducible, but it is not the same random contraction process used
   in the paper's default settings. It may systematically bias which local
   structures survive coarsening.

   Recommended fix: add a seeded random contraction mode and record the seed and
   contraction policy. Keep deterministic mode only as a documented
   reproducibility approximation.

4. Only shortest-path distance is implemented.
   Severity: MEDIUM.

   Shortest path is the paper's default and is defensible, but diffusion,
   resistance, heat-kernel, and feature-space distances are absent.

   Recommended fix: no change needed unless the thesis claims to reproduce
   paper ablations.

### Code Changes

No Diversity Curves algorithmic behavior was changed. A cross-method vector
length guard was added so variable-length dense signatures fail loudly instead
of silently truncating distances. Tests were added for spread values, infinity
handling on disconnected graphs, interpolation behavior, and determinism.

## Weisfeiler-Lehman / WL Audit

### Expected Algorithm

According to `src/docs/experimentation/theory.md` and the local
Shervashidze et al. paper:

- Use 1-dimensional WL refinement.
- Initialize node labels. For unlabeled graphs, degree labels are allowed.
- At each iteration, concatenate each node's current label with the sorted
  multiset of neighbor labels.
- Compress equal strings to equal labels using a shared mapping.
- Build feature vectors by counting labels from the original graph and all WL
  iterations.
- The WL subtree kernel is the inner product between those feature-count
  vectors.

### Actual Behavior

Implemented in `src/experimentation/workflows.py`:

- `wl_features()` initializes labels as node degrees.
- Each iteration forms string signatures from current labels and sorted neighbor
  labels.
- Features count initial and refined labels.
- Labels are not integer-compressed, but deterministic strings make equality
  equivalent for the current small graphs.
- `WLSubtreeMMDWorkflow` compares graph distributions by squared L2 distance
  between mean sparse WL feature-count vectors, equivalent to linear-kernel MMD
  over explicit features.

### Mismatches

1. No support for input node labels or edge labels.
   Severity: HIGH for labeled graph benchmarks; LOW for current unlabeled
   synthetic graphs.

   The implementation is a degree-initialized unlabeled WL variant. This is
   defensible for the current synthetic graphs, but not a complete
   reproduction of the labeled WL graph-kernel setting.

   Recommended fix: add optional node-label handling and document whether the
   thesis experiments are unlabeled-only.

2. No graph-kernel matrix workflow.
   Severity: MEDIUM.

   The paper defines graph kernels and classification usage. The repository
   uses WL features inside a distribution-comparison pipeline via linear MMD.
   This is mathematically coherent, but it is not the same experimental method.

   Recommended fix: keep `WLFeatures+MMD` naming and avoid claiming a full WL
   graph-kernel reproduction. Add a kernel-matrix path only if paper-level WL
   graph-kernel benchmarks are needed.

3. Raw feature counts are size-sensitive.
   Severity: MEDIUM.

   For fixed-size 50-node synthetic graphs, raw counts are comparable. For
   variable-size graphs, graph size can dominate.

   Recommended fix: add a normalization option for WL histograms or keep
   experiments fixed-size.

4. String labels are not compressed integers.
   Severity: LOW to MEDIUM.

   Equality behavior is correct for deterministic strings, but the
   implementation is less efficient and not a direct Algorithm 2 implementation.

   Recommended fix: not necessary for current graph sizes; use shared integer
   compression if scaling or reference matching becomes important.

### Code Changes

No WL algorithmic behavior was changed. Tests were added for manually verified
WL feature counts on a 3-node path and existing isomorphism invariance checks
were retained.

## Distribution-Level Reproducibility

The runner preserves paired graph distributions and computes:

- `distribution_score`
- `mean_shift_score`
- `paired_score`
- runtime
- memory
- status and error message

This is suitable for the current perturbation study structure. The main
reproducibility issue is that result rows do not log method hyperparameters.
For high-fidelity thesis runs, rows should include a `workflow_params` JSON
field with at least:

- WL iterations and label policy.
- NetLSD time grid length, time range, normalization mode, heat/wave mode, and
  eigensolver mode.
- Diversity Curves scale schedule, repetitions, graph metric, contraction
  policy, and upsampling policy.

## Code Changes Made

Changed `src/experimentation/workflows.py`:

- `squared_l2()` now raises `ValueError` for unequal vector lengths.
- `dense_mean()` now raises `ValueError` when dense vectors have inconsistent
  lengths.

Rationale: silently ignoring coordinates changes the mathematical meaning of
signature distances. This is especially dangerous for future variable-size
Diversity Curve experiments.

## Tests Added

Extended `src/tests/test_workflows.py` with focused validation tests:

- WL manual feature counts on a 3-node path.
- NetLSD known normalized-Laplacian eigenvalues for an edge, a path, and
  isolated nodes.
- NetLSD heat trace against a manual eigenvalue sum.
- NetLSD determinism and finite values with isolated nodes.
- Diversity Curves manual shortest-path spread values.
- Disconnected shortest-path distances use infinity for unreachable pairs.
- Diversity Curve determinism across repeated calls.
- Dense vector length mismatches raise errors.

## Remaining Uncertainties

- No external reference implementation comparisons were run. The audit avoided
  introducing dependencies such as GraKeL, netlsd, NetworkX, SciPy, or the
  authors' Diversity Curves packages.
- Exact NetLSD normalization policy should be chosen deliberately before
  changing thesis experiment defaults. The paper evaluates multiple normalized
  and unnormalized variants.
- Diversity Curves high-fidelity reproduction requires dataset-level scale
  management and upsampling, which is larger than a safe local patch.
- Existing generated CSV/SVG outputs were not regenerated. Any algorithmic
  changes to defaults would require a full rerun.

## Thesis Suitability Judgment

Current code is suitable for a fixed-size, synthetic, controlled perturbation
study if the thesis describes the methods as lightweight self-contained
approximations:

> We compare graph distributions using WL-subtree feature MMD, raw NetLSD
> heat-trace mean-signature distance, and shortest-path Diversity Curve
> mean-curve distance under controlled synthetic perturbations.

Current code is not suitable for an unqualified claim that the thesis faithfully
reproduces the original NetLSD, Diversity Curves, or WL graph-kernel papers.
Before making high-fidelity paper-reproduction claims, the recommended fixes
above should be implemented and the experiments rerun.
