# Paired statistical test results

**The tests have been run.** This analysis covers the three synthetic datasets only: 72 dataset / perturbation / workflow settings, each with 24 paired seeds. It includes 72 alpha-.1-to-1.0 comparisons and 720 adjacent-alpha comparisons. IMDB-BINARY is excluded; ZINC results are not available in this source.

**Interpretation status:** these are exploratory results conditional on independent seed trajectories. The historical reuse of perturbation random streams is unresolved. In addition, method eligibility was informed by these data's diagnostic shapes. The adjusted p-values therefore must not be represented as calibrated confirmatory thesis evidence. Correction for multiple comparisons does not repair either issue.

## Main results

All tests are two-sided. One Holm correction covers **2,376 contrast/method slots**: 792 contrasts × three methods. Unavailable tests retain an internal p=1 slot in this correction, but appear as unavailable in the delivered tables. This avoids making the multiplicity penalty smaller merely by withholding tests.

| Comparison family | Method | Tests run | Adjusted p < .05 | Increase | Decrease |
| --- | --- | ---: | ---: | ---: | ---: |
| Alpha .1 → 1.0 | Paired t | 45 | 41 | 41 | 0 |
| Alpha .1 → 1.0 | Wilcoxon signed-rank | 38 | 36 | 36 | 0 |
| Alpha .1 → 1.0 | Exact sign | 72 | 65 | 65 | 0 |
| Adjacent alpha levels | Paired t | 352 | 304 | 277 | 27 |
| Adjacent alpha levels | Wilcoxon signed-rank | 416 | 358 | 327 | 31 |
| Adjacent alpha levels | Exact sign | 644 | 526 | 478 | 48 |

The test sets overlap. Do not sum these counts as independent discoveries or compare their percentages as measures of test power: the methods have different hypotheses and eligibility sets. An increase in the endpoint comparison is compatible with significant decreases during intermediate steps. The 76 completely zero adjacent comparisons were reported without effect tests.

## Concrete results

### ER / triangle insertion / GraphStats: overall increase

For alpha .1 → 1.0, all 24 seeds increase. The mean difference is **+0.120724**, with pointwise 95% t interval **[+0.112726, +0.128723]**.

- Paired t: t(23) = **31.2225**; raw p = **2.4641e−20**; Holm-adjusted p = **5.1697e−17**.
- Wilcoxon: W = **0**; raw p = **1.1921e−7**; Holm-adjusted p = **0.000242949**.
- Sign: **24 positive / 0 negative / 0 zero**; raw p = **1.1921e−7**; Holm-adjusted p = **0.000242949**.

The three methods agree on direction under their respective assumptions. They test different properties, and this is not three independent replications.

### ER / triangle insertion / GraphStats: decrease after the peak

For alpha .3 → .4, all 24 seeds decrease. The mean difference is **−0.033016**, with pointwise 95% t interval **[−0.035444, −0.030588]**.

- Paired t: t(23) = **−28.1291**; raw p = **2.5601e−19**; Holm-adjusted p = **5.3481e−16**.
- Wilcoxon: W = **0**; Holm-adjusted p = **0.000242949**.
- Sign: **0 positive / 24 negative / 0 zero**; Holm-adjusted p = **0.000242949**.

This distinguishes an overall endpoint increase from monotonic growth. A single endpoint p-value would miss this reversal.

### BA / triangle insertion: GraphStats decreases while WL increases

For alpha .3 → .4:

| Workflow | Mean difference, own units | Positive / negative seeds | Wilcoxon W | Raw Wilcoxon p | Holm-adjusted Wilcoxon p |
| --- | ---: | --- | ---: | ---: | ---: |
| GraphStats | −0.026831 | 1 / 23 | 1 | 2.3842e−7 | 0.000263453 |
| WL | +80.614383 | 24 / 0 | 0 | 1.1921e−7 | 0.000242949 |

Paired t-tests were withheld for these two contrasts because the conservative screen flagged outliers. Wilcoxon and sign results both support the opposing directions under their assumptions. The GraphStats sign-test adjusted p is .00323355, and WL's is .000242949. These are within-workflow results; the raw mean magnitudes are not comparable and this is not a direct statistical test of a workflow-by-alpha interaction.

### SBM / community weakening / NetLSD: directional evidence despite skewness

For alpha .1 → 1.0, all 24 differences are positive. The observed mean difference is **+0.015038**, and the median is **+0.013163**.

Paired t and Wilcoxon were withheld because the shape is strongly skewed. The exact sign test gives raw p = **1.1921e−7**, Holm-adjusted p = **0.000242949**. Its pointwise 95% interval for the probability of a positive difference, conditional on a nonzero difference, is **[0.8575, 1.0]**.

