# Results Schema

Each completed workflow run should emit one row per dataset, perturbation,
alpha, seed, and workflow combination.

Expected result table columns:

| Column | Type | Description |
| --- | --- | --- |
| `dataset` | string | Synthetic graph family name. |
| `dataset_params` | JSON string | Concrete generator parameters used for the row. |
| `perturbation` | string | Perturbation method name. |
| `perturbation_params` | JSON string | Perturbation summary metadata for the paired distribution. |
| `alpha` | float | Perturbation strength. |
| `seed` | integer | Random seed used for the run. |
| `workflow` | string | Workflow name. |
| `distribution_score` | float/null | Distribution-level comparison score. |
| `mean_shift_score` | float/null | Mean representation shift score. |
| `paired_score` | float/null | Paired graph comparison score. |
| `runtime_seconds` | float/null | Wall-clock runtime for the workflow run. |
| `memory_mb` | float/null | Peak or measured memory usage in megabytes. |
| `status` | string | Run status, such as `success`, `failed`, or `skipped`. |
| `error_message` | string/null | Error detail when `status` is not `success`. |

The schema is intentionally narrow for the first synthetic experiments.
Perturbation metadata such as edges added, edges removed, rewires, triangles
affected, or target hubs can be stored in sidecar metadata or added as optional
columns during orchestration if needed.

## Evaluation Summary Schema

The evaluation summary contains one row per workflow, dataset, and perturbation.

| Column | Type | Description |
| --- | --- | --- |
| `workflow` | string | Workflow name. |
| `dataset` | string | Synthetic graph family name. |
| `perturbation` | string | Perturbation method name. |
| `sensitivity` | float | Spearman correlation between alpha and distribution score. |
| `monotonicity` | float | Fraction of adjacent alpha steps where the score decreases. |
| `paired_detectability` | float | Spearman correlation between alpha and paired score. |
| `mean_shift_detectability` | float | Spearman correlation between alpha and mean-shift score. |
| `robustness_cv` | float | Coefficient of variation across seed-level means. |
| `ranking_stability_tau` | float | Kendall tau ranking stability across seeds. |
| `relative_runtime` | float | Runtime divided by the fastest workflow for the same setting. |
| `interpretability_score` | integer | Fixed interpretability score. |
| `granularity_label` | string | Local, local/mesoscopic, mesoscopic, or global. |

## Final Matrix Schema

The final matrix contains one row per workflow.

| Column | Type | Description |
| --- | --- | --- |
| `workflow` | string | Workflow name. |
| `sensitivity_label` | string | Threshold label for sensitivity. |
| `monotonicity_label` | string | Threshold label for monotonicity violations. |
| `paired_label` | string | Threshold label for paired detectability. |
| `mean_shift_label` | string | Threshold label for mean-shift detectability. |
| `granularity_label` | string | Dominant or multiscale detection label. |
| `robustness_label` | string | Threshold label for robustness CV. |
| `efficiency_label` | string | Relative runtime label. |
| `interpretability_label` | string | Qualitative interpretability label. |
