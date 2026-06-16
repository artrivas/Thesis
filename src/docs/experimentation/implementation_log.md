# Implementation Log

## Day 1

Implemented the project baseline for synthetic graph distribution experiments.
No real datasets, graph generators, perturbation algorithms, workflow execution,
or heavy experiments were implemented.

Files added:

- `.gitignore`: ignores Python cache files and generated experiment outputs.
- `experimentation/__init__.py`: exposes the public Day 1 configuration helpers.
- `experimentation/config.py`: defines dataclass-based configuration for
  synthetic datasets, perturbations, workflows, alpha values, seeds, and output
  paths. Includes default and debug configurations plus output directory
  creation.
- `docs/experimentation/theory.md`: documents the theoretical motivation for
  distribution-level, paired graph comparison experiments.
- `docs/experimentation/implementation_log.md`: records the Day 1 files and
  implementation scope.
- `docs/experimentation/experimental_protocol.md`: describes the high-level
  experimental pipeline from datasets to tables and figures.
- `docs/experimentation/results_schema.md`: defines the expected result table
  columns.
- `tests/test_experimentation_baseline.py`: adds smoke tests for configuration
  loading, output directory creation, and documentation file existence.

Configuration defaults established today:

- Synthetic families: Erdős-Rényi, Stochastic Block Model, Barabási-Albert.
- Perturbations: edge addition/deletion, triangle injection/removal, community
  weakening, hub modification.
- Workflows: `GraphStats+MMD`, `WLFeatures+MMD`, `NativeNetLSD`, and
  `DiversityCurveDistance`.
- Alpha values: `0.0, 0.1, 0.2, ..., 1.0`.
- Seeds: `0, 1, 2, 3, 4`.
- Graphs per distribution: `100`.
- Default output root: `outputs/experimentation_native_netlsd`.

Known Day 1 limitations:

- The module contains configuration only.
- The test suite uses only the Python standard library.
- Future workflow implementations may require dependencies such as NetworkX,
  NumPy, SciPy, scikit-learn, GraKeL or an equivalent WL implementation, and a
  NetLSD implementation.

## Days 2-4

Implemented the core synthetic experimentation components. Real datasets remain
out of scope and were not added.

Files added:

- `experimentation/graph.py`: defines a minimal undirected simple graph class
  with edge operations, copy semantics, degree queries, density, connected
  components, triangle counting, triangle edge lookup, open wedge lookup, and
  structural equality checks.
- `experimentation/datasets.py`: implements synthetic distribution generation
  for Erdős-Rényi, Stochastic Block Model, and Barabási-Albert graphs. Adds
  `SyntheticDatasetConfig`, `PairedDistribution`,
  `generate_graph_distribution`, and `generate_paired_distribution`.
- `experimentation/perturbations.py`: implements controlled perturbations for
  edge addition/deletion, triangle injection/removal, community weakening, and
  hub modification. Each perturbation returns a graph copy plus metadata.
- `experimentation/workflows.py`: implements the common workflow interface and
  four representation/discrepancy pipelines: `GraphStats+MMD`,
  `WLFeatures+MMD`, `NativeNetLSD`, and `DiversityCurveDistance`.
- `tests/test_synthetic_datasets.py`: tests generator size, non-empty graphs,
  reproducibility, and SBM community labels.
- `tests/test_perturbations.py`: tests alpha-zero copy behavior, edge
  perturbation budgets, SBM community weakening, graceful skip behavior, and hub
  targeting.
- `tests/test_workflows.py`: tests that each workflow runs on a tiny paired
  graph distribution and returns numeric distribution, mean-shift, and paired
  scores.

Files modified:

- `experimentation/__init__.py`: exports the synthetic dataset, graph,
  perturbation, and workflow helpers.
- `docs/experimentation/theory.md`: adds the rationale for synthetic datasets,
  perturbation families, and workflow implementations.
- `docs/experimentation/experimental_protocol.md`: adds operational alpha
  definitions and the common workflow evaluation interface.
- `docs/experimentation/results_schema.md`: clarifies that perturbation
  metadata can be stored as sidecar metadata or added as optional orchestration
  columns later.
- `docs/experimentation/implementation_log.md`: records all Days 2-4 changes.

Dependency notes:

- No external dependencies are required for the current implementation.
- NetworkX and NumPy were not available in the environment, so the module uses a
  small internal graph class and standard-library implementations.
- NetLSD uses a simple Jacobi eigensolver fallback for normalized Laplacian
  eigenvalues. This is appropriate for tiny synthetic smoke tests but should be
  replaced by NumPy/SciPy for larger experiments.
