# Randomness correction and thesis rerun plan

Date: 2026-09-16. Status: implementation and pilot validation complete. The stream
protocol, graph artifacts, ZINC importer/configurations, and sanity tools are
implemented. All 165 tests, 576 smoke rows, and 1,056 pilot rows passed; all pilot
audits passed and 32 pilot figures were generated. See the
[validation and resource report](../../results/analysis/2026-09-16_implementation_validation/README.md).
Final protocol/power planning and production runs remain outstanding.
See [implementation instructions](corrected_runs.md) for commands and the
additional NetLSD convergence issue found during sanity checking.

## Objective and scope

Produce reproducible experiments with separately derived random streams across runs, retain the individual measurements needed for granular analysis, and rerun the experiments supporting the thesis's final claims.

Preserve the historical results and analyses as exploratory evidence. The known seed overlap does not establish that their findings are wrong or quantify the resulting dependence. Fixing the stream assignment addresses this design concern; it does not automatically establish every statistical assumption.

The proposed synthetic scope remains ER, SBM, and BA; six perturbations; four current workflows; alpha 0.0 through 1.0 in steps of 0.1; and 100 graphs per distribution. Exclude IMDB-BINARY. Implement ZINC (called “ZYNC” in the request) as the real-data experiment, including its loader, configuration, logging, sanity checks, pilot, and production analysis described in section 5. This plan updates the scope described in the older `final_experimentation_plan.md` for the forthcoming rerun.

## 0. Preserve the current results — completed

The complete `results/` directory was copied to `archive/results_snapshots/2026-09-16_before_randomness_fix/results/`. The snapshot includes raw runs, legacy outputs, analyses, figures, logs, and documentation present in that directory.

Verified **181 files, 91,052,691 bytes** by comparing every relative path, size, and SHA-256 hash against the source both before and after the copy. The source was unchanged. The [snapshot manifest](../../archive/results_snapshots/2026-09-16_before_randomness_fix/snapshot_manifest.json) records all files and hashes. This is a separate local copy on the same storage, not an off-device backup. It does not include files outside `results/`, such as source code, input datasets, or the thesis.

Keep this snapshot as the historical reference and write corrected experiments to new run directories.

## 1. Define and implement the random-stream protocol

Current issue: `datasets.py:generate_paired_distribution` passes `seed + index` to each perturbation. For example, run 0 / graph 1 and run 1 / graph 0 both receive seed 1. Dataset generation also needs a separate stream namespace from perturbation generation.

Introduce a small standard-library helper, proposed as `src/experimentation/randomness.py`, that derives a Python random seed using SHA-256 over a canonical, explicitly structured payload. Do not use addition, ambiguous string concatenation, or Python's process-dependent built-in `hash()`.

Record a master seed and a versioned protocol identifier, proposed `sha256_streams_v1`. Derive streams from:

| Purpose | Identity fields in addition to master seed and protocol version |
|---|---|
| Synthetic graph generation | Dataset identity and generator parameters, replicate ID, graph ID, purpose |
| Real-dataset sampling | Dataset version/checksum, sampling-policy identity, replicate ID, purpose |
| Graph perturbation | Dataset/configuration identity, replicate ID, graph ID, perturbation name, purpose |

Replicate IDs remain human-readable values such as 0, 1, 2. They are distinct from derived generator seeds. Dataset identity excludes transient output paths and includes the parameters that define the graph population.

Preserve deliberate pairing:

- Generate the same source graphs for all alpha values, perturbations, and workflows within a replicate.
- Exclude alpha from the perturbation stream identity so the same graph/perturbation uses a coupled sequence across alpha.
- Exclude workflow identity from graph generation and perturbation streams so every method evaluates identical graph pairs.
- Do not claim that a shared seed alone guarantees nested edits across alpha. Verify and document the actual perturbation behavior; record realized edits, failed attempts, and no-ops.

Audit every random generator, including Diversity Curve coarsening. Its current graph-derived fixed seed can be treated as part of a deterministic representation conditional on the graph; document that decision and keep its configuration fixed across runs. If it is instead made a source of replicate variation, give it its own namespace and define pairing explicitly before launching production runs. Avoid changing metric definitions as part of this correction.

