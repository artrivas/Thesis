"""Evaluation metrics for synthetic graph distribution experiments."""

from __future__ import annotations

from collections import defaultdict
import csv
import math
from pathlib import Path

from experimentation.runner import read_result_rows
from experimentation.workflows import DIVERSITY_CURVES_WORKFLOW, NATIVE_NETLSD_WORKFLOW


EVALUATION_SUMMARY_COLUMNS = (
    "workflow",
    "dataset",
    "perturbation",
    "sensitivity",
    "monotonicity",
    "paired_detectability",
    "mean_shift_detectability",
    "edit_distance_validation",
    "paired_edit_distance_validation",
    "robustness_cv",
    "ranking_stability_tau",
    "relative_runtime",
    "interpretability_score",
    "granularity_label",
)

FINAL_MATRIX_COLUMNS = (
    "workflow",
    "sensitivity_label",
    "monotonicity_label",
    "paired_label",
    "mean_shift_label",
    "granularity_label",
    "robustness_label",
    "efficiency_label",
    "interpretability_label",
)

FAILURE_MAP_COLUMNS = (
    "dataset",
    "perturbation",
    "cause",
    "mean_edit_distance_raw",
    "max_edit_distance_raw",
    "best_workflow",
    "best_sensitivity",
    "monotonicity",
    "robustness_cv",
    "note",
)

# Diagnosis thresholds for the failure map. Documented in failure_map.md.
EDIT_STARVED_MAX_EDITS = 1.0  # fewer than one edited edge even at the largest alpha
METHOD_BLIND_SENSITIVITY = 0.30  # edits happened but the best workflow stays flat
UNSTABLE_MONOTONICITY = 0.30  # violation fraction above this is non-monotone
UNSTABLE_CV = 0.35  # seed CV above this is unstable

FAILURE_CAUSES = ("inapplicable", "perturbation_starved", "method_blind", "unstable", "ok")

INTERPRETABILITY_SCORES = {
    "structural_statistics_mmd": 3,
    "wl_subtree_kernel_mmd": 2,
    NATIVE_NETLSD_WORKFLOW: 2,
    DIVERSITY_CURVES_WORKFLOW: 3,
    "diversity_curves_l2": 3,
}

MEAN_SHIFT_DUPLICATE_WORKFLOWS = {
    NATIVE_NETLSD_WORKFLOW,
    DIVERSITY_CURVES_WORKFLOW,
    "diversity_curves_l2",
}

PERTURBATION_GRANULARITY = {
    "edge_insertion": "local",
    "edge_deletion": "local",
    "edge_addition_deletion": "local",
    "triangle_insertion": "local/mesoscopic",
    "triangle_deletion": "local/mesoscopic",
    "triangle_injection_removal": "local/mesoscopic",
    "community_weakening": "mesoscopic",
    "hub_modification": "global",
}


def evaluate_results(results_path: Path | str, output_dir: Path | str | None = None) -> dict[str, Path]:
    """Create evaluation summary and final matrix CSVs from a result file."""

    rows = read_result_rows(results_path)
    output_root = Path(output_dir) if output_dir is not None else Path(results_path).parent
    output_root.mkdir(parents=True, exist_ok=True)
    summary = generate_evaluation_summary(rows)
    final_matrix = generate_final_matrix(summary)
    failure_map = generate_failure_map(rows, summary)

    summary_path = output_root / "evaluation_summary.csv"
    matrix_path = output_root / "final_matrix.csv"
    failure_map_path = output_root / "failure_map.csv"
    write_table(summary, EVALUATION_SUMMARY_COLUMNS, summary_path)
    write_table(final_matrix, FINAL_MATRIX_COLUMNS, matrix_path)
    write_table(failure_map, FAILURE_MAP_COLUMNS, failure_map_path)
    return {
        "evaluation_summary": summary_path,
        "final_matrix": matrix_path,
        "failure_map": failure_map_path,
    }


