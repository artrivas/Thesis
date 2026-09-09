# Real Datasets: IMDB-BINARY via the TUDataset Loader

## Why IMDB-BINARY

The synthetic families (ER, SBM, BA) are where the protocol has *ground truth*:
we know exactly what structure was planted and perturbed. Real data plays a
different, complementary role — it tests the **robustness** of the synthetic
conclusions on graphs we did not design, **not** ground-truth recovery.

IMDB-BINARY is the best fit for this unlabeled, structure-only pipeline:

- **Unlabeled** — node features are absent, so the workflows operate purely on
  structure, exactly as on the synthetic families (WL falls back to degree
  labels; no node-attribute machinery is needed).
- **Triangle-rich** — ego-network co-appearance graphs are dense and highly
  clustered, so the triangle and clustering perturbations have budget to spend
  (unlike triangle_deletion on ER — see `failure_map.md`).
- **Real community structure** — genre/actor ego-networks have genuine
  mesoscopic structure, so `community_weakening` with *detected* communities is
  meaningful here (IMDB-BINARY has no planted partition, so `label_source =
  detected`; see `community_detection.md`).

## Integration: a dataset family, nothing else changes

The loader builds the repo's own `Graph` objects, so IMDB-BINARY enters the grid
as a dataset family `imdb_binary` and **every** downstream component applies
unchanged: all perturbations, all four workflows, the edit-distance ground truth,
the seed band, and the failure map. `generate_graph_distribution` dispatches to
the loader when the family is real (or `data_root` is set); a seed-dependent
subsample of `num_graphs` graphs gives across-seed replication variation.

```
python -m experimentation.cli run --config imdb --workers $(nproc) --evaluate --figures
```

## Getting the data (manual step)

The development sandbox cannot reach the dataset host (403; only github/pypi are
reachable). On a machine with open internet (the Lightning AI studio):

```
python scripts/fetch_imdb_binary.py        # downloads + unzips into src/data/IMDB-BINARY/
```

The script uses only the standard library. The real dataset is **not** committed
(`src/.gitignore` ignores `data/`); only the tiny TU fixture under
`tests/fixtures/TINYTU/` is tracked, and the loader is unit-tested against it.

## TU text format

Files in `<data_root>/IMDB-BINARY/`:

- `IMDB-BINARY_A.txt` — `i, j` edges, 1-indexed **global** node ids (undirected
  edges appear in both directions);
- `IMDB-BINARY_graph_indicator.txt` — graph id per global node;
- `IMDB-BINARY_graph_labels.txt` — label per graph;
- `IMDB-BINARY_node_labels.txt` — absent for IMDB-BINARY (unlabeled).

The loader groups global nodes by graph, reindexes each graph to 0-based local
ids, and attaches `graph_label` (and `node_labels` when present) to metadata.

## Variable graph sizes: bandwidth & normalization sensitivity

The synthetic defaults were tuned for `n = 50` fixed-size graphs. IMDB-BINARY
graphs vary widely (≈12–130+ nodes), which interacts with two design choices:

- **MMD bandwidth (`StructuralStatisticsMMD`, default `bandwidth = 10`).** The
  structural feature vector contains size-dependent entries (node/edge/triangle
  counts) whose scale grows with `n`. With heterogeneous sizes a fixed RBF
  bandwidth can either saturate (all pairs look maximally different) or collapse
  (all pairs look identical). The recommended remedy is a **median-heuristic
  auto-bandwidth**: set `bandwidth` to the median pairwise distance of the pooled
  feature vectors for the comparison. `workflows.median_heuristic_bandwidth` is
  provided for this; instantiate `StructuralStatisticsMMDWorkflow(bandwidth=...)`
  accordingly when running on real data. (The default is left unchanged so
  synthetic results stay reproducible.) `rbf_kernel_is_nearly_constant` can be
  used to detect a collapsed kernel.
- **NetLSD normalization (`normalization = "empty"`, divides by `n`).** The
  empty-graph normalization makes heat traces comparable across sizes, which is
  exactly why it matters more here than on fixed-`n` synthetic data. It is the
  right default for IMDB-BINARY; `"none"` would let raw size dominate the L2
  distance between mean signatures. Note also that the exact full-spectrum
  eigendecomposition is `O(n^3)` per graph (Jacobi fallback when torch is
  absent), so large real graphs are the runtime bottleneck — another reason the
  CPU-parallel runner (`parallelism.md`) matters.

## Real vs synthetic framing

- **Synthetic** = controlled ground truth: validates *whether and how* a workflow
  detects a known, parameterized change (sensitivity, monotonicity, edit-distance
  correlation, failure causes).
- **Real (IMDB-BINARY)** = robustness check: do the rankings and behaviors found
  on synthetic data **survive** on messy, unlabeled, variable-size real graphs?
  There is no planted truth to recover here; the value is external validity.

## Tests

`tests/test_real_datasets.py`: loads the TINYTU fixture (triangle / path /
single-edge graphs) with correct structure and labels; a missing dataset raises
an actionable error; the real family flows through `generate_graph_distribution`
and a full `run_experiment` (detected communities, edit distances) unchanged.
