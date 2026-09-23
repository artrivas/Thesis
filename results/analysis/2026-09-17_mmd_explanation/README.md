# Sensitivity of GraphStats and WL to structural perturbations

This report uses corrected results only: the BA, ER, and ZINC pilots and the separately labeled corrected SBM diagnostic probes. Each setting has three replicate samples of 100 graphs. The historical results are excluded. Correlations and comparisons are descriptive; no significance claims or new default configurations are selected.

The additions analysis also uses the previously generated corrected BA edge-insertion and triangle-insertion probes. The BA triangle-insertion probe reproduces the pilot setting; it is not additional independent evidence. The corrected evidence here does not cover every synthetic dataset–addition combination.

## What sensitivity means in this analysis

The user's hypothesis is that **GraphStats behaves poorly under structural additions**. To evaluate that claim, we need to distinguish three properties:

| Property | Question | What these results establish |
|---|---|---|
| Early score response | Does a small perturbation already produce a large fraction of the subsequent score range? | We measure the score at alpha 0.1 relative to the maximum of the mean curve. This is a descriptive shape measure, not statistical power. |
| Severity resolution | Does the score continue to distinguish increasing perturbation budgets, without plateauing or reversing? | We inspect all three replicate curves, peak-to-endpoint decline, and rank association with positive alpha. |
| Calibrated detection sensitivity | How reliably can a perturbation be detected at a fixed false-positive rate? | Not established by these plots; this requires independent unperturbed reference comparisons and a calibrated decision rule. |

A large initial response and poor later resolution can coexist. Also, a larger raw GraphStats score than a WL score would not establish greater sensitivity: their feature spaces and kernels have different scales. Alpha measures the intervention budget, not a universally valid structural distance. Monotonicity is useful for the thesis's severity-tracking objective, but is not a mathematical requirement of a distribution distance along every graph-edit path.

## Does GraphStats behave poorly under additions?

**The current evidence supports that hypothesis for severity resolution on BA graphs with the current raw descriptors and bandwidth 10. It does not support a general failure on every dataset.** Here, additions mean random edge insertion and edge insertion that closes an open wedge (triangle insertion).

![GraphStats sensitivity to edge and triangle insertion on corrected BA and ZINC results](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/analysis/2026-09-17_mmd_explanation/addition_sensitivity.png)

Thin lines show each replicate; thick lines show their mean. Each panel uses its own raw-score axis. All curves use the same GraphStats definition and bandwidth. No hypothesis tests are inferred from these three replicates.

| Dataset / addition | Score at alpha 0.1 / mean-curve peak | Alpha at mean peak | Peak-to-endpoint decrease | Median replicate Spearman rho, positive alpha |
|---|---:|---:|---:|---:|
| BA / random edges | 39.0% | 0.3 | 12.8% | -0.20 |
| BA / triangle closure | 57.8% | 0.3 | 16.3% | -0.44 |
| ZINC / random edges | 2.1% | 1.0 | 0.0% | 1.00 |
| ZINC / triangle closure | 4.4% | 0.9 | 0.08% | 0.99 |

For both BA additions, the mean score peaks after **29 added edges** and is lower after **97 added edges**. Thus a smaller endpoint score cannot be interpreted as fewer edits or a return toward the original graph in edit distance. This is a substantial ordering reversal for this experiment's severity objective. It is also not specific to triangle insertion: random edge insertion exhibits the same broad problem. Triangle closure produces the stronger early response and decline.

ZINC supplies a useful counterexample to a blanket failure claim. Its edge-insertion score increases in every replicate across the alpha grid. Its triangle-insertion mean has only a small endpoint reversal (0.08%), with strong positive ordering overall. These results suggest a **dataset–descriptor-scale–kernel interaction**, rather than an inherent inability of GraphStats to handle additions.

One relevant difference is the realized dose. At alpha 1, BA receives 97 edges per graph, whereas these ZINC samples receive 25.22 on average; at alpha 0.1 BA receives nine edges, while smaller ZINC graphs receive fewer. The same alpha therefore does not mean the same absolute displacement relative to bandwidth 10. Triangle formation and descriptor dispersion also differ between datasets, so graph size or edit count alone is not an isolated explanation. The bandwidth substitution below directly tests the kernel-scale mechanism on BA.

There is also useful selectivity within BA. Starting from the same graphs and ending with the same 194 edges, random insertion produces about 96.26 triangles per graph, while triangle closure produces about 180.86 (originally 18.67). GraphStats has an explicit triangle-count coordinate, so a stronger early reaction to triangle closure is consistent with its representation. However, the endpoint MMD scores are approximately 1.349 and 1.332, respectively: that ordering does not preserve the ordering of triangle increases. MMD compares the full descriptor distributions; it is not a triangle counter or an edit-distance surrogate.

**A defensible thesis hypothesis is:** “With unstandardized structural descriptors and a fixed RBF bandwidth of 10, sufficiently large addition-induced displacements can produce an early strong score response followed by saturation or reversal, reducing resolution of increasing perturbation severity.” The BA controls below support this mechanism. Its prevalence across ER, SBM, other graph sizes, and other bandwidths remains to be assessed with corrected runs. “GraphStats is insensitive to additions” would misdescribe the observed BA response.