def generate_evaluation_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Generate one evaluation row per workflow, dataset, and perturbation."""

    success_rows = [row for row in rows if row.get("status") == "success"]
    relative_runtime_by_id = _relative_runtime_by_row(success_rows)
    ranking_tau_by_group = _ranking_stability_by_dataset_perturbation(success_rows)
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in success_rows:
        grouped[(str(row["workflow"]), str(row["dataset"]), str(row["perturbation"]))].append(row)

    summary = []
    for (workflow, dataset, perturbation), group_rows in sorted(grouped.items()):
        alpha_distribution = _numeric_pairs(group_rows, "alpha", "distribution_score")
        alpha_paired = _numeric_pairs(group_rows, "alpha", "paired_score")
        alpha_mean_shift = _numeric_pairs(group_rows, "alpha", "mean_shift_score")
        edit_distribution = _numeric_pairs(group_rows, "edit_distance_weighted", "distribution_score")
        edit_paired = _numeric_pairs(group_rows, "edit_distance_weighted", "paired_score")
        relative_runtimes = [
            relative_runtime_by_id[id(row)]
            for row in group_rows
            if id(row) in relative_runtime_by_id
        ]
        seed_means = _seed_means(group_rows, "distribution_score")
        summary.append(
            {
                "workflow": workflow,
                "dataset": dataset,
                "perturbation": perturbation,
                "sensitivity": spearman_correlation_from_pairs(alpha_distribution),
                "monotonicity": monotonicity_violation_fraction(alpha_distribution),
                "paired_detectability": spearman_correlation_from_pairs(alpha_paired),
                "mean_shift_detectability": spearman_correlation_from_pairs(alpha_mean_shift),
                "edit_distance_validation": spearman_correlation_from_pairs(edit_distribution),
                "paired_edit_distance_validation": spearman_correlation_from_pairs(edit_paired),
                "mean_shift_duplicates_distribution": mean_shift_duplicates_distribution(group_rows),
                "robustness_cv": coefficient_of_variation(list(seed_means.values())),
                "ranking_stability_tau": ranking_tau_by_group.get((dataset, perturbation), 1.0),
                "relative_runtime": mean(relative_runtimes),
                "interpretability_score": INTERPRETABILITY_SCORES.get(workflow, 1),
                "granularity_label": PERTURBATION_GRANULARITY.get(perturbation, "unknown"),
            }
        )
    return summary


def generate_final_matrix(summary_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in summary_rows:
        grouped[str(row["workflow"])].append(row)

    final_rows = []
    for workflow, rows in sorted(grouped.items()):
        sensitivity = mean(_numbers(rows, "sensitivity"))
        monotonicity = mean(_numbers(rows, "monotonicity"))
        paired = mean(_numbers(rows, "paired_detectability"))
        mean_shift = mean(_numbers(rows, "mean_shift_detectability"))
        robustness = mean(_numbers(rows, "robustness_cv"))
        runtime = mean(_numbers(rows, "relative_runtime"))
        interpretability = mean(_numbers(rows, "interpretability_score"))
        duplicate_mean_shift = is_duplicate_mean_shift_workflow(workflow, rows)
        final_rows.append(
            {
                "workflow": workflow,
                "sensitivity_label": correlation_label(sensitivity),
                "monotonicity_label": monotonicity_label(monotonicity),
                "paired_label": correlation_label(paired),
                "mean_shift_label": "Duplicate" if duplicate_mean_shift else correlation_label(mean_shift),
                "granularity_label": summarize_granularity(rows),
                "robustness_label": robustness_label(robustness),
                "efficiency_label": efficiency_label(runtime),
                "interpretability_label": interpretability_label(interpretability),
            }
        )
    return final_rows


def generate_failure_map(
    rows: list[dict[str, object]],
    summary_rows: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Diagnose, per (dataset, perturbation), WHY a hypothesis succeeded or failed.

    The failure map is an EXPLANATION artifact: each cell is labeled with a
    diagnosed cause (see ``failure_map.md``) derived from logged metadata and
    scores, not merely a score value. Causes, in precedence order:

    - ``inapplicable`` — no successful rows (cell skipped). Rare after detected
      community labels were added.
    - ``perturbation_starved`` — alpha > 0 but almost nothing was edited (e.g.
      triangle_deletion on ER: too few triangles to spend the budget).
    - ``method_blind`` — edits happened but the best workflow's scores stayed flat.
    - ``unstable`` — the best workflow responds but is non-monotone or high-CV
      across seeds.
    - ``ok`` — behaves as intended.
    """

    if summary_rows is None:
        summary_rows = generate_evaluation_summary(rows)
    summary_by_cell: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for summary_row in summary_rows:
        summary_by_cell[(str(summary_row["dataset"]), str(summary_row["perturbation"]))].append(summary_row)
    rows_by_cell: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        rows_by_cell[(str(row.get("dataset")), str(row.get("perturbation")))].append(row)

    diagnoses = []
    for cell in sorted(rows_by_cell):
        dataset, perturbation = cell
        diagnoses.append(
            _diagnose_cell(dataset, perturbation, rows_by_cell[cell], summary_by_cell.get(cell, []))
        )
    return diagnoses