This supports consistent direction under the independent-sign model. It is not a test that the population mean difference is positive.

### SBM / hub modification / NetLSD: one changed seed is insufficient

For alpha .4 → .5, 23 differences are zero and one is negative. The exact conditional sign test has one nonzero pair and gives raw and adjusted **p = 1.0**. Paired t and Wilcoxon were withheld. There is insufficient evidence of a systematic directional shift; this does not establish equivalence or prove the absence of an effect.

## Pattern across the full grid

All **48 adjacent comparisons with a negative direction and adjusted sign-test p < .05** belong to GraphStats. They comprise:

- 21 triangle-insertion contrasts: seven intervals in each synthetic dataset.
- 18 edge-insertion contrasts: seven BA, six ER, five SBM.
- Eight triangle-deletion contrasts: four BA, two ER, two SBM.
- One SBM hub-modification contrast.

These are dependent comparisons across related curves, not 48 independent replications. Nevertheless, they locate the recurring decreases that a mean-versus-alpha plot alone cannot quantify. They do not show that the other workflows are universally better; detection timing, scale and the meaning of the measured change remain separate questions.

Seven endpoint comparisons do not cross the adjusted .05 sign-test threshold: ER community weakening for Diversity, NetLSD and GraphStats; ER hub modification for Diversity, NetLSD and WL; and SBM hub modification for Diversity. Non-rejection does not establish no relationship, particularly when an endpoint comparison can hide a nonlinear response.

## Which tests were allowed to run?

I used narrower screens than the earlier `no_clear_flag` count, to avoid treating absence of a simple flag as sufficient justification:

- **Paired t:** nonconstant differences; previous normality/skewness screen has no flag; normal Q–Q correlation at least .97; no Tukey outlier flags. This yields 45 endpoints and 352 adjacent comparisons. These thresholds are cautious diagnostic conventions, not mathematically proven validity conditions. The t-test is computed as a one-sample t-test on paired differences, which is equivalent to a paired t-test.
- **Wilcoxon:** nonconstant differences; at least six nonzero pairs; absolute sample skewness at most 1; absolute Bowley and 10/90 tail asymmetry each at most .3. This yields 38 endpoints and 416 adjacent comparisons. These descriptive screens do not certify symmetry. Six nonzero pairs is a minimum information screen, not a guarantee of adequate power after correction.
- **Sign:** every contrast with at least one nonzero difference. No normality or symmetry screen is needed. Counts of positive, negative and zero differences are retained, including sparse contrasts that cannot reject at .05.

No method was chosen because its effect p-value was smaller than another method's. Withheld results are marked with reasons in `results.json`. The prior diagnostic thresholds and the additional conservative eligibility thresholds were fixed before calculating this run's effect-test results, but the study remains data-informed and exploratory.

Wilcoxon p-values are calculated from the exact conditional random-sign distribution using average ranks, with numerical zeros discarded. Dynamic programming evaluates this distribution without Monte Carlo noise and handles tied ranks. Magnitudes within the recorded numerical tolerance of a tie group's smallest magnitude share a rank. This assumes independent, equiprobable signs conditional on magnitudes under the symmetric null. The implementation was checked against SciPy's untied exact calculation and explicit enumeration of a tied example.

The t intervals and sign-proportion intervals are **pointwise 95% intervals**, not simultaneous intervals adjusted for the full family. A pointwise interval excluding zero should not substitute for the adjusted p-value. Likewise, the Wilcoxon nonzero-pair Hodges–Lehmann estimate and the t-test mean difference are different effect summaries. They remain in each workflow's own score units.

## Files and verification

- [Endpoint result table, all 72 settings](endpoint_results.md): mean differences, available pointwise intervals, sign counts and adjusted p-values for each method.
- [All 792 contrast results](all_contrast_results.md): the same information for every endpoint and adjacent comparison.
- `results.json`: complete statistics, raw and adjusted p-values, effect sizes, intervals, eligibility and reasons for withheld tests.
- `manifest.json`: source and diagnostic checksums, thresholds, version information and result counts.

Run `python scripts/run_paired_statistical_tests.py` with the optional analysis dependencies installed. This execution took **13.7 seconds**, including rechecking every saved paired difference against the source rows. Nine focused verification tests passed, covering diagnostics, missing data, exact signed ranks with ties/zeros, agreement with SciPy, and multiplicity correction. No historical experiment values were changed.

References for test definitions: [paired t-test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_rel.html), [Wilcoxon signed-rank](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html), [exact binomial/sign test](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html).
