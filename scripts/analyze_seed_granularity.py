"""Descriptive seed-level analysis of all synthetic result settings.

No new hypothesis tests; preserves raw seed observations and uses empirical
spread, not uncertainty intervals, in the figures.
"""
import hashlib
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"results/runs/2026-07-03_merged/results/results.csv.gz"
OUT=ROOT/"results/analysis/2026-09-15_granular_analysis"
DS={"erdos_renyi":"ER", "barabasi_albert":"BA", "stochastic_block_model":"SBM", "zinc":"ZINC"}
WF={"structural_statistics_mmd":"GraphStats + RBF MMD²", "wl_subtree_kernel_mmd":"WL features + linear MMD²", "native_netlsd":"NetLSD", "diversity_curves_shortest_path":"Diversity curves"}
KEY=["dataset","perturbation","workflow"]


def step_summary(d,tol):
    d=np.asarray(d,float)
    pos=int((d>tol).sum());neg=int((d < -tol).sum());zero=len(d)-pos-neg
    mean=float(d.mean());median=float(np.median(d))
    opposite=(mean>tol and neg>pos) or (mean < -tol and pos>neg)
    return {"mean_change":mean,"median_change":median,"positive":pos,"negative":neg,"zero":zero,
            "mean_opposes_more_nonzero_seeds":bool(opposite),
            "mean_opposes_absolute_majority":bool(opposite and max(pos,neg)>len(d)/2)}


def draw_setting(key,alpha,values,steps,selected,out,seeds=None):
    fig,axes=plt.subplots(2,2,figsize=(13,8.6),layout="constrained")
    ax=axes[0,0]
    for s,y in enumerate(values):ax.plot(alpha,y,lw=.8,color="#7290A4",alpha=.28)
    ax.plot(alpha,values.mean(0),color="#172F47",lw=2.5,label="Mean")
    ax.plot(alpha,np.median(values,axis=0),color="#C45C24",lw=2,ls="--",label="Median")
    ax.set_title("Individual seed trajectories");ax.set_xlabel("Perturbation strength α");ax.set_ylabel("Distribution score (workflow units)");ax.legend(fontsize=9)
    ax=axes[0,1]
    ax.boxplot(values,positions=alpha,widths=.047,showfliers=False,manage_ticks=False)
    for i in range(len(alpha)):
        ax.scatter(alpha[i]+np.linspace(-.025,.025,len(values)),values[:,i],s=9,color="#266F9D",alpha=.5)
    ax.set_title(f"All {len(values)} scores at each alpha; box = middle 50%");ax.set_xlabel("Perturbation strength α");ax.set_ylabel("Distribution score (workflow units)")
    ax=axes[1,0];j=selected;d=values[:,j+1]-values[:,j];row=steps[j]
    tol=1e-12*max(1,float(abs(values).max()))
    colors=np.where(d>tol,"#267E70",np.where(d < -tol,"#C6553E","#888888"))
    ax.axhline(0,color="#888888",lw=1)
    ax.scatter(np.arange(len(d)) if seeds is None else seeds,d,c=colors,s=25)
    ax.axhline(row["mean_change"],color="#172F47",label=f"Mean {row['mean_change']:+.4g}",lw=1.8)
    ax.axhline(row["median_change"],color="#C45C24",label=f"Median {row['median_change']:+.4g}",lw=1.8,ls="--")
    ax.set_title(f"Paired changes: α {alpha[j]:.1f} → {alpha[j+1]:.1f}\n{row['positive']} increase / {row['negative']} decrease / {row['zero']} unchanged",fontsize=11)
    ax.set_xlabel("Seed ID");ax.set_ylabel("Score at higher α minus score at lower α");ax.legend(fontsize=9)
    ax=axes[1,1];x=np.arange(len(alpha)-1)
    pos=np.array([r["positive"] for r in steps]);neg=np.array([r["negative"] for r in steps]);zero=np.array([r["zero"] for r in steps])
    ax.bar(x,pos,color="#267E70",label="Increase")
    ax.bar(x,neg,bottom=pos,color="#C6553E",label="Decrease")
    ax.bar(x,zero,bottom=pos+neg,color="#B7BEC5",label="Unchanged")
    ax.set_xticks(x,[f"{a:.1f}→{b:.1f}" for a,b in zip(alpha[:-1],alpha[1:])],rotation=40,ha="right",fontsize=8)
    ax.set_ylim(0,len(values)*1.15);ax.set_title("Direction counts for every adjacent step");ax.set_xlabel("Alpha interval");ax.set_ylabel("Number of seeds");ax.legend(fontsize=9,ncol=3,loc="upper center")
    for ax in axes.flat:ax.grid(axis="y",alpha=.13)
    fig.suptitle(f"{DS[key[0]]} / {key[1].replace('_',' ')} / {WF[key[2]]}\nDescriptive variation across {len(values)} seeds; boxes and points are not confidence intervals",fontsize=13)
    fig.savefig(out,dpi=135);plt.close(fig)


