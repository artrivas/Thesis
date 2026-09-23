---
title: Remove the `triangle_injection_removal` perturbation
date: 2026-09-23
time_utc: 17:11 UTC
status: done
---

## Decision

Remove the `triangle_injection_removal` perturbation type from the codebase,
following the same reasoning and treatment as
[[2026-09-23-remove-edge-addition-deletion]]: deprecated, no longer used, the
user asked for it to be removed in the same session, immediately after the
`edge_addition_deletion` removal.

## Context

`triangle_injection_removal` was the triangle-family counterpart to
`edge_addition_deletion`: it closed open wedges (injection) and broke existing
triangle edges (removal) in the same call, dispatched from `perturb_graph()`
in [`src/experimentation/perturbations.py`](../../src/experimentation/perturbations.py).

Like `edge_addition_deletion`, it was already absent from
`DEFAULT_PERTURBATION_METHODS` in
[`src/experimentation/config.py`](../../src/experimentation/config.py) and
already listed in `EXCLUDED_PERTURBATIONS` in
[`src/experimentation/dashboard.py`](../../src/experimentation/dashboard.py).

## What changed

- [`src/experimentation/perturbations.py`](../../src/experimentation/perturbations.py):
  removed the `triangle_injection_removal` dispatch branch in `perturb_graph()`
  and deleted the `_triangle_injection_removal()` function. Calling
  `perturb_graph(..., "triangle_injection_removal", ...)` now raises
  `ValueError: Unknown perturbation type: triangle_injection_removal`.
- [`docs/experimentation/full_fidelity_implementation_netlsd_diversity_wl.md`](../../docs/experimentation/full_fidelity_implementation_netlsd_diversity_wl.md):
  removed the "legacy mixed perturbations" list entirely (it only ever held
  these two entries) and pointed to both decision records.

No test in `tests/` called `perturb_graph(..., "triangle_injection_removal", ...)`
directly, so no test needed updating to keep exercising a still-supported
perturbation type (unlike `edge_addition_deletion`, which required updating
`tests/test_perturbations.py` and `tests/test_figures.py`).

## What was deliberately left alone

Same rationale as [[2026-09-23-remove-edge-addition-deletion]] — these only
label **historical result data**, not a live generation path:

- `src/experimentation/dashboard.py` — `EXCLUDED_PERTURBATIONS` set.
- `src/experimentation/evaluation.py` — `PERTURBATION_GRANULARITY` map.
- `src/experimentation/figures.py` — `_short_label()` map.
- `tests/test_dashboard.py` — fixture emulating a historical CSV row
  (`test_aggregate_edge_triangle_perturbations_are_excluded`).

## Verification

Ran the full test suite after the change:

```
PYTHONPATH=src python -m unittest discover -s tests
```

Result: `Ran 165 tests ... OK (skipped=15)` (same pre-existing skips as before,
for optional analysis dependencies not installed in this environment).
