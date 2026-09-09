# Validating `alpha`: a Nominal Control, Defended Empirically

## What `alpha` is — and is not

`alpha ∈ [0, 1]` is a **nominal** perturbation strength: it sets the *expected*
number of edge edits (e.g. `edge_deletion` removes `⌊alpha · |E|⌋` edges). It is
**not** itself a structural distance. The actual edits are drawn at random, so for
any single graph `alpha` only controls the *budget*, not the realized change. A
sceptic can therefore object: *"any rise in a workflow's score with `alpha` could
be an artifact of randomness, not of a real, controlled structural change."*

This module answers that objection with two independent lines of evidence.

## Defense 1 — replication over many seeds (it is not luck)

Each `(dataset, perturbation, alpha)` score is computed over many seeds (see
`seed_sweep.md`). Replication turns each score into a **distribution over noise
realizations**, which lets us separate signal from luck:

- **Coefficient of variation (CV)** over seed-level means must be low — the score
  at a given `alpha` is stable across noise draws.
- **Kendall-tau** ranking stability across seeds must be high — the *ordering* of
  workflows does not flip between noise draws.
- The **alpha-vs-score curve must rise above the per-seed dispersion band**
  (`figure_1`, mean ± std and a bootstrap CI). A trend that clears the noise band
  cannot be explained by randomness.

If a trend were "just randomness", CV would be large, tau would be unstable, and
the curve would sit inside its own noise band. Many seeds is what makes those
diagnostics meaningful — a single seed gives CV = 0 and tau = 1 by construction
(degenerate), which is exactly the artifact this redesign removes.

## Defense 2 — monotone correlation with an edit-distance ground truth

Replication shows the response is *stable*; it does not show it tracks *real
structural change*. For that we compare each workflow's score against an exact,
per-pair **edit distance** computed from the logged perturbation operations
(`ground_truth.py`), never the NP-hard graph edit distance.

- **Raw edit distance** — the number of edited edges, i.e. `|E(G) △ E(G^α)|`.
  Under the paired protocol the node correspondence is known, so this is the
  exact edit distance under the identity node map.
- **Importance-weighted edit distance** — each edited edge is weighted by a
  topology importance score on the **original** graph (default: a Brandes
  betweenness product, `1 + cb[u]·cb[v]`, which is defined for both removed and
  added edges and ranks hub/bridge edits above peripheral edits). The weight
  function is pluggable; literal edge betweenness is also provided.

The evaluation reports, per `(workflow, dataset, perturbation)`:

- `edit_distance_validation` — Spearman correlation between
  `distribution_score` and `edit_distance_weighted`;
- `paired_edit_distance_validation` — Spearman correlation between
  `paired_score` and `edit_distance_weighted`.

A high positive correlation means the workflow's score grows with *how much
important structure was actually edited* — not merely with the nominal dial. That
is the sense in which `alpha` is **validated**: it is a faithful proxy for a real,
importance-weighted structural distance, established empirically rather than
assumed.

## Why weight by importance

Raw count treats every edit equally, but deleting a bridge between two
communities changes a graph far more than deleting one redundant edge inside a
clique. Weighting by betweenness makes the ground-truth distance reflect
*structural* impact, so the correlation tests whether a workflow responds to
*meaningful* change rather than to bookkeeping. The barbell test
(`tests/test_ground_truth.py`) shows the weighting ranks a bridge removal above a
peripheral removal while the raw count cannot tell them apart.

## A caution about paired analysis

`paired_score` and `paired_edit_distance_validation` are **diagnostics available
only under the synthetic protocol**, where every `G_i` has a constructed
counterpart `G_i^α`. They are **not** distribution distances: real-world graph
populations have **no canonical pairing** between an "original" and a "perturbed"
graph, so a paired distance cannot be computed there. Paired quantities are used
here to *explain* and *validate* behavior on synthetic data; the headline,
transferable metric remains the unpaired distribution-level separation
(`distribution_score`), which is well-defined for real populations too.

## Tests

`tests/test_ground_truth.py`:

- raw edit distance equals known counts on hand-built perturbations and matches
  the logged `edges_added` / `edges_removed`;
- importance weighting changes the ordering of a hub/bridge edit vs a leaf edit
  while the raw count stays equal;
- cell-mean edit distance is 0 at `alpha = 0` and increases with `alpha`.
