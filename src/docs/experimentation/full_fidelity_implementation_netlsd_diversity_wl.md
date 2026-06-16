# Full-Fidelity Implementation Report: NetLSD, Diversity Curves, and WL

Date: 2026-06-16

## Executive Summary

The repository has been upgraded from lightweight graph descriptors toward
paper-faithful thesis defaults for NetLSD, Diversity Curves, and the
Weisfeiler-Lehman subtree workflow.

The main implementation changes are:

- `NativeNetLSD` now uses 250 log-spaced time scales on `[1e-2, 1e2]`, the
  normalized Laplacian, exact heat traces, and explicit neutral-graph
  normalization.
- `DiversityCurveDistance` now builds dataset-level curves over all integer
  cardinalities by default, supports deterministic seeded random edge
  contractions, and upsamples smaller graphs to the common dataset scale.
- `WLFeatures+MMD` now uses shared canonical 1-WL compression across the graph
  collection being compared, supports discrete node labels, exposes a WL
  subtree kernel matrix helper, and keeps the distribution score as linear MMD
  over WL subtree histograms.
- Experiment rows now log workflow parameters, implementation mode,
  perturbation family, perturbation direction, graph counts, and node/edge size
  ranges.
- Edge and triangle insertion/deletion are now separate perturbation methods:
  `edge_insertion`, `edge_deletion`, `triangle_insertion`, and
  `triangle_deletion`.

The implementation is suitable for thesis-scale synthetic experiments with the
documented limitations below. It is not a bit-for-bit reproduction of any
authors' external reference package.

## Sources Used

Documentation inspected in `src/docs`:

- `src/docs/experimentation/implementation_audit_netlsd_diversity_wl.md`
- `src/docs/experimentation/implementation_audit.md`
- `src/docs/experimentation/theory.md`
- `src/docs/experimentation/experimental_protocol.md`
- `src/docs/experimentation/final_experimentation_plan.md`
- `src/docs/experimentation/implementation_log.md`
- `src/docs/experimentation/results_schema.md`

Local papers also used because no PDFs are stored under `src/docs`:

- `papers/NetLSD.pdf`
- `papers/DiversityCurves.pdf`
- `papers/shervashidze11a.pdf`

## Files Inspected

- `src/experimentation/workflows.py`
- `src/experimentation/graph.py`
- `src/experimentation/perturbations.py`
- `src/experimentation/datasets.py`
- `src/experimentation/runner.py`
- `src/experimentation/config.py`
- `src/experimentation/evaluation.py`
- `src/experimentation/figures.py`
- `src/experimentation/dashboard.py`
- `src/experimentation/cli.py`
- `src/tests/test_workflows.py`
- `src/tests/test_perturbations.py`
- `src/tests/test_runner.py`

## Files Changed

- `src/experimentation/workflows.py`
- `src/experimentation/perturbations.py`
- `src/experimentation/datasets.py`
- `src/experimentation/runner.py`
- `src/experimentation/config.py`
- `src/experimentation/evaluation.py`
- `src/experimentation/figures.py`
- `src/experimentation/dashboard.py`
- `src/tests/test_workflows.py`
- `src/tests/test_perturbations.py`
- `src/tests/test_runner.py`
- `src/tests/test_experimentation_baseline.py`
- `src/docs/experimentation/implementation_audit_netlsd_diversity_wl.md`
- `src/docs/experimentation/results_schema.md`
- `src/docs/experimentation/theory.md`
- `src/docs/experimentation/full_fidelity_implementation_netlsd_diversity_wl.md`

Generated debug artifacts:

- `src/outputs/full_fidelity_debug/results/results.csv`
- `src/outputs/full_fidelity_debug/evaluation/evaluation_summary.csv`
- `src/outputs/full_fidelity_debug/evaluation/final_matrix.csv`
- `src/outputs/full_fidelity_debug/figures/*.svg`

## NetLSD

Expected algorithm from the local docs and paper:

1. Build the normalized graph Laplacian.
2. Compute eigenvalues `lambda_i`.
3. For each logarithmic time scale `t`, compute heat trace
   `h_t = sum_i exp(-t * lambda_i)`.
4. Use 250 time scales over `[1e-2, 1e2]`.
5. Normalize against a neutral graph when comparing different-size graphs.
6. Compare graph signatures using an L2-type distance over the time grid.

