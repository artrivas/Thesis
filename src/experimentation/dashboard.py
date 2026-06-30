"""Interactive Streamlit dashboard for experiment result sanity checks."""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experimentation.evaluation import (
    FAILURE_CAUSES,
    generate_evaluation_summary,
    generate_failure_map,
    generate_final_matrix,
)
from experimentation.runner import read_result_rows
from experimentation.workflows import DIVERSITY_CURVES_WORKFLOW, LEGACY_NETLSD_MMD_WORKFLOW, NATIVE_NETLSD_WORKFLOW


DEFAULT_RESULTS_ROOT = Path("results/runs")
DEFAULT_RESULTS_PATH_CANDIDATES = (
    Path("outputs/experimentation_native_netlsd/results/results.csv"),
)
FAILURE_CAUSE_COLORS = {
    "ok": "#2ca02c",
    "perturbation_starved": "#ff7f0e",
    "method_blind": "#d62728",
    "unstable": "#9467bd",
    "inapplicable": "#9aa0a6",
}
LEGACY_DIVERSITY_WORKFLOW = "diversity_curves_l2"
FIXED_DIVERSITY_WORKFLOW = DIVERSITY_CURVES_WORKFLOW
LEGACY_WORKFLOWS = {LEGACY_DIVERSITY_WORKFLOW, LEGACY_NETLSD_MMD_WORKFLOW}
DATASET_LABELS = {
    "erdos_renyi": "ER",
    "stochastic_block_model": "SBM",
    "barabasi_albert": "BA",
}
PERTURBATION_LABELS = {
    "edge_insertion": "edge insertion",
    "edge_deletion": "edge deletion",
    "triangle_insertion": "triangle insertion",
    "triangle_deletion": "triangle deletion",
    "community_weakening": "community",
    "hub_modification": "hub",
}
EXCLUDED_PERTURBATIONS = {
    "edge_addition_deletion",
    "triangle_injection_removal",
}
WORKFLOW_LABELS = {
    "structural_statistics_mmd": "GraphStats+MMD",
    "wl_subtree_kernel_mmd": "WLFeatures+MMD",
    NATIVE_NETLSD_WORKFLOW: "NativeNetLSD",
    LEGACY_NETLSD_MMD_WORKFLOW: "NetLSD+MMD legacy",
    FIXED_DIVERSITY_WORKFLOW: "DiversityCurveDistance",
    LEGACY_DIVERSITY_WORKFLOW: "Diversity L2 legacy",
}
NUMERIC_FLOAT_COLUMNS = (
    "alpha",
    "distribution_score",
    "mean_shift_score",
    "paired_score",
    "edit_distance_raw",
    "edit_distance_weighted",
    "runtime_seconds",
    "memory_mb",
)
NUMERIC_INT_COLUMNS = ("seed",)
SCORE_COLUMNS = ("distribution_score", "paired_score", "mean_shift_score")
EVALUATION_HEATMAP_METRICS = {
    "Sensitivity": "sensitivity",
    "Monotonicity violations": "monotonicity",
    "Paired detectability": "paired_detectability",
    "Mean-shift detectability": "mean_shift_detectability",
    "Edit-distance validation": "edit_distance_validation",
    "Paired edit-distance validation": "paired_edit_distance_validation",
    "Robustness CV": "robustness_cv",
    "Ranking stability tau": "ranking_stability_tau",
    "Relative runtime": "relative_runtime",
    "Interpretability": "interpretability_score",
}


def default_results_path(candidates: tuple[Path, ...] = DEFAULT_RESULTS_PATH_CANDIDATES) -> Path:
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def load_result_rows(path: Path | str) -> list[dict[str, object]]:
    return [dict(row) for row in read_result_rows(path)]


def discover_runs(results_root: Path | str = DEFAULT_RESULTS_ROOT) -> list[Path]:
    """Return traceable run directories (newest first) under a results root.

    A run directory is one that contains ``results/results.csv``. Reads only the
    filesystem layout — no recompute.
    """

    root = Path(results_root)
    if not root.is_dir():
        return []
    runs = [child for child in root.iterdir() if run_results_path(child).is_file()]
    return sorted(runs, key=lambda path: path.name, reverse=True)


