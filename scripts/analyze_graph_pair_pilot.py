"""Matched graph-level pilot: BA triangle insertion, seeds 0,1,2.

Reconstructs graph-level distances and signed MMD² contribution decompositions.
Every aggregate is checked against the historical row; no new hypothesis tests.
"""
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from experimentation.datasets import SyntheticDatasetConfig,generate_paired_distribution
from experimentation.workflows import structural_statistics,WLSubtreeMMDWorkflow,sparse_mean,sparse_dot,sparse_l2

OUT=ROOT/"results/analysis/2026-09-15_granular_analysis"
SOURCE=ROOT/"results/runs/2026-07-03_merged/results/results.csv.gz"


def graph_hash(graph):
    return hashlib.sha256(json.dumps([graph.num_nodes,sorted(graph.edges())],separators=(",",":")).encode()).hexdigest()


def rbf_contributions(x,y,bandwidth):
    kxx=np.exp(-cdist(x,x,"sqeuclidean")/(2*bandwidth**2))
    kyy=np.exp(-cdist(y,y,"sqeuclidean")/(2*bandwidth**2))
    kxy=np.exp(-cdist(x,y,"sqeuclidean")/(2*bandwidth**2))
    return kxx.mean(1)+kyy.mean(1)-kxy.mean(1)-kxy.mean(0)


