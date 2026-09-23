# Corrected experiments and ZINC

New experiments use `sha256_streams_v1` and `graph_records_v1`. The historical
results remain unchanged and have a verified copy under
`archive/results_snapshots/2026-09-16_before_randomness_fix/`.

## NetLSD solver sanity correction

During validation, the historical Python Jacobi solver was found to return after
1,000 iterations even when it had not converged. On one 50-node BA graph, its
heat signature differed from a library solver by 0.002162. This is a separate
numerical issue from the random-stream collision.

Corrected CPU runs use NumPy's symmetric eigensolver when installed. The
standard-library fallback now checks convergence with a size-dependent iteration
budget; it raises rather than silently returning an unconverged diagonal. The
workflow records `eigenvalue_solver` in its parameters. Tests cover known spectra
and agreement with a converged Jacobi reference on a 50-node graph. The heat-trace
definition, time scales, and normalization remain fixed.

`NetLSDWorkflow(eigensolver="legacy_jacobi")` explicitly reproduces the historical
unchecked backend. Preliminary pilot directories ending in `_pilot_streams_v1`
were stopped and retained; use the `_pilot_validated` runs for pilot analysis.
Historical-versus-corrected NetLSD differences cannot be attributed solely to
the random-stream change, because the solver also changed.

## Reproducibility

`master_seed` is an experiment-wide key; `seed` is the replicate ID. Separate
purposes distinguish graph generation, dataset sampling, and perturbations.
Dataset identity, replicate, graph ID, and perturbation name determine the
derived stream. Alpha and workflow are deliberately omitted from perturbation
identity to preserve pairing. This does not guarantee nested edits for every
perturbation algorithm.

Pilot configurations use master seed 20260917; production defaults to 20260916.
The legacy seed-plus-index path is explicit and used only to reconstruct old
results. Diversity Curves keeps its fixed graph-derived coarsening policy as
part of the representation definition.

## Real datasets

ZINC has a dedicated checked JSON-cache loader, topology projection,
`zinc-debug` / `zinc-pilot` / `zinc` configurations, and graph-level logging;
see the sections above for import commands, sanity checks, and dataset
provenance.

IMDB-BINARY (previously loaded via a generic TU-format loader, `--config imdb`)
was removed on 2026-09-23 as an uninformative benchmark — see
[../../agent/decisions/2026-09-23-remove-imdb-binary.md](../../agent/decisions/2026-09-23-remove-imdb-binary.md)
and the retired [real_datasets.md](real_datasets.md) writeup, kept for
historical reference when reading old `imdb_binary` result rows.

## ZINC source and interpretation

The importer uses the 12,000-graph benchmark subset: 10,000 train, 1,000 validation,
and 1,000 test source records. The subset index files are pinned to benchmarking-gnns
revision `b6c407712fa576e9699555e1e035d1e327ccae6c`; archive and cache checksums
are saved in `data/ZINC/manifest.json`.

