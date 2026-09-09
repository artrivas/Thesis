"""Fresh, independent exploratory analysis: interaction-effect hero figures.

This script deliberately ignores every pre-existing figure/table in this repo
(`figures/`, `figures_final/`, `evaluation/*.csv`, the earlier
`poster_figures/hero_*` pair) and recomputes everything from the raw,
per-seed rows in the last completed run:

    src/results/runs/2026-07-03_merged/results/results.csv

It targets DATASET x WORKFLOW x PERTURBATION interaction effects (does a
workflow's behavior flip sign or rank depending on the dataset?), not the
main effects ("score increases with alpha") already documented elsewhere.

Produces, under src/results/runs/2026-07-03_merged/poster_figures/interaction_findings/:

    hero_1_triangle_insertion_synthetic_vs_real.png / .svg
        GraphStats+MMD's response to triangle insertion, overlaid across all
        four datasets: it reverses (rises then falls) on every synthetic
        graph family (ER, BA, SBM) but rises smoothly and monotonically on
        real IMDB-BINARY graphs -- the same metric, opposite qualitative
        behavior, entirely explained by which dataset it's run on.

    hero_2_community_weakening_ground_truth_myth.png / .svg
        Community-weakening sensitivity (Spearman rho, all four workflows),
        grouped by dataset: ground-truth SBM communities do NOT produce the
        strongest signal. Detected (non-ground-truth) communities on
        degree-heterogeneous BA graphs beat SBM's ground truth for 3 of 4
        workflows; ER (also detected, no ground truth) fails outright. What
        predicts signal strength is latent structural heterogeneity, not
        whether ground-truth labels exist.

Run from the src/ directory with the project's existing venv:

    .venv/bin/python3 scripts/generate_interaction_hero_figures.py
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
OUTPUT_DIR = RUN_ROOT / "poster_figures" / "interaction_findings"

WORKFLOW_COLORS = {
    "structural_statistics_mmd": "#0072B2",
    "wl_subtree_kernel_mmd": "#E69F00",
    "native_netlsd": "#009E73",
    "diversity_curves_shortest_path": "#CC79A7",
}
WORKFLOW_SHORT = {
    "structural_statistics_mmd": "GraphStats+MMD",
    "wl_subtree_kernel_mmd": "WL+MMD",
    "native_netlsd": "NetLSD",
    "diversity_curves_shortest_path": "Diversity Curves",
}

DATASET_COLORS = {
    "barabasi_albert": "#7570B3",
    "erdos_renyi": "#D95F02",
    "imdb_binary": "#1B9E77",
    "stochastic_block_model": "#E7298A",
}
DATASET_SHORT = {
    "barabasi_albert": "BA (synthetic)",
    "erdos_renyi": "ER (synthetic)",
    "imdb_binary": "IMDB-BINARY (real)",
    "stochastic_block_model": "SBM (synthetic)",
}


def load_results() -> pd.DataFrame:
    df = pd.read_csv(RESULTS_CSV)
    df = df[df["status"] == "success"].copy()
    for column in ("alpha", "seed", "distribution_score"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def spearmanr(x: pd.Series, y: pd.Series) -> float:
    xr, yr = x.rank(), y.rank()
    if xr.std() == 0 or yr.std() == 0:
        return 0.0
    return float(np.corrcoef(xr, yr)[0, 1])


# ---------------------------------------------------------------------------
# HERO 1: GraphStats+MMD, triangle_insertion, 4 datasets overlaid
# ---------------------------------------------------------------------------

def build_hero_reversal(df: pd.DataFrame) -> plt.Figure:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 24,
            "axes.labelsize": 28,
            "legend.fontsize": 22,
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
    cell = df[(df["perturbation"] == "triangle_insertion") & (df["workflow"] == "structural_statistics_mmd")]

    fig = plt.figure(figsize=(16, 12.5))
    fig.subplots_adjust(left=0.10, right=0.97, bottom=0.115, top=0.62)
    ax = fig.add_subplot(111)

    for dataset in ["barabasi_albert", "erdos_renyi", "stochastic_block_model", "imdb_binary"]:
        sub = cell[cell["dataset"] == dataset]
        stats = sub.groupby("alpha")["distribution_score"].agg(["mean", "std"]).reset_index()
        stats["std"] = stats["std"].fillna(0.0)
        scale = stats["mean"].abs().max()
        scale = scale if scale and scale > 1e-12 else 1.0
        stats["mean_n"] = stats["mean"] / scale
        stats["std_n"] = stats["std"] / scale
        color = DATASET_COLORS[dataset]
        ax.plot(stats["alpha"], stats["mean_n"], color=color, linewidth=5.0, marker="o", markersize=12,
                 markeredgecolor="white", markeredgewidth=0.6, label=DATASET_SHORT[dataset])
        ax.fill_between(stats["alpha"], stats["mean_n"] - stats["std_n"], stats["mean_n"] + stats["std_n"],
                          color=color, alpha=0.12, linewidth=0)

    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.05, 1.15)
    ax.set_xticks([i / 10 for i in range(0, 11, 2)])
    ax.set_xlabel(r"$\alpha$  (perturbation strength: fraction of triangle-insertion budget spent)")
    ax.set_ylabel("Normalized GraphStats+MMD score")

    fig.text(0.5, 0.975, "One metric, opposite verdicts", fontsize=38, fontweight="bold", ha="center")
    fig.text(0.5, 0.905, "GraphStats+MMD under triangle insertion, same workflow across all four datasets",
              fontsize=23, color="#333333", ha="center")
    fig.text(
        0.5, 0.72,
        "It REVERSES on every synthetic graph (ER, BA, SBM) but rises\n"
        "cleanly on real IMDB-BINARY data -- the 'failure' is a synthetic-data\n"
        "artifact, not a flaw in the metric itself",
        ha="center", va="center", fontsize=23, fontweight="bold", color="#B00020",
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#FFF3F3", edgecolor="#B00020", linewidth=2),
    )

    ax.annotate(
        "synthetic graphs:\npeak, then reverse",
        xy=(0.3, 1.0), xytext=(0.40, 0.60),
        fontsize=21, fontweight="bold", color="#333333", ha="left",
        arrowprops=dict(arrowstyle="->", color="#333333", linewidth=2.5),
    )
    ax.annotate(
        "real IMDB-BINARY:\nsmooth, monotonic rise",
        xy=(0.9, 1.0), xytext=(0.35, 0.28),
        fontsize=21, fontweight="bold", color=DATASET_COLORS["imdb_binary"], ha="left",
        arrowprops=dict(arrowstyle="->", color=DATASET_COLORS["imdb_binary"], linewidth=2.5),
    )

    legend = ax.legend(loc="lower right", frameon=True, ncol=1, fontsize=20)
    legend.get_frame().set_alpha(0.9)

    fig.text(
        0.5, 0.025,
        "Note: lines here are colored by DATASET, not by workflow (unlike the other hero figures) -- "
        "this panel fixes the workflow (GraphStats+MMD) and varies the dataset. "
        "Ribbon = +/-1 std across seeds (24 seeds: BA/ER/SBM; 5 seeds: IMDB-BINARY). "
        "Scores normalized by each dataset's own max for shape comparison.",
        ha="center", fontsize=15, style="italic", color="#555555",
    )
    return fig


# ---------------------------------------------------------------------------
# HERO 2: community_weakening sensitivity, grouped bars, all datasets x workflows
# ---------------------------------------------------------------------------

def build_hero_ground_truth_myth(df: pd.DataFrame) -> plt.Figure:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 24,
            "axes.labelsize": 28,
            "legend.fontsize": 20,
            "xtick.labelsize": 19,
            "ytick.labelsize": 24,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": "#e5e5e5",
            "grid.linewidth": 1.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )
    cell = df[df["perturbation"] == "community_weakening"]

    dataset_order = ["erdos_renyi", "stochastic_block_model", "barabasi_albert", "imdb_binary"]
    dataset_axis_labels = {
        "erdos_renyi": "ER -- no structure",
        "stochastic_block_model": "SBM -- ground truth",
        "barabasi_albert": "BA -- detected",
        "imdb_binary": "IMDB-BINARY -- real",
    }
    workflow_order = list(WORKFLOW_SHORT.keys())

    sens = {}
    for (wf, dataset), g in cell.groupby(["workflow", "dataset"]):
        sens[(wf, dataset)] = spearmanr(g["alpha"], g["distribution_score"])

    fig = plt.figure(figsize=(16, 12.5))
    fig.subplots_adjust(left=0.09, right=0.97, bottom=0.20, top=0.62)
    ax = fig.add_subplot(111)

    n_wf = len(workflow_order)
    group_width = 0.8
    bar_width = group_width / n_wf
    x_base = np.arange(len(dataset_order))

    for i, wf in enumerate(workflow_order):
        heights = [sens[(wf, ds)] for ds in dataset_order]
        xpos = x_base - group_width / 2 + bar_width * (i + 0.5)
        ax.bar(xpos, heights, width=bar_width * 0.92, color=WORKFLOW_COLORS[wf],
                edgecolor="white", linewidth=0.8, label=WORKFLOW_SHORT[wf])

    ax.set_xticks(x_base)
    ax.set_xticklabels([dataset_axis_labels[d] for d in dataset_order])
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Sensitivity to community weakening\n(Spearman rho, alpha vs. score)")
    ax.axhline(0, color="#333333", linewidth=1.0)

    fig.text(0.5, 0.975, "Ground truth is not what predicts signal", fontsize=36, fontweight="bold", ha="center")
    fig.text(0.5, 0.905, "Community-weakening sensitivity, all four workflows, by dataset",
              fontsize=23, color="#333333", ha="center")
    fig.text(
        0.5, 0.72,
        "SBM's GROUND-TRUTH partition is beaten by BA's purely DETECTED one\n"
        "for 3 of 4 workflows -- only structureless ER fails, ground truth or not",
        ha="center", va="center", fontsize=23, fontweight="bold", color="#8B5A00",
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#FFF8E7", edgecolor="#8B5A00", linewidth=2),
    )

    legend = ax.legend(loc="upper left", frameon=True, ncol=2, fontsize=19, bbox_to_anchor=(0.0, 1.0))
    legend.get_frame().set_alpha(0.9)

    fig.text(
        0.5, 0.03,
        "24 seeds (ER, SBM, BA); 5 seeds (IMDB-BINARY). Community labels: ground truth only for SBM; "
        "detected (Clauset-Newman-Moore) for ER, BA, and IMDB-BINARY.",
        ha="center", fontsize=16, style="italic", color="#555555",
    )
    return fig


def monotonicity_violation_fraction(alpha: pd.Series, score: pd.Series) -> float:
    means = pd.DataFrame({"alpha": alpha, "score": score}).groupby("alpha")["score"].mean().sort_index()
    vals = means.values
    if len(vals) < 2:
        return 0.0
    violations = sum(1 for a, b in zip(vals, vals[1:]) if b < a)
    return violations / (len(vals) - 1)


def coefficient_of_variation(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    avg = values.mean()
    sigma = values.std(ddof=0)
    if abs(avg) < 1e-12:
        return 0.0 if sigma < 1e-12 else np.inf
    return sigma / abs(avg)


def compute_cell_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (workflow, dataset, perturbation): sensitivity, monotonicity violation, seed CV."""

    rows = []
    for (workflow, dataset, perturbation), g in df.groupby(["workflow", "dataset", "perturbation"]):
        sensitivity = spearmanr(g["alpha"], g["distribution_score"])
        violation = monotonicity_violation_fraction(g["alpha"], g["distribution_score"])
        seed_means = g.groupby("seed")["distribution_score"].mean()
        seed_cv = coefficient_of_variation(seed_means.values)
        rows.append({
            "workflow": workflow, "dataset": dataset, "perturbation": perturbation,
            "sensitivity": sensitivity, "monotonicity_violation": violation, "seed_cv": seed_cv,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# HERO 3: confidently-wrong vs correctly-uncertain scatter
# ---------------------------------------------------------------------------

def build_hero_confidence_scatter(df: pd.DataFrame) -> plt.Figure:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 24,
            "axes.labelsize": 27,
            "legend.fontsize": 18,
            "xtick.labelsize": 23,
            "ytick.labelsize": 23,
            "axes.grid": True,
            "grid.color": "#e5e5e5",
            "grid.linewidth": 1.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )
    metrics = compute_cell_metrics(df)
    metrics["wf_short"] = metrics["workflow"].map(WORKFLOW_SHORT)
    metrics["size"] = 130 + 950 * metrics["sensitivity"].clip(lower=0.0)

    confidently_wrong = (metrics["monotonicity_violation"] >= 0.3) & (metrics["seed_cv"] <= 0.05)
    correctly_uncertain = (metrics["sensitivity"] >= 0.6) & (metrics["seed_cv"] >= 0.15)

    fig = plt.figure(figsize=(16, 10.0))
    fig.subplots_adjust(left=0.11, right=0.80, bottom=0.13, top=0.80)
    ax = fig.add_subplot(111)

    for workflow, short in WORKFLOW_SHORT.items():
        sub = metrics[metrics["workflow"] == workflow]
        ax.scatter(
            sub["monotonicity_violation"], sub["seed_cv"], s=sub["size"],
            color=WORKFLOW_COLORS[workflow], alpha=0.75, edgecolor="white", linewidth=1.0,
            label=short, zorder=3,
        )

    # Outline the two categories of interest without disturbing the workflow color encoding.
    ax.scatter(
        metrics.loc[confidently_wrong, "monotonicity_violation"], metrics.loc[confidently_wrong, "seed_cv"],
        s=metrics.loc[confidently_wrong, "size"] + 260, facecolors="none", edgecolors="#B00020",
        linewidth=3.0, zorder=4,
    )
    ax.scatter(
        metrics.loc[correctly_uncertain, "monotonicity_violation"], metrics.loc[correctly_uncertain, "seed_cv"],
        s=metrics.loc[correctly_uncertain, "size"] + 260, facecolors="none", edgecolors="#00695C",
        linewidth=3.0, zorder=4,
    )

    ax.set_xlim(-0.03, 0.78)
    ax.set_ylim(-0.02, 0.68)
    ax.set_xlabel("Monotonicity violation fraction (higher = more alpha-steps go the wrong way)")
    ax.set_ylabel("Seed CV (higher = noisier across seeds)")

    fig.text(0.5, 0.965, "Low seed noise is not the same as being right", fontsize=34, fontweight="bold", ha="center")
    fig.text(
        0.5, 0.88,
        "Monotonicity violation vs. seed CV, all 96 workflow x dataset x perturbation cells "
        "(marker size = sensitivity)",
        fontsize=20, color="#333333", ha="center",
    )

    ax.annotate(
        "confidently wrong: near-zero seed noise,\nbut systematically non-monotonic\n(GraphStats+MMD, synthetic triangle/edge cells)",
        xy=(0.55, 0.025), xytext=(0.36, 0.32),
        fontsize=16, fontweight="bold", color="#B00020", ha="left",
        arrowprops=dict(arrowstyle="->", color="#B00020", linewidth=2.5),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#FFF3F3", edgecolor="#B00020", linewidth=1.5),
    )
    ax.annotate(
        "correctly uncertain: noisy across seeds,\nbut high sensitivity (right trend)\n(mostly IMDB-BINARY cells)",
        xy=(0.09, 0.20), xytext=(0.16, 0.58),
        fontsize=16, fontweight="bold", color="#00695C", ha="left",
        arrowprops=dict(arrowstyle="->", color="#00695C", linewidth=2.5),
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#F1FBF9", edgecolor="#00695C", linewidth=1.5),
    )

    legend = ax.legend(
        loc="upper left", frameon=True, fontsize=17, title="Workflow", title_fontsize=17,
        bbox_to_anchor=(1.01, 1.0), borderaxespad=0.0,
    )
    legend.get_frame().set_alpha(0.9)

    fig.text(
        0.5, 0.03,
        "96 cells = 4 workflows x 4 datasets x 6 perturbations. Red/teal rings mark the two categories "
        "discussed on the poster; ring color, not fill, indicates category membership.",
        ha="center", fontsize=14, style="italic", color="#555555",
    )
    return fig


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_results()

    fig1 = build_hero_reversal(df)
    fig1.savefig(OUTPUT_DIR / "hero_1_triangle_insertion_synthetic_vs_real.png", dpi=300, bbox_inches="tight")
    fig1.savefig(OUTPUT_DIR / "hero_1_triangle_insertion_synthetic_vs_real.svg", format="svg", bbox_inches="tight")
    plt.close(fig1)

    fig2 = build_hero_ground_truth_myth(df)
    fig2.savefig(OUTPUT_DIR / "hero_2_community_weakening_ground_truth_myth.png", dpi=300, bbox_inches="tight")
    fig2.savefig(OUTPUT_DIR / "hero_2_community_weakening_ground_truth_myth.svg", format="svg", bbox_inches="tight")
    plt.close(fig2)

    fig3 = build_hero_confidence_scatter(df)
    fig3.savefig(OUTPUT_DIR / "hero_3_confidently_wrong_vs_correctly_uncertain.png", dpi=300, bbox_inches="tight")
    fig3.savefig(OUTPUT_DIR / "hero_3_confidently_wrong_vs_correctly_uncertain.svg", format="svg", bbox_inches="tight")
    plt.close(fig3)

    print(OUTPUT_DIR / "hero_1_triangle_insertion_synthetic_vs_real.png")
    print(OUTPUT_DIR / "hero_2_community_weakening_ground_truth_myth.png")
    print(OUTPUT_DIR / "hero_3_confidently_wrong_vs_correctly_uncertain.png")


if __name__ == "__main__":
    main()
