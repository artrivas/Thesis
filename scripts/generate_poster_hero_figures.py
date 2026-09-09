"""Generate the two A0-poster HERO figures plus one supplementary panel set.

Reads only the merged run's raw results (no cached figures/plots are used as
input):

    src/results/runs/2026-07-03_merged/results/results.csv

Produces, under src/results/runs/2026-07-03_merged/poster_figures/:

    hero_1_triangle_insertion_divergence.png / .svg
        BA + triangle_insertion: GraphStats+MMD's score curve reverses while
        the other three workflows keep climbing -- the strongest direct
        evidence that no single metric is universally best.

    hero_2_edge_deletion_agreement.png / .svg
        ER + edge_deletion: all four workflows rise together, monotonically,
        with near-zero seed variance -- the "textbook" clean-agreement case.

    supplementary_panels.png / .svg
        2x2 small-multiples (smaller fonts, clearly secondary) covering the
        remaining annotated cells: IMDB hub_modification (real-data
        saturation), ER hub_modification (unstable global signal), SBM
        community_weakening (ground-truth community signal, corrected
        direction), IMDB community_weakening (pseudo-community signal).

Run from the src/ directory with the project's existing venv:

    .venv/bin/python3 scripts/generate_poster_hero_figures.py
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

# Okabe-Ito colorblind-safe palette, consistent with figures_final/.
WORKFLOW_COLORS = {
    "structural_statistics_mmd": "#0072B2",
    "wl_subtree_kernel_mmd": "#E69F00",
    "native_netlsd": "#009E73",
    "diversity_curves_shortest_path": "#CC79A7",
}
WORKFLOW_MARKERS = {
    "structural_statistics_mmd": "o",
    "wl_subtree_kernel_mmd": "s",
    "native_netlsd": "^",
    "diversity_curves_shortest_path": "D",
}
WORKFLOW_SHORT = {
    "structural_statistics_mmd": "GraphStats+MMD",
    "wl_subtree_kernel_mmd": "WL+MMD",
    "native_netlsd": "NetLSD",
    "diversity_curves_shortest_path": "Diversity Curves",
}

NORMALIZATION_NOTE = (
    "Scores normalized within each workflow (0-1 by its own max) to compare response "
    "shapes, not absolute distance magnitudes. Ribbon = +/-1 std across seeds."
)


def load_results() -> pd.DataFrame:
    df = pd.read_csv(RESULTS_CSV)
    df = df[df["status"] == "success"].copy()
    for column in ("alpha", "seed", "distribution_score"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def _alpha_stats(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    grouped = df.groupby("alpha")[score_col].agg(["mean", "std"]).reset_index()
    grouped["std"] = grouped["std"].fillna(0.0)
    return grouped.sort_values("alpha")


def _normalize(stats: pd.DataFrame) -> pd.DataFrame:
    scale = stats["mean"].abs().max()
    scale = scale if scale and abs(scale) > 1e-12 else 1.0
    stats = stats.copy()
    stats["mean"] = stats["mean"] / scale
    stats["std"] = stats["std"] / scale
    return stats


def _plot_cell(ax, df: pd.DataFrame, dataset: str, perturbation: str, linewidth: float, markersize: float, ribbon_alpha: float) -> None:
    cell = df[(df["dataset"] == dataset) & (df["perturbation"] == perturbation)]
    for workflow in WORKFLOW_SHORT:
        subset = cell[cell["workflow"] == workflow]
        if subset.empty:
            continue
        stats = _normalize(_alpha_stats(subset, "distribution_score"))
        color = WORKFLOW_COLORS[workflow]
        marker = WORKFLOW_MARKERS[workflow]
        ax.plot(
            stats["alpha"], stats["mean"], color=color, linewidth=linewidth,
            marker=marker, markersize=markersize, markeredgecolor="white", markeredgewidth=0.6,
        )
        ax.fill_between(
            stats["alpha"], stats["mean"] - stats["std"], stats["mean"] + stats["std"],
            color=color, alpha=ribbon_alpha, linewidth=0,
        )
    ax.set_xlim(-0.02, 1.02)
    ax.set_xticks([i / 10 for i in range(0, 11, 2)])


def _legend_handles(linewidth: float, markersize: float):
    return [
        Line2D(
            [0], [0], color=WORKFLOW_COLORS[w], linewidth=linewidth, marker=WORKFLOW_MARKERS[w],
            markersize=markersize, markeredgecolor="white", markeredgewidth=0.6, label=WORKFLOW_SHORT[w],
        )
        for w in WORKFLOW_SHORT
    ]


# ---------------------------------------------------------------------------
# HERO 1: BA + triangle_insertion -- divergence / no-universal-best-metric
# ---------------------------------------------------------------------------

def build_hero_divergence(df: pd.DataFrame) -> plt.Figure:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 24,
            "axes.titlesize": 34,
            "axes.titleweight": "bold",
            "axes.labelsize": 28,
            "legend.fontsize": 24,
            "xtick.labelsize": 24,
            "ytick.labelsize": 24,
            "axes.grid": True,
            "grid.color": "#e5e5e5",
            "grid.linewidth": 1.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )
    fig = plt.figure(figsize=(16, 12.5))
    fig.subplots_adjust(left=0.09, right=0.97, bottom=0.115, top=0.60)
    ax = fig.add_subplot(111)
    _plot_cell(ax, df, "barabasi_albert", "triangle_insertion", linewidth=5.0, markersize=13, ribbon_alpha=0.14)

    ax.set_ylim(-0.35, 1.08)
    ax.set_xlabel(r"$\alpha$  (perturbation strength: fraction of triangle-insertion budget spent)")
    ax.set_ylabel("Normalized distribution score")

    fig.text(0.5, 0.975, "No single metric is universal", fontsize=38, fontweight="bold", ha="center")
    fig.text(0.5, 0.905, "Triangle insertion on BA graphs", fontsize=25, color="#333333", ha="center")
    fig.text(
        0.5, 0.72,
        "GraphStats+MMD REVERSES ($\\rho$ = -0.05) while the other three keep\nclimbing ($\\rho \\approx 0.99$) as more triangles are inserted",
        ha="center", va="center", fontsize=23, fontweight="bold", color="#B00020",
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#FFF3F3", edgecolor="#B00020", linewidth=2),
    )

    # Point directly at the peak-then-reversal of GraphStats+MMD.
    ax.annotate(
        "peaks here, then\nfalls as $\\alpha \\to 1$",
        xy=(0.3, 1.0), xytext=(0.62, 0.55),
        fontsize=22, fontweight="bold", color=WORKFLOW_COLORS["structural_statistics_mmd"],
        ha="left",
        arrowprops=dict(arrowstyle="->", color=WORKFLOW_COLORS["structural_statistics_mmd"], linewidth=3),
    )

    legend = ax.legend(handles=_legend_handles(5.0, 15), loc="lower left", frameon=True, ncol=1)
    legend.get_frame().set_alpha(0.9)

    fig.text(0.5, 0.025, NORMALIZATION_NOTE, ha="center", fontsize=17, style="italic", color="#555555")
    return fig


# ---------------------------------------------------------------------------
# HERO 2: ER + edge_deletion -- textbook clean agreement
# ---------------------------------------------------------------------------

def build_hero_agreement(df: pd.DataFrame) -> plt.Figure:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 24,
            "axes.titlesize": 34,
            "axes.titleweight": "bold",
            "axes.labelsize": 28,
            "legend.fontsize": 24,
            "xtick.labelsize": 24,
            "ytick.labelsize": 24,
            "axes.grid": True,
            "grid.color": "#e5e5e5",
            "grid.linewidth": 1.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )
    fig = plt.figure(figsize=(16, 12.5))
    fig.subplots_adjust(left=0.09, right=0.97, bottom=0.115, top=0.60)
    ax = fig.add_subplot(111)
    _plot_cell(ax, df, "erdos_renyi", "edge_deletion", linewidth=5.0, markersize=13, ribbon_alpha=0.14)

    ax.set_ylim(-0.05, 1.08)
    ax.set_xlabel(r"$\alpha$  (perturbation strength: fraction of edges deleted)")
    ax.set_ylabel("Normalized distribution score")

    fig.text(0.5, 0.975, "The textbook case: every metric agrees", fontsize=38, fontweight="bold", ha="center")
    fig.text(0.5, 0.905, "Edge deletion on ER graphs", fontsize=25, color="#333333", ha="center")
    fig.text(
        0.5, 0.72,
        "All four detect the perturbation with near-perfect monotonicity\n"
        "($\\rho \\geq 0.99$, seed CV $\\leq$ 3.4%) -- each reliably, though their sensitivity onset differs",
        ha="center", va="center", fontsize=23, fontweight="bold", color="#00695C",
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#F1FBF9", edgecolor="#00695C", linewidth=2),
    )

    legend = ax.legend(handles=_legend_handles(5.0, 15), loc="lower right", frameon=True, ncol=1)
    legend.get_frame().set_alpha(0.9)

    fig.text(0.5, 0.025, NORMALIZATION_NOTE, ha="center", fontsize=17, style="italic", color="#555555")
    return fig


# ---------------------------------------------------------------------------
# SUPPLEMENTARY: remaining annotated cells, small multiples, secondary scale
# ---------------------------------------------------------------------------

SUPP_SPECS = [
    dict(
        letter="C", dataset="imdb_binary", perturbation="hub_modification",
        title="C. Hub modification (IMDB-BINARY)", tag="real-data saturation",
    ),
    dict(
        letter="D", dataset="erdos_renyi", perturbation="hub_modification",
        title="D. Hub modification (ER)", tag="unstable global signal",
    ),
    dict(
        letter="E", dataset="stochastic_block_model", perturbation="community_weakening",
        title="E. Community weakening (SBM, ground truth)", tag="ground-truth community signal",
    ),
    dict(
        letter="F", dataset="imdb_binary", perturbation="community_weakening",
        title="F. Community weakening (IMDB, detected)", tag="pseudo-community signal",
    ),
]


def build_supplementary(df: pd.DataFrame) -> plt.Figure:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 12,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 12,
            "legend.fontsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "axes.grid": True,
            "grid.color": "#e5e5e5",
            "grid.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 7.5), sharex=True, sharey=True)
    for ax, spec in zip(axes.flatten(), SUPP_SPECS):
        _plot_cell(ax, df, spec["dataset"], spec["perturbation"], linewidth=2.0, markersize=4, ribbon_alpha=0.10)
        ax.set_title(spec["title"], fontsize=12)
        ax.text(
            0.03, 0.94, spec["tag"], transform=ax.transAxes, fontsize=8.5, style="italic",
            color="#444444", va="top",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#f2f2f2", edgecolor="none"),
        )
        ax.set_ylim(-0.05, 1.08)

    fig.text(0.5, 0.035, r"$\alpha$ (perturbation strength)", ha="center", fontsize=12)
    fig.text(0.02, 0.55, "Normalized score", va="center", rotation="vertical", fontsize=12)
    fig.suptitle("Supplementary evidence: saturation, instability, and community signal", fontsize=14, y=1.0)

    legend_handles = _legend_handles(2.2, 6)
    fig.legend(handles=legend_handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout(rect=(0.04, 0.06, 1.0, 0.96))
    return fig


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_results()

    fig1 = build_hero_divergence(df)
    fig1.savefig(OUTPUT_DIR / "hero_1_triangle_insertion_divergence.png", dpi=300, bbox_inches="tight")
    fig1.savefig(OUTPUT_DIR / "hero_1_triangle_insertion_divergence.svg", format="svg", bbox_inches="tight")
    plt.close(fig1)

    fig2 = build_hero_agreement(df)
    fig2.savefig(OUTPUT_DIR / "hero_2_edge_deletion_agreement.png", dpi=300, bbox_inches="tight")
    fig2.savefig(OUTPUT_DIR / "hero_2_edge_deletion_agreement.svg", format="svg", bbox_inches="tight")
    plt.close(fig2)

    fig3 = build_supplementary(df)
    fig3.savefig(OUTPUT_DIR / "supplementary_panels.png", dpi=220, bbox_inches="tight")
    fig3.savefig(OUTPUT_DIR / "supplementary_panels.svg", format="svg", bbox_inches="tight")
    plt.close(fig3)

    print(OUTPUT_DIR / "hero_1_triangle_insertion_divergence.png")
    print(OUTPUT_DIR / "hero_2_edge_deletion_agreement.png")
    print(OUTPUT_DIR / "supplementary_panels.png")


if __name__ == "__main__":
    main()
