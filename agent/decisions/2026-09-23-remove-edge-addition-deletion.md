---
title: Remove the `edge_addition_deletion` perturbation
date: 2026-09-23
time_utc: 17:04 UTC
status: done
---

## Decision

Remove the `edge_addition_deletion` perturbation type from the codebase. The
user requested this removal, stating it is deprecated and no longer used.

## Context

`edge_addition_deletion` was one of the perturbation strategies implemented in
[`src/experimentation/perturbations.py`](../../src/experimentation/perturbations.py).
It combined a random edge removal pass with a random edge insertion pass
(mixed direction), dispatched from `perturb_graph()`.

It was already absent from `DEFAULT_PERTURBATION_METHODS` in
[`src/experimentation/config.py`](../../src/experimentation/config.py), and it
was already listed in `EXCLUDED_PERTURBATIONS` in
[`src/experimentation/dashboard.py`](../../src/experimentation/dashboard.py),
meaning it had already been phased out of active experiment configs and was
being filtered out of aggregate dashboard views before this change.

Historical run outputs under `results/runs/*/code_snapshot/` still reference
it — those are frozen snapshots of past runs and were left untouched.

## What changed

- [`src/experimentation/perturbations.py`](../../src/experimentation/perturbations.py):
  removed the `edge_addition_deletion` dispatch branch in `perturb_graph()`
  and deleted the `_edge_addition_deletion()` function. Calling
  `perturb_graph(..., "edge_addition_deletion", ...)` now raises
  `ValueError: Unknown perturbation type: edge_addition_deletion`.
- [`docs/experimentation/full_fidelity_implementation_netlsd_diversity_wl.md`](../../docs/experimentation/full_fidelity_implementation_netlsd_diversity_wl.md):
  dropped it from the "legacy mixed perturbations" list and added a pointer to
  this decision record.
- [`tests/test_perturbations.py`](../../tests/test_perturbations.py): the two
  tests that called `perturb_graph(..., "edge_addition_deletion", ...)` as a
  generic exercise of the alpha/budget logic were switched to use
  `edge_insertion` instead (equivalent coverage, still-supported type).
- [`tests/test_figures.py`](../../tests/test_figures.py): `tiny_figure_config()`
  built a `PerturbationConfig` that actually drove the perturbation pipeline
  with `edge_addition_deletion`; switched to `edge_insertion` so the figures
  pipeline test keeps exercising a real perturbation end to end.

## What was deliberately left alone

These modules reference the string `"edge_addition_deletion"` only as a label
for **historical result data**, not as a live code path that generates
perturbations. They were left unchanged so that analysis/dashboard tooling
still displays and filters old run data correctly:

- `src/experimentation/dashboard.py` — `EXCLUDED_PERTURBATIONS` set.
- `src/experimentation/evaluation.py` — `PERTURBATION_GRANULARITY` map.
- `src/experimentation/figures.py` — `_short_label()` map.
- `tests/test_dashboard.py`, `tests/test_evaluation.py`, `tests/test_runner.py`
  — fixtures emulating historical CSV rows.

If the user later wants historical data support dropped too, these are the
remaining places to touch.

## Verification

Ran the full test suite after the change:

```
PYTHONPATH=src python -m unittest discover -s tests
```

Result: `Ran 165 tests ... OK (skipped=15)` (skips are pre-existing, for
optional analysis dependencies not installed in this environment).