def main():
    global SOURCE, OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results",type=Path,default=SOURCE)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    original_source=SOURCE.resolve();SOURCE=args.results.resolve()
    OUT=(args.output.resolve() if args.output else OUT if SOURCE==original_source else SOURCE.parent.parent/"granular_analysis")
    (OUT/"seed_figures").mkdir(parents=True,exist_ok=True)
    data=pd.read_csv(SOURCE);data=data[data.dataset.isin(DS)]
    if data.empty:raise ValueError("No supported synthetic or ZINC rows in source")
    if data.duplicated(KEY+["seed","alpha"]).any() or not (data.status=="success").all():raise ValueError("Invalid source grid")
    summaries=[];all_steps=[];payload=[]
    for key,g in data.groupby(KEY,sort=True):
        wide=g.pivot(index="seed",columns="alpha",values="distribution_score").sort_index().sort_index(axis=1)
        edits=g.pivot(index="seed",columns="alpha",values="edit_distance_raw").reindex(index=wide.index,columns=wide.columns)
        if wide.shape[0]<2 or wide.shape[1]<2 or wide.isna().any().any():raise ValueError("Incomplete trajectories")
        a=wide.columns.to_numpy();v=wide.to_numpy();tol=1e-12*max(1,float(abs(v).max()))
        steps=[]
        for j in range(len(a)-1):
            r={**dict(zip(KEY,key)),"alpha_low":float(a[j]),"alpha_high":float(a[j+1]),**step_summary(v[:,j+1]-v[:,j],tol)}
            steps.append(r);all_steps.append(r)
        opposite=[i for i,r in enumerate(steps) if r["mean_opposes_absolute_majority"]]
        # If no mean/majority disagreement, show the step with the most balanced
        # increase/decrease counts. Its choice is descriptive, not a test.
        j=opposite[0] if opposite else int(np.argmax([min(r["positive"],r["negative"]) for r in steps]))
        if len(a)==11 and key==("barabasi_albert","triangle_insertion","structural_statistics_mmd"):j=3
        filename="__".join(key)+".png"
        draw_setting(key,a,v,steps,j,OUT/"seed_figures"/filename,seeds=wide.index.to_numpy())
        diff=np.diff(v,axis=1)
        positive_diff=diff[:,a[:-1]>0]
        summary={**dict(zip(KEY,key)),"seed_count":len(v),"positive_alpha_interval_count":positive_diff.shape[1],"seeds_with_any_decrease_positive_alpha":int((positive_diff < -tol).any(1).sum()),
                 "seeds_nondecreasing_positive_alpha":int((positive_diff >= -tol).all(1).sum()),
                 "mean_opposes_absolute_majority_steps":len(opposite),
                 "mean_opposes_more_nonzero_steps":sum(r["mean_opposes_more_nonzero_seeds"] for r in steps),
                 "unchanged_score_with_increasing_edit_count_cells":int(((abs(diff)<=tol)&(np.diff(edits.to_numpy(),axis=1)>1e-9)).sum()),
                 "first_peak_alpha_by_seed":[float(a[i]) for i in np.argmax(v,axis=1)],
                 "figure":"seed_figures/"+filename}
        summaries.append(summary)
        payload.append({**dict(zip(KEY,key)),"seeds":[int(s) for s in wide.index],"alpha":a.tolist(),"distribution_score":v.tolist(),"edit_distance_raw":edits.to_numpy().tolist(),
                        "mean":v.mean(0).tolist(),"median":np.median(v,axis=0).tolist(),"q25":np.quantile(v,.25,axis=0).tolist(),"q75":np.quantile(v,.75,axis=0).tolist(),"tolerance":tol})
    opposite=[r for r in all_steps if r["mean_opposes_absolute_majority"]]
    for name,value in [("seed_summary",summaries),("adjacent_seed_counts",all_steps),("seed_trajectories",payload),("mean_majority_disagreements",opposite)]:
        (OUT/f"{name}.json").write_text(json.dumps(value,indent=2,allow_nan=False),encoding="utf-8")
    lines=[f"# Seed-level analysis: {len(summaries)} settings","","Each figure shows individual trajectories, score distributions, paired changes, and direction counts. Falling trajectories are counted over positive-alpha intervals. Descriptive only; no new significance tests.","",
           "| Dataset | Perturbation | Workflow | Seeds with at least one decrease | Steps where mean opposes majority | Figure |","|---|---|---|---:|---:|---|"]
    for r in summaries:
        lines.append(f"| {DS[r['dataset']]} | {r['perturbation'].replace('_',' ')} | {WF[r['workflow']]} | {r['seeds_with_any_decrease_positive_alpha']} | {r['mean_opposes_absolute_majority_steps']} | [Open]({r['figure']}) |")
    (OUT/"all_settings.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    manifest={"source":str(SOURCE),"sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),"rows":len(data),"settings":len(summaries),"figures":len(summaries),
              "steps_mean_opposes_absolute_majority":len(opposite),"steps_mean_opposes_more_nonzero":sum(r["mean_opposes_more_nonzero_seeds"] for r in all_steps),
              "scope":"Synthetic/ZINC settings present in source; seed-level distribution scores. No new p-values or graph-level inference."}
    (OUT/"seed_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest),flush=True)
    print(json.dumps(opposite,indent=2),flush=True)


if __name__=="__main__":main()