The importer follows the [official PyTorch Geometric ZINC source](https://github.com/pyg-team/pytorch_geometric/blob/master/torch_geometric/datasets/zinc.py)
for archive location and fields, but writes a portable JSON cache. Torch is an
optional import-time dependency; the loader uses the standard library. A
restricted pickle reader allows only tensor reconstruction and weights-only
storage loading. It never extracts arbitrary archive paths.

The primary experiment uses simple undirected unweighted topology. Source atom
and bond types are retained as provenance, not assigned to newly inserted edges.
WL explicitly uses degree labels; regression targets are unused. Structural
perturbations do not claim to preserve valid chemistry.

Debug and pilot runs sample the validation split; production samples the train
split. Sampling is without replacement within a replicate, with separately
derived streams across replicates. Record overlap is reported, not silently
removed. Inference is conditional on this fixed pool. The test split is audited
for source integrity but is not used in experiments.

The source audit found 9,397/10,000 training graphs and 925/1,000 validation graphs
have no triangles. Triangle-deletion no-ops must therefore be distinguished from
metric insensitivity. The audit also reports three exact duplicate training
records and one exact train/validation overlap; this is not an isomorphism-based
deduplication guarantee.

## Commands

Run from the repository root with the package installed, or set `PYTHONPATH=src`.
Commands below use a normal `python` environment; locally the tested interpreter
is `src/.venv/bin/python`.

```sh
# Import once; subsequent invocations verify the existing cache.
python -m pip install -e '.[analysis,zinc-import]'
python scripts/fetch_zinc.py
python scripts/audit_zinc_cache.py

# Smoke tests and production-size pilots, all isolated from production streams.
python -m experimentation.cli run --config debug --run-id synthetic-smoke-v1 --workers 2
python -m experimentation.cli run --config zinc-debug --run-id zinc-smoke-v1 --workers 2
python -m experimentation.cli run --config ba-pilot --run-id ba-pilot-v1 --workers 3
python -m experimentation.cli run --config er-pilot --run-id er-pilot-v1 --workers 3
python -m experimentation.cli run --config zinc-pilot --run-id zinc-pilot-v1 --workers 2

python scripts/audit_corrected_run.py --results results/runs/zinc-pilot-v1/results/results.csv
python scripts/analyze_seed_granularity.py --results results/runs/zinc-pilot-v1/results/results.csv --output results/runs/zinc-pilot-v1/granular_analysis
python scripts/summarize_pilot_resources.py --run results/runs/zinc-pilot-v1 --output results/pilot_resources.json

# Full grids, after pilot review and final protocol/resource planning.
python -m experimentation.cli run --config replication --seed-count 24 --run-id synthetic-production-v1 --workers 3
python -m experimentation.cli run --config zinc --seed-count 24 --run-id zinc-production-v1 --workers 3

python -m unittest discover -s tests
```

For CPU-only import dependencies, install Torch from its CPU wheel index before
installing the optional project extra. `--data-root` and `--master-seed` are
available on `run`; changing either the resolved dataset identity or master seed
requires a fresh compatible run. Numeric seed ranges remain shard indices.

## Artifacts and completion checks

Each result links to two gzipped JSON files in `results/graph_records/`: one
shared graph-pair record per cell and one diagnostic file per workflow. Files
include topology/source hashes, original and perturbed edges, descriptors,
actual edits, no-op reasons, stream seeds, individual distances, and applicable
MMD components. Original graph records plus perturbation metadata make the
sample recoverable without inferring it from a hash.

MMD contributions are signed, sample-dependent decompositions whose average is
the empirical MMD². They are not independent graph distances. Runtime and peak
memory describe the workflow computation; `diagnostic_seconds` measures the
additional workflow diagnostic calculation. Total wall time also includes
graph generation, graph-record construction, serialization, and scheduling.

The parent process publishes sidecars atomically before appending a result row.
Resume validates checksums, removes successful/skipped rows with missing or
corrupt sidecars, and recomputes them without duplicate keys. Failed cells are
retained until `--rerun-failed`. Old schema rows and incompatible dataset,
master-seed, workflow, or implementation-code versions are rejected. Merging
corrected shards also copies and verifies their sidecars; historical and
corrected protocols cannot be merged together.

Each run saves resolved configuration, workflow parameters, library versions,
a code fingerprint on every row, and a package source snapshot. Code snapshots
from run start are preserved if files change while a job is active. The sanity report checks
grid completeness, hashes, graph pairing, unexpected stream reuse, edit counts,
zero-alpha controls, finite scores, the GraphStats MMD bound, and reconstruction
of aggregate scores. It deliberately does not require every metric to increase.

Granular analysis accepts synthetic and ZINC results, with arbitrary complete
alpha grids and at least two replicates. It adds no hypothesis tests. The final
inferential protocol remains a separate scientific deliverable: eliminating
seed collisions does not certify normality, symmetry, adequate power, or
population-level generalization.