def _diagnose_cell(
    dataset: str,
    perturbation: str,
    cell_rows: list[dict[str, object]],
    cell_summary: list[dict[str, object]],
) -> dict[str, object]:
    success_rows = [row for row in cell_rows if row.get("status") == "success"]
    edits_by_alpha = _edit_amounts_by_alpha(success_rows)
    positive_alpha_edits = [value for alpha, value in edits_by_alpha.items() if alpha > 0]
    max_edits = max(positive_alpha_edits, default=0.0)
    mean_edits = mean(positive_alpha_edits)

    best = max(cell_summary, key=lambda row: _float(row.get("sensitivity")), default=None)
    best_workflow = str(best["workflow"]) if best else ""
    best_sensitivity = _float(best.get("sensitivity")) if best else math.nan
    best_monotonicity = _float(best.get("monotonicity")) if best else math.nan
    best_cv = _float(best.get("robustness_cv")) if best else math.nan

    if not success_rows:
        cause = "inapplicable"
        note = "no successful rows (cell skipped)"
    elif max_edits < EDIT_STARVED_MAX_EDITS:
        cause = "perturbation_starved"
        note = f"max mean edits at alpha>0 = {max_edits:.2f} (< {EDIT_STARVED_MAX_EDITS})"
    elif not math.isfinite(best_sensitivity) or best_sensitivity < METHOD_BLIND_SENSITIVITY:
        cause = "method_blind"
        note = f"edits occurred but best sensitivity = {_fmt(best_sensitivity)}"
    elif (math.isfinite(best_monotonicity) and best_monotonicity > UNSTABLE_MONOTONICITY) or (
        math.isfinite(best_cv) and best_cv > UNSTABLE_CV
    ):
        cause = "unstable"
        note = f"monotonicity={_fmt(best_monotonicity)}, cv={_fmt(best_cv)}"
    else:
        cause = "ok"
        note = f"sensitivity={_fmt(best_sensitivity)}, cv={_fmt(best_cv)}"

    return {
        "dataset": dataset,
        "perturbation": perturbation,
        "cause": cause,
        "mean_edit_distance_raw": round(mean_edits, 4),
        "max_edit_distance_raw": round(max_edits, 4),
        "best_workflow": best_workflow,
        "best_sensitivity": _round_or_blank(best_sensitivity),
        "monotonicity": _round_or_blank(best_monotonicity),
        "robustness_cv": _round_or_blank(best_cv),
        "note": note,
    }


def _edit_amounts_by_alpha(success_rows: list[dict[str, object]]) -> dict[float, float]:
    by_alpha: dict[float, list[float]] = defaultdict(list)
    for row in success_rows:
        edits = _float(row.get("edit_distance_raw"))
        alpha = _float(row.get("alpha"))
        if math.isfinite(edits) and math.isfinite(alpha):
            by_alpha[alpha].append(edits)
    return {alpha: mean(values) for alpha, values in by_alpha.items()}


