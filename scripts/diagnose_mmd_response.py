"""Reproduce seed-zero triangle curves and inspect RBF terms and bandwidth.

This targeted diagnostic leaves the historical run untouched. Raw bandwidth
values and reference-only standardization are exploratory ablations, not tuned
or selected production settings. Requires numpy, pandas, scipy, matplotlib.
"""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist, pdist

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from experimentation.datasets import SyntheticDatasetConfig, generate_paired_distribution
from experimentation.workflows import structural_statistics

OUT = ROOT / "results/analysis/2026-09-09_statistical_audit"
FEATURES = ["nodes", "edges", "density", "mean_degree", "degree_variance", "clustering", "triangles", "transitivity", "components"]


def kernel_terms(x, y, bandwidth):
    xx = np.exp(-cdist(x, x, "sqeuclidean")/(2*bandwidth**2)).mean()
    yy = np.exp(-cdist(y, y, "sqeuclidean")/(2*bandwidth**2)).mean()
    xy = np.exp(-cdist(x, y, "sqeuclidean")/(2*bandwidth**2)).mean()
    return {"xx": float(xx), "yy": float(yy), "xy": float(xy), "mmd2": float(max(0, xx+yy-2*xy))}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(ROOT / "results/runs/2026-07-03_merged/results/results.csv.gz")
    rows = []
    for dataset in ["barabasi_albert", "erdos_renyi", "stochastic_block_model", "imdb_binary"]:
        selected = df[(df.dataset == dataset) & (df.seed == 0) & (df.perturbation == "triangle_insertion") & (df.workflow == "structural_statistics_mmd")].sort_values("alpha")
        params = json.loads(selected.iloc[0].dataset_params)
        params.setdefault("randomness_protocol", "legacy_seed_plus_index")
        config = SyntheticDatasetConfig(**params)
        for _, logged in selected.iterrows():
            paired = generate_paired_distribution(config, "triangle_insertion", float(logged.alpha), 0)
            x = np.asarray([structural_statistics(g) for g in paired.original_graphs])
            y = np.asarray([structural_statistics(g) for g in paired.perturbed_graphs])
            terms = kernel_terms(x, y, 10.)
            error = abs(terms["mmd2"]-logged.distribution_score)
            if error > 1e-9:
                raise ValueError(f"Regenerated score mismatch {dataset} {logged.alpha}: {error}")
            distances = ((x[:,None,:]-y[None,:,:])**2).mean(axis=(0,1))
            total = distances.sum()
            # Fit scaling and bandwidth only on original graphs; keep across alpha.
            scale = x.std(axis=0)
            scale[scale < 1e-12] = 1.
            xs, ys = x/scale, y/scale
            positive = pdist(xs)
            positive = positive[positive > 0]
            bw = float(np.median(positive)) if len(positive) else 1.
            row = {"dataset": dataset, "seed": 0, "alpha": float(logged.alpha),
                   **terms, "reproduction_abs_error": float(error),
                   "paired_l2": float(np.linalg.norm(y-x, axis=1).mean()),
                   "cross_distance_feature_fraction": dict(zip(FEATURES, (distances/total).tolist())) if total else {},
                   "raw_bandwidth_sweep": {str(b): kernel_terms(x,y,b)["mmd2"] for b in [1., 10., 100., 1000.]},
                   "reference_scaled_median_bandwidth": bw,
                   "reference_scaled_mmd2": kernel_terms(xs,ys,bw)["mmd2"]}
            rows.append(row)
        print("Reproduced", dataset, "11 alpha levels, seed 0", flush=True)
    (OUT/"mmd_kernel_diagnostics.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    fig, axes = plt.subplots(1, 3, figsize=(14,4.5), layout="constrained")
    g = pd.DataFrame([r for r in rows if r["dataset"] == "barabasi_albert"])
    for name, label in [("xx", "within original: Kxx"), ("yy", "within perturbed: Kyy"), ("xy", "cross sample: Kxy"), ("mmd2", "MMD² = Kxx + Kyy − 2Kxy")]:
        axes[0].plot(g.alpha, g[name], label=label)
    axes[0].set_title("Why the original score falls")
    axes[0].legend(fontsize=8)
    axes[0].set_ylabel("Kernel mean / MMD²")
    for b in ["1.0", "10.0", "100.0", "1000.0"]:
        axes[1].plot(g.alpha, [v[b] for v in g.raw_bandwidth_sweep], label="bandwidth="+b)
    axes[1].set_title("Bandwidth changes the response")
    axes[1].legend(fontsize=8)
    axes[1].set_ylabel("Raw-descriptor RBF MMD²")
    axes[2].plot(g.alpha, g.reference_scaled_mmd2, color="#226A9D")
    axes[2].set_title("Reference-scaled descriptors")
    axes[2].set_ylabel("RBF MMD²; reference median bandwidth")
    for ax in axes:
        ax.set_xlabel("Perturbation strength α")
        ax.grid(alpha=.15)
    fig.suptitle("Triangle insertion in Barabási–Albert graphs: reproduced seed 0\nDiagnostic ablations on identical graphs; this is not a validated replacement configuration", fontsize=13)
    fig.savefig(OUT/"mmd_mechanism.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
