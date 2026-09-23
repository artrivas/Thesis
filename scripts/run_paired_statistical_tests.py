"""Exploratory paired tests for the previously audited synthetic contrasts.

Results remain conditional on independence and on diagnostic-based eligibility.
No test is selected based on its effect p-value. A single Holm family reserves
all 792 contrasts x 3 methods, including unavailable tests as p=1 internally.
"""
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
import scipy
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "results/analysis/2026-09-10_distributional_conditions"
SOURCE = ROOT / "results/runs/2026-07-03_merged/results/results.csv.gz"
OUT = ROOT / "results/analysis/2026-09-10_paired_tests"
METHODS = ["paired_t", "wilcoxon", "sign"]
KEY = ["dataset", "perturbation", "workflow"]
DS = {"erdos_renyi":"ER", "stochastic_block_model":"SBM", "barabasi_albert":"BA"}
WF = {"structural_statistics_mmd":"GraphStats", "wl_subtree_kernel_mmd":"WL", "native_netlsd":"NetLSD", "diversity_curves_shortest_path":"Diversity"}


def holm(pvalues):
    values=np.asarray(pvalues,float)
    order=np.argsort(values)
    corrected=np.minimum(1.,np.maximum.accumulate(values[order]*np.arange(len(values),0,-1)))
    result=np.empty(len(values));result[order]=corrected
    return result


def signed_rank_exact(differences, tolerance):
    """Exact conditional sign-allocation distribution, including tied ranks.

    Discard numerical zeros. Magnitudes within tolerance of a group's smallest
    magnitude receive average ranks. Integer doubled ranks permit exact dynamic
    programming; no Monte Carlo or continuous-rank approximation is used.
    """
    d=np.asarray(differences,float)
    d=d[np.abs(d)>tolerance]
    if not len(d):
        return None
    order=np.argsort(np.abs(d));ordered=np.abs(d)[order]
    ranks2=np.empty(len(d),dtype=int)
    i=0
    while i<len(d):
        j=i+1
        while j<len(d) and ordered[j]-ordered[i]<=tolerance:
            j+=1
        ranks2[order[i:j]]=i+1+j
        i=j
    total=int(ranks2.sum());positive=int(ranks2[d>0].sum())
    counts=[0]*(total+1);counts[0]=1;reachable=0
    for rank in ranks2:
        for s in range(reachable,-1,-1):
            counts[s+int(rank)]+=counts[s]
        reachable+=int(rank)
    denominator=2**len(d)
    p=min(1.,2*min(sum(counts[:positive+1]),sum(counts[positive:]))/denominator)
    walsh=(d[:,None]+d[None,:])/2
    return {"statistic":min(positive,total-positive)/2,"positive_rank_sum":positive/2,
            "p_raw":p,"n_nonzero":len(d),
            "hodges_lehmann_nonzero":float(np.median(walsh[np.triu_indices(len(d))])),
            "method":"exact conditional sign allocation with average tied ranks; numerical zeros discarded"}


def test_contrast(row):
    d=np.array(row["differences"],float);tol=row["numerical_tolerance"]
    result={k:row[k] for k in KEY+["alpha_low","alpha_high","contrast","n","zero_count","nonzero_count","mean","median","sd"]}
    result["positive_count"]=int((d>tol).sum());result["negative_count"]=int((d < -tol).sum())
    result["source_shape_screen"]=row["normality_screen"]
    result["tests"]={m:{"status":"not_run","reason":None,"p_raw":None,"p_holm":None} for m in METHODS}
    if row["all_zero"]:
        for test in result["tests"].values():test["reason"]="No observed change: all differences numerically zero"
        return result
    t_reasons=[]
    if row["constant"]: t_reasons.append("constant differences")
    if row["normality_screen"]!="no_clear_flag":t_reasons.append("normality/skewness review flag")
    if row["normal_qq_r"] is None or row["normal_qq_r"]<.97:t_reasons.append("normal Q-Q correlation below .97")
    if row["tukey_outliers"]!=0:t_reasons.append("outlier flags or undefined IQR")
    if not t_reasons:
        test=stats.ttest_1samp(d,0.,alternative="two-sided")
        interval=test.confidence_interval(.95)
        result["tests"]["paired_t"]={"status":"run","reason":"Conservative shape screen compatible; not certification", "statistic":float(test.statistic),
            "df":len(d)-1,"p_raw":float(test.pvalue),"p_holm":None,
            "mean_difference_ci95_pointwise":[float(interval.low),float(interval.high)],
            "cohens_dz":float(d.mean()/d.std(ddof=1))}
    else:result["tests"]["paired_t"]["reason"]="; ".join(t_reasons)
    w_reasons=[]
    if row["constant"]:w_reasons.append("constant differences")
    if row["nonzero_count"]<6:w_reasons.append("fewer than six nonzero differences")
    for name,cutoff in [("sample_skewness",1.),("bowley_asymmetry",.3),("tail_asymmetry",.3)]:
        if row[name] is None or abs(row[name])>cutoff:w_reasons.append(f"{name} unavailable or outside ±{cutoff}")
    if not w_reasons:
        result["tests"]["wilcoxon"]={"status":"run","reason":"Conservative symmetry screen compatible; not certification","p_holm":None,**signed_rank_exact(d,tol)}
    else:result["tests"]["wilcoxon"]["reason"]="; ".join(w_reasons)
    n=result["nonzero_count"];k=result["positive_count"]
    sign=stats.binomtest(k,n,p=.5,alternative="two-sided")
    interval=sign.proportion_ci(.95,method="exact")
    result["tests"]["sign"]={"status":"run","reason":"No normality or symmetry assumption; conditional on nonzero differences", "statistic":k,"n_nonzero":n,
        "p_raw":float(sign.pvalue),"p_holm":None,"positive_fraction_nonzero":k/n,
        "positive_fraction_ci95_pointwise":[float(interval.low),float(interval.high)]}
    return result


