"""Audit existing seed trajectories; do not rerun or change source experiments.

Run with the figures dependencies plus scipy. Outputs are exploratory: inference
assumes independent seed trajectories, which the legacy seed+graph_index scheme
does not guarantee. No alpha-label permutation or pooled-row p-values are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
KEY = ["dataset", "perturbation", "workflow"]
NAMES = {"structural_statistics_mmd": "GraphStats + RBF MMD²",
         "wl_subtree_kernel_mmd": "WL features + linear MMD²",
         "native_netlsd": "NetLSD", "diversity_curves_shortest_path": "Diversity curves"}
COLORS = dict(zip(NAMES, ["#C64F38", "#226A9D", "#497C55", "#9860A6"]))


def sign_summary(values):
    """Two-sided conditional sign test; omit numerical zeros and count them."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    tol = 1e-12 * max(1.0, float(np.max(np.abs(x))) if len(x) else 1.0)
    pos, neg = int((x > tol).sum()), int((x < -tol).sum())
    return {"positive": pos, "negative": neg, "zero": len(x)-pos-neg,
            "p_independent_seeds": float(stats.binomtest(pos, pos+neg).pvalue) if pos+neg else 1.0}


def holm(p):
    p = np.asarray(p)
    order = np.argsort(p)
    adjusted = np.minimum(1, np.maximum.accumulate(p[order] * np.arange(len(p), 0, -1)))
    result = np.empty(len(p))
    result[order] = adjusted
    return result


def shape(x):
    x = np.asarray(x, dtype=float)
    constant = np.ptp(x) <= 1e-12 * max(1.0, float(np.max(np.abs(x))))
    q25, med, q75 = np.quantile(x, [.25, .5, .75])
    iqr = q75-q25
    return {"n": len(x), "mean": float(x.mean()), "median": float(med),
            "sd": float(x.std(ddof=1)), "constant": bool(constant),
            "shapiro_p_diagnostic_only": None if constant else float(stats.shapiro(x).pvalue),
            "skewness": None if constant else float(stats.skew(x, bias=False)),
            "bowley_asymmetry": float((q75+q25-2*med)/iqr) if iqr else None,
            "tukey_outliers": int(((x < q25-1.5*iqr) | (x > q75+1.5*iqr)).sum()) if iqr else None}


def audit(df, out):
    required = KEY + ["alpha", "seed", "distribution_score", "mean_shift_score", "paired_score", "edit_distance_raw"]
    if df[required].isna().any().any() or df.duplicated(KEY+["alpha", "seed"]).any():
        raise ValueError("Missing values or duplicate experimental keys")
    if not (df.status == "success").all():
        raise ValueError("Source includes unsuccessful rows; review before inference")
    groups, trajectories, contrasts = [], [], []
    for key, g in df.groupby(KEY, sort=True):
        info = dict(zip(KEY, key))
        wide = g.pivot(index="seed", columns="alpha", values="distribution_score").sort_index(axis=1)
        if wide.isna().any().any() or not np.allclose(wide.columns, np.linspace(0, 1, 11)):
            raise ValueError(f"Incomplete alpha trajectories: {key}")
        rhos = []
        for seed, row in wide.iterrows():
            y = row.to_numpy()
            rho = float(stats.spearmanr(wide.columns[1:], y[1:]).statistic) if np.ptp(y[1:]) else np.nan
            rhos.append(rho)
            trajectories.append({**info, "seed": int(seed), "rho_positive_alpha": rho,
                                 "rho_all_alpha": float(stats.spearmanr(wide.columns, y).statistic),
                                 "endpoint_difference_1_minus_0_1": float(y[-1]-y[1])})
        means = wide.mean()
        signs = sign_summary(rhos)
        finite = np.array(rhos)[np.isfinite(rhos)]
        groups.append({**info, "n_seeds": len(wide), "rho_seed_median_positive_alpha": float(np.median(finite)) if len(finite) else None,
                       "rho_seed_min_positive_alpha": float(min(finite)) if len(finite) else None,
                       "rho_seed_max_positive_alpha": float(max(finite)) if len(finite) else None,
                       "pooled_rho_descriptive": float(stats.spearmanr(g.alpha, g.distribution_score).statistic),
                       "peak_mean_alpha": float(means.idxmax()), "peak_mean": float(means.max()),
                       "end_mean": float(means.loc[1.0]), "trend_sign": signs,
                       "undefined_rho_count": int(len(rhos)-len(finite))})
        # A broad contrast chosen for this audit, plus every adjacent contrast.
        for lo, hi in [(0.1, 1.0)] + list(zip(wide.columns[:-1], wide.columns[1:])):
            d = (wide[hi]-wide[lo]).to_numpy()
            contrasts.append({**info, "alpha_low": float(lo), "alpha_high": float(hi),
                              **shape(d), "sign": sign_summary(d)})
    adjusted = holm([g["trend_sign"]["p_independent_seeds"] for g in groups])
    for g, p in zip(groups, adjusted):
        g["trend_sign"]["holm_p_96_independent_seeds"] = float(p)
    broad = [c for c in contrasts if c["alpha_low"] == .1 and c["alpha_high"] == 1.]
    for c, p in zip(broad, holm([c["sign"]["p_independent_seeds"] for c in broad])):
        c["sign"]["holm_p_96_independent_seeds"] = float(p)
    for name, data in [("trajectory_summary", groups), ("seed_trajectories", trajectories), ("paired_difference_diagnostics", contrasts)]:
        # NaN correlations are missing, never silently replaced by zero.
        cleaned = json.loads(pd.DataFrame(data).to_json(orient="records"))
        (out / f"{name}.json").write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
    return groups, contrasts