Implemented behavior:

- `NetLSDWorkflow` defaults to `NETLSD_DEFAULT_TIMESCALES`, a 250-point
  log-space grid from `0.01` to `100.0`.
- `normalized_laplacian_eigenvalues()` computes the normalized Laplacian exactly
  with a PyTorch eigensolver when available or a deterministic Jacobi fallback.
- `netlsd_signature(..., normalization="empty")` computes heat traces and
  divides by an empty-graph neutral trace by default.
- `normalization="none"` and `normalization="complete"` remain explicit options.
- Distribution comparison is L2 distance between mean NetLSD signatures.
- Paired comparison is average within-pair L2 distance.
- Result rows log the time-scale count/min/max, schedule, normalization,
  Laplacian type, heat signature type, and full-spectrum eigenvalue mode.

Intentional deviations and limitations:

- The implementation uses exact full-spectrum eigenvalues. This is faithful for
  small graphs and preferable for thesis accuracy, but it does not implement the
  paper's scalable large-graph approximation.
- Wave-trace variants are not implemented.
- Complete-graph neutral normalization is implemented as the formula described
  in the local paper notes, but the thesis should choose and report one
  normalization mode consistently. The default is `empty`.

## Diversity Curves

Expected algorithm from the local docs and paper:

1. Define graph spread using shortest-path distances:
   `Div(G) = sum_x 1 / sum_y exp(-d(x, y))`.
2. Build a curve over graph cardinalities/scales.
3. Coarsen graphs by repeated edge contractions.
4. Repeat randomized coarsenings and average the resulting curves.
5. For variable-size graph datasets, upsample smaller graphs to a common
   maximum cardinality.
6. Keep disconnected-graph behavior finite by ignoring infinite shortest-path
   terms and anchoring unreachable scale behavior.

Implemented behavior:

- `DiversityCurvesWorkflow` now defaults to all integer cardinalities from `1`
  to the largest graph in the compared collection.
- `diversity_curve_representations()` resolves a common dataset-level scale
  schedule and returns equal-length curves.
- Seeded random edge contraction is used by default. Edge order is canonicalized
  before random draws to avoid dependence on raw node IDs.
- Smaller graphs are upsampled by duplicating original nodes and connecting the
  duplicate to the source node's closed neighborhood.
- Disconnected graphs remain finite; unreachable low-cardinality scales are
  interpolated from the `DivCurve(G)_1 = 1` anchor where possible.
- Result rows log scale schedule, scale count, repetitions, upsampling,
  contraction mode, metric, random seed, and distribution distance.

Intentional deviations and limitations:

- The implementation is dependency-free and has not been numerically validated
  against the authors' Diversity Curves reference implementation.
- The random contraction implementation contracts one edge at a time rather than
  reproducing any package-specific batched random edge-score implementation.
- Only the shortest-path metric variant is implemented.

## Weisfeiler-Lehman / WL

Expected algorithm from the local docs and WL subtree kernel paper:

1. Initialize node labels from discrete node labels when present; use a defined
   unlabeled fallback otherwise.
2. For each 1-WL iteration, collect each node's current label and sorted
   multiset of neighbor labels.
3. Compress equal signatures to equal new labels using a shared dictionary.
4. Build graph feature vectors by counting labels from the initial graph and all
   refined iterations.
5. The WL subtree kernel between graphs is the inner product of these feature
   histograms.

Implemented behavior:

- `wl_feature_matrix()` computes features for a graph collection using a shared
  canonical compression dictionary at every WL iteration.
- The default label policy is `node_label_or_degree`: use `graph.metadata` node
  labels when available, otherwise initialize unlabeled graphs by degree.
- `label_initialization="degree"` and `label_initialization="constant"` are
  explicit options.
- `wl_subtree_kernel_matrix()` computes the WL subtree kernel matrix from the
  feature histograms.
- `WLSubtreeMMDWorkflow` computes original and perturbed features jointly so
  both distributions share the same compressed WL feature space.
- Distribution comparison remains linear MMD, i.e. squared distance between mean
  WL feature histograms.
- Result rows log WL iterations, label policy, node-label key, compression mode,
  feature construction, and kernel/distance mode.

Intentional deviations and limitations:

- Edge labels and continuous attributes are not implemented.
- The workflow is a graph-distribution comparison method, not the full graph
  classification pipeline from the WL kernel paper.
- Raw count histograms remain size-sensitive by design; no histogram
  normalization is enabled by default.

## Perturbation Split

The default perturbation grid now uses:

- `edge_insertion`
- `edge_deletion`
- `triangle_insertion`
- `triangle_deletion`
- `community_weakening`
- `hub_modification`

Legacy mixed perturbations are still callable for backward compatibility:

- `edge_addition_deletion`
- `triangle_injection_removal`

Every new perturbation row records:

- `perturbation`
- `perturbation_family`
- `perturbation_direction`
- serialized `perturbation_params`

## Reproducibility Logging

`results.csv` now includes:

- `implementation_mode`
- `workflow_params`
- `perturbation_family`
- `perturbation_direction`
- `graph_count`
- `node_count_min`
- `node_count_max`
- `edge_count_min`
- `edge_count_max`

`workflow_params` is canonical JSON and is included in the resume key. This
prevents stale rows from a previous workflow configuration from satisfying a new
paper-faithful run.

## Tests Added Or Updated

NetLSD tests:

- Known normalized-Laplacian eigenvalues for an edge, path, and isolated graph.
- Heat trace equals manual `sum(exp(-t * lambda_i))`.
- Default 250 time scales over `[1e-2, 1e2]`.
- Empty-graph neutral normalization is size-neutral.
- Isomorphic graphs and repeated calls produce deterministic signatures.
- Dense vector length mismatch raises instead of truncating.

Diversity Curves tests:

- Manual shortest-path spread values.
- Legacy graph-local curve behavior on tiny graphs.
- Dataset-level all-integer scale schedule.
- Upsampling smaller graphs to common scale.
- Disconnected graph finite behavior.
- Determinism across repeated calls.

WL tests:

- Manual 1-WL subtree counts on a 3-node path.
- Shared compression across compared graph collections.
- Discrete node-label handling.
- WL kernel matrix symmetry.
- Isomorphic graph behavior and deterministic runs.

Perturbation tests:

- Separate edge insertion/deletion metadata and edge-change behavior.
- Separate triangle insertion/deletion metadata.
- Runner-level assertion that all four directional perturbations produce
  distinct result rows.

## Commands Run

```bash
python3 -m unittest tests.test_workflows tests.test_perturbations tests.test_runner
```

Result: 44 tests passed.

```bash
python3 -m unittest discover -s tests
```

Result: 72 tests passed, 2 skipped.

```bash
python3 -m experimentation.cli run_debug_experiment --output-root outputs/full_fidelity_debug --no-resume --device cpu
```

Result: generated `outputs/full_fidelity_debug/results/results.csv`.

```bash
python3 -m experimentation.cli evaluate_results --results outputs/full_fidelity_debug/results/results.csv --output-dir outputs/full_fidelity_debug/evaluation
```

Result: generated `evaluation_summary.csv` and `final_matrix.csv`.

```bash
python3 -m experimentation.cli generate_figures --results outputs/full_fidelity_debug/results/results.csv --output-dir outputs/full_fidelity_debug/figures
```

Result: generated six SVG figures.

## Output Regeneration

The debug experiment outputs were regenerated with the upgraded defaults. The
full synthetic thesis grid was not regenerated in this audit turn because the
new NetLSD default computes 250 heat-trace samples from exact spectra and the
full grid is the expensive thesis-scale run. Use:

```bash
python3 -m experimentation.cli run_full_synthetic_experiment --output-root outputs/experimentation_native_netlsd --device cpu --no-resume --console-log
python3 -m experimentation.cli evaluate_results --results outputs/experimentation_native_netlsd/results/results.csv
python3 -m experimentation.cli generate_figures --results outputs/experimentation_native_netlsd/results/results.csv
```

Use `--device cuda` only if PyTorch with CUDA is available.

## Remaining Human Review

- Confirm the thesis normalization policy for NetLSD (`empty` is now default;
  `complete` and `none` are available).
- Decide whether large-graph NetLSD approximation is required for final runs.
- Validate Diversity Curves numerically against an authors' implementation if
  exact reference-package reproduction is required.
- Decide whether WL histograms should be normalized for any variable-size
  dataset analysis.
- Add edge-label or continuous-attribute WL support only if thesis datasets
  require it.