## Both use MMD, but their kernels and representations differ

MMD is a framework, not a single fixed distance. The actual comparisons are:

| Workflow | Graph representation | Kernel | Empirical score |
|---|---|---|---|
| GraphStats | Nine raw structural statistics | Gaussian, `exp(-||x-y||²/(2 sigma²))`, sigma=10 | `Kxx + Kyy - 2 Kxy` |
| WL | Degree labels and three neighborhood-refinement rounds, counted as histograms | Linear inner product | `||mean phi_original - mean phi_perturbed||²` |

The kernel determines the geometry of the distribution comparison. A Gaussian kernel compares local similarity in descriptor space; the linear WL score compares mean histogram counts. MMD's ability to distinguish distributions depends on its kernel. In particular, the implemented linear comparison is not a general detector of changes to higher moments of the WL feature-vector distribution. [Gretton et al., 2012](https://www.jmlr.org/papers/volume13/gretton12a/gretton12a.pdf).

The earlier description of WL as “conservative” is better expressed as a **more gradual relative score response** on the BA triangle-insertion path. It does not establish better false-positive control or universally lower detection sensitivity. The plots normalized to each curve's own maximum compare shape only.

## The sharp GraphStats response is bandwidth-dependent

For BA triangle insertion, at alpha 0.1 GraphStats has already reached **57.8% of the maximum of its mean curve**, while WL reaches **8.4%**. The plots below use the identical corrected graph pairs.

![Response shape and bandwidth](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/analysis/2026-09-17_mmd_explanation/bandwidth_response.png)

With sigma=10, descriptor separations of 10, 20, and 30 yield Gaussian similarities approximately 0.607, 0.135, and 0.011. Large changes in raw counts quickly place perturbed graphs beyond the kernel's useful similarity range. The previous diagnostic found that triangles and edges supply about 73.5% and 26.1% of squared cross-sample descriptor distance at the BA endpoint. These unstandardized counts dominate the geometry.

Changing only bandwidth moves the transition: sigma=3 saturates sooner; sigma=30 shifts the peak later; sigma=100 produces a gradual increasing curve across this grid. Thus the sharp early rise is demonstrably associated with bandwidth **relative to descriptor scales**, not merely an intrinsic property of GraphStats. Keeping a bandwidth fixed across alpha is itself appropriate for a consistent comparison; changing it adaptively at every alpha would change the ruler during measurement.

The later decline has a different, but connected, explanation. Between alpha 0.3 and 1.0, mean cross-sample similarity Kxy is already almost zero, while perturbed within-sample similarity Kyy falls from 0.7666 to 0.5070. Since MMD² = Kxx + Kyy - 2 Kxy, the score falls from 1.5912 to 1.3317. Individual descriptor displacement nevertheless grows from 47.2 to 189.4. The representation still sees more change; the bounded Gaussian comparison no longer orders the path monotonically. These terms were reconstructed from saved graph records.

