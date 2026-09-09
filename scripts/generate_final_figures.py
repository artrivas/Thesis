"""Generate the thesis-final figure set from the merged 2026-07-03_merged run.

Reads only:
    src/results/runs/2026-07-03_merged/results/results.csv
    src/results/runs/2026-07-03_merged/evaluation/evaluation_summary.csv

Writes into src/results/runs/2026-07-03_merged/figures_final/:
    main_response_curves.{pdf,svg}          -- Figura principal 1
    summary_performance_heatmap.{pdf,svg}   -- Figura principal 2
    granularity_heatmap_refined.{pdf,svg}   -- Figura principal 3
    appendix_full_score_curves.{pdf,svg}    -- Apendice A (24 paneles, distribution_score)
    appendix_full_paired_distance_curves.{pdf,svg}  -- Apendice B (24 paneles, paired_score)

Does not recompute or alter any experimental value: every number plotted here
comes straight out of the two CSVs above (results.csv / evaluation_summary.csv),
the same files experimentation/evaluation.py and experimentation/figures.py
already use. This script only changes *how* those numbers are displayed.

Run from the src/ directory with the project's existing venv:

    .venv/bin/python3 scripts/generate_final_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

RUN_ROOT = Path(__file__).resolve().parent.parent / "results" / "runs" / "2026-07-03_merged"
_RAW_RESULTS_CSV = RUN_ROOT / "results" / "results.csv"
# The 23 MB raw CSV is not committed; the gzipped copy next to it is. pandas
# reads either transparently from the file extension.
RESULTS_CSV = _RAW_RESULTS_CSV if _RAW_RESULTS_CSV.is_file() else _RAW_RESULTS_CSV.with_suffix(".csv.gz")
EVAL_SUMMARY_CSV = RUN_ROOT / "evaluation" / "evaluation_summary.csv"
OUTPUT_DIR = RUN_ROOT / "figures_final"

# ---------------------------------------------------------------------------
# Shared vocabulary: one order, one color, one short name per workflow, used
# identically across every figure in this script (and matching the palette
# used for the poster figure so the whole thesis is visually consistent).
# ---------------------------------------------------------------------------

WORKFLOW_ORDER = [
    "structural_statistics_mmd",
    "wl_subtree_kernel_mmd",
    "native_netlsd",
    "diversity_curves_shortest_path",
]

WORKFLOW_SHORT = {
    "structural_statistics_mmd": "GraphStats+MMD",
    "wl_subtree_kernel_mmd": "WL+MMD",
    "native_netlsd": "NetLSD",
    "diversity_curves_shortest_path": "Diversity Curves",
}

# Okabe-Ito colorblind-safe palette.
WORKFLOW_COLORS = {
    "structural_statistics_mmd": "#0072B2",  # blue
    "wl_subtree_kernel_mmd": "#E69F00",       # orange
    "native_netlsd": "#009E73",               # bluish green
    "diversity_curves_shortest_path": "#CC79A7",  # reddish purple
}

WORKFLOW_MARKERS = {
    "structural_statistics_mmd": "o",
    "wl_subtree_kernel_mmd": "s",
    "native_netlsd": "^",
    "diversity_curves_shortest_path": "D",
}

# Methodological family, used to order the granularity heatmap.
WORKFLOW_FAMILY = {
    "structural_statistics_mmd": "MMD-based",
    "wl_subtree_kernel_mmd": "MMD-based",
    "native_netlsd": "Mean-shift-based",
    "diversity_curves_shortest_path": "Mean-shift-based",
}

DATASET_LABELS = {
    "barabasi_albert": "BA",
    "erdos_renyi": "ER",
    "stochastic_block_model": "SBM",
    "imdb_binary": "IMDB-BINARY",
}
DATASET_ORDER = ["barabasi_albert", "erdos_renyi", "stochastic_block_model", "imdb_binary"]

PERTURBATION_LABELS = {
    "edge_insertion": "edge insertion",
    "edge_deletion": "edge deletion",
    "triangle_insertion": "triangle insertion",
    "triangle_deletion": "triangle deletion",
    "community_weakening": "community weakening",
    "hub_modification": "hub modification",
}
PERTURBATION_ORDER = [
    "edge_deletion",
    "edge_insertion",
    "triangle_deletion",
    "triangle_insertion",
    "community_weakening",
    "hub_modification",
]

# Same taxonomy experimentation/evaluation.py uses (PERTURBATION_GRANULARITY),
# reproduced here so this script needs only the two CSVs, not the package.
PERTURBATION_GRANULARITY = {
    "edge_insertion": "local",
    "edge_deletion": "local",
    "triangle_insertion": "local/mesoscopic",
    "triangle_deletion": "local/mesoscopic",
    "community_weakening": "mesoscopic",
    "hub_modification": "global",
}

ALPHA_TICKS = [0.0, 0.25, 0.5, 0.75, 1.0]

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 12,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "legend.fontsize": 10.5,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "axes.grid": True,
        "grid.color": "#e7e7e7",
        "grid.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,  # embed text as text, not paths, in the PDF too
    }
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_results() -> pd.DataFrame:
    df = pd.read_csv(RESULTS_CSV)
    df = df[df["status"] == "success"].copy()
    for column in ("alpha", "seed", "distribution_score", "paired_score", "mean_shift_score"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def load_evaluation_summary() -> pd.DataFrame:
    df = pd.read_csv(EVAL_SUMMARY_CSV)
    numeric_columns = [
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
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def save_figure(fig: plt.Figure, name: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = OUTPUT_DIR / f"{name}.pdf"
    svg_path = OUTPUT_DIR / f"{name}.svg"
    fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(pdf_path)
    print(svg_path)


# ---------------------------------------------------------------------------
# Shared plotting helpers
# ---------------------------------------------------------------------------


def _alpha_stats(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """Per-alpha mean/std of score_col, averaged over the seed replicates."""

    grouped = df.groupby("alpha")[score_col].agg(["mean", "std", "count"]).reset_index()
    grouped["std"] = grouped["std"].fillna(0.0)
    return grouped.sort_values("alpha")


def _normalize(stats: pd.DataFrame) -> pd.DataFrame:
    """Scale mean/std by the workflow's own max mean, so shapes are comparable."""

    scale = stats["mean"].max()
    scale = scale if scale and abs(scale) > 1e-12 else 1.0
    stats = stats.copy()
    stats["mean"] = stats["mean"] / scale
    stats["std"] = stats["std"] / scale
    return stats


