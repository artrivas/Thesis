"""Inspect distributional conditions on synthetic paired score differences.

This is a shape audit, not a test-selection algorithm or effect-significance run.
All raw differences and shape diagnostics are retained. IMDB is excluded.
"""
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np
import pandas as pd
import scipy
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/runs/2026-07-03_merged/results/results.csv.gz"
OUT = ROOT / "results/analysis/2026-09-10_distributional_conditions"
KEY = ["dataset", "perturbation", "workflow"]
DS = {"erdos_renyi": "ER", "stochastic_block_model": "SBM", "barabasi_albert": "BA"}
WF = {"structural_statistics_mmd": "GraphStats", "wl_subtree_kernel_mmd": "WL", "native_netlsd": "NetLSD", "diversity_curves_shortest_path": "Diversity"}


def inspect_difference(low, high):
    low, high = np.asarray(low, float), np.asarray(high, float)
    d = high-low
    if len(d) < 3 or not np.isfinite(d).all():
        raise ValueError("At least three complete finite pairs are required")
    tol = 1e-12 * max(1., float(np.max(np.abs(np.concatenate([low, high])))))
    zeros = np.abs(d) <= tol
    constant = np.ptp(d) <= tol
    q10, q25, med, q75, q90 = np.quantile(d, [.1,.25,.5,.75,.9])
    iqr = q75-q25
    n = len(d)
    result = {"n": n, "differences": d.tolist(), "numerical_tolerance": tol,
              "mean": float(d.mean()), "median": float(med), "sd": float(d.std(ddof=1)),
              "zero_count": int(zeros.sum()), "nonzero_count": int((~zeros).sum()),
              "constant": bool(constant), "all_zero": bool(zeros.all()),
              "normality_screen": "degenerate" if constant else None,
              "shapiro_p": None, "sample_skewness": None, "excess_kurtosis": None,
              "normal_qq_r": None, "bowley_asymmetry": None, "tail_asymmetry": None,
              "tukey_outliers": None, "tied_nonzero_absolute_values": 0}
    nz = np.sort(np.abs(d[~zeros]))
    if len(nz):
        result["tied_nonzero_absolute_values"] = int(np.sum(np.diff(nz) <= tol))
    if constant:
        return result
    # Standardization improves numerical stability without changing normality.
    z = (d-d.mean())/d.std(ddof=1)
    p = float(stats.shapiro(z).pvalue)
    skew = float(stats.skew(z, bias=False))
    result.update(shapiro_p=p, sample_skewness=skew,
                  excess_kurtosis=float(stats.kurtosis(z, bias=False)),
                  normal_qq_r=float(stats.probplot(z)[1][2]),
                  bowley_asymmetry=float((q75+q25-2*med)/iqr) if iqr>tol else None,
                  tail_asymmetry=float((q90+q10-2*med)/(q90-q10)) if q90-q10>tol else None,
                  tukey_outliers=int(((d<q25-1.5*iqr)|(d>q75+1.5*iqr)).sum()) if iqr>tol else None,
                  normality_screen="review_shape" if p<.05 or abs(skew)>1 else "no_clear_flag")
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(SOURCE)
    df = frame[frame.dataset.isin(DS)].copy()
    if df.duplicated(KEY+["alpha", "seed"]).any() or not (df.status=="success").all():
        raise ValueError("Duplicate keys or failed rows")
    rows, summaries = [], []
    for key,g in df.groupby(KEY):
        wide=g.pivot(index="seed", columns="alpha", values="distribution_score").sort_index(axis=1)
        if wide.shape != (24,11) or wide.isna().any().any() or not np.allclose(wide.columns,np.linspace(0,1,11)):
            raise ValueError(f"Unexpected experimental grid: {key}")
        group=[]
        for lo,hi in [(.1,1.)]+list(zip(wide.columns[:-1],wide.columns[1:])):
            row={**dict(zip(KEY,key)), "alpha_low": float(lo), "alpha_high": float(hi),
                 "contrast": "endpoint" if hi-lo>.2 else "adjacent",
                 "seeds": [int(x) for x in wide.index], **inspect_difference(wide[lo],wide[hi])}
            rows.append(row);group.append(row)
        endpoint=group[0]; adj=group[1:]
        summaries.append({**dict(zip(KEY,key)), "endpoint_shapiro_p": endpoint["shapiro_p"],
                          "endpoint_skewness": endpoint["sample_skewness"],
                          "endpoint_bowley": endpoint["bowley_asymmetry"],
                          "endpoint_screen": endpoint["normality_screen"],
                          "adjacent_normality_review_count": sum(r["normality_screen"]=="review_shape" for r in adj),
                          "adjacent_degenerate_count": sum(r["constant"] for r in adj),
                          "adjacent_with_at_most_5_nonzero": sum(0<r["nonzero_count"]<=5 for r in adj)})
    counts={}
    for family in ["endpoint", "adjacent"]:
        subset=[r for r in rows if r["contrast"]==family]
        counts[family]={"total":len(subset), "constant":sum(r["constant"] for r in subset),
                        "all_zero":sum(r["all_zero"] for r in subset),
                        "shapiro_below_05":sum(r["shapiro_p"] is not None and r["shapiro_p"]<.05 for r in subset),
                        "absolute_skew_above_1":sum(r["sample_skewness"] is not None and abs(r["sample_skewness"])>1 for r in subset),
                        "review_shape":sum(r["normality_screen"]=="review_shape" for r in subset),
                        "no_clear_flag":sum(r["normality_screen"]=="no_clear_flag" for r in subset),
                        "nonconstant_with_zeros":sum(not r["constant"] and r["zero_count"]>0 for r in subset),
                        "one_to_five_nonzero":sum(0<r["nonzero_count"]<=5 for r in subset)}
    manifest={"source":str(SOURCE.relative_to(ROOT)), "source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "rows_analyzed":len(df), "settings":len(summaries), "counts":counts,
              "versions":{"python":sys.version,"numpy":np.__version__,"scipy":scipy.__version__,"pandas":pd.__version__},
              "scope":"Distribution score; synthetic only. ZINC data not present in this source.",
              "screen":"Review if Shapiro p<.05 OR absolute sample skewness>1. Diagnostic convention, not automatic test selection or proof of invalidity. No-clear-flag does not establish normality or symmetry.",
              "symmetry":"Bowley and 10/90 tail balance are descriptive. Reflection plots assess shape about the sample median. No symmetry p-value or pass/fail is claimed.",
              "normality_pvalues":"Unadjusted exploratory shape diagnostics, not effect p-values. Independence across seeds is not established; Shapiro reference p-values also rely on independent sampling."}
    for name,data in [("contrast_diagnostics",rows),("setting_summary",summaries),("manifest",manifest)]:
        (OUT/f"{name}.json").write_text(json.dumps(data,indent=2,allow_nan=False),encoding="utf-8")
    lines=["# Distributional screen by experimental setting", "",
           "Endpoint differences are score(1.0) minus score(0.1), paired across 24 seeds. Adjacent columns summarize all 10 alpha increments, including the structural zero baseline. Review = raw Shapiro p < .05 or |sample skewness| > 1; this is a screening convention, not a validity decision. Degenerate = numerically constant differences. The other settings still require judgment about tails and symmetry.", "",
           "| Dataset | Perturbation | Workflow | Endpoint Shapiro p | Endpoint skewness | Endpoint Bowley | Endpoint screen | Adjacent review / 10 | Adjacent degenerate / 10 | Adjacent only 1–5 nonzero / 10 |",
           "|---|---|---|---:|---:|---:|---|---:|---:|---:|"]
    for s in summaries:
        lines.append(f"| {DS[s['dataset']]} | {s['perturbation'].replace('_',' ')} | {WF[s['workflow']]} | {s['endpoint_shapiro_p']:.4g} | {s['endpoint_skewness']:.3f} | {s['endpoint_bowley']:.3f} | {s['endpoint_screen']} | {s['adjacent_normality_review_count']} | {s['adjacent_degenerate_count']} | {s['adjacent_with_at_most_5_nonzero']} |")
    (OUT/"setting_summary.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    examples=[("erdos_renyi","triangle_insertion","structural_statistics_mmd",.1,1.),
              ("stochastic_block_model","community_weakening","native_netlsd",.1,1.),
              ("stochastic_block_model","hub_modification","native_netlsd",.4,.5),
              ("erdos_renyi","hub_modification","structural_statistics_mmd",.5,.6)]
    selected=[]
    fig,axes=plt.subplots(4,3,figsize=(13,13),layout="constrained")
    for i,ex in enumerate(examples):
        row=next(r for r in rows if tuple(r[k] for k in KEY+["alpha_low","alpha_high"])==ex)
        selected.append(row)
        d=np.array(row["differences"]); med=np.median(d)
        axes[i,0].scatter(np.arange(len(d)),d,s=24,color="#266F9D")
        axes[i,0].axhline(med,color="#BB5338",lw=1,label="Sample median")
        axes[i,0].set_xlabel("Seed");axes[i,0].set_ylabel("Paired score difference")
        axes[i,0].set_title(f"{DS[ex[0]]} / {ex[1].replace('_',' ')}\n{WF[ex[2]]}: α {ex[3]} → {ex[4]}",fontsize=10)
        if row["constant"]:
            for ax in axes[i,1:]:
                ax.text(.5,.5,"All 24 differences are zero\nNo distributional shape to assess",ha="center",va="center",transform=ax.transAxes)
                ax.set_axis_off()
            continue
        stats.probplot(d,plot=axes[i,1])
        axes[i,1].set_title(f"Normal Q–Q: p={row['shapiro_p']:.3g}, skew={row['sample_skewness']:.2f}",fontsize=10)
        ordered=np.sort(d);left=(med-ordered[:len(d)//2])[::-1];right=ordered[len(d)//2:]-med
        extent=max(left.max(),right.max())
        axes[i,2].scatter(left,right,s=25,color="#266F9D")
        axes[i,2].plot([0,extent],[0,extent],color="#BB5338",lw=1)
        axes[i,2].set_xlabel("Distance below sample median")
        axes[i,2].set_ylabel("Matched distance above sample median")
        axes[i,2].set_title("Symmetry reflection plot",fontsize=10)
        axes[i,2].set_aspect("equal",adjustable="box")
        for ax in axes[i,:]:
            for axis in [ax.xaxis, ax.yaxis]:
                axis.set_major_formatter(FuncFormatter(lambda value, position: f"{value:.3g}"))
                axis.set_major_locator(MaxNLocator(nbins=4))
    fig.suptitle("Actual paired differences: compatible shape, skewness, sparse change, and no change\nNormality p-values are exploratory; proximity to the reflection diagonal supports sample symmetry",fontsize=13)
    fig.savefig(OUT/"distributional_examples.png",dpi=140)
    plt.close(fig)
    (OUT/"reviewed_examples.json").write_text(json.dumps(selected,indent=2),encoding="utf-8")
    print(json.dumps(counts,indent=2))
    for row in selected:
        print(json.dumps({k:v for k,v in row.items() if k not in ["differences","seeds"]}))


if __name__=="__main__":
    main()
