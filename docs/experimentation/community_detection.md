# Detected-Community Fallback for `community_weakening`

## Motivation

`community_weakening` rewires intra-community edges into inter-community edges to
erode mesoscopic structure. It previously required a planted partition
(`community_labels` in metadata) and **skipped** whenever one was absent — so it
only ever ran on the SBM family and produced empty rows for ER and BA. That left
a hole in the failure analysis: a skipped cell tells you nothing about whether a
workflow is blind to community structure.

The perturbation now **always applies**. When a ground-truth partition is present
it is used; otherwise communities are **detected** on the graph. The metadata
records which path was taken via `label_source ∈ {ground_truth, detected}`, and
this is propagated into the result CSV as the `label_source` column.

## Algorithm: greedy modularity maximization (Clauset–Newman–Moore)

The detector is a dependency-free, deterministic, agglomerative maximization of
Newman's modularity (`detect_communities` in `perturbations.py`):

1. Every node starts in its own community.
2. At each step, consider every pair of **adjacent** communities `c, d` and
   compute the modularity gain of merging them:

   ```
   dQ(c, d) = B_cd / m  -  (D_c * D_d) / (2 * m^2)
   ```

   where `B_cd` is the number of edges between the communities, `D_c` is the
   total degree of community `c`, and `m` is the number of edges.
3. Merge the pair with the largest **positive** gain. Stop when no merge improves
   modularity. Ties break toward the lowest community ids, so the partition is
   fully deterministic and reproducible across machines and shards.

Only adjacent community pairs are considered, since merging non-adjacent
communities always has `dQ < 0`. Community ids are remapped to a contiguous
`0..k-1` range. Edgeless graphs return all-singleton labels (no intra edges to
rewire). Complexity is comfortably within budget for the `n≈50` synthetic graphs
and the variable-size IMDB-BINARY graphs.

`detect_communities` recovers a planted two-block partition (verified on two
6-cliques joined by a single bridge) — see
`tests/test_perturbations.py::test_detect_communities_recovers_planted_partition`.

## `ground_truth` vs `detected`

- **`ground_truth`** — the SBM family carries its planted block assignment in
  `community_labels`. Weakening removes *real* mesoscopic structure, so a
  community-sensitive workflow should respond as `alpha` rises. This is the
  positive control and matches the previous behavior exactly.
- **`detected`** — ER and BA have no planted partition. The detector returns the
  modularity-optimal partition *of that particular graph*, and weakening then
  rewires those detected intra-community edges.

## The ER negative-control interpretation

An Erdős–Rényi graph has **no community structure** — edges are independent. Any
partition the detector returns is an artifact of finite-size noise, not signal.
Weakening a *noise* partition does not remove any real mesoscopic structure, so
**low sensitivity on ER `community_weakening` is the correct, expected outcome**,
not a failure of the method. This is exactly why the cell is labeled a negative
control: it establishes the floor against which the SBM (`ground_truth`) response
is read. Reporting a `detected` row (instead of skipping) makes this negative
control visible and lets the failure map distinguish "method is blind" from
"there was nothing to detect".

BA sits in between: preferential-attachment graphs have weak, hub-induced
community structure, so a small `detected` response is plausible but should be
far weaker than SBM's `ground_truth` response.

## Result-schema impact

- New metadata keys on `community_weakening` results: `label_source` and
  `num_communities`.
- New CSV column `label_source` (empty for non-community perturbations),
  propagated through `_summarize_perturbations` → `_run_workflow_grid`.

## Tests

`tests/test_perturbations.py`:

- SBM uses `ground_truth` and matches the old rewiring behavior;
- ER and BA now produce non-skipped rows tagged `detected`;
- the detector recovers a known planted two-community graph;
- edgeless graphs are handled.
