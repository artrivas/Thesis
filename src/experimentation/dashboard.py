"""Interactive Streamlit dashboard for experiment result sanity checks."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Iterable

from experimentation.evaluation import generate_evaluation_summary, generate_final_matrix
from experimentation.runner import read_result_rows


DEFAULT_RESULTS_PATH = Path("outputs/experimentation/results/results.csv")
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
    return any(row.get("workflow") == "diversity_curves_l2" for row in rows)


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

    if has_legacy_diversity_rows(prepared_rows):
        st.warning(
            "This result file contains legacy `diversity_curves_l2` rows. "
            "Run the fixed experiments with `--no-resume` or a fresh output root before interpreting diversity results."
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
    path_text = st.sidebar.text_input("Or result path", str(DEFAULT_RESULTS_PATH))
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
    fig = px.line(
        grouped,
        x="alpha",
        y=y_column,
        color="workflow",
        facet_col="dataset",
        facet_row="perturbation",
        markers=True,
        title=title,
        hover_data=["dataset", "perturbation", "workflow"],
    )
    fig.update_layout(legend_title_text="Workflow", margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(fig, width="stretch")


def _scatter_chart(st, px, df) -> None:
    chart_df = _finite_frame(df, ("mean_shift_score", "paired_score"))
    if chart_df.empty:
        st.info("No successful rows with finite mean-shift and paired scores.")
        return
    fig = px.scatter(
        chart_df,
        x="mean_shift_score",
        y="paired_score",
        color="workflow",
        symbol="dataset",
        hover_data=["dataset", "perturbation", "alpha", "seed", "workflow"],
        title="Mean Shift vs Paired Distance",
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