def _fmt(value: float) -> str:
    return f"{value:.2f}" if math.isfinite(value) else "n/a"


def _round_or_blank(value: float) -> object:
    return round(value, 4) if math.isfinite(value) else ""


def is_duplicate_mean_shift_workflow(workflow: str, summary_rows: list[dict[str, object]]) -> bool:
    if workflow in MEAN_SHIFT_DUPLICATE_WORKFLOWS:
        return True
    duplicate_flags = [row.get("mean_shift_duplicates_distribution") for row in summary_rows]
    return bool(duplicate_flags) and all(_truthy(value) for value in duplicate_flags)


def mean_shift_duplicates_distribution(rows: list[dict[str, object]], tolerance: float = 1e-12) -> bool:
    pairs = []
    for row in rows:
        distribution = _float(row.get("distribution_score"))
        mean_shift = _float(row.get("mean_shift_score"))
        if math.isfinite(distribution) and math.isfinite(mean_shift):
            pairs.append((distribution, mean_shift))
    return bool(pairs) and all(abs(distribution - mean_shift) <= tolerance for distribution, mean_shift in pairs)


def spearman_correlation_from_pairs(pairs: list[tuple[float, float]]) -> float:
    if len(pairs) < 2:
        return 0.0
    xs, ys = zip(*pairs)
    return spearman_correlation(list(xs), list(ys))


def spearman_correlation(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys):
        raise ValueError("Spearman correlation requires equal-length inputs")
    if len(xs) < 2:
        return 0.0
    return pearson_correlation(rank_values(xs), rank_values(ys))


def monotonicity_violation_fraction(pairs: list[tuple[float, float]]) -> float:
    by_alpha: dict[float, list[float]] = defaultdict(list)
    for alpha, score in pairs:
        by_alpha[alpha].append(score)
    means = [(alpha, mean(scores)) for alpha, scores in sorted(by_alpha.items())]
    if len(means) < 2:
        return 0.0
    violations = sum(1 for left, right in zip(means, means[1:]) if right[1] < left[1])
    return violations / (len(means) - 1)


def coefficient_of_variation(values: list[float]) -> float:
    if not values:
        return 0.0
    average = mean(values)
    variance = sum((value - average) ** 2 for value in values) / len(values)
    sigma = math.sqrt(variance)
    if abs(average) < 1e-12:
        return 0.0 if sigma < 1e-12 else math.inf
    return sigma / abs(average)


def kendall_tau_from_score_maps(left: dict[str, float], right: dict[str, float]) -> float:
    common = sorted(set(left) & set(right))
    if len(common) < 2:
        return 1.0
    concordant = 0
    discordant = 0
    for index, first in enumerate(common):
        for second in common[index + 1 :]:
            left_delta = left[first] - left[second]
            right_delta = right[first] - right[second]
            product = left_delta * right_delta
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
    total = concordant + discordant
    if total == 0:
        return 1.0
    return (concordant - discordant) / total


def correlation_label(value: float) -> str:
    if value >= 0.90:
        return "Very high"
    if value >= 0.75:
        return "High"
    if value >= 0.50:
        return "Medium"
    return "Low"


def monotonicity_label(violation_fraction: float) -> str:
    if violation_fraction <= 0.05:
        return "Very high"
    if violation_fraction <= 0.15:
        return "High"
    if violation_fraction <= 0.30:
        return "Medium"
    return "Low"


def robustness_label(cv: float) -> str:
    if cv <= 0.10:
        return "Very high"
    if cv <= 0.20:
        return "High"
    if cv <= 0.35:
        return "Medium"
    return "Low"


def efficiency_label(relative_runtime: float) -> str:
    if relative_runtime <= 1.25:
        return "Very high"
    if relative_runtime <= 1.75:
        return "High"
    if relative_runtime <= 2.50:
        return "Medium"
    return "Low"


def interpretability_label(score: float) -> str:
    if score >= 3:
        return "Very high"
    if score >= 2:
        return "High"
    return "Low"