def _clean_axes(ax: plt.Axes) -> None:
    ax.set_xlim(-0.02, 1.02)
    ax.set_xticks(ALPHA_TICKS)
    ax.set_xticklabels([f"{t:g}" for t in ALPHA_TICKS])


# ---------------------------------------------------------------------------
# Figura principal 1: main_response_curves
# ---------------------------------------------------------------------------

# Order is reading order: row 1 = panels 1-4, row 2 = panels 5-8.
# 'overlay_paired_workflows' lists the workflow(s) for which the normalized
# paired_score is also drawn (dashed, same color) on top of distribution_score.
# Only structural_statistics_mmd is overlaid, and only in the two cells where
# the Pearson correlation between distribution_score(alpha) and paired_score(alpha)
# is lowest for that workflow (0.51 and 0.44 respectively -- see the diagnostic
# in the chat): these are the two cases where the "two curves say the same
# thing" simplification actually breaks down, so showing both is informative
# rather than redundant. Overlaying all four workflows there would just add
# clutter, since for the other three the two curves are >0.93 correlated.
MAIN_PANEL_SPECS = [
    dict(dataset="barabasi_albert", perturbation="edge_deletion", overlay_paired_workflows=[],
         tag="detección consistente"),
    dict(dataset="erdos_renyi", perturbation="edge_insertion", overlay_paired_workflows=["structural_statistics_mmd"],
         tag="GraphStats+MMD diverge"),
    dict(dataset="barabasi_albert", perturbation="triangle_insertion", overlay_paired_workflows=["structural_statistics_mmd"],
         tag="divergencia más fuerte"),
    dict(dataset="stochastic_block_model", perturbation="community_weakening", overlay_paired_workflows=[],
         tag="partición real"),
    dict(dataset="erdos_renyi", perturbation="community_weakening", overlay_paired_workflows=[],
         tag="control negativo"),
    dict(dataset="erdos_renyi", perturbation="hub_modification", overlay_paired_workflows=[],
         tag="señal inestable"),
    dict(dataset="imdb_binary", perturbation="hub_modification", overlay_paired_workflows=[],
         tag="dato real"),
    dict(dataset="imdb_binary", perturbation="community_weakening", overlay_paired_workflows=[],
         tag="comunidad detectada"),
]