def format_p(test):
    return "—" if test["status"]!="run" else f"{test['p_holm']:.3g}"


def write_table(rows,path,full=False):
    lines=["# Paired statistical results"+(" — all contrasts" if full else " — alpha 0.1 to 1.0"),"",
        "Exploratory, conditional on independent seed trajectories. All p-values below are two-sided and Holm-adjusted over the full 2,376-slot contrast/method family. A dash means the method was withheld by the diagnostic screen, not p=1. Mean changes are in each workflow's own units. Sign direction counts include all 24 seeds. Intervals are pointwise 95%, not multiplicity-adjusted.","",
        "| Dataset | Perturbation | Workflow | Alpha low → high | Mean change | Mean change 95% CI (t eligible only) | + / − / zero | t adjusted p | Wilcoxon adjusted p | Sign adjusted p |",
        "|---|---|---|---|---:|---|---|---:|---:|---:|"]
    for r in rows:
        t=r["tests"]["paired_t"];ci=t.get("mean_difference_ci95_pointwise")
        ci_text=f"[{ci[0]:.5g}, {ci[1]:.5g}]" if ci else "—"
        lines.append(f"| {DS[r['dataset']]} | {r['perturbation'].replace('_',' ')} | {WF[r['workflow']]} | {r['alpha_low']:.1f} → {r['alpha_high']:.1f} | {r['mean']:+.6g} | {ci_text} | {r['positive_count']} / {r['negative_count']} / {r['zero_count']} | {format_p(t)} | {format_p(r['tests']['wilcoxon'])} | {format_p(r['tests']['sign'])} |")
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")


def main():
    start=time.perf_counter();OUT.mkdir(parents=True,exist_ok=True)
    audit_manifest=json.loads((AUDIT/"manifest.json").read_text())
    source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if source_hash!=audit_manifest["source_sha256"]:raise ValueError("Source changed since assumptions audit")
    source_rows=json.loads((AUDIT/"contrast_diagnostics.json").read_text())
    if len(source_rows)!=792:raise ValueError("Unexpected contrast count")
    frame=pd.read_csv(SOURCE)
    indexed=frame.set_index(KEY+["seed","alpha"])
    for r in source_rows:
        key=tuple(r[k] for k in KEY)
        actual=[float(indexed.loc[key+(s,r["alpha_high"]),"distribution_score"])-float(indexed.loc[key+(s,r["alpha_low"]),"distribution_score"]) for s in r["seeds"]]
        if not np.allclose(actual,r["differences"],rtol=0,atol=1e-14):raise ValueError("Saved differences mismatch source")
    results=[test_contrast(r) for r in source_rows]
    slots=[r["tests"][method] for r in results for method in METHODS]
    p=holm([t["p_raw"] if t["status"]=="run" else 1. for t in slots])
    for test,adjusted in zip(slots,p):
        if test["status"]=="run":test["p_holm"]=float(adjusted)
    summary={}
    for family in ["endpoint","adjacent"]:
        subset=[r for r in results if r["contrast"]==family]
        summary[family]={}
        for method in METHODS:
            ran=[r for r in subset if r["tests"][method]["status"]=="run"]
            selected=[r for r in ran if r["tests"][method]["p_holm"]<.05]
            direction=lambda r: (r["positive_count"]-r["negative_count"]) if method=="sign" else (r["tests"][method]["positive_rank_sum"]-(r["tests"][method]["n_nonzero"]*(r["tests"][method]["n_nonzero"]+1)/4)) if method=="wilcoxon" else r["mean"]
            summary[family][method]={"run":len(ran),"withheld":len(subset)-len(ran),"adjusted_p_below_05":len(selected),
                "positive":sum(direction(r)>0 for r in selected),"negative":sum(direction(r)<0 for r in selected)}
    (OUT/"results.json").write_text(json.dumps(results,indent=2,allow_nan=False),encoding="utf-8")
    manifest={"source_sha256":source_hash,"assumptions_audit_sha256":hashlib.sha256((AUDIT/"contrast_diagnostics.json").read_bytes()).hexdigest(),
        "source":str(SOURCE.relative_to(ROOT)),"scope":"Synthetic only; 72 endpoints and 720 adjacent contrasts; 24 paired seeds each",
        "inference_status":"Exploratory: legacy random-stream reuse and data-informed eligibility preclude claiming calibrated confirmatory p-values.",
        "holm_family_slots":len(slots),"summary":summary,"elapsed_seconds":time.perf_counter()-start,
        "t_screen":"Prior no_clear_flag, QQ r>=.97, no Tukey flags, nonconstant",
        "wilcoxon_screen":"Nonconstant, at least 6 nonzero, absolute sample skew<=1, absolute Bowley<=.3, absolute tail asymmetry<=.3",
        "eligibility_note":"Heuristic shape screens fixed before effect-test execution; they are not formal assumption certification. Not a select-the-smallest-p workflow.",
        "ci_note":"95% pointwise, conditional on the relevant test assumptions; not simultaneous intervals",
        "versions":{"python":sys.version,"scipy":scipy.__version__,"numpy":np.__version__}}
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    write_table([r for r in results if r["contrast"]=="endpoint"],OUT/"endpoint_results.md")
    write_table(results,OUT/"all_contrast_results.md",full=True)
    print(json.dumps(manifest,indent=2))


if __name__=="__main__":
    main()
