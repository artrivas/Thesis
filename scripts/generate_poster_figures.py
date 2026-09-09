"""Generate the combined A-F poster figure from the merged 2026-07-03_merged run.

Reads only src/results/runs/2026-07-03_merged/results/results.csv. Produces
one 2x3 static SVG + PNG figure, plus a companion Markdown file with the long
per-panel captions (too long to render legibly inside a small subplot), under
src/results/runs/2026-07-03_merged/poster_figures/.

Run from the src/ directory with the project's existing venv:

    .venv/bin/python3 scripts/generate_poster_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

RUN_ROOT = Path(__file__).resolve().parent.parent / "results" / "runs" / "2026-07-03_merged"
_RAW_RESULTS_CSV = RUN_ROOT / "results" / "results.csv"
# The 23 MB raw CSV is not committed; the gzipped copy next to it is. pandas
# reads either transparently from the file extension.
RESULTS_CSV = _RAW_RESULTS_CSV if _RAW_RESULTS_CSV.is_file() else _RAW_RESULTS_CSV.with_suffix(".csv.gz")
OUTPUT_DIR = RUN_ROOT / "poster_figures"

# Same palette/labels as experimentation/figures.py, for visual consistency
# with the rest of the run's artifacts.
WORKFLOW_COLORS = {
    "structural_statistics_mmd": "#1f77b4",
    "wl_subtree_kernel_mmd": "#d62728",
    "native_netlsd": "#2ca02c",
    "diversity_curves_shortest_path": "#9467bd",
}
WORKFLOW_LABELS = {
    "structural_statistics_mmd": "GraphStats+MMD",
    "wl_subtree_kernel_mmd": "WLFeatures+MMD",
    "native_netlsd": "NetLSD",
    "diversity_curves_shortest_path": "DiversityCurveDistance",
}

Y_MIN, Y_MAX = -0.02, 1.05
RIBBON_ALPHA = 0.10

NORMALIZATION_NOTE = (
    "Scores are normalized within each workflow to compare response profiles, "
    "not absolute distance magnitudes."
)

# Order is reading order: row 1 = A, B, C; row 2 = D, E, F.
PANEL_SPECS = [
    dict(
        letter="A",
        dataset="stochastic_block_model",
        perturbation="edge_deletion",
        score_col="distribution_score",
        title="A. Local edge deletion",
        tag="consistent detection",
        caption=(
            "In SBM, all workflows respond monotonically to edge deletion, but their "
            "response speed differs. This confirms that local edge perturbations are "
            "detectable, while still revealing different sensitivity thresholds."
        ),
    ),
    dict(
        letter="B",
        dataset="barabasi_albert",
        perturbation="triangle_insertion",
        score_col="distribution_score",
        title="B. Triangle insertion",
        tag="method disagreement",
        caption=(
            "Triangle insertion separates response profiles: GraphStats+MMD saturates "
            "early, while WLFeatures+MMD, NetLSD, and DiversityCurveDistance provide a "
            "more gradual sensitivity curve."
        ),
    ),
    dict(
        letter="C",
        dataset="imdb_binary",
        perturbation="hub_modification",
        score_col="distribution_score",
        title="C. Hub modification on real graphs",
        tag="real-data saturation",
        caption=(
            "On IMDB-BINARY, hub modification produces early saturation, especially for "
            "GraphStats+MMD, while other workflows converge after intermediate "
            "perturbation levels."
        ),
    ),
    dict(
        letter="D",
        dataset="erdos_renyi",
        perturbation="hub_modification",
        score_col="distribution_score",
        title="D. Hub modification in ER",
        tag="unstable global signal",
        caption=(
            "In structureless ER graphs, hub modification produces rapid saturation and "
            "large seed variability, suggesting that global perturbations can become "
            "unstable or hard to interpret."
        ),
    ),
    dict(
        letter="E",
        dataset="stochastic_block_model",
        perturbation="community_weakening",
        score_col="distribution_score",
        title="E. Ground-truth community weakening",
        tag="ground-truth community signal",
        caption=(
            "In SBM, community weakening produces a meaningful mesoscopic signal because "
            "the partition is part of the generative process. WLFeatures+MMD reacts "
            "early, while GraphStats+MMD responds more slowly."
        ),
    ),
    dict(
        letter="F",
        dataset="imdb_binary",
        perturbation="community_weakening",
        score_col="distribution_score",
        title="F. Detected-community weakening",
        tag="pseudo-community signal",
        caption=(
            "In IMDB-BINARY, detected communities provide an operational mesoscopic "
            "signal, but they should be interpreted as pseudo-labels rather than ground "
            "truth."
        ),
    ),
]

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 13,
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
        "axes.labelsize": 13,
        "legend.fontsize": 13,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "axes.grid": True,
        "grid.color": "#e5e5e5",
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.fonttype": "none",  # keep text as text in the SVG, not paths
    }
)


def load_results() -> pd.DataFrame:
    df = pd.read_csv(RESULTS_CSV)
    df = df[df["status"] == "success"].copy()
    for column in ("alpha", "seed", "distribution_score", "paired_score", "mean_shift_score"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def _alpha_stats(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """Per-alpha mean/std of score_col, averaged over the seed replicates."""

    grouped = df.groupby("alpha")[score_col].agg(["mean", "std", "count"]).reset_index()
    grouped["std"] = grouped["std"].fillna(0.0)
    return grouped.sort_values("alpha")


def _normalize(stats: pd.DataFrame) -> pd.DataFrame:
    scale = stats["mean"].max()
    scale = scale if scale and abs(scale) > 1e-12 else 1.0
    stats = stats.copy()
    stats["mean"] = stats["mean"] / scale
    stats["std"] = stats["std"] / scale
    return stats


def _plot_panel(ax, df: pd.DataFrame, spec: dict) -> None:
    cell = df[(df["dataset"] == spec["dataset"]) & (df["perturbation"] == spec["perturbation"])]
    for workflow in WORKFLOW_LABELS:
        subset = cell[cell["workflow"] == workflow]
        if subset.empty:
            continue
        stats = _normalize(_alpha_stats(subset, spec["score_col"]))
        color = WORKFLOW_COLORS[workflow]
        ax.plot(stats["alpha"], stats["mean"], color=color, linewidth=2.4, marker="o", markersize=4)
        ax.fill_between(
            stats["alpha"],
            stats["mean"] - stats["std"],
            stats["mean"] + stats["std"],
            color=color,
            alpha=RIBBON_ALPHA,
            linewidth=0,
        )

    ax.set_title(spec["title"])
    ax.text(
        0.03,
        0.94,
        spec["tag"],
        transform=ax.transAxes,
        fontsize=10,
        style="italic",
        color="#444444",
        va="top",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#f2f2f2", edgecolor="none"),
    )
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_xticks([i / 10 for i in range(0, 11, 2)])


def build_figure(df: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(2, 3, figsize=(17, 10), sharex=True, sharey=True)
    flat_axes = axes.flatten()

    for ax, spec in zip(flat_axes, PANEL_SPECS):
        _plot_panel(ax, df, spec)

    # Suppress x tick labels on the top row (shared x-axis already ties the range).
    for ax in axes[0]:
        ax.tick_params(labelbottom=False)

    # Single shared x-axis label and y-axis label instead of one per panel.
    fig.text(0.5, 0.085, "alpha (perturbation strength)", ha="center", fontsize=14)
    fig.text(0.07, 0.55, "Normalized score", va="center", rotation="vertical", fontsize=14)

    # One shared legend (workflow color key) instead of six repeated legends.
    legend_handles = [
        Line2D([0], [0], color=WORKFLOW_COLORS[workflow], linewidth=2.6, label=WORKFLOW_LABELS[workflow])
        for workflow in WORKFLOW_LABELS
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=4,
        frameon=False,
        bbox_to_anchor=(0.5, 0.02),
    )

    # Normalization caveat, shared once for the whole figure.
    fig.text(0.5, -0.01, NORMALIZATION_NOTE, ha="center", fontsize=11, style="italic", color="#555555")

    fig.tight_layout(rect=(0.09, 0.11, 1.0, 1.0))
    return fig


def write_captions_file() -> Path:
    """Write the long per-panel captions to a companion file.

    These are too long to render legibly inside a small 2x3-grid subplot, so
    they are kept here for pasting under each panel in the poster layout tool
    instead of being baked into the figure image.
    """

    lines = ["# Panel captions (for poster layout, not embedded in the figure)", ""]
    for spec in PANEL_SPECS:
        lines.append(f"**{spec['title']}** ({spec['tag']})")
        lines.append("")
        lines.append(spec["caption"])
        lines.append("")
    lines.append(f"**Shared note (place once under the whole figure):** {NORMALIZATION_NOTE}")
    path = OUTPUT_DIR / "panel_captions.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_results()
    fig = build_figure(df)
    svg_path = OUTPUT_DIR / "poster_figure_A_F.svg"
    png_path = OUTPUT_DIR / "poster_figure_A_F.png"
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(svg_path)
    print(png_path)
    print(write_captions_file())


if __name__ == "__main__":
    main()