def figures(df, out):
    fig, axes = plt.subplots(2, 4, figsize=(15, 7.6), layout="constrained")
    datasets = ["barabasi_albert", "erdos_renyi", "stochastic_block_model", "imdb_binary"]
    for col, dataset in enumerate(datasets):
        for row, workflow in enumerate(list(NAMES)[:2]):
            ax = axes[row, col]
            g = df[(df.dataset == dataset) & (df.perturbation == "triangle_insertion") & (df.workflow == workflow)]
            for _, s in g.groupby("seed"):
                s = s.sort_values("alpha")
                ax.plot(s.alpha, s.distribution_score, color=COLORS[workflow], alpha=.20, lw=.8)
            mean = g.groupby("alpha").distribution_score.mean()
            ax.plot(mean.index, mean, color=COLORS[workflow], lw=2.7)
            ax.set_title(dataset.replace("_", " ") + f" (n={g.seed.nunique()})", fontsize=10)
            ax.set_xlabel("Perturbation strength α")
            ax.set_ylabel(NAMES[workflow] + "\nraw score", fontsize=9)
            ax.grid(alpha=.15)
    fig.suptitle("Triangle insertion: individual seed trajectories and their mean\nEach panel uses its own raw score scale; thin lines are runs, not confidence intervals", fontsize=14)
    fig.savefig(out / "triangle_seed_trajectories.png", dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(12, 7), layout="constrained")
    examples = [("barabasi_albert", "triangle_insertion", "structural_statistics_mmd"),
                ("erdos_renyi", "hub_modification", "structural_statistics_mmd"),
                ("imdb_binary", "triangle_insertion", "structural_statistics_mmd")]
    for col, (dataset, perturbation, workflow) in enumerate(examples):
        g = df[(df.dataset == dataset) & (df.perturbation == perturbation) & (df.workflow == workflow)]
        wide = g.pivot(index="seed", columns="alpha", values="distribution_score")
        d = (wide[1.]-wide[.1]).to_numpy()
        axes[0,col].scatter(range(len(d)), d, color=COLORS[workflow])
        axes[0,col].axhline(0, color="gray", lw=1)
        axes[0,col].set_title(dataset.replace("_", " ")+"\n"+perturbation.replace("_", " "), fontsize=11)
        axes[0,col].set_xlabel("Seed index")
        axes[0,col].set_ylabel("Score(1.0) − score(0.1)")
        stats.probplot(d, plot=axes[1,col])
        axes[1,col].set_title(f"Normal Q–Q plot (n={len(d)})", fontsize=11)
    fig.suptitle("Assess paired differences across seeds, separately for each setting\nGraphStats + RBF MMD²; normality checks cannot establish independence or symmetry", fontsize=13)
    fig.savefig(out / "paired_difference_diagnostics.png", dpi=160)
    plt.close(fig)


def structural_checks(df, out):
    checks = {"score_identities": {}, "hub_edit_plateaus": {}, "score_ranges": {}}
    for workflow, g in df.groupby("workflow"):
        checks["score_ranges"][workflow] = {"min": float(g.distribution_score.min()), "max": float(g.distribution_score.max())}
        if workflow != "structural_statistics_mmd":
            expected = g.mean_shift_score**2 if workflow == "wl_subtree_kernel_mmd" else g.mean_shift_score
            checks["score_identities"][workflow] = {"mean_shift_power": 2 if workflow == "wl_subtree_kernel_mmd" else 1,
                "max_absolute_error": float(abs(g.distribution_score-expected).max())}
    g = df[(df.workflow == "structural_statistics_mmd") & (df.perturbation == "hub_modification")]
    for dataset, data in g.groupby("dataset"):
        wide = data.pivot(index="seed", columns="alpha", values="edit_distance_raw").sort_index(axis=1)
        plateaus = [a for a in wide.columns if np.allclose(wide.loc[:, a:], wide.loc[:, [1.]], rtol=0, atol=1e-10)]
        checks["hub_edit_plateaus"][dataset] = {"first_alpha_equal_to_endpoint_all_seeds": float(min(plateaus)),
                                               "mean_edits_by_alpha": {str(a): float(v) for a,v in wide.mean().items()}}
    (out/"structural_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT/"results/runs/2026-07-03_merged/results/results.csv.gz")
    parser.add_argument("--output", type=Path, default=ROOT/"results/analysis/2026-09-09_statistical_audit")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.results)
    groups, contrasts = audit(df, args.output)
    figures(df, args.output)
    structural_checks(df, args.output)
    manifest = {"source": str(args.results.relative_to(ROOT)),
                "source_sha256": hashlib.sha256(args.results.read_bytes()).hexdigest(),
                "rows": len(df), "groups": len(groups),
                "versions": {"python": sys.version, "scipy": scipy.__version__, "numpy": np.__version__, "pandas": pd.__version__},
                "inference_status": "Exploratory. Sign-test p-values assume independent seeds; legacy perturbation random streams overlap across seeds.",
                "tests": "Two-sided exact sign tests on positive-alpha within-seed Spearman correlations and on score(1)-score(.1), Holm correction separately across 96 settings per family.",
                "normality": "Shapiro-Wilk and shape diagnostics on paired differences only. No automatic t/Wilcoxon selection."}
    (args.output/"analysis_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for g in groups:
        if g["perturbation"] == "triangle_insertion" and g["workflow"] in list(NAMES)[:2]:
            print(json.dumps(g))
    print("Rows", len(df), "groups", len(groups), "contrast diagnostics", len(contrasts), flush=True)


if __name__ == "__main__":
    main()