Acceptance: the full planned stream-key inventory has no unintended duplicate derived seeds; intentional duplicates are explicitly checked. The historical `(run=0, graph=1)` versus `(run=1, graph=0)` collision must have a regression test. This inventory check prevents assignment collisions, not a mathematical proof of statistical independence.

## 2. Version outputs and save graph-level measurements

Update configuration serialization, manifests, resume checks, and documentation in `config.py`, `runner.py`, and `results_schema.md`. Use a new run directory and schema/protocol version. A corrected run must reject attempts to resume or merge historical rows whose randomness protocol is missing or incompatible. Changing only a directory name is insufficient protection.

Keep aggregate rows for compatibility with existing analysis. Add compressed, keyed sidecar artifacts:

- **Graph-pair records:** dataset/version, replicate ID, stable source graph ID, perturbation, alpha, original/perturbed graph hashes, stream identity, requested and realized edits, and relevant structural descriptors before/after.
- **Workflow-pair records:** graph-pair key, workflow/configuration identity, individual representation distance, status, and applicable diagnostic values.
- **MMD diagnostics:** kernel means Kxx, Kyy, Kxy for GraphStats; squared mean-feature displacement for WL; and signed pair contributions where available. Contributions must be labeled as sample-dependent decompositions, not independent graph distances.

Use representations already computed by each workflow. Avoid recomputing them merely for logging. Persist graph data once per cell rather than duplicating it four times. Store the source/perturbation provenance needed to reconstruct graph pairs; hashes alone are not reconstruction data. Keep runtime and memory measurements for the workflow separate from diagnostic computation and serialization overhead.

Retain the runner's single-writer design. Publish sidecar files atomically, then mark the corresponding result complete. Resume must detect missing, incomplete, or checksum-invalid sidecars and repair the affected cell without duplicates. A row with absent required graph measurements is not a complete granular result.

Acceptance: graph-level means reconstruct `paired_score`; applicable contributions reconstruct `distribution_score` within documented floating-point tolerances; every aggregate row links to the expected graph records. Graphs must remain identical across workflows and source graph identities stable across alpha.

## 3. Validate with tests and a small pilot

Extend the dataset, perturbation, workflow, runner, parallel-runner, seed-sweep, and traceability tests as appropriate. Check:

1. Identical protocol/configuration reproduces graph hashes and scores, excluding timing metadata.
2. Changing replicate or graph identity changes the derived stream; changing worker count, scheduling order, sharding, or resume state does not.
3. Deliberate pairing survives the correction; alpha zero compares identical representations and yields the expected zero scores.
4. Stream-version mismatches and incomplete graph artifacts are detected during resume.
5. Serial and parallel outputs agree by logical key, and aggregate/graph-level consistency checks pass.

Run a reduced-size smoke grid covering all synthetic families and perturbations, followed by a production-size diagnostic pilot: BA triangle insertion and ER community weakening, three pilot replicates, eleven alpha levels, all four workflows, 100 graph pairs per cell. The latter is 66 cells and 264 aggregate rows.

Inspect distributions, failures, no-ops, graph pairing, kernel behavior, and the previously surprising patterns. Do not require the new curves or p-values to match the historical findings. Reserve a separate master seed for this pilot; exclude pilot results from final inferential analysis.

Acceptance: correctness checks pass, graph-level artifacts are complete, and runtime, peak memory, and compressed output size are measured. Stop to fix failures before a production run.

## 4. Freeze the final protocol and estimate cost

Before inspecting final results, write down the target claims, comparisons, sampling units, analysis methods, practical effect sizes of interest, treatment of ties/zeros/failures, and multiplicity families. Use historical data and pilot data only for planning. Do not add replicates until a desired p-value appears.

Use 24 synthetic replicates as the initial planning baseline, not an assertion of adequate power. Assess power or expected precision for the selected claims, including multiplicity and likely ties, and fix the final count before production. Use fresh production streams separate from the pilot.

At 24 replicates, the full synthetic grid contains:

- 4,752 graph-distribution cells.
- 19,008 workflow-level rows.
- 475,200 graph-pair observations across alpha and perturbations.
- 1,900,800 workflow-pair distance records. These are repeated measurements, not that many independent replicates.

