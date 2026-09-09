# Interaction-effect findings (fresh analysis, run `2026-07-03_merged`)

**This file is new** — it does not modify or reuse
[`../hero_analysis_notes.md`](../hero_analysis_notes.md), which documents a
different, earlier pass (main-effect "cleanest agreement" / "clearest
divergence" figures). This file is the output of an independent re-analysis
requested to specifically hunt for **interaction effects** (workflow x
dataset x perturbation), starting only from the raw per-seed rows in
`../../results/results.csv` — no cached plots, evaluation summaries, or
conclusions from the earlier pass were used as inputs.

## Run verification (redone independently)

- `results.csv`: 20,328 rows, one row per (dataset, perturbation, alpha,
  seed, workflow) — this **is** the lowest-level logged data; there is no
  finer per-graph-pair breakdown in this run (`graph_count` records how many
  paired graphs went into each row's score, but individual pair scores are
  not separately logged — see `docs/experimentation/results_schema.md`).
- All 96 (4 workflows x 4 datasets x 6 perturbations) cells confirmed present
  with `status=success`. Synthetic datasets (ER, SBM, BA): 24 seeds x 11
  alphas = 264 rows/cell. IMDB-BINARY: 5 seeds x 11 alphas = 55 rows/cell.
  **No crashed/partial cells** — nothing is missing for the analysis below.
- IMDB-BINARY graphs vary substantially in size (12-84 nodes, 0-1485 edges)
  vs. fixed 50-node synthetic graphs — relevant to findings #1 and #3 below.
- Caveat carried through every finding involving IMDB-BINARY: only **5
  seeds**, vs. 24 for the synthetic datasets. Take IMDB-specific numbers as
  suggestive, not as statistically equivalent in confidence to the synthetic
  ones.

## Ranked findings

### 1. GraphStats+MMD gives the opposite verdict on synthetic vs. real graphs (HERO FIGURE)

**Data slice:** workflow `structural_statistics_mmd`, perturbation
`triangle_insertion`, all four datasets, all alphas, all seeds.

**What's there:** the per-alpha mean score rises to a peak around
alpha=0.2-0.3 and then **monotonically declines** through alpha=1.0 on
every synthetic dataset (BA: 1.617 -> 1.361; ER: 0.606 -> 0.456; SBM:
0.708 -> 0.546 — all peak-then-fall). On IMDB-BINARY the same workflow
instead rises smoothly and **monotonically** from 0 to 0.085 with no
reversal. Recomputed Spearman(alpha, score): BA = -0.048, ER = -0.018,
SBM = +0.072 (~0), IMDB = **+0.970**.

**Why non-obvious:** a naive reader seeing a metric fail (near-zero or
negative rank correlation) on 3 of 4 datasets would conclude the metric is
broken for this perturbation, full stop. Instead it recovers completely on
real data — the failure is specific to the synthetic generative structure
(triangle insertion into graphs with a narrow, homogeneous triangle-count
distribution apparently makes the MMD witness non-injective past a point),
not an intrinsic flaw of GraphStats+MMD. This complicates any
recommendation made purely from synthetic benchmarks.

**Visualization:** line chart, x = alpha, y = normalized distribution_score,
one line per dataset (4 lines), same workflow. This is exactly
`hero_1_triangle_insertion_synthetic_vs_real.png/.svg` in this folder.
Takeaway annotated on-figure: *"It REVERSES on every synthetic graph (ER,
BA, SBM) but rises cleanly on real IMDB-BINARY data — the 'failure' is a
synthetic-data artifact, not a flaw in the metric itself."*

**Robustness:** the synthetic reversal is consistent across 24 seeds each
(BA/ER/SBM) with tight ribbons (seed CV 2.1-6.3%) — this is not seed noise,
it is a systematic, low-variance effect. The IMDB recovery is only 5 seeds;
the qualitative shape (monotonic rise, no peak) is unambiguous, but treat
the exact IMDB rho=0.97 as approximate.

### 2. Ground-truth community labels are not what makes community weakening detectable (HERO FIGURE)

**Data slice:** perturbation `community_weakening`, all four workflows, all
four datasets.