def linear_contributions(x,y):
    mx,my=sparse_mean(x),sparse_mean(y)
    mu={k:my.get(k,0.)-mx.get(k,0.) for k in set(mx)|set(my)}
    return np.array([sparse_dot(b,mu)-sparse_dot(a,mu) for a,b in zip(x,y)])


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frame=pd.read_csv(SOURCE)
    source=frame[(frame.dataset=="barabasi_albert")&(frame.perturbation=="triangle_insertion")&(frame.seed.isin([0,1,2]))]
    pairs=[];checks=[];original_hashes={}
    for seed in [0,1,2]:
        for alpha in np.linspace(0,1,11).round(1):
            sel=source[(source.seed==seed)&(source.alpha==alpha)]
            gs=sel[sel.workflow=="structural_statistics_mmd"].iloc[0]
            wl=sel[sel.workflow=="wl_subtree_kernel_mmd"].iloc[0]
            params=json.loads(gs.dataset_params)
            params.setdefault("randomness_protocol", "legacy_seed_plus_index")
            config=SyntheticDatasetConfig(**params)
            paired=generate_paired_distribution(config,"triangle_insertion",float(alpha),seed)
            x=np.array([structural_statistics(g) for g in paired.original_graphs])
            y=np.array([structural_statistics(g) for g in paired.perturbed_graphs])
            params=json.loads(gs.workflow_params)
            gc=rbf_contributions(x,y,params["bandwidth"]);gd=np.linalg.norm(y-x,axis=1)
            wp=json.loads(wl.workflow_params)
            model=WLSubtreeMMDWorkflow(iterations=wp["wl_iterations"],label_initialization=wp["wl_label_initialization"],node_label_key=wp["wl_node_label_key"])
            representations=model.compute_representations(paired.original_graphs+paired.perturbed_graphs)
            wx,wy=representations[:len(x)],representations[len(x):]
            wc=linear_contributions(wx,wy);wd=np.array([sparse_l2(a,b) for a,b in zip(wx,wy)])
            for name,logged,c,d in [("GraphStats",gs,gc,gd),("WL",wl,wc,wd)]:
                if not np.isclose(c.mean(),logged.distribution_score,rtol=1e-10,atol=1e-10):raise ValueError("Distribution reproduction mismatch")
                if not np.isclose(d.mean(),logged.paired_score,rtol=1e-10,atol=1e-10):raise ValueError("Paired-score reproduction mismatch")
                checks.append({"seed":seed,"alpha":float(alpha),"workflow":name,"score":float(c.mean()),"score_error":float(abs(c.mean()-logged.distribution_score)),"paired_score":float(d.mean()),"paired_error":float(abs(d.mean()-logged.paired_score))})
            for i,(a,b) in enumerate(zip(paired.original_graphs,paired.perturbed_graphs)):
                identity=(seed,i);h=graph_hash(a)
                if identity in original_hashes and h!=original_hashes[identity]:raise ValueError("Source graph identity changed across alpha")
                original_hashes[identity]=h
                pairs.append({"dataset":"barabasi_albert","perturbation":"triangle_insertion","seed":seed,"graph_index":i,"alpha":float(alpha),"original_hash":h,"perturbed_hash":graph_hash(b),
                    "raw_edits":len(set(a.edges())^set(b.edges())),"original_descriptors":x[i].tolist(),"perturbed_descriptors":y[i].tolist(),
                    "graphstats_paired_distance":float(gd[i]),"wl_paired_distance":float(wd[i]),"graphstats_mmd_contribution":float(gc[i]),"wl_mmd_contribution":float(wc[i])})
        print("Reproduced graph-pair pilot seed",seed,flush=True)
    (OUT/"graph_pair_pilot.json").write_text(json.dumps(pairs,indent=2,allow_nan=False),encoding="utf-8")
    transitions=[];pdf=pd.DataFrame(pairs)
    for seed in [0,1,2]:
        g=pdf[pdf.seed==seed]
        for prefix in ["graphstats","wl"]:
            distance=g.pivot(index="graph_index",columns="alpha",values=prefix+"_paired_distance")
            contribution=g.pivot(index="graph_index",columns="alpha",values=prefix+"_mmd_contribution")
            d=(distance[.4]-distance[.3]).to_numpy();c=(contribution[.4]-contribution[.3]).to_numpy()
            transitions.append({"seed":seed,"workflow":prefix,"alpha_low":.3,"alpha_high":.4,"graphs":len(d),
                "paired_distance_increases":int((d>1e-10).sum()),"paired_distance_decreases":int((d < -1e-10).sum()),"paired_distance_unchanged":int((abs(d)<=1e-10).sum()),
                "mean_paired_distance_change":float(d.mean()),"median_paired_distance_change":float(np.median(d)),
                "contribution_increases":int((c>1e-10).sum()),"contribution_decreases":int((c < -1e-10).sum()),
                "mmd_change":float(c.mean())})
    manifest={"source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),"dataset":"barabasi_albert","perturbation":"triangle_insertion","seeds":[0,1,2],"graph_count_per_seed":100,
              "descriptor_columns":["nodes","edges","density","mean_degree","degree_variance","clustering","triangles","transitivity","components"],
              "graph_rows":len(pairs),"matched_workflow_rows":len(checks),"max_score_reproduction_error":max(c["score_error"] for c in checks),"max_paired_reproduction_error":max(c["paired_error"] for c in checks),
              "contribution_definition":"Signed, sample-dependent paired decomposition whose mean is empirical MMD². Not a graph distance, independent observation, or causal importance measure.","transitions":transitions,"checks":checks}
    (OUT/"graph_pair_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    draw_pilot(pdf)
    print(json.dumps(transitions,indent=2),flush=True)


def draw_pilot(df):
    g=df[df.seed==0];fig,axes=plt.subplots(2,2,figsize=(12,8.4),layout="constrained")
    for j,prefix in enumerate(["graphstats","wl"]):
        w=g.pivot(index="graph_index",columns="alpha",values=prefix+"_paired_distance")
        for _,r in w.iterrows():axes[0,j].plot(w.columns,r,color="#6A8DA3",alpha=.2,lw=.7)
        axes[0,j].plot(w.columns,w.mean(),color="#172F47",lw=2,label="Mean of 100 pairs")
        axes[0,j].plot(w.columns,w.median(),color="#C45C24",ls="--",lw=2,label="Median")
        axes[0,j].set_title(prefix+": individual graph-pair distances");axes[0,j].set_xlabel("Perturbation strength α");axes[0,j].set_ylabel("Representation L2 distance");axes[0,j].legend(fontsize=9)
        c=g.pivot(index="graph_index",columns="alpha",values=prefix+"_mmd_contribution")
        dx=w[.4]-w[.3];dy=c[.4]-c[.3]
        axes[1,j].scatter(dx,dy,s=20,alpha=.7,color="#266F9D")
        axes[1,j].axhline(0,color="#C6553E",lw=1);axes[1,j].axvline(0,color="#888888",lw=1)
        axes[1,j].set_xlabel("Change in graph-pair distance, α .3 → .4")
        axes[1,j].set_ylabel("Change in signed MMD² contribution")
        axes[1,j].set_title(f"100 pairs; aggregate MMD² change = {dy.mean():+.4g}")
        for ax in axes[:,j]:ax.grid(alpha=.15)
    fig.suptitle("Inside one distribution: BA triangle insertion, seed 0\nEach line or point is one graph pair; contributions depend on the whole sample",fontsize=13)
    fig.savefig(OUT/"graph_pair_pilot.png",dpi=145);plt.close(fig)


if __name__=="__main__":main()
