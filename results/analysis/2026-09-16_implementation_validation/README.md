# Corrected experiment implementation: validation record

The random-stream protocol, graph-level artifacts, protected resume/merge path,
ZINC importer and experiment configurations, sanity audits, and ZINC-compatible
granular plots are implemented and validated. All three pilots finished and
passed their audits. Final production experiments and confirmatory statistical
claims are not complete.

## Completed checks

- **165 automated tests pass**, including 50,400 distinct synthetic stream keys,
  the historical seed-collision regression, serial/parallel agreement for all
  four workflows, missing/corrupt sidecar recovery, incompatible-resume checks,
  ZINC fixtures, and numerical eigensolver controls. [Test log](unit_tests.txt).
- **All 181 original historical files and backup copies remain byte-identical**
  to the pre-implementation inventory. [Hash verification](historical_results_check.json).
- **Synthetic smoke run: 432 successful rows**, complete graph artifacts,
  checked pairing/streams, and matching aggregate reconstruction.
  [Sanity report](../../runs/2026-09-16_synthetic_smoke_validated/sanity_report.json).
- **ZINC smoke run: 144 successful rows** with the same checks.
  [Sanity report](../../runs/2026-09-16_zinc_smoke_validated/sanity_report.json).
- **24 ZINC setting figures generated**, each showing individual trajectories,
  score distributions, paired changes, and direction counts.
  [Figure index](../../runs/2026-09-16_zinc_smoke_validated/granular_analysis/all_settings.md).

Smoke results are implementation checks with two replicates and three alpha
values, not sufficient evidence for substantive inferential claims.

## ZINC data audit

Imported the benchmark subset into a checked cache: 10,000 training records,
1,000 validation records, and 1,000 test records. Training is the proposed
production pool; validation is used for pilots; test records are audited but not
used in experiments. The dataset fingerprint is
`1a97cb33f8552a5b692e74c7efbcb4b2bc5e6c70551cc59cc8363049047432ef`.

The cache audit found 9,397 training and 925 validation graphs with no triangles.
Triangle-deletion no-ops must be reported as such, rather than treated as metric
insensitivity. It also found three exact duplicate training records and one
exact training/validation overlap. These checks compare attributed records in
their source node order, not molecular isomorphism classes. No records were
silently removed. [Cache audit](../../../data/ZINC/sanity_report.json).

## Numerical issue discovered during sanity checking

The old NetLSD Jacobi implementation could stop after 1,000 rotations without
convergence. On a 50-node BA graph, its heat signature differed from a library
solver by 0.002162. The CPU path now uses NumPy when available, with an explicitly
recorded backend; the standard-library alternative checks convergence. Tests
verify known graph spectra and agreement with a converged reference. Heat-trace
definition, normalization, and time scales are unchanged.

Consequently, historical-versus-corrected NetLSD differences cannot be attributed
solely to the seed fix. Preliminary pilot folders ending `_pilot_streams_v1`
were stopped and preserved. The `_pilot_validated` folders use the checked
implementation. The old solver remains an explicit historical-reproduction
option.

## Completed larger pilots

| Pilot | Replicates | Graphs per cell | Alpha levels | Successful rows |
|---|---:|---:|---:|---:|
| BA, triangle insertion | 3 | 100 | 11 | 132 |
| ER, community weakening | 3 | 100 | 11 | 132 |
| ZINC, all six perturbations | 3 | 100 | 11 | 792 |

All **1,056 pilot rows** succeeded, with no audit issues:
[BA audit](../../runs/2026-09-16_ba_pilot_validated/sanity_report.json),
[ER audit](../../runs/2026-09-16_er_pilot_validated/sanity_report.json),
[ZINC audit](../../runs/2026-09-16_zinc_pilot_validated/sanity_report.json).
These contain 26,400 graph-pair observations and 105,600 workflow-pair records,
including repeated measurements across alpha and workflows; they are not that
many independent replicates. The ZINC run resumed with more workers after the
synthetic jobs finished. All 384 checkpointed rows were preserved exactly,
with no duplicates in the final 792 rows. [Resume check](checkpoint_resume_check.json).

The 32 pilot figures show every replicate, rather than just its mean:
[BA figures](../../runs/2026-09-16_ba_pilot_validated/granular_analysis/all_settings.md),
[ER figures](../../runs/2026-09-16_er_pilot_validated/granular_analysis/all_settings.md),
[ZINC figures](../../runs/2026-09-16_zinc_pilot_validated/granular_analysis/all_settings.md).

### Descriptive findings from the pilots

- In ZINC community weakening, GraphStats' mean increased between alpha 0.8
  and 0.9, although two of the three replicate scores decreased. NetLSD and
  Diversity Curves show the same mean-versus-majority discrepancy between 0.9
  and 1.0. This directly illustrates the information hidden by a mean curve;
  three pilot replicates do not establish a population-level effect.
- ZINC triangle deletion made no change in **2,740 of 3,000** positive-alpha
  graph-pair observations (91.3%). These repeated observations must not be
  interpreted as 3,000 independent graphs. The no-op reason was no feasible
  change. Community weakening had two additional rounded-budget no-ops.
- The ZINC pilot sampled 300 source instances across three replicates,
  representing 268 distinct records. Pairwise replicate overlap was 11, 11,
  and 10 source IDs. Independent sampling streams need not yield disjoint
  samples; the interpretation remains conditional on the fixed source pool.
- For BA triangle insertion, all three GraphStats trajectories had at least
  one decline over positive-alpha intervals, while the other three workflows
  were nondecreasing. For ER community weakening, all four workflows had
  declines in every replicate. Monotonicity is an outcome to investigate,
  not a software sanity requirement.

### Measured resources

| Pilot | Elapsed minutes | Workers | Result files, decimal MB | 24-replicate planning estimate |
|---|---:|---|---:|---:|
| BA triangle insertion | 29.4 | 3 | 2.90 | 3.9 hours |
| ER community weakening | 33.5 | 3 | 3.79 | 4.5 hours |
| ZINC, six perturbations | 42.3 | 2, then 8 | 12.14 | 5.6 hours |

The estimates multiply the observed three-replicate workload by eight and
assume the same worker schedule. They are planning points, not guaranteed
runtime ranges. Concurrent pilots shared the machine, ZINC production uses a
different split, and the two synthetic pilots cover only two of 18 settings.
Result-file measurements exclude the source dataset cache, plots, and environment.
Projected ZINC result files are approximately 97 MB at 24 replicates.
[Machine-readable measurements and limitations](pilot_resources.json).

The [process-memory monitor](process_memory.json) observed a peak summed RSS of
approximately **2.49 GiB** across the monitored jobs. Shared pages may be counted
more than once, and 30-second sampling may miss peaks. Diversity Curves dominated
workflow runtime. No external compute service was provisioned or charged.

Full-grid resource projections must use completed pilot measurements, clearly
distinguish the two sampled synthetic settings from the unmeasured settings,
and account for a different production ZINC split.

## Remaining before final thesis results

Freeze the scientific claims, analysis unit, contrasts, practical effect sizes,
multiplicity families, and no-op policy; determine the production replicate count
using power or precision planning. Benchmark uncovered synthetic settings before
quoting a complete production budget. Then execute the production grids using
fresh streams and perform the prespecified granular and inferential analyses.
The pilot does not certify t-test normality or Wilcoxon symmetry, and no new
confirmatory p-values have been produced.

See [commands and implementation details](../../../docs/experimentation/corrected_runs.md)
and the [rerun plan](../../../docs/experimentation/randomness_rerun_plan.md).