def _panel_title(spec: dict) -> str:
    main = f"{DATASET_LABELS[spec['dataset']]} · {PERTURBATION_LABELS[spec['perturbation']]}"
    return f"{main}\n({spec['tag']})"


def _plot_response_panel(ax: plt.Axes, df: pd.DataFrame, spec: dict) -> None:
    cell = df[(df["dataset"] == spec["dataset"]) & (df["perturbation"] == spec["perturbation"])]
    for workflow in WORKFLOW_ORDER:
        subset = cell[cell["workflow"] == workflow]
        if subset.empty:
            continue
        color = WORKFLOW_COLORS[workflow]
        marker = WORKFLOW_MARKERS[workflow]

        dist_stats = _normalize(_alpha_stats(subset, "distribution_score"))
        ax.plot(
            dist_stats["alpha"], dist_stats["mean"],
            color=color, linewidth=2.2, marker=marker, markersize=4.5, linestyle="-",
        )
        ax.fill_between(
            dist_stats["alpha"],
            dist_stats["mean"] - dist_stats["std"],
            dist_stats["mean"] + dist_stats["std"],
            color=color, alpha=0.12, linewidth=0,
        )

        if workflow in spec["overlay_paired_workflows"]:
            paired_stats = _normalize(_alpha_stats(subset, "paired_score"))
            ax.plot(
                paired_stats["alpha"], paired_stats["mean"],
                color=color, linewidth=1.6, linestyle="--", alpha=0.9,
                marker=marker, markersize=3, markerfacecolor="white",
            )

    ax.set_title(_panel_title(spec), fontsize=11, pad=8)
    ax.set_ylim(-0.03, 1.08)
    _clean_axes(ax)


def plot_main_response_curves(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(18, 8.0), sharex=True, sharey=True, gridspec_kw={"hspace": 0.5})
    flat_axes = axes.flatten()
    for ax, spec in zip(flat_axes, MAIN_PANEL_SPECS):
        _plot_response_panel(ax, df, spec)

    for ax in axes[0]:
        ax.tick_params(labelbottom=False)
    for ax in axes[:, 1:].flatten():
        ax.tick_params(labelleft=False)

    fig.text(0.5, 0.05, r"$\alpha$ (intensidad de perturbación)", ha="center", fontsize=13)
    fig.text(0.08, 0.55, "Score normalizado (por workflow)", va="center", rotation="vertical", fontsize=13)

    workflow_handles = [
        Line2D(
            [0], [0], color=WORKFLOW_COLORS[w], linewidth=2.4, marker=WORKFLOW_MARKERS[w],
            markersize=6, label=WORKFLOW_SHORT[w],
        )
        for w in WORKFLOW_ORDER
    ]
    style_handles = [
        Line2D([0], [0], color="#555555", linewidth=2.2, linestyle="-", label="distribution_score"),
        Line2D(
            [0], [0], color="#555555", linewidth=1.6, linestyle="--",
            label="paired_score (solo GraphStats+MMD, donde diverge del distribution_score)",
        ),
    ]
    legend1 = fig.legend(
        handles=workflow_handles, loc="lower center", ncol=4, frameon=False,
        bbox_to_anchor=(0.5, -0.015), title="Workflow",
    )
    fig.add_artist(legend1)
    fig.legend(
        handles=style_handles, loc="lower center", ncol=2, frameon=False,
        bbox_to_anchor=(0.5, -0.075),
    )

    fig.text(
        0.5, -0.115,
        "Cada curva se normaliza dividiendo por su propio máximo (compara la forma de la respuesta, no la "
        "magnitud absoluta entre workflows). La banda sombreada es ± 1 desv. estándar entre semillas.",
        ha="center", fontsize=9.5, style="italic", color="#555555",
    )

    fig.suptitle("Figura 1. Curvas de respuesta representativas ante α", fontsize=16, y=1.02, fontweight="bold")
    fig.tight_layout(rect=(0.09, 0.14, 1.0, 1.0))
    save_figure(fig, "main_response_curves")


