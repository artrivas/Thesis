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
| `implementation_mode` | string | Workflow implementation mode, such as `paper_faithful` or `descriptor_baseline`. |
| `workflow_params` | JSON string | Reproducibility metadata for the workflow configuration. |
| `perturbation_family` | string | Perturbation family, such as `edge`, `triangle`, `community`, or `hub`. |
| `perturbation_direction` | string | Direction, such as `insertion`, `deletion`, `weakening`, or `modification`. |
| `graph_count` | integer | Number of paired source graphs in the row. |
| `node_count_min` | integer | Minimum node count across original and perturbed graphs. |
| `node_count_max` | integer | Maximum node count across original and perturbed graphs. |
| `edge_count_min` | integer | Minimum edge count across original and perturbed graphs. |
| `edge_count_max` | integer | Maximum edge count across original and perturbed graphs. |
| `distribution_score` | float/null | Distribution-level comparison score. |
| `mean_shift_score` | float/null | Mean representation shift score. |
| `paired_score` | float/null | Paired graph comparison score. |
| `runtime_seconds` | float/null | Wall-clock runtime for the workflow run. |
| `memory_mb` | float/null | Peak or measured memory usage in megabytes. |
| `status` | string | Run status, such as `success`, `failed`, or `skipped`. |
| `error_message` | string/null | Error detail when `status` is not `success`. |

`workflow_params` must include enough detail to reproduce the method behavior,
including NetLSD time-scale schedule and normalization, Diversity Curve scale
schedule and coarsening policy, WL iterations and label initialization, and the
random seed when relevant.

Perturbation insertion and deletion must remain separate rows. Do not merge
`edge_insertion` with `edge_deletion`, and do not merge `triangle_insertion`
with `triangle_deletion`.

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