**What's there:** sensitivity (Spearman rho) by dataset, averaged is
misleading — the raw per-workflow numbers: ER (detected labels, no ground
truth) = 0.30-0.49 across the four workflows; **SBM (ground truth) =
0.52-0.89**; **BA (detected, no ground truth) = 0.96-0.99**; IMDB (detected,
real) = 0.74-0.95. BA's purely-detected partition beats SBM's engineered
ground-truth partition for 3 of the 4 workflows (GraphStats+MMD, NetLSD,
Diversity Curves) — only WL+MMD ranks SBM (0.518) below both BA (0.983) and
IMDB (0.744), and even there SBM isn't the top performer.

**Why non-obvious:** the intuitive story is "ground truth communities
(SBM) should give the cleanest signal; detected communities (BA, ER, IMDB)
are noisier proxies and should underperform." The data says the opposite for
the dataset that matters most here: BA, which has **no designed community
structure at all**, produces a stronger and more consistent signal than
SBM's literal ground truth. What predicts signal strength is not "were
labels given," it's whether the graph has *any* exploitable structural
heterogeneity: BA's preferential attachment creates hub-dominated, highly
modular structure that Clauset-Newman-Moore detection locks onto reliably;
ER's uniform randomness has none, so detected communities there are close
to noise regardless of the metric used on top of them.

**Visualization:** grouped bar chart, x = dataset (ordered ER -> SBM -> BA
-> IMDB to mirror "no structure -> planted -> emergent -> real"), bars
grouped/colored by workflow, y = sensitivity. This is exactly
`hero_2_community_weakening_ground_truth_myth.png/.svg` in this folder.
Takeaway annotated on-figure: *"SBM's GROUND-TRUTH partition is beaten by
BA's purely DETECTED one for 3 of 4 workflows — only structureless ER fails,
ground truth or not."*

**Robustness:** ER/SBM/BA numbers are each over 24 seeds; the BA > SBM gap is
large (0.96-0.99 vs 0.52-0.89, no overlap for 3 of 4 workflows) and holds
workflow-by-workflow, not just on average — this is not an artifact of
averaging across a mix of good and bad cells.

### 3. ER is a uniformly hard substrate for mesoscopic/global perturbations — across every workflow, not just one

**Data slice:** perturbations `community_weakening` and `hub_modification`,
all four workflows, ER vs. the other three datasets.