# ---------------------------------------------------------------------------
# Figura principal 2: summary_performance_heatmap
# ---------------------------------------------------------------------------


def _column_minmax_goodness(values: np.ndarray, lower_is_better: bool) -> np.ndarray:
    """Per-column min-max scaling so color always means 'better', any unit."""

    v = -values if lower_is_better else values
    vmin, vmax = np.nanmin(v), np.nanmax(v)
    if vmax - vmin < 1e-12:
        return np.full_like(v, 0.5)
    return (v - vmin) / (vmax - vmin)


def plot_summary_performance_heatmap(summary: pd.DataFrame) -> None:
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(16, 5.2), gridspec_kw={"width_ratios": [1.05, 1.0]})

    # --- Panel A: workflow x perturbation-type sensitivity (avg over datasets) ---
    pivot = (
        summary.groupby(["workflow", "perturbation"])["sensitivity"]
        .mean()
        .unstack("perturbation")
        .reindex(index=WORKFLOW_ORDER, columns=PERTURBATION_ORDER)
    )
    data_a = pivot.to_numpy()
    im_a = ax_a.imshow(data_a, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
    ax_a.set_xticks(range(len(PERTURBATION_ORDER)))
    ax_a.set_xticklabels([PERTURBATION_LABELS[p] for p in PERTURBATION_ORDER], rotation=35, ha="right")
    ax_a.set_yticks(range(len(WORKFLOW_ORDER)))
    ax_a.set_yticklabels([WORKFLOW_SHORT[w] for w in WORKFLOW_ORDER])
    for i in range(data_a.shape[0]):
        for j in range(data_a.shape[1]):
            value = data_a[i, j]
            text_color = "white" if value < 0.55 else "#111111"
            ax_a.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=9.5, color=text_color)
    ax_a.set_title("A. Sensibilidad promedio por tipo de perturbación\n(promedio entre datasets)", fontsize=12)
    cbar_a = fig.colorbar(im_a, ax=ax_a, fraction=0.046, pad=0.03)
    cbar_a.set_label("Sensibilidad (Spearman α↔score, recortado a [0,1])", fontsize=9.5)

    # --- Panel B: workflow x criterion, per-column min-max "goodness" color ---
    # Arrow marks direction of "better" so columns need only a short label;
    # the full definition goes in the caption below instead of the tick label,
    # which is what was colliding between adjacent columns before.
    criteria = [
        ("sensitivity", "Sensibilidad ↑", False, "{:.2f}"),
        ("monotonicity", "Monotonicidad ↓", True, "{:.2f}"),
        ("paired_detectability", "Detect. pareada ↑", False, "{:.2f}"),
        ("robustness_cv", "Robustez (CV) ↓", True, "{:.2f}"),
        ("relative_runtime", "Eficiencia ↓", True, "×{:.1f}"),
        ("interpretability_score", "Interpretabilidad ↑", False, "{:.0f}"),
    ]
    per_workflow = summary.groupby("workflow").mean(numeric_only=True).reindex(WORKFLOW_ORDER)

    color_matrix = np.zeros((len(WORKFLOW_ORDER), len(criteria)))
    text_matrix = []
    for col_index, (column, _label, lower_is_better, fmt) in enumerate(criteria):
        raw = per_workflow[column].to_numpy()
        color_matrix[:, col_index] = _column_minmax_goodness(raw, lower_is_better)
        text_matrix.append([fmt.format(v) for v in raw])

    im_b = ax_b.imshow(color_matrix, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
    ax_b.set_xticks(range(len(criteria)))
    ax_b.set_xticklabels([label for _, label, _, _ in criteria], fontsize=9.5, rotation=25, ha="right")
    ax_b.set_yticks(range(len(WORKFLOW_ORDER)))
    ax_b.set_yticklabels([WORKFLOW_SHORT[w] for w in WORKFLOW_ORDER])
    for i in range(len(WORKFLOW_ORDER)):
        for j in range(len(criteria)):
            value = color_matrix[i, j]
            text_color = "white" if value < 0.55 else "#111111"
            ax_b.text(j, i, text_matrix[j][i], ha="center", va="center", fontsize=9.5, color=text_color)
    ax_b.set_title("B. Comparación de desempeño por criterio\n(color = mejor/peor dentro de cada columna; texto = valor real)", fontsize=12)
    cbar_b = fig.colorbar(im_b, ax=ax_b, fraction=0.046, pad=0.03)
    cbar_b.set_label("Mejor →", fontsize=9.5)
    cbar_b.set_ticks([0, 1])
    cbar_b.set_ticklabels(["peor de los 4", "mejor de los 4"])

    fig.text(
        0.5, -0.10,
        "↑ mayor = mejor, ↓ menor = mejor (cada columna se normaliza por separado, comparando solo entre los 4 workflows).\n"
        "mean_shift_detectability se excluye de (B): para NetLSD y Diversity Curves es idéntico a distribution_score "
        "por construcción (duplicado, ver evaluation.py::MEAN_SHIFT_DUPLICATE_WORKFLOWS), no una comparación independiente.",
        ha="center", fontsize=9, style="italic", color="#555555",
    )

    fig.suptitle("Figura 2. Síntesis comparativa de desempeño", fontsize=16, y=1.08, fontweight="bold")
    fig.tight_layout(rect=(0.0, 0.04, 1.0, 1.0))
    save_figure(fig, "summary_performance_heatmap")


# ---------------------------------------------------------------------------
# Figura principal 3: granularity_heatmap_refined
# ---------------------------------------------------------------------------


def _granularity_values(summary: pd.DataFrame) -> pd.DataFrame:
    """Same aggregation as experimentation/figures.py::_granularity_values:
    every row's (clipped) sensitivity is added to the bucket(s) named in its
    granularity_label (split on '/'), AND unconditionally to an overall bucket
    (named 'multiscale' in the original code; relabeled 'Promedio' here since
    that is what it actually is -- every row contributes to it regardless of
    scale, so it is the workflow's average sensitivity, not a 'multiscale
    detection' signal in its own right).
    """

    rows = []
    for _, row in summary.iterrows():
        workflow = row["workflow"]
        score = float(np.clip(row["sensitivity"], 0.0, 1.0))
        label = row.get("granularity_label") or PERTURBATION_GRANULARITY.get(row["perturbation"], "unknown")
        for scale in str(label).split("/"):
            rows.append((workflow, scale, score))
        rows.append((workflow, "Promedio", score))
    long_df = pd.DataFrame(rows, columns=["workflow", "scale", "score"])
    return long_df.groupby(["workflow", "scale"])["score"].mean().unstack("scale")


def _order_workflows_by_family(pivot: pd.DataFrame) -> list[str]:
    ordered = []
    for family in ("MMD-based", "Mean-shift-based"):
        members = [w for w in WORKFLOW_ORDER if WORKFLOW_FAMILY[w] == family]
        members.sort(key=lambda w: pivot.loc[w, "Promedio"], reverse=True)
        ordered.extend(members)
    return ordered


def _qualitative_tier(value: float) -> tuple[str, str]:
    if value >= 0.75:
        return "alto", "#1b7837"
    if value >= 0.50:
        return "medio", "#b58900"
    return "bajo", "#b2182b"


def plot_granularity_heatmap_refined(summary: pd.DataFrame) -> None:
    scales = ["local", "mesoscopic", "global", "Promedio"]
    pivot = _granularity_values(summary).reindex(columns=scales)
    workflow_order = _order_workflows_by_family(pivot)
    pivot = pivot.reindex(index=workflow_order)
    data = pivot.to_numpy()

    # Near-tie detection: for each column, flag workflows within 0.03 of the
    # column's max value. Computed from the data, not hard-coded.
    tie_threshold = 0.03
    tie_notes = []
    tie_mask = np.zeros_like(data, dtype=bool)
    for col_index, scale in enumerate(scales):
        column = data[:, col_index]
        best = np.nanmax(column)
        close = np.where(best - column <= tie_threshold)[0]
        if len(close) >= 2:
            tie_mask[close, col_index] = True
            names = ", ".join(WORKFLOW_SHORT[workflow_order[i]] for i in close)
            values = ", ".join(f"{column[i]:.2f}" for i in close)
            tie_notes.append(f"{scale}: {names} (Δ≤{tie_threshold:g}; valores {values})")

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    im = ax.imshow(data, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")

    # Reserve extra room to the right (qualitative alto/medio/bajo column) and
    # above (the "nivel" header) so those annotations are never clipped by the
    # axes box -- this is what produced the cut-off "m dio" text before.
    n_rows = len(workflow_order)
    ax.set_xlim(-0.5, len(scales) + 1.15)
    ax.set_ylim(n_rows - 0.5, -1.05)

    ax.set_xticks(range(len(scales)))
    ax.set_xticklabels(["local", "mesoscopic", "global", "Promedio"])
    ax.set_yticks(range(len(workflow_order)))
    ax.set_yticklabels([WORKFLOW_SHORT[w] for w in workflow_order])

    # Family separator line + label.
    families_in_order = [WORKFLOW_FAMILY[w] for w in workflow_order]
    boundary = families_in_order.index("Mean-shift-based") if "Mean-shift-based" in families_in_order else None
    if boundary is not None and 0 < boundary < len(workflow_order):
        ax.axhline(boundary - 0.5, color="white", linewidth=2.4)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            text_color = "white" if value < 0.55 else "#111111"
            marker = "≈ " if tie_mask[i, j] else ""
            ax.text(j, i, f"{marker}{value:.2f}", ha="center", va="center", fontsize=10.5, color=text_color)
            if tie_mask[i, j]:
                ax.add_patch(
                    plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor="white",
                                  linewidth=1.6, linestyle=(0, (2, 1.5)))
                )

    # Qualitative alto/medio/bajo column, based on 'Promedio'. clip_on=False so
    # it is never cut off by the axes box regardless of layout engine rounding.
    qual_x = len(scales) - 0.15
    for row_index, workflow in enumerate(workflow_order):
        tier, color = _qualitative_tier(pivot.loc[workflow, "Promedio"])
        ax.text(
            qual_x, row_index, tier, ha="left", va="center", fontsize=10.5, color=color,
            fontweight="bold", clip_on=False,
        )
    ax.text(qual_x, -0.85, "nivel", fontsize=9.5, fontweight="bold", color="#333333", ha="left", clip_on=False)

    cbar = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.10)
    cbar.set_label("Sensibilidad promedio (0 = sin señal, 1 = detección monotónica fuerte)", fontsize=9.5)

    family_handles = [
        Patch(facecolor="none", edgecolor="none", label="── MMD-based (GraphStats+MMD, WL+MMD)"),
        Patch(facecolor="none", edgecolor="none", label="── Mean-shift-based (NetLSD, Diversity Curves)"),
    ]
    ax.legend(
        handles=family_handles, loc="upper left", bbox_to_anchor=(0.0, -0.18), frameon=False, fontsize=9,
        handlelength=0, ncol=1,
    )

    if tie_notes:
        note = "Valores casi idénticos (≈, recuadro punteado): " + " | ".join(tie_notes)
    else:
        note = "No se detectaron empates cercanos (Δ>0.03 en todas las columnas)."
    fig.text(0.5, -0.14, note, ha="center", fontsize=8.6, style="italic", color="#555555", wrap=True)

    fig.suptitle("Figura 3. Granularidad estructural por workflow", fontsize=15, y=1.06, fontweight="bold")
    fig.tight_layout(rect=(0.0, 0.12, 1.0, 1.0))
    save_figure(fig, "granularity_heatmap_refined")