def summarize_granularity(rows: list[dict[str, object]]) -> str:
    detected: set[str] = set()
    best_scale = "unknown"
    best_score = -math.inf
    scale_scores: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        score = _float(row.get("sensitivity"))
        label = str(row.get("granularity_label", "unknown"))
        for scale in label.split("/"):
            scale_scores[scale].append(score)
    for scale, scores in scale_scores.items():
        score = mean(scores)
        if score > best_score:
            best_scale = scale
            best_score = score
        if score >= 0.50:
            detected.add(scale)
    if len(detected) >= 3:
        return "multiscale"
    if detected:
        return "/".join(sorted(detected))
    return best_scale


def rank_values(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor
        while end + 1 < len(indexed) and indexed[end + 1][1] == indexed[cursor][1]:
            end += 1
        average_rank = (cursor + end) / 2 + 1
        for index in range(cursor, end + 1):
            ranks[indexed[index][0]] = average_rank
        cursor = end + 1
    return ranks


def pearson_correlation(xs: list[float], ys: list[float]) -> float:
    mean_x = mean(xs)
    mean_y = mean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denominator_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    denominator = denominator_x * denominator_y
    if denominator == 0:
        return 0.0
    return numerator / denominator


def mean(values: list[float]) -> float:
    clean = [value for value in values if value is not None and not math.isnan(value)]
    if not clean:
        return 0.0
    return sum(clean) / len(clean)


def write_table(rows: list[dict[str, object]], columns: tuple[str, ...], path: Path | str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in columns})
    return output_path


def _relative_runtime_by_row(rows: list[dict[str, object]]) -> dict[int, float]:
    by_setting: dict[tuple[str, str, float, int], list[tuple[dict[str, object], float]]] = defaultdict(list)
    for row in rows:
        runtime = _float(row.get("runtime_seconds"))
        by_setting[
            (
                str(row["dataset"]),
                str(row["perturbation"]),
                _float(row["alpha"]),
                int(_float(row["seed"])),
            )
        ].append((row, runtime))

    relative = {}
    for values in by_setting.values():
        fastest = min((runtime for _, runtime in values if runtime >= 0.0), default=0.0)
        for row, runtime in values:
            relative[id(row)] = 1.0 if fastest <= 0 else runtime / fastest
    return relative


def _ranking_stability_by_dataset_perturbation(rows: list[dict[str, object]]) -> dict[tuple[str, str], float]:
    grouped: dict[tuple[str, str], dict[int, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in rows:
        grouped[(str(row["dataset"]), str(row["perturbation"]))][int(_float(row["seed"]))][str(row["workflow"])].append(
            _float(row.get("distribution_score"))
        )

    stability = {}
    for key, by_seed in grouped.items():
        seed_scores = {
            seed: {workflow: mean(scores) for workflow, scores in workflows.items()}
            for seed, workflows in by_seed.items()
        }
        seeds = sorted(seed_scores)
        if len(seeds) < 2:
            stability[key] = 1.0
            continue
        taus = []
        for index, left_seed in enumerate(seeds):
            for right_seed in seeds[index + 1 :]:
                taus.append(kendall_tau_from_score_maps(seed_scores[left_seed], seed_scores[right_seed]))
        stability[key] = mean(taus)
    return stability


def _seed_means(rows: list[dict[str, object]], value_key: str) -> dict[int, float]:
    by_seed: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        by_seed[int(_float(row["seed"]))].append(_float(row.get(value_key)))
    return {seed: mean(values) for seed, values in by_seed.items()}


def _numeric_pairs(rows: list[dict[str, object]], x_key: str, y_key: str) -> list[tuple[float, float]]:
    pairs = []
    for row in rows:
        x = _float(row.get(x_key))
        y = _float(row.get(y_key))
        if math.isfinite(x) and math.isfinite(y):
            pairs.append((x, y))
    return pairs


def _numbers(rows: list[dict[str, object]], key: str) -> list[float]:
    return [_float(row.get(key)) for row in rows if math.isfinite(_float(row.get(key)))]


def _float(value: object) -> float:
    if value in (None, ""):
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes"}


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value