**What's there:** on both perturbations, ER produces the lowest sensitivity
of the four datasets for **all four workflows simultaneously**
(community_weakening: ER 0.30-0.49 vs. 0.52-0.99 elsewhere; hub_modification:
ER 0.39-0.51 vs. 0.63-0.91 elsewhere) and the highest seed dispersion
(hub_modification seed CV on ER: 0.41-0.61, several times every other
dataset's CV for the same perturbation).

**Why non-obvious:** if a perturbation failed for only one workflow on ER,
you'd blame the workflow. Here it fails for *all four*, which points instead
to a dataset property: ER graphs have no hubs and no communities to begin
with (uniform degree distribution, no planted or emergent modularity), so
"hub modification" and "community weakening" are, in a real sense, acting on
structure that barely exists. This reframes ER's poor showing from "these
metrics are bad at detecting X" to "ER is close to a null substrate for
perturbations that presuppose meso/macro structure" — an important
caveat for how ER should be used (or not used) as a benchmark for these two
perturbation types specifically.

**Visualization:** small-multiple or grouped bar (dataset x perturbation,
faceted or grouped), y = sensitivity, with ER's bars visually called out
(e.g., outlined or grayed) across both perturbation panels to make the
cross-perturbation, cross-workflow consistency legible at a glance.

**Robustness:** 24 seeds for ER and the two comparison datasets it's
consistently below (BA, SBM); effect holds for every one of the four
workflows without exception, which is what makes this a dataset-level (not
workflow-level) claim.

### 4. The same low-noise number means different things on synthetic vs. real data: "confidently wrong" vs. "correctly uncertain"

**Data slice:** workflow `structural_statistics_mmd` (GraphStats+MMD),
compared across perturbation x dataset cells, using both monotonicity
violation and seed CV together (not either alone).

**What's there:** on synthetic triangle/edge-insertion perturbations
(BA edge_insertion, BA/ER/SBM triangle_deletion, BA triangle_insertion),
GraphStats+MMD has **low seed noise (CV 2.1-4.3%) but high monotonicity
violation (30-70% of alpha-steps move the wrong way)** — i.e. it is
reproducibly, confidently non-monotonic; the seed variance alone would make
it look like a *reliable* metric. On IMDB hub_modification/
community_weakening and BA hub_modification, the same workflow instead shows
**high seed noise (CV 16-24%) but high sensitivity (rho 0.63-0.95)** — noisy,
but trending correctly.

**Why non-obvious:** it's tempting to use seed CV alone as a proxy for
"trustworthiness." This shows that's wrong in both directions: low CV can
mean "confidently biased," and high CV can mean "correctly uncertain." A
metric-selection rule that only checks seed variance would keep the
synthetic-triangle failure modes (they look stable) and might discard the
noisier-but-correct real-data behavior.

**Visualization:** scatter plot, x = monotonicity violation fraction, y =
seed CV, one point per (workflow, dataset, perturbation) cell, colored by
workflow; annotate the two quadrants of interest ("confidently wrong" =
low-CV/high-violation corner; "correctly uncertain" = high-CV/high-
sensitivity, sized or shaped by sensitivity). One-line takeaway: *"Low seed
noise is not the same as being right."*

**Robustness:** the synthetic "confidently wrong" cells are all 24-seed
estimates with small CVs (tight confidence), so the low variance itself is
well-supported. The "correctly uncertain" IMDB cells are only 5 seeds —
flag that the CV=16-24% there is itself imprecisely estimated, though the
qualitative point (noisier than the synthetic cells, still directionally
right) is robust to that.

### 5. Hub-modification's ceiling is set by the dataset/perturbation budget, not by which metric is measuring it

**Data slice:** perturbation `hub_modification`, all four workflows, all
four datasets — comparing the alpha at which each workflow's per-alpha mean
score stops changing (saturation onset).

**What's there:** within a given dataset, all four workflows saturate at
essentially the same alpha: ER and SBM both saturate at alpha=0.4 for every
workflow; BA saturates at alpha=0.6 for every workflow; IMDB saturates at
alpha=0.4 for GraphStats+MMD and alpha=0.6 for the other three. The
saturation point moves with the *dataset*, not with the *workflow*.

**Why non-obvious:** the natural assumption is that a "weaker" or "less
sensitive" metric saturates earlier because it runs out of resolving power
first. Here, four methodologically unrelated workflows (an MMD-based
descriptor test, a WL-kernel MMD test, a spectral heat-trace distance, and a
diversity-curve distance) all hit their ceiling at the *same* alpha for a
given dataset. That is much better explained by the perturbation generator
itself running out of eligible hub edges to modify at a fixed alpha for that
graph family, than by any property of the four metrics. It means
"hub_modification looks saturated" is a statement about the dataset/budget
design, not a knock against whichever metric is being reported.

**Visualization:** a small table or dot-plot of saturation-onset alpha,
rows = dataset, columns = workflow, values annotated directly (values will
visually line up almost perfectly within each row) — the "no variation
across columns" pattern *is* the finding, so a plain annotated grid reads
faster than a line chart here.

**Robustness:** the plateau values themselves are exact matches (differences
<1% of the final value, per-dataset, for all four workflows) across 24 seeds
for the synthetic datasets — this is a strong, low-ambiguity effect. IMDB's
minor exception (GraphStats+MMD saturating at 0.4 vs. 0.6 for the rest) is
based on 5 seeds and is the one cell in this finding worth re-checking with
more seeds before leaning on it.

## What I checked but did NOT promote to a headline finding

I also tested whether the "most sensitive workflow" ranking among
{WL+MMD, NetLSD, Diversity Curves} (excluding GraphStats+MMD, which is
last on every dataset by a wide margin) flips by dataset. Averaged across
all 6 perturbations it looks like it flips (WL+MMD leads on BA/ER, NetLSD
leads on SBM/IMDB) — but checking head-to-head per perturbation, NetLSD
actually wins 4 of 6 individual perturbations *on BA* despite WL+MMD having
the higher unweighted average there (driven by one large margin on
community_weakening), and the mean-level gaps are mostly under 0.03. I'm not
presenting this as a finding — it's much weaker and more sensitive to
averaging choices than #1-#5 above, and I'd rather flag that I looked and
found it inconclusive than dress it up as a fourth ranking-flip result.

## Figure files in this folder

- `hero_1_triangle_insertion_synthetic_vs_real.png` / `.svg` — finding #1.
- `hero_2_community_weakening_ground_truth_myth.png` / `.svg` — finding #2.
- Generated by [`scripts/generate_interaction_hero_figures.py`](../../../../scripts/generate_interaction_hero_figures.py),
  reading only `results/results.csv` from this run.
