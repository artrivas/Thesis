# Failure Map: Explaining *Why* a Cell Behaves as It Does

The failure map turns the `(dataset × perturbation)` grid into an **explanation
artifact**. Each cell is labeled with a *diagnosed cause*, derived from logged
metadata and scores, so a reader can tell **why** a hypothesis succeeded or failed
in that cell — not merely read off a score. It is produced as both an SVG
(`figure_6_failure_map.svg`) and a machine-readable `failure_map.csv`.

## The five causes (in precedence order)

A cell is assigned exactly one cause; earlier causes win when several apply.

1. **`inapplicable`** — no successful rows in the cell (it was skipped). Should be
   rare now that `community_weakening` detects communities instead of skipping
   (see `community_detection.md`).

2. **`perturbation_starved`** — `alpha > 0` but almost nothing was actually
   edited. Detected when the **maximum** cell-mean `edit_distance_raw` over
   `alpha > 0` stays below `EDIT_STARVED_MAX_EDITS = 1.0` (fewer than one edited
   edge even at the largest budget). The flat scores here are *not* the method's
   fault — there was no structural change to detect.

3. **`method_blind`** — edits genuinely happened, but the **best** workflow's
   score stayed flat (best `sensitivity < METHOD_BLIND_SENSITIVITY = 0.30`). This
   is the diagnosis that actually indicts a method: real structure changed and it
   did not respond.

4. **`unstable`** — the best workflow responds but is **non-monotone or noisy**
   across seeds (best `monotonicity > 0.30` violation fraction, or best seed
   `robustness_cv > 0.35`).

5. **`ok`** — edits happened, the best workflow is sensitive, monotone, and
   stable across seeds.

The precedence is what makes the map informative: `perturbation_starved` is
checked *before* `method_blind` so that a cell where nothing was edited is never
mistaken for a blind method. Likewise `method_blind` precedes `unstable`: a
method that does not respond at all is reported as blind rather than unstable.

## Worked example: `triangle_deletion` on Erdős–Rényi

`triangle_deletion` spends its budget by removing edges that belong to triangles.
An Erdős–Rényi graph at the densities used here has **very few triangles**, so the
perturbation runs out of triangle edges almost immediately: `triangles_affected`
and `edges_removed` stay near zero, and therefore so does `edit_distance_raw` — at
*every* `alpha`. The map labels this cell **`perturbation_starved`**, with a note
like `max mean edits at alpha>0 = 0.00 (< 1.0)`.

This is the crucial interpretive point: the workflows' flat scores on this cell
are **correct** — there was essentially no structural change to detect. Without
the failure map, that flatness looks identical to `method_blind` (a real failure
of the method). The map separates "the method can't see it" from "there was
nothing to see", which is exactly the kind of explanation the experiment needs to
defend or reject a hypothesis. The same starvation is expected for
`triangle_deletion` on SBM when within-block triangles are scarce.

Contrast with SBM + `community_weakening` (`label_source = ground_truth`): real
mesoscopic structure is removed, edits are plentiful, and a community-sensitive
workflow should land in `ok`. A community-*insensitive* workflow on the same cell
would instead be flagged `method_blind` — a genuine, reportable blindness.

## Columns of `failure_map.csv`

`dataset, perturbation, cause, mean_edit_distance_raw, max_edit_distance_raw,
best_workflow, best_sensitivity, monotonicity, robustness_cv, note`.

`best_*` refer to the workflow with the highest sensitivity in that cell; `note`
is a short human-readable justification of the assigned cause.

## Relationship to the seed band (figure 1)

The `unstable` cause is the tabular counterpart of figure 1's per-seed dispersion
band: a cell whose alpha-vs-score curve fails to clear its own mean ± std / 95%
bootstrap band over seeds is exactly the kind of cell that gets flagged `unstable`
(high CV) or `method_blind` (flat). The band is the visual argument; the failure
map is the machine-readable verdict.

## Tests

`tests/test_failure_map.py` builds synthetic rows that trigger each cause —
`ok`, `perturbation_starved` (including the triangle_deletion-on-ER example),
`method_blind`, `unstable`, `inapplicable` — and asserts the produced label, plus
that the SVG renders.
