"""Interactive Streamlit dashboard for experiment result sanity checks."""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experimentation.evaluation import generate_evaluation_summary, generate_final_matrix
from experimentation.runner import read_result_rows
from experimentation.workflows import DIVERSITY_CURVES_WORKFLOW, LEGACY_NETLSD_MMD_WORKFLOW, NATIVE_NETLSD_WORKFLOW


DEFAULT_RESULTS_PATH_CANDIDATES = (
    Path("outputs/experimentation_native_netlsd/results/results.csv"),
)
LEGACY_DIVERSITY_WORKFLOW = "diversity_curves_l2"
FIXED_DIVERSITY_WORKFLOW = DIVERSITY_CURVES_WORKFLOW
LEGACY_WORKFLOWS = {LEGACY_DIVERSITY_WORKFLOW, LEGACY_NETLSD_MMD_WORKFLOW}
DATASET_LABELS = {
    "erdos_renyi": "ER",
    "stochastic_block_model": "SBM",
    "barabasi_albert": "BA",
}
PERTURBATION_LABELS = {
    "edge_addition_deletion": "edge",
    "triangle_injection_removal": "triangle",
    "community_weakening": "community",
    "hub_modification": "hub",
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
    "runtime_seconds",
    "memory_mb",
)
NUMERIC_INT_COLUMNS = ("seed",)
SCORE_COLUMNS = ("distribution_score", "paired_score", "mean_shift_score")


def default_results_path(candidates: tuple[Path, ...] = DEFAULT_RESULTS_PATH_CANDIDATES) -> Path:
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def load_result_rows(path: Path | str) -> list[dict[str, object]]:
    return [dict(row) for row in read_result_rows(path)]


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
    ]


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

    rows = _load_rows_from_sidebar(st)
    if not rows:
        st.info("No result rows loaded.")
        return

    prepared_rows = prepare_result_rows(rows)
    df = pd.DataFrame(prepared_rows)
    _render_status_summary(st, df)

    if has_legacy_workflow_rows(prepared_rows):
        st.warning(
            "This result file contains legacy workflow rows. "
            f"Use `{DEFAULT_RESULTS_PATH_CANDIDATES[0]}` for corrected NativeNetLSD and shortest-path diversity results."
        )

    filtered = _filter_dataframe(st, df)
    chart_df = filtered[filtered["status"] == "success"].copy()

    tabs = st.tabs(
        [
            "Score vs Alpha",
            "Paired Distance",
            "Mean Shift vs Paired",
            "Evaluation Summary",
            "Final Matrix",
            "Raw Rows",
        ]
    )
    with tabs[0]:
        _line_chart(st, px, chart_df, "distribution_score", "Distribution Score vs Alpha")
    with tabs[1]:
        _line_chart(st, px, chart_df, "paired_score", "Paired Distance vs Alpha")
    with tabs[2]:
        _scatter_chart(st, px, chart_df)
    with tabs[3]:
        summary_rows, _ = build_evaluation_tables(_records_for_evaluation(filtered))
        summary_df = pd.DataFrame(summary_rows)
        st.dataframe(summary_df, width="stretch")
        _summary_heatmap(st, px, summary_df)
    with tabs[4]:
        _, matrix_rows = build_evaluation_tables(_records_for_evaluation(filtered))
        st.dataframe(pd.DataFrame(matrix_rows), width="stretch")
    with tabs[5]:
        st.dataframe(filtered, width="stretch")


def _load_rows_from_sidebar(st) -> list[dict[str, object]]:
    st.sidebar.header("Results")
    uploaded = st.sidebar.file_uploader("Upload result CSV", type="csv")
    path_text = st.sidebar.text_input("Or result path", str(default_results_path()))
    if uploaded is not None:
        return parse_uploaded_csv(uploaded.getvalue().decode("utf-8"))
    path = Path(path_text)
    if not path.is_file():
        st.sidebar.error(f"Result file not found: {path}")
        return []
    return load_result_rows(path)


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
    fig = px.scatter(
        chart_df,
        x="mean_shift_score",
        y="paired_score",
        color="workflow_label",
        symbol="dataset_label",
        hover_data=["dataset", "perturbation", "alpha", "seed", "workflow"],
        title="Mean Shift vs Paired Distance",
        category_orders={
            "dataset_label": list(DATASET_LABELS.values()),
            "workflow_label": list(WORKFLOW_LABELS.values()),
        },
        labels={
            "workflow_label": "Workflow",
            "dataset_label": "Dataset",
        },
    )
    fig.update_layout(legend_title_text="Workflow", margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(fig, width="stretch")


def _summary_heatmap(st, px, summary_df) -> None:
    if summary_df.empty:
        return
    fig = px.density_heatmap(
        summary_df,
        x="perturbation",
        y="workflow",
        z="sensitivity",
        histfunc="avg",
        color_continuous_scale="Greens",
        title="Average Sensitivity",
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
