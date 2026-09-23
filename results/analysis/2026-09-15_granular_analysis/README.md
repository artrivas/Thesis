# What the mean hides: granular analysis

The mean is a useful overview, but it cannot show whether most runs follow its direction, whether responses plateau, or which individual graphs produce a distributional response. We examined those questions at two levels. This report is descriptive; it adds no hypothesis tests.

## Across seeds: all 72 synthetic settings

The analysis covers 19,008 saved rows: three synthetic datasets, six perturbations, four workflows, eleven alpha values, and 24 seeds. IMDB-BINARY is excluded. ZINC is not present in these results.

Start with the [BA hub-modification / WL figure](seed_figures/barabasi_albert__hub_modification__wl_subtree_kernel_mmd.png). Read its four panels in this order:

1. **Individual trajectories:** each thin line follows the same seed across alpha. Mean and median show the overall response. Look for shared trends, plateaus, and seeds that behave differently.
2. **Scores at each alpha:** every dot is a seed; each box covers the middle 50%. These show observed spread, not confidence intervals.
3. **Paired changes:** each dot is one seed's higher-alpha score minus its lower-alpha score. Positive means an increase; negative means a decrease. This preserves pairing and shows effect magnitudes.
4. **Direction counts:** how many seeds increase, decrease, or remain unchanged at every adjacent step. These reveal mixed behavior that a single curve conceals.

Across 720 adjacent setting/alpha comparisons, **eight mean changes oppose the direction of an absolute majority of the 24 seeds**. A ninth opposes a majority only among nonzero changes, with 19 seeds unchanged. Two examples:

| Setting | Alpha step | Mean change | Median paired change | Increase / decrease |
|---|---|---:|---:|---:|
| BA, hub modification, WL | 0.6 to 0.7 | +0.17672 | -0.10950 | 11 / 13 |
| ER, community weakening, WL | 0.5 to 0.6 | -0.00244 | +0.10780 | 14 / 10 |

In the first case, positive changes outweigh the negative changes in magnitude, despite fewer seeds increasing. However, the shift is small relative to the score level of roughly 250: the broad picture is a plateau, not a strong reversal. The narrow 13-to-11 split is also not evidence of a reliable population trend. The second case similarly shows heterogeneous changes around a small mean change. The median of paired changes is not generally the difference of the two marginal medians.

These examples demonstrate information loss; they do not imply all mean curves are misleading. Inspect the magnitude, spread, and counts together. A flat mean may mean every run is flat, or that increases and decreases cancel.

Browse [all 72 settings and figures](all_settings.md). Figures highlight the first mean/majority disagreement when present; otherwise they highlight the most mixed adjacent step. BA triangle-insertion GraphStats specifically highlights alpha 0.3 to 0.4. These selections are exploratory, not prespecified statistical comparisons.

## Within runs: individual graph pairs

The historical table stores aggregate scores, not individual graph-pair distances. We therefore reconstructed a focused pilot: **BA triangle insertion, seeds 0, 1, and 2, with 100 graph pairs at each of eleven alpha values**. Original graph identities were checked across alpha, and all 66 workflow rows reproduced both saved distribution and paired scores. Maximum absolute errors were 1.14e-13 and 5.69e-14, respectively.

At alpha 0.3 to 0.4:

| Seed | GraphStats pair distances increasing | GraphStats MMD² change | WL pair distances increasing | WL MMD² change |
|---|---:|---:|---:|---:|
| 0 | 100 / 100 | -0.02545 | 94 / 100 | +79.8844 |
| 1 | 100 / 100 | -0.01324 | 96 / 100 | +77.1382 |
| 2 | 100 / 100 | -0.03655 | 96 / 100 | +88.2260 |

**GraphStats MMD falls even though every individual graph-pair representation distance grows.** Thus this decline cannot be explained as a few graph pairs getting closer and pulling down the mean paired distance. It concerns how the distribution metric summarizes the samples. It is consistent with the earlier [kernel diagnosis](../2026-09-09_statistical_audit/README.md).

The [graph-pair pilot figure](graph_pair_pilot.png) shows seed 0. Its top panels follow all 100 pairs. The bottom panels compare each pair's distance change with a signed decomposition of the MMD² change. For GraphStats, 76 contributions decrease; for WL all 100 increase. The corresponding GraphStats decreasing counts for seeds 1 and 2 are 60 and 81.

For equal sample sizes, the GraphStats decomposition assigns pair i the value:

`mean_j K(x_i,x_j) + mean_j K(y_i,y_j) - mean_j K(x_i,y_j) - mean_j K(x_j,y_i)`.

For linear WL features it assigns `dot(y_i - x_i, mean(y) - mean(x))`. Averaging contributions exactly recovers the respective biased empirical MMD². These are **signed, sample-dependent bookkeeping contributions**, not graph distances, causal feature importances, or independent observations. Every contribution depends on the full sample.

GraphStats uses L2 distances in nine raw descriptor coordinates, whose units differ; these distances are not a universal ground truth for graph change. WL here means the implemented **WL subtree features with linear MMD²**, not WWL. Their numerical scales must not be directly compared.

## How this should guide the thesis analysis

Use the mean curve as an overview, then report the seed spread, individual paired changes, direction counts, and plateau/reversal intervals for each setting. Explain representative unexpected patterns using graph-level records and the metric's components. Only then use a justified statistical test for a clearly defined claim. A t-test or Wilcoxon result alone cannot supply this granular explanation.

The seed figures are exhaustive for the current synthetic results. The graph-level pilot is limited to one dataset/perturbation and three seeds; it should not be generalized to every setting. Existing perturbation random-stream overlap also prevents treating every seed or graph observation as an independent replicate for formal inference. These restrictions do not prevent descriptive inspection of the observed runs.

For future ZINC runs, retaining graph identifiers, actual edit counts, graph-pair representation distances, and descriptor changes alongside aggregate scores will make the same analysis possible without reconstruction. No new ZINC experiment or full graph-level rerun was launched here.

## Files and reproduction

- [All settings](all_settings.md): 72 figure links and counts of trajectories with decreases.
- [Raw seed trajectories](seed_trajectories.json): scores and edit counts, preserving seed/alpha pairing.
- [Every adjacent interval](adjacent_seed_counts.json): 720 descriptive comparisons.
- [Eight mean/majority disagreements](mean_majority_disagreements.json).
- [Graph-level pilot records](graph_pair_pilot.json): 3,300 records, including hashes, descriptors, distances, edits, and contributions.
- [Seed manifest](seed_manifest.json) and [graph manifest](graph_pair_manifest.json): source hash, checks, and scope.

From the repository root, with the analysis dependencies installed:

```sh
python scripts/analyze_seed_granularity.py
python scripts/analyze_graph_pair_pilot.py
python -m unittest discover -s tests -p 'test_granular_analysis.py'
```

The first script analyzes saved scores on CPU; the second regenerates only the pilot graphs and representations. Neither trains a model or requires a paid service. Runtime depends on hardware; this run was not instrumented for a reliable cost benchmark.