# ---------------------------------------------------------------------------
# Apendice: full 4x6 grids (one figure for distribution_score, one for paired_score)
# ---------------------------------------------------------------------------


def _plot_appendix_grid(df: pd.DataFrame, score_col: str, title: str, filename: str) -> None:
    n_rows, n_cols = len(DATASET_ORDER), len(PERTURBATION_ORDER)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(22, 13), sharex=True, sharey=True)

    for row_index, dataset in enumerate(DATASET_ORDER):
        for col_index, perturbation in enumerate(PERTURBATION_ORDER):
            ax = axes[row_index, col_index]
            cell = df[(df["dataset"] == dataset) & (df["perturbation"] == perturbation)]
            for workflow in WORKFLOW_ORDER:
                subset = cell[cell["workflow"] == workflow]
                if subset.empty:
                    continue
                stats = _normalize(_alpha_stats(subset, score_col))
                color = WORKFLOW_COLORS[workflow]
                ax.plot(stats["alpha"], stats["mean"], color=color, linewidth=1.6, marker=WORKFLOW_MARKERS[workflow], markersize=2.6)
                ax.fill_between(
                    stats["alpha"], stats["mean"] - stats["std"], stats["mean"] + stats["std"],
                    color=color, alpha=0.10, linewidth=0,
                )
            ax.set_ylim(-0.03, 1.08)
            _clean_axes(ax)
            ax.tick_params(labelsize=7.5)
            if row_index == 0:
                ax.set_title(PERTURBATION_LABELS[perturbation], fontsize=10.5)
            if col_index == 0:
                ax.set_ylabel(DATASET_LABELS[dataset], fontsize=10.5, fontweight="bold")

    handles = [
        Line2D([0], [0], color=WORKFLOW_COLORS[w], linewidth=2.2, marker=WORKFLOW_MARKERS[w], markersize=6, label=WORKFLOW_SHORT[w])
        for w in WORKFLOW_ORDER
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.text(0.5, -0.055, r"$\alpha$ (intensidad de perturbación)", ha="center", fontsize=12)
    fig.text(0.07, 0.5, "Score normalizado (por workflow)", va="center", rotation="vertical", fontsize=12)
    fig.suptitle(title, fontsize=16, y=1.01, fontweight="bold")
    fig.tight_layout(rect=(0.08, 0.03, 1.0, 1.0))
    save_figure(fig, filename)


def plot_appendix_full_score_curves(df: pd.DataFrame) -> None:
    _plot_appendix_grid(
        df, "distribution_score",
        "Apendice A. Curvas completas de distribution_score vs α (4 datasets × 6 perturbaciones)",
        "appendix_full_score_curves",
    )


def plot_appendix_full_paired_distance_curves(df: pd.DataFrame) -> None:
    _plot_appendix_grid(
        df, "paired_score",
        "Apendice B. Curvas completas de paired_score vs α (4 datasets × 6 perturbaciones)",
        "appendix_full_paired_distance_curves",
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_results()
    summary = load_evaluation_summary()

    plot_main_response_curves(df)
    plot_summary_performance_heatmap(summary)
    plot_granularity_heatmap_refined(summary)
    plot_appendix_full_score_curves(df)
    plot_appendix_full_paired_distance_curves(df)


if __name__ == "__main__":
    main()
