# Seed Sweep: One Knob for Replication Breadth

## The knob

Replication breadth is a single, explicit knob — not a hand-edited seed list.

- `seeds_from_count(n, base_seed=0)` → `(base_seed, base_seed+1, …, base_seed+n-1)`.
  Deterministic and machine-independent.
- `ExperimentConfig` accepts **either** an explicit `seeds` list **or** a
  `seed_count`. `ExperimentConfig.resolved_seeds()` resolves the effective list:
  - `seed_count` **takes precedence** when both are set;
  - an explicit `seeds` list is used when `seed_count` is `None`;
  - if **neither** is provided, it raises a clear error.

  > Contract: to force an explicit `seeds` list when building on a config that
  > already sets `seed_count` (e.g. `debug_config`), pass `seed_count=None` in
  > your `replace(...)`. Otherwise the inherited `seed_count` wins by precedence.

- Named configs: `debug_config` (small, `seed_count=2`) and `replication_config`
  (`seed_count=24`, in the 20–30 band). The CLI selects them with
  `--config {debug,full,replication,imdb}`, and `--seed-count N` overrides the
  breadth deterministically.

The **resolved** seed list is recorded in `run_manifest.json` (see
`traceability.md`), so a run's replication breadth is reproducible, and it is the
basis for `--seed-range` sharding (see `parallelism.md`). Because the list is
deterministic, the same `seed_count` always yields the same seeds and therefore
the same results — resume, re-runs, and shards are bit-identical, and shards are
non-overlapping by construction.

```
python -m experimentation.cli run --config replication --workers $(nproc) --evaluate --figures
python -m experimentation.cli run --config full --seed-count 30 --workers $(nproc)
```

## Why many seeds is the defense against "it's just randomness"

`alpha` is a *nominal* control: it sets the expected number of edits, but the
edits are random (see `alpha_validation.md`). A single seed gives one noise
realization — and the degenerate `CV = 0`, `tau = 1` we saw before, which proves
nothing. Replicating over many seeds turns each `(dataset, perturbation, alpha)`
score into a **distribution over noise realizations**, which is what makes the
robustness diagnostics meaningful:

- **Coefficient of variation (CV)** is computed over **seed-level means**; with
  many seeds it becomes non-degenerate and small CV means the score is stable
  across noise draws.
- **Kendall-tau** ranking stability is computed by comparing workflow rankings
  **across seeds**; it is only informative with ≥ 2 seeds and becomes a real
  stability measure as the seed count grows.
- **figure_1's per-seed band** (mean ± std and a bootstrap CI over seeds) is the
  visual form of the same evidence: an `alpha`-vs-score curve that **rises above
  its own noise band** cannot be explained by luck.

So `seed_count` maps directly onto the strength of the defense: more seeds →
tighter CV estimates, more reliable tau, and a narrower, more convincing band.
`seed_count = 24` (the replication default) is chosen to give stable CV/tau and a
readable band while keeping the CPU-parallel sweep tractable; `--seed-count 30`
pushes it to the top of the recommended range.

## How it ties the pieces together

- **Item 1 sharding** slices `resolved_seeds()` by index, so a 24- or 30-seed
  sweep can be split across Lightning machines and merged back to a result
  numerically identical to the unsharded run.
- **Item 4** consumes the many-seed rows to produce non-degenerate CV/tau and the
  figure_1 band, and the failure map's `unstable` cause flags cells whose curve
  fails to clear the band.
- **Item 5** records the resolved seeds in the manifest for traceability.

## Tests

`tests/test_seed_sweep.py`: `seeds_from_count` is deterministic and correct;
`seed_count` overrides `seeds`; missing-both raises; the debug and replication
configs resolve to the expected lists; `seed_count = 30` resolves to 30 seeds; a
`--seed-range` slice equals the corresponding sublist and disjoint shards
partition the list.