- WL subtree features are implemented manually with deterministic relabeling.
- Diversity Curves use shortest-path spread over deterministic
  edge-contraction scales.

## Days 5-7

Implemented experiment orchestration, result storage, evaluation metrics, SVG
figures, CLI commands, and final documentation. Real datasets remain out of
scope and were not added.

Files added:

- `experimentation/runner.py`: executes the synthetic grid
  `dataset x perturbation x alpha x seed x workflow`, preserves paired graph
  distributions, measures runtime and memory with standard-library tools, and
  writes result CSV files.
- `experimentation/evaluation.py`: implements sensitivity, monotonicity,
  paired detectability, mean-shift detectability, robustness CV, Kendall tau
  ranking stability, relative runtime, interpretability scores, granularity
  summaries, evaluation summary CSVs, and final matrix CSVs.
- `experimentation/figures.py`: generates dependency-free SVG figures for
  score vs alpha, paired distance vs alpha, mean-shift vs paired-shift,
  granularity heatmap, and runtime comparison.
- `experimentation/cli.py`: adds commands for `run_debug_experiment`,
  `run_full_synthetic_experiment`, `evaluate_results`, and `generate_figures`.
- `docs/experimentation/final_experimentation_plan.md`: records the final
  synthetic experimentation plan, schemas, commands, limitations, and future
  work.
- `tests/test_runner.py`: tests end-to-end debug-style execution, result CSV
  creation, expected columns, and workflow failure isolation.
- `tests/test_evaluation.py`: tests monotonic sensitivity, monotonicity
  violations, label thresholds, summary generation, and evaluation CSV output.
- `tests/test_figures.py`: tests SVG figure generation, final documentation
  existence, debug pipeline figure generation, and documented CLI commands.

Files modified:

- `experimentation/config.py`: adds concrete synthetic dataset configurations,
  `full_synthetic_config`, and run-ready `debug_config` settings.
- `experimentation/__init__.py`: exports runner, evaluation, and figure helpers.
- `docs/experimentation/theory.md`: adds evaluation metric definitions and
  threshold labels.
- `docs/experimentation/experimental_protocol.md`: adds runner, evaluation,
  figure generation, and command usage.
- `docs/experimentation/results_schema.md`: adds `dataset_params`,
  `perturbation_params`, evaluation summary schema, and final matrix schema.
- `docs/experimentation/implementation_log.md`: records all Days 5-7 changes.

Dependency notes:

- Result storage uses CSV from the Python standard library.
- Figures are SVG files generated without matplotlib.
- Memory measurement uses `tracemalloc`; values are best-effort and intended
  for relative comparison in this phase.

## Sanity Check Fixes

Updated the experiment code to avoid known sources of misleading results:

- Replaced the first-pass Diversity Curves neighborhood summary with
  shortest-path spread over deterministic edge-contraction scales.
- Renamed the default diversity workflow to `diversity_curves_shortest_path`.
- Fixed WL subtree features so iteration labels are canonical across graphs
  rather than remapped independently per graph.
- Prevented hub modification from removing a hub edge and then adding that same
  edge back while counting it as a rewire.
- Added regression tests for the corrected metric and perturbation behavior.

## Full-Fidelity Method Upgrade

Upgraded the thesis-facing defaults for NetLSD, Diversity Curves, and
Weisfeiler-Lehman workflows.

Files modified:

- `experimentation/workflows.py`: adds 250-scale NetLSD heat traces with
  neutral normalization, shared-compression WL subtree features, WL kernel
  matrix generation, dataset-level Diversity Curves with all-cardinality scale
  schedules, seeded random contraction, and upsampling.
- `experimentation/perturbations.py`: adds separate `edge_insertion`,
  `edge_deletion`, `triangle_insertion`, and `triangle_deletion` perturbations
  while keeping the older mixed perturbations as legacy aliases.
- `experimentation/runner.py`: writes workflow implementation metadata,
  perturbation family/direction, graph counts, and node/edge size ranges to
  each result row; workflow parameters are part of the resume key.
- `experimentation/config.py`, `evaluation.py`, `figures.py`, and
  `dashboard.py`: update defaults, labels, and summaries for the directional
  perturbation split.
- `docs/experimentation/full_fidelity_implementation_netlsd_diversity_wl.md`:
  records the implemented algorithms, deviations, commands, tests, and
  remaining thesis review items.

Validation:

- `python3 -m unittest discover -s tests` passed with 72 tests and 2 skipped.
- `python3 -m experimentation.cli run_debug_experiment --output-root outputs/full_fidelity_debug --no-resume --device cpu`
  regenerated debug result rows with the upgraded defaults.
- Evaluation CSVs and SVG figures were regenerated for
  `outputs/full_fidelity_debug`.