def run_results_path(run_dir: Path | str) -> Path:
    return Path(run_dir) / "results" / "results.csv"


def run_evaluation_path(run_dir: Path | str, filename: str) -> Path:
    return Path(run_dir) / "evaluation" / filename


def load_failure_map_rows(run_dir: Path | str | None, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Prefer the precomputed failure_map.csv in the run dir; else derive it.

    Deriving the map from rows is a cheap tabular pass (no graph recompute), used
    only as a fallback when the run was produced without ``--evaluate``.
    """

    if run_dir is not None:
        path = run_evaluation_path(run_dir, "failure_map.csv")
        if path.is_file():
            return [dict(row) for row in read_result_rows(path)]
    return generate_failure_map(rows)


def seed_band_table(
    rows: Iterable[dict[str, object]],
    dataset: str,
    perturbation: str,
    value_key: str = "distribution_score",
) -> list[dict[str, object]]:
    """Per (workflow, alpha) mean/std/n over seeds for the alpha-vs-score band.

    Operates on prepared (numeric) rows. The std over seeds is the visual defense
    against the "it's just randomness" objection (see seed_sweep.md).
    """

    from collections import defaultdict

    grouped: dict[tuple[str, float], list[float]] = defaultdict(list)
    for row in rows:
        if row.get("status") != "success":
            continue
        if str(row.get("dataset")) != dataset or str(row.get("perturbation")) != perturbation:
            continue
        value = _float(row.get(value_key))
        alpha = _float(row.get("alpha"))
        if math.isfinite(value) and math.isfinite(alpha):
            grouped[(str(row.get("workflow")), alpha)].append(value)

    table = []
    for (workflow, alpha), values in sorted(grouped.items()):
        average = sum(values) / len(values)
        if len(values) > 1:
            std = math.sqrt(sum((value - average) ** 2 for value in values) / len(values))
        else:
            std = 0.0
        table.append(
            {
                "workflow": workflow,
                "alpha": alpha,
                "mean": average,
                "std": std,
                "lower": average - std,
                "upper": average + std,
                "n_seeds": len(values),
            }
        )
    return table


def edit_distance_validation_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Successful rows with finite edit_distance_weighted and distribution_score."""

    return [
        row
        for row in rows
        if row.get("status") == "success"
        and math.isfinite(_float(row.get("edit_distance_weighted")))
        and math.isfinite(_float(row.get("distribution_score")))
        and not is_excluded_perturbation(row)
    ]


def community_label_source_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Successful community_weakening rows tagged with a label_source."""

    return [
        row
        for row in rows
        if row.get("status") == "success"
        and str(row.get("perturbation")) == "community_weakening"
        and str(row.get("label_source") or "") in {"ground_truth", "detected"}
    ]


def parse_uploaded_csv(text: str) -> list[dict[str, object]]:
    return [dict(row) for row in csv.DictReader(text.splitlines())]


def prepare_result_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    prepared = []
    for row in rows:
        item = dict(row)
        for column in NUMERIC_FLOAT_COLUMNS:
            item[column] = _float(item.get(column))
        for column in NUMERIC_INT_COLUMNS:
            value = _float(item.get(column))
            item[column] = int(value) if math.isfinite(value) else math.nan
        item["status"] = str(item.get("status") or "")
        item["workflow"] = str(item.get("workflow") or "")
        item["dataset"] = str(item.get("dataset") or "")
        item["perturbation"] = str(item.get("perturbation") or "")
        prepared.append(item)
    return prepared


def default_chart_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return [
        row
        for row in rows
        if row.get("status") == "success" and math.isfinite(_float(row.get("distribution_score")))
        and not is_excluded_perturbation(row)
    ]


def is_excluded_perturbation(row: dict[str, object]) -> bool:
    return str(row.get("perturbation") or "") in EXCLUDED_PERTURBATIONS


def exclude_aggregate_perturbations(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in rows if not is_excluded_perturbation(row)]


def has_legacy_diversity_rows(rows: Iterable[dict[str, object]]) -> bool:
    return any(row.get("workflow") == LEGACY_DIVERSITY_WORKFLOW for row in rows)


def has_legacy_workflow_rows(rows: Iterable[dict[str, object]]) -> bool:
    return any(row.get("workflow") in LEGACY_WORKFLOWS for row in rows)


def build_evaluation_tables(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summary = generate_evaluation_summary(rows)
    return summary, generate_final_matrix(summary)


def main() -> None:
    st, px, pd = _dashboard_dependencies()
    st.set_page_config(page_title="Experiment Results", layout="wide")
    st.title("Experiment Results")

    rows, run_dir = _load_rows_from_sidebar(st)
    if not rows:
        st.info("No result rows loaded.")
        return

    prepared_rows = exclude_aggregate_perturbations(prepare_result_rows(rows))
    if not prepared_rows:
        st.info("No result rows loaded after removing legacy aggregate edge/triangle perturbations.")
        return
    df = pd.DataFrame(prepared_rows)
    _render_status_summary(st, df)

    if has_legacy_workflow_rows(prepared_rows):
        st.warning(
            "This result file contains legacy workflow rows. "
            "Select a corrected run under results/runs/ for NativeNetLSD and shortest-path diversity results."
        )

    filtered = _filter_dataframe(st, df)
    chart_df = filtered[filtered["status"] == "success"].copy()

    tabs = st.tabs(
        [
            "Score vs Alpha (seed band)",
            "Failure Map",
            "Edit-distance Validation",
            "Community: truth vs detected",
            "Paired Distance",
            "Mean Shift vs Paired",
            "Evaluation Summary",
            "Final Matrix",
            "Raw Rows",
        ]
    )
    with tabs[0]:
        _seed_band_chart(st, px, pd, chart_df)
    with tabs[1]:
        _failure_map_panel(st, px, pd, _records_for_evaluation(filtered), run_dir)
    with tabs[2]:
        _edit_distance_validation_chart(st, px, pd, chart_df)
    with tabs[3]:
        _community_comparison_chart(st, px, pd, chart_df)
    with tabs[4]:
        _line_chart(st, px, chart_df, "paired_score", "Paired Distance vs Alpha")
    with tabs[5]:
        _scatter_chart(st, px, chart_df)
    with tabs[6]:
        summary_rows, _ = build_evaluation_tables(_records_for_evaluation(filtered))
        summary_df = pd.DataFrame(summary_rows)
        st.dataframe(summary_df, width="stretch")
        _summary_heatmap(st, px, summary_df)
    with tabs[7]:
        _, matrix_rows = build_evaluation_tables(_records_for_evaluation(filtered))
        st.dataframe(pd.DataFrame(matrix_rows), width="stretch")
    with tabs[8]:
        st.dataframe(filtered, width="stretch")


def _load_rows_from_sidebar(st) -> tuple[list[dict[str, object]], Path | None]:
    st.sidebar.header("Results")
    results_root = st.sidebar.text_input("Results root", str(DEFAULT_RESULTS_ROOT))
    runs = discover_runs(results_root)
    if runs:
        labels = [run.name for run in runs]
        choice = st.sidebar.selectbox("Run", labels, index=0)
        selected = runs[labels.index(choice)]
        manifest = selected / "run_manifest.json"
        if manifest.is_file():
            st.sidebar.caption(f"manifest: {manifest}")
        return load_result_rows(run_results_path(selected)), selected

    st.sidebar.info(f"No runs found under {results_root}. Upload or point to a CSV.")
    uploaded = st.sidebar.file_uploader("Upload result CSV", type="csv")
    path_text = st.sidebar.text_input("Or result path", str(default_results_path()))
    if uploaded is not None:
        return parse_uploaded_csv(uploaded.getvalue().decode("utf-8")), None
    path = Path(path_text)
    if not path.is_file():
        st.sidebar.error(f"Result file not found: {path}")
        return [], None
    run_dir = path.parent.parent if path.parent.name == "results" else None
    return load_result_rows(path), run_dir


def _render_status_summary(st, df) -> None:
    total = len(df)
    success = int((df["status"] == "success").sum()) if total else 0
    skipped = int((df["status"] == "skipped").sum()) if total else 0
    failed = int((df["status"] == "failed").sum()) if total else 0
    datasets = int(df["dataset"].nunique()) if total else 0
    workflows = int(df["workflow"].nunique()) if total else 0
    columns = st.columns(5)
    columns[0].metric("Rows", total)
    columns[1].metric("Success", success)
    columns[2].metric("Skipped", skipped)
    columns[3].metric("Failed", failed)
    columns[4].metric("Datasets / Workflows", f"{datasets} / {workflows}")


def _filter_dataframe(st, df):
    st.sidebar.header("Filters")
    filtered = df
    for column in ("dataset", "perturbation", "workflow", "status"):
        values = sorted(value for value in filtered[column].dropna().unique() if value != "")
        selected = st.sidebar.multiselect(column, values, default=values)
        if selected:
            filtered = filtered[filtered[column].isin(selected)]
    seeds = sorted(value for value in filtered["seed"].dropna().unique() if not _is_nan(value))
    selected_seeds = st.sidebar.multiselect("seed", seeds, default=seeds)
    if selected_seeds:
        filtered = filtered[filtered["seed"].isin(selected_seeds)]
    return filtered


def _line_chart(st, px, df, y_column: str, title: str) -> None:
    chart_df = _finite_frame(df, ("alpha", y_column))
    if chart_df.empty:
        st.info(f"No successful rows with finite `{y_column}` values.")
        return
    grouped = (
        chart_df.groupby(["dataset", "perturbation", "workflow", "alpha"], as_index=False)[y_column]
        .mean()
        .sort_values(["dataset", "perturbation", "workflow", "alpha"])
    )
    grouped = _add_display_labels(grouped)
    normalized_column = f"{y_column}_normalized"
    grouped = _add_normalized_metric(grouped, y_column, normalized_column)
    fig = px.line(
        grouped,
        x="alpha",
        y=normalized_column,
        color="workflow_label",
        facet_col="dataset_label",
        facet_row="perturbation_label",
        markers=True,
        title=f"{title} (normalized per workflow)",
        hover_data={
            "dataset": True,
            "perturbation": True,
            "workflow": True,
            y_column: ":.4g",
            normalized_column: ":.3f",
            "dataset_label": False,
            "perturbation_label": False,
            "workflow_label": False,
        },
        category_orders={
            "dataset_label": list(DATASET_LABELS.values()),
            "perturbation_label": list(PERTURBATION_LABELS.values()),
            "workflow_label": list(WORKFLOW_LABELS.values()),
        },
        facet_row_spacing=0.055,
        facet_col_spacing=0.045,
        labels={
            "alpha": "Alpha",
            normalized_column: "Normalized score",
            "workflow_label": "Workflow",
        },
    )
    _clean_facet_annotations(fig)
    fig.update_yaxes(range=[0, 1.05])
    fig.update_layout(
        height=_facet_chart_height(grouped["perturbation_label"].nunique()),
        legend_title_text="Workflow",
        margin=dict(l=30, r=30, t=80, b=30),
    )
    st.plotly_chart(fig, width="stretch")


def _scatter_chart(st, px, df) -> None:
    chart_df = _finite_frame(df, ("mean_shift_score", "paired_score"))
    if chart_df.empty:
        st.info("No successful rows with finite mean-shift and paired scores.")
        return
    chart_df = _add_display_labels(chart_df)
    chart_df = _add_normalized_metric(chart_df, "mean_shift_score", "mean_shift_score_normalized")
    chart_df = _add_normalized_metric(chart_df, "paired_score", "paired_score_normalized")
    fig = px.scatter(
        chart_df,
        x="mean_shift_score_normalized",
        y="paired_score_normalized",
        color="workflow_label",
        symbol="dataset_label",
        hover_data={
            "dataset": True,
            "perturbation": True,
            "alpha": True,
            "seed": True,
            "workflow": True,
            "mean_shift_score": ":.4g",
            "paired_score": ":.4g",
            "mean_shift_score_normalized": ":.3f",
            "paired_score_normalized": ":.3f",
            "dataset_label": False,
            "workflow_label": False,
        },
        title="Mean Shift vs Paired Distance (normalized per dataset, perturbation, workflow)",
        category_orders={
            "dataset_label": list(DATASET_LABELS.values()),
            "workflow_label": list(WORKFLOW_LABELS.values()),
        },
        labels={
            "mean_shift_score_normalized": "Normalized mean-shift",
            "paired_score_normalized": "Normalized paired distance",
            "workflow_label": "Workflow",
            "dataset_label": "Dataset",
        },
    )
    fig.update_xaxes(range=[0, 1.05])
    fig.update_yaxes(range=[0, 1.05])
    fig.update_layout(legend_title_text="Workflow", margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(fig, width="stretch")


def _seed_band_chart(st, px, pd, df) -> None:
    if df.empty:
        st.info("No successful rows available.")
        return
    datasets = sorted(value for value in df["dataset"].dropna().unique() if value != "")
    perturbations = sorted(value for value in df["perturbation"].dropna().unique() if value != "")
    if not datasets or not perturbations:
        st.info("No (dataset, perturbation) cells available.")
        return
    dataset = st.selectbox("Dataset", datasets, key="seed_band_dataset")
    perturbation = st.selectbox("Perturbation", perturbations, key="seed_band_perturbation")

    table = seed_band_table(df.to_dict("records"), dataset, perturbation, "distribution_score")
    if not table:
        st.info("No rows for the selected cell.")
        return
    band_df = pd.DataFrame(table)
    band_df["workflow_label"] = band_df["workflow"].apply(lambda value: _display_label(WORKFLOW_LABELS, value))
    max_seeds = int(band_df["n_seeds"].max())
    fig = px.line(
        band_df,
        x="alpha",
        y="mean",
        color="workflow_label",
        error_y="std",
        markers=True,
        title=f"{_display_label(DATASET_LABELS, dataset)} / {_display_label(PERTURBATION_LABELS, perturbation)} "
        f"- mean +/- std over up to {max_seeds} seeds",
        category_orders={"workflow_label": list(WORKFLOW_LABELS.values())},
        labels={"alpha": "Alpha", "mean": "Distribution score", "workflow_label": "Workflow"},
    )
    fig.update_layout(legend_title_text="Workflow", margin=dict(l=30, r=30, t=70, b=30))
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "A rising mean that clears its own seed band is the visual defense against "
        "the 'it's just randomness' objection (see seed_sweep.md)."
    )


def _failure_map_panel(st, px, pd, records, run_dir) -> None:
    failure_rows = load_failure_map_rows(run_dir, records)
    if not failure_rows:
        st.info("No failure-map cells available.")
        return
    fm_df = pd.DataFrame(failure_rows)
    fig = px.scatter(
        fm_df,
        x="perturbation",
        y="dataset",
        color="cause",
        color_discrete_map=FAILURE_CAUSE_COLORS,
        category_orders={"cause": list(FAILURE_CAUSES)},
        hover_data={
            "best_workflow": True,
            "best_sensitivity": True,
            "max_edit_distance_raw": True,
            "note": True,
        },
        title="Failure map: diagnosed cause per (dataset, perturbation)",
    )
    fig.update_traces(marker=dict(size=26, symbol="square"))
    fig.update_layout(legend_title_text="Cause", margin=dict(l=30, r=30, t=60, b=30))
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Explains WHY a cell behaves as it does: perturbation_starved (nothing to "
        "detect) vs method_blind (real change missed) vs unstable vs ok. See failure_map.md."
    )
    st.dataframe(fm_df, width="stretch")


def _edit_distance_validation_chart(st, px, pd, df) -> None:
    rows = edit_distance_validation_rows(df.to_dict("records"))
    if not rows:
        st.info("No rows with finite edit_distance_weighted and distribution_score.")
        return
    chart_df = _add_display_labels(pd.DataFrame(rows))
    fig = px.scatter(
        chart_df,
        x="edit_distance_weighted",
        y="distribution_score",
        color="workflow_label",
        facet_col="dataset_label",
        hover_data={"perturbation": True, "alpha": True, "seed": True, "workflow": True},
        category_orders={
            "dataset_label": list(DATASET_LABELS.values()),
            "workflow_label": list(WORKFLOW_LABELS.values()),
        },
        title="Edit-distance validation: distribution score vs importance-weighted edit distance",
        labels={
            "edit_distance_weighted": "Weighted edit distance (ground truth)",
            "distribution_score": "Distribution score",
            "workflow_label": "Workflow",
        },
    )
    _clean_facet_annotations(fig)
    fig.update_layout(legend_title_text="Workflow", margin=dict(l=30, r=30, t=70, b=30))
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "A positive trend validates alpha: scores grow with how much important "
        "structure was actually edited, not merely with the nominal dial (see alpha_validation.md)."
    )


def _community_comparison_chart(st, px, pd, df) -> None:
    rows = community_label_source_rows(df.to_dict("records"))
    if not rows:
        st.info("No community_weakening rows with a label_source.")
        return
    chart_df = pd.DataFrame(rows)
    grouped = (
        chart_df.groupby(["dataset", "label_source", "alpha"], as_index=False)["distribution_score"]
        .mean()
        .sort_values(["dataset", "label_source", "alpha"])
    )
    grouped["dataset_label"] = grouped["dataset"].apply(lambda value: _display_label(DATASET_LABELS, value))
    fig = px.line(
        grouped,
        x="alpha",
        y="distribution_score",
        color="dataset_label",
        line_dash="label_source",
        markers=True,
        title="Community weakening: ground_truth (SBM) vs detected (ER/BA)",
        labels={
            "alpha": "Alpha",
            "distribution_score": "Distribution score",
            "dataset_label": "Dataset",
            "label_source": "Label source",
        },
    )
    fig.update_layout(margin=dict(l=30, r=30, t=70, b=30))
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "ER/BA use DETECTED communities (a partition of a near-structureless graph is "
        "noise -> expected low/flat response: the negative control). SBM uses the planted "
        "GROUND_TRUTH partition. See community_detection.md."
    )


def _summary_heatmap(st, px, summary_df) -> None:
    if summary_df.empty:
        return
    selected_label = st.selectbox("Metric", list(EVALUATION_HEATMAP_METRICS), key="evaluation_heatmap_metric")
    metric = EVALUATION_HEATMAP_METRICS[selected_label]
    fig = px.density_heatmap(
        summary_df,
        x="perturbation",
        y="workflow",
        z=metric,
        histfunc="avg",
        color_continuous_scale="Greens",
        title=f"Average {selected_label}",
        labels={metric: selected_label},
    )
    fig.update_layout(margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(fig, width="stretch")


def _records_for_evaluation(df) -> list[dict[str, object]]:
    records = []
    for row in df.to_dict(orient="records"):
        item = dict(row)
        for key, value in item.items():
            if _is_nan(value):
                item[key] = ""
        records.append(item)
    return records


def _finite_frame(df, columns: tuple[str, ...]):
    filtered = df
    for column in columns:
        filtered = filtered[filtered[column].apply(lambda value: math.isfinite(_float(value)))]
    return filtered


def _add_display_labels(df):
    labeled = df.copy()
    labeled["dataset_label"] = labeled["dataset"].apply(lambda value: _display_label(DATASET_LABELS, value))
    labeled["perturbation_label"] = labeled["perturbation"].apply(
        lambda value: _display_label(PERTURBATION_LABELS, value)
    )
    labeled["workflow_label"] = labeled["workflow"].apply(lambda value: _display_label(WORKFLOW_LABELS, value))
    return labeled


def _add_normalized_metric(df, value_column: str, output_column: str):
    normalized = df.copy()
    max_by_panel = normalized.groupby(["dataset", "perturbation", "workflow"])[value_column].transform("max")
    denominator = max_by_panel.mask(max_by_panel <= 0, 1.0)
    normalized[output_column] = normalized[value_column] / denominator
    return normalized


def _display_label(labels: dict[str, str], value: object) -> str:
    text = str(value)
    return labels.get(text, text)


def _clean_facet_annotations(fig) -> None:
    for annotation in fig.layout.annotations:
        annotation.text = _clean_facet_label_text(annotation.text)


def _clean_facet_label_text(text: str) -> str:
    if "=" not in text:
        return text
    return text.split("=", 1)[1]


def _facet_chart_height(row_count: int) -> int:
    return max(620, 210 * max(1, row_count) + 160)


def _dashboard_dependencies():
    try:
        import pandas as pd  # type: ignore[import-not-found]
        import plotly.express as px  # type: ignore[import-not-found]
        import streamlit as st  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "Dashboard dependencies are missing. Install them with: "
            "python3 -m pip install -r requirements-dashboard.txt"
        ) from exc
    return st, px, pd


def _float(value: object) -> float:
    if value in (None, ""):
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _is_nan(value: object) -> bool:
    return isinstance(value, float) and math.isnan(value)


if __name__ == "__main__":
    main()