Graph-MMD literature also documents nonmonotone responses and dependence on kernel parameters. [O'Bray et al., 2022](https://arxiv.org/pdf/2106.01098). The observed improvement of ordering at sigma=100 is not proof that 100 is a universally better parameter: it changes sensitivity elsewhere, including at low alpha.

This separates two goals: responding to an initial departure and grading how much further the system changes. A rapid rise may be useful for the first goal while saturation harms the second. The current plots demonstrate score responses; establishing an actual detection threshold or detection power would additionally require calibrated reference variability.

## Holding the representation fixed isolates part of the explanation

I recomputed the same BA comparisons with a linear kernel on GraphStats and a Gaussian kernel on WL. The WL Gaussian bandwidth is the median positive pairwise distance among original WL representations in each replicate, approximately 19.7–19.9, frozen across alpha. It is not the same numerical bandwidth as GraphStats, because those spaces have different scales.

![Kernel substitutions](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/analysis/2026-09-17_mmd_explanation/kernel_substitution.png)

On the same GraphStats descriptors, substituting a linear kernel removes the early peak: at alpha 0.1, the score is only 0.55% of its own endpoint maximum. This isolates a major role for the aggregation/kernel choice. On WL, the reference-scaled Gaussian changes the curve more modestly: the corresponding early fraction becomes 11.6%, rather than 8.4%. Therefore both representation and kernel matter; “Gaussian versus linear” alone does not explain every response.

WL's original gradual BA curve reflects gradual displacement of average feature counts. About 98.4% of its endpoint score comes from the initial degree histogram. Moreover, 186/300 individual WL pair-distance trajectories have a decline despite the monotone aggregate score. Gradual aggregate growth is not a guarantee of stable or monotone individual responses.

These are exploratory substitutions. Original result files, metric defaults, and benchmark definitions remain unchanged.

## WL does not perform better at community weakening in every corrected setting

If “better” means a more consistently increasing relationship with positive alpha, the median within-replicate Spearman correlations are:

| Dataset | GraphStats + RBF | WL + linear |
|---|---:|---:|
| ER | -0.12 | 0.70 |
| SBM, additional corrected probe | 0.93 | 0.50 |
| ZINC | 0.96 | 0.96 |

Alpha zero is omitted from these correlations because identical-copy comparisons force a zero score. This avoids letting that built-in point drive the ordering statistic. These numbers assess ordering only; they do not establish detection power, correctness, or superiority. The three individual replicates are visible in the figure.

![Corrected community comparisons](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/analysis/2026-09-17_mmd_explanation/community_comparison.png)

**ER:** rewiring changes adjacency and node neighborhoods, but the average summaries are similar before and after: triangle count 33.71 → 33.41, clustering 0.1177 → 0.1153, and unchanged edge count. GraphStats' limited descriptor set therefore has relatively little endpoint shift to register. WL records more detailed patterns of neighbors and can register changes that leave these coarse summaries similar. This explains a plausible advantage in ordering here, but not a demonstrated advantage at identifying planted communities: ER has no planted partition in this experiment.

Some WL score also comes from the loss of exact histogram overlap. The earlier diagnostic found about 99.7% singleton labels at its deeper rounds in these ER samples, and approximately 1.0 empirical contribution per such round even between independent unperturbed samples. A positive WL score is therefore not, by itself, evidence of a community effect. Null calibration would require more than the few illustrative reference draws currently available.

**SBM:** a planted partition introduces genuine block structure, but the rewiring also changes ordinary statistics. Mean triangles fall 27.38 → 15.70 and clustering 0.1515 → 0.0837. This gives GraphStats a strong measurable signal. The sharper interpretation is not simply that GraphStats “understands communities”; it detects a consequence of the community intervention.

## A feature-omission control confirms how GraphStats responds in SBM

I repeated the endpoint comparison on the same corrected graphs with unchanged bandwidth 10:

| SBM descriptor choice | Mean RBF MMD² |
|---|---:|
| All nine descriptors | 0.317344 |
| Omit triangle count | 0.000846 |
| Triangle count only | 0.421028 |

![Triangle-mediated community response](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/analysis/2026-09-17_mmd_explanation/community_triangle_mechanism.png)

The marked collapse when triangle count is omitted supports a concrete mechanism: **in this configuration, GraphStats' community response is strongly mediated by triangle-count change**. The triangle-only score being larger than the full score also shows why these are not additive feature-importance shares: dropping coordinates changes every Gaussian similarity. We did not change the graphs or the perturbation itself.

The effect has a structural explanation. Within-block edges in this assortative SBM have more opportunities to participate in local closure than the replacement between-block edges. Removing them reduces triangles. At large alpha the operator also crosses from assortative into disassortative organization, so the full path cannot be described as merely erasing communities.

## Structural changes versus feature changes in WL

The WL features here are **computed from topology**, not external attributes that were edited independently. Initial labels are degrees. A refinement step encodes a node's current label together with the multiset of its neighbors' labels. This is how the WL subtree kernel converts structure into comparable counts. [Shervashidze et al., 2011](https://jmlr.org/papers/volume12/shervashidze11a/shervashidze11a.pdf).

For example, a degree-three node whose neighbor degrees are `{1,1,4}` differs after one refinement from a degree-three node whose neighbor degrees are `{2,2,2}`. A rewire can change these patterns without changing the central node's degree. Structural change is being detected **through a change in the derived feature**, so the two are not competing interpretations.

WL does not receive the planted community labels in these experiments. Its response comes from degrees and neighborhood patterns, not from directly measuring whether nodes stayed inside their planted blocks. Limited-round 1-WL can also miss some structural differences; the earlier six-cycle versus two-triangle control gives identical WL histograms despite different triangles and components. Degree-preserving community rewiring is therefore a useful additional control, not something these existing results already isolate.

The defensible insight is conditional: **WL can respond to changes in neighborhood composition that coarse GraphStats summaries miss; GraphStats can respond strongly to community interventions when those interventions alter its chosen statistics. Kernel geometry then determines how each representation's changes become a distribution score.**

## Reproduction

```sh
src/.venv/bin/python scripts/explain_mmd_comparison.py
src/.venv/bin/python scripts/probe_community_descriptors.py
src/.venv/bin/python scripts/analyze_addition_sensitivity.py
```

[Kernel substitution values](kernel_substitutions.json), [community trajectories and correlations](community_comparison.json), [descriptor ablations](community_descriptor_ablation.json), and [source manifest](manifest.json) preserve the numerical evidence. The broader [structural analysis](../2026-09-16_structural_insights/README.md) contains the graph-level and WL-resolution checks referenced here.

[Addition sensitivity values and input hashes](addition_sensitivity.json) preserve all 132 replicate–alpha records used in the new addition figure. These are repeated measurements along 12 replicate trajectories, not 132 independent experimental replicates. The addition script only reads existing corrected diagnostics and generates the figure and summaries; it does not rerun graph experiments. Figures are embedded directly in this Markdown using absolute workspace paths for display in Codex.