Estimate runtime from measured cell costs, stratified by dataset/perturbation and workflow where needed; benchmark worker throughput rather than simply dividing serial time by worker count. Estimate storage from measured compressed bytes per artifact type. Benchmark uncovered expensive settings before quoting a full-run estimate. ZINC needs a separate estimate after its graph sizes and workflow compatibility are known.

Deliver a projected wall-clock range, peak memory requirement, disk footprint, and any external compute cost. Do not invent a dollar estimate from row counts. Local analysis needs no paid service; experiment execution still consumes machine time and resources.

## 5. Implement the ZINC experiments and their sanity checks

This is an implementation deliverable, not just a proposal to add a dataset later. The current real-data support is a TU-format loader with an IMDB-BINARY registration; it does not provide a complete ZINC experiment. Implement the following stages after the shared randomness and artifact changes; ZINC preparation can proceed alongside synthetic validation.

### 5.1 Dataset and scientific protocol

**Proposed default:** the 12,000-graph ZINC benchmark subset, preserving its provided train/validation/test split identities. PyTorch Geometric documents both this subset and the larger dataset; pin the chosen source and importer version rather than silently using the full collection. [Official ZINC dataset documentation](https://pytorch-geometric.readthedocs.io/en/latest/generated/torch_geometric.datasets.ZINC.html).

Use the validation split for development/pilot and the train split as the fixed production sampling pool; leave the test split unused for this study. This is a perturbation study, not a prediction benchmark, so these roles must be stated explicitly. Confirm split counts against the pinned source during import, record any cross-split duplicate identities/topologies, and make no out-of-population generalization claim from this split arrangement alone. Any different subset or split policy must be recorded before production results are inspected.

For each replicate, sample 100 source graphs without replacement within that replicate, with independently derived sampling streams across replicates. Keep the chosen graphs fixed across every alpha, perturbation, and workflow in that replicate. Save the sampled source IDs and report overlap between replicates. The inferential target is repeated sampling and perturbation **conditional on this fixed ZINC pool**; it is not automatically the population of all molecules.

Use **structural stress tests** as the primary experiment, consistent with the synthetic study. Preserve atom/bond attributes in the source cache, but evaluate a documented simple, undirected, unweighted topology projection with all four workflows. Explicitly configure WL to use degree initialization for this primary comparison so it does not silently use atom labels while the other methods ignore them. Record this configuration difference from any historical WL defaults. Chemical validity is not a constraint of these structural perturbations, and perturbed outputs are not claimed to be valid molecules. Label-aware or chemistry-preserving experiments would require a separately specified extension.

### 5.2 Implement acquisition, conversion, and configuration

Proposed implementation locations:

| Component | Work |
|---|---|
| `scripts/fetch_zinc.py` | Fetch the pinned source, retain checksums and provenance, and convert to a versioned local cache. Keep any PyTorch Geometric import dependency optional, separate from the core experiment runtime. |
| `src/experimentation/zinc_dataset.py` | Load/cache source records; retain split, stable source ID, node count, undirected edges, original atom/bond data, and any target as unused provenance. Convert to repository `Graph` objects and sample with the new stream protocol. |
| `datasets.py`, `config.py` | Register `zinc` dispatch; add dataset variant, split, fingerprint, projection policy, and sample-size fields; supply debug/pilot/production configurations. Avoid forcing ZINC through the existing TU-only loader. |
| `cli.py` | Expose planned configurations `zinc-debug`, `zinc-pilot`, and `zinc`, including existing seed-count, worker, and resume options. Ensure resolved settings reach the manifest. |
| `runner.py`, graph sidecars | Preserve source IDs and dataset fingerprint through every aggregate and graph-level artifact. Refuse resume after a dataset, projection, sampling-policy, or randomness-version change. |
| Analysis scripts and docs | Include ZINC explicitly rather than silently filtering to the three synthetic names. Add dataset-aware figure labels, expected-grid counts, applicability/no-op summaries, and ZINC instructions in `real_datasets.md` and `results_schema.md`. |

Do not mutate cached source metadata when perturbing a graph. `Graph.copy()` currently shallow-copies metadata, so test nested attribute isolation or use immutable source records. Bond attributes in the source cache describe the original molecule, not newly inserted edges in the topology experiment. Hash the source attributes as well as topology for dataset integrity; distinguish source-record fingerprints from topology hashes.

### 5.3 Loader and sampling sanity checks

Implement small offline fixtures in `tests/test_zinc_datasets.py` and a real-cache audit report. Validate:

- File checksums, expected split sizes, stable IDs, deterministic cache conversion, and no unreported filtering or duplicate source IDs.
- Source-to-cache node and edge counts. Reciprocal directed encodings become one undirected edge; isolated nodes remain present; indices are in bounds; conflicting reciprocal bond attributes are detected. Reject unsupported self-loops or parallel bonds explicitly rather than silently dropping information.
- Atom/bond attribute lengths and preservation in the source cache; the topology projection's deliberate omission of those attributes from scores is recorded.
- Sample size, unique source IDs within a replicate, deterministic replay, distinct stream keys across replicates, and identical sampled graphs across alpha/methods. Different seeds need not produce disjoint samples.
- Dataset summaries: node/edge counts, components, degrees, triangles, and potential perturbation opportunities. Report disconnected/edgeless graphs and test handling; do not silently discard them because a workflow encounters difficulties.
- Missing/corrupt files and oversized sample requests fail clearly. Tests using tiny fixtures run without downloading the real dataset.

### 5.4 Perturbation sanity checks

Run all six planned perturbations through ZINC fixtures and the pilot. Check source immutability, node-ID stability, absence of self-loops/duplicate edges, symmetric adjacency, exact edit accounting, and reproducibility. At alpha zero, every perturbation must return the original graph. Use deterministic communities detected on the original topology for community weakening and retain that partition across alpha; atom types are not community ground truth.

| Perturbation | Required check and interpretation |
|---|---|
| Edge insertion | Only permitted non-edges are added; counts match feasible realized operations. |
| Edge deletion | Only existing edges are removed; counts match realized operations. Disconnection is recorded. |
| Triangle insertion | Record motif operations and actual edge changes separately; show fixtures where a triangle can be formed. |
| Triangle deletion | Report graphs with no eligible triangles as no-op/inapplicable according to the frozen convention; an unchanged graph is not evidence of metric insensitivity. |
| Community weakening | Report detected partition, eligible intra/inter-community edges, successful rewires, and cases where rewiring is impossible. |
| Hub modification | Record the hub-selection/tie policy, eligible operations, actual edits, and saturation. |

Do not assume increasing alpha always produces nested edits or strictly more actual changes; test the implemented algorithm and document exceptions. Save requested operations, realized operations, edit distances, and no-op reasons per graph. Separate “nothing changed” from “graph changed but score did not.” No-op frequencies are reported for the full sampling pool/pilot, without selecting only easy-to-perturb graphs after seeing scores. Any decision to omit an inapplicable perturbation from confirmatory tests must be frozen before production.

### 5.5 Workflow and end-to-end sanity checks

- All four methods receive identical graph pairs, with parameter and input hashes recorded. No target value is used to select graphs, tune metrics, or calculate scores.
- Identity comparisons yield zero within stated tolerances; successful scores are finite and nonnegative within numerical tolerance. GraphStats RBF MMD² stays within its theoretical [0, 2] bound for the implemented unit-amplitude kernel.
- Individual distances average to the saved paired score, and MMD decompositions reconstruct distribution scores. Signed contributions may be negative; do not apply the distance nonnegativity check to them.
- Relabeling-node controls check invariance for the deterministic structural/WL/NetLSD methods up to numerical tolerance. Quantify any variability from Diversity Curve coarsening separately rather than assuming exact relabeling invariance for a randomized approximation.
- Small hand-checked graph controls verify representations and edit accounting. A changed graph need not make every metric strictly increase; monotonicity and sensitivity are scientific outcomes, not pass/fail implementation requirements.
- Inspect GraphStats descriptor scale and kernel saturation, WL feature magnitudes, NetLSD normalization on variable-sized graphs, and Diversity Curve behavior on disconnected graphs. Keep the baseline configuration fixed; any alternative bandwidth/normalization is a labeled, prespecified sensitivity analysis.
- Serial, parallel, interrupted/resumed, and seed-sharded runs agree by logical key. There are no duplicate/missing aggregate or graph-level records, and manifests contain dataset and protocol fingerprints.

Extend existing runner, workflow, CLI, and analysis tests where those boundaries change. Produce a machine-readable sanity summary plus a readable report with failures, skips, no-op counts, plots, runtime, memory, and disk size. An unexpected scientific response triggers investigation; it is not automatically a software failure.

### 5.6 ZINC pilot, cost estimate, and production run

First run an offline fixture smoke test, then `zinc-debug`: two pilot replicates, 10 graphs each, six perturbations, alpha 0 / 0.5 / 1, all four methods (**144 aggregate rows**). Next run `zinc-pilot` on the validation split: three pilot replicates, 100 graphs, six perturbations, all eleven alpha values, all four methods (**792 aggregate rows**). Use separate pilot streams and exclude these data from production inference.

Production starts after implementation checks pass, applicability is documented, the measured resource budget is known, and the final protocol is frozen. The initial planning grid is 24 replicates × 6 perturbations × 11 alpha values × 4 workflows = **6,336 aggregate rows**, with 100 graph pairs per cell. This entails 1,584 cells, 158,400 graph-pair observations, and 633,600 workflow-pair distances. Confirm replicate count using the precision/power planning in section 4; 24 is not a guarantee of adequate power.

If the full grids remain unchanged, synthetic plus ZINC production totals **25,344 aggregate rows**. Benchmark ZINC directly; do not infer its runtime solely from synthetic experiments. Preserve failed/skipped/no-op cases with reasons rather than presenting an artificially complete successful grid.

Required ZINC deliverables: working importer/loader/configurations, offline and real-data sanity reports, reproducible pilot with resource estimates, frozen production protocol, traceable production results with graph measurements, and the same granular analysis used for the synthetic datasets. Statistical tests follow section 6 and the fixed-pool sampling interpretation above.

## 6. Run and analyze the corrected experiments

Run the frozen synthetic grid in a new traceable directory after the pilot and protocol checks pass. Run ZINC once its separate preparation is complete. Save configuration, code revision/diff, environment, dataset checksums, stream protocol, manifest, and completion inventory.

For each dataset/perturbation/workflow setting, generate individual seed trajectories, observed score distributions, paired changes between alpha levels, direction counts, plateau/reversal summaries, and graph-level explanations for selected cases. Reuse and adapt the existing granular-analysis scripts. Show actual edit counts alongside alpha when saturation or no-ops matter.

Use a whole replicate trajectory as the unit for distribution-score inference. Do not treat alpha rows, graph pairs, or MMD contributions as independent distribution-score replicates. A claim about individual graph distances is a different estimand and requires its own dependence-aware design.

Choose tests for explicit claims, not merely to obtain one p-value per experiment:

- Paired t-tests concern mean contrasts; inspect the difference distribution and influential observations. [NIST t-test guidance](https://www.itl.nist.gov/div898/handbook/eda/section3/eda353.htm).
- Wilcoxon signed-rank has symmetry and independent-difference requirements; ties and zeros also affect its calculation. Do not select it automatically after a normality-test rejection. [SciPy Wilcoxon documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html).
- For a directional claim, consider a prespecified sign test with zero counts and magnitudes reported. For an entire alpha-response claim, use a justified repeated-measures analysis; an endpoint comparison cannot establish monotonicity or absence of nonlinear effects.

Report effect magnitudes and suitable uncertainty intervals alongside multiplicity-adjusted p-values where justified. Granular plots remain useful without a significance claim. A failed assumption check is not permission to shop among tests; follow the prespecified sensitivity/reporting procedure.

Compare new and historical findings descriptively, including changes in conclusions. Do not pool the two protocols. The same numeric replicate ID across protocols does not establish matched graph realizations.

## Deliverables and order

1. Verified copy of current results — completed; see section 0.
2. Versioned stream helper and configuration integration.
3. Graph-level artifacts and compatible crash/resume behavior.
4. Synthetic test results, pilot report, and measured resource estimate.
5. ZINC importer/loader/configurations, sanity checks, and pilot/resource report.
6. Frozen synthetic and ZINC production/analysis protocols.
7. Corrected synthetic and ZINC production results with complete provenance.
8. Granular reports, justified targeted inference, and historical-versus-corrected comparison where historical data exist.

The snapshot, implementation, source-data audit, smoke checks, and all three
pilots are complete. Pilot resource measurements and descriptive plots are in
the linked validation report. Final protocol/power planning, production
experiments, and confirmatory inference remain outstanding.
