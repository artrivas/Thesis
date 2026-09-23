"""Descriptive mechanism audit of preserved experiments; never writes run inputs.

Run with the repository's scientific Python environment. No significance tests.
Additional probes use the pilot master seed and are explicitly separate from
the recorded four-workflow production-size pilots.
"""
from collections import defaultdict
import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from experimentation.artifacts import read_artifact
from experimentation.config import default_synthetic_dataset_configs
from experimentation.datasets import generate_paired_distribution
from experimentation.graph import Graph
from experimentation.workflows import (structural_statistics, wl_feature_matrix,
    sparse_mean, NetLSDWorkflow, DiversityCurvesWorkflow, shortest_path_spread,
    normalized_laplacian_eigenvalues, NETLSD_DEFAULT_TIMESCALES)

OUT = ROOT / "results/analysis/2026-09-16_structural_insights"
FEATURES = ["nodes", "edges", "density", "mean_degree", "degree_variance",
            "clustering", "triangles", "transitivity", "components"]
WF = {"structural_statistics_mmd": "GraphStats", "wl_subtree_kernel_mmd": "WL",
      "native_netlsd": "NetLSD", "diversity_curves_shortest_path": "Diversity"}
RUNS = [f"2026-09-16_{x}_pilot_validated" for x in ("ba", "er", "zinc")]


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def graph(record):
    g = Graph(record["num_nodes"], metadata=record.get("metadata", {}))
    for u, v in record["edges"]:
        g.add_edge(u, v)
    return g


def kernel(x, y, bw=10.):
    d = ((x[:, None, :] - y[None, :, :])**2).sum(axis=2)
    return np.exp(-d/(2*bw*bw))


def mmd(x, y, bw=10.):
    terms = {"xx": float(kernel(x,x,bw).mean()), "yy": float(kernel(y,y,bw).mean()),
             "xy": float(kernel(x,y,bw).mean())}
    return {**terms, "score": terms["xx"]+terms["yy"]-2*terms["xy"]}


def partition_stats(g, labels):
    if not labels:
        return {}
    labels = np.asarray(labels)
    sizes = np.unique(labels, return_counts=True)[1]
    possible_in = int(sum(s*(s-1)//2 for s in sizes))
    possible_out = g.num_nodes*(g.num_nodes-1)//2-possible_in
    inside = sum(labels[u] == labels[v] for u,v in g.edges())
    m = g.number_of_edges()
    degrees = np.asarray(g.degrees())
    q = inside/m-sum((degrees[labels==c].sum()/(2*m))**2 for c in set(labels)) if m else 0.
    return {"intra_density": float(inside/possible_in) if possible_in else 0.,
            "inter_density": float((m-inside)/possible_out) if possible_out else 0.,
            "fixed_partition_modularity": float(q), "community_count": len(sizes)}


def spectra(gs):
    t = np.asarray(NETLSD_DEFAULT_TIMESCALES)
    return np.asarray([np.exp(-np.asarray(normalized_laplacian_eigenvalues(g))[:,None]*t).mean(0) for g in gs])


def wl_parts(gs, hs):
    fs = wl_feature_matrix(gs+hs, 3, label_initialization="degree")
    n = len(gs)
    mx, my = sparse_mean(fs[:n]), sparse_mean(fs[n:])
    out = []
    for level in range(4):
        # Feature names are 'h<iteration>:<label>'; inspect the whole prefix.
        keys = [k for k in set(mx)|set(my) if k.split(":",1)[0] == f"h{level}"]
        xx = sum(mx.get(k,0.)**2 for k in keys)
        yy = sum(my.get(k,0.)**2 for k in keys)
        xy = sum(mx.get(k,0.)*my.get(k,0.) for k in keys)
        out.append({"level": level, "score": xx+yy-2*xy, "xx": xx, "yy": yy, "xy": xy,
                    "mean_feature_cosine": xy/(xx*yy)**.5 if xx*yy else None})
    return out


def read_runs():
    rows, cells, provenance = [], {}, []
    for run in RUNS:
        root = ROOT/"results/runs"/run/"results"
        path = root/"results.csv"
        provenance.append({"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for r in csv.DictReader(path.open()):
            assert r["status"] == "success"
            r = {**r, "alpha": float(r["alpha"]), "seed": int(r["seed"])}
            key = (r["dataset"],r["perturbation"],r["seed"],r["alpha"])
            if key not in cells:
                cells[key] = read_artifact(root,r["graph_artifact"],r["graph_sha256"])["pairs"]
            r["details"] = read_artifact(root,r["workflow_artifact"],r["workflow_sha256"])["details"]
            rows.append(r)
    return rows, cells, provenance


def audit_cells(cells):
    stats = []
    for (ds,pt,seed,a), pairs in sorted(cells.items()):
        x = np.array([p["original"]["descriptors"] for p in pairs])
        y = np.array([p["perturbed"]["descriptors"] for p in pairs])
        extras = defaultdict(list)
        for p in pairs:
            g,h = graph(p["original"]), graph(p["perturbed"])
            dg,dh = np.asarray(g.degrees()),np.asarray(h.degrees())
            extras["degree_l1"].append(float(abs(dg-dh).sum()))
            extras["max_degree_before"].append(float(dg.max()))
            extras["max_degree_after"].append(float(dh.max()))
            labels = p["perturbation"].get("community_labels")
            if labels:
                for k,v in partition_stats(g,labels).items(): extras[k+"_before"].append(v)
                for k,v in partition_stats(h,labels).items(): extras[k+"_after"].append(v)
            hubs = p["perturbation"].get("target_hubs")
            if hubs:
                extras["target_hub_degree_before"].append(float(dg[list(hubs)].sum()))
                extras["target_hub_degree_after"].append(float(dh[list(hubs)].sum()))
            if pt.startswith("triangle"):
                extras["logged_triangles_affected"].append(p["perturbation"]["triangles_affected"])
                extras["absolute_actual_triangle_change"].append(abs(p["perturbed"]["descriptors"][6]-p["original"]["descriptors"][6]))
        stats.append({"dataset":ds,"perturbation":pt,"seed":seed,"alpha":a,
            "graphs":len(pairs),"no_ops":sum(p["no_op"] for p in pairs),
            "mean_raw_edits":float(np.mean([p["raw_edits"] for p in pairs])),
            "mean_before":dict(zip(FEATURES,x.mean(0).tolist())),
            "mean_after":dict(zip(FEATURES,y.mean(0).tolist())),
            **{k:float(np.mean(v)) for k,v in extras.items()}})
    save("cell_structure.json",stats)
    return stats


def granular(rows,cells):
    by_setting = defaultdict(list)
    rowstats = []
    for r in rows:
        key = (r["dataset"],r["perturbation"],r["seed"],r["alpha"])
        pairs = cells[key]
        distances = np.array(r["details"]["paired_distances"])
        assert np.isclose(distances.mean(),float(r["paired_score"]),atol=1e-8,rtol=1e-8)
        edits = np.array([p["raw_edits"] for p in pairs])
        shift,paired = float(r["mean_shift_score"]),float(r["paired_score"])
        rowstats.append({**{k:r[k] for k in ("dataset","perturbation","seed","alpha","workflow")},
            "distribution_score":float(r["distribution_score"]),"mean_shift_score":shift,"paired_score":paired,
            "coherence_ratio":shift/paired if paired>1e-12 else None,
            "distance_quantiles":np.quantile(distances,[0,.25,.5,.75,.9,1]).tolist(),
            "changed_graphs":int((edits>0).sum()),
            "changed_graphs_with_zero_distance":int(((edits>0)&(distances<=1e-10)).sum())})
        by_setting[(r["dataset"],r["perturbation"],r["workflow"],r["seed"])].append(r)
    trajectories=[]
    for (ds,pt,wf,seed),rs in sorted(by_setting.items()):
        rs.sort(key=lambda r:r["alpha"])
        vals=np.array([r["details"]["paired_distances"] for r in rs])
        # Graph order is stable; assert IDs rather than relying on position alone.
        ids=[[p["graph_id"] for p in cells[(ds,pt,seed,r["alpha"])]] for r in rs]
        assert all(i==ids[0] for i in ids)
        changes=np.diff(vals,axis=0)
        graphs=[cells[(ds,pt,seed,r["alpha"])] for r in rs]
        more_edits=np.array([[q["raw_edits"]>p["raw_edits"] for p,q in zip(g,h)] for g,h in zip(graphs[:-1],graphs[1:])])
        different=np.array([[q["perturbed"]["topology_hash"]!=p["perturbed"]["topology_hash"] for p,q in zip(g,h)] for g,h in zip(graphs[:-1],graphs[1:])])
        tol=1e-10*max(1.,abs(vals).max())
        trajectories.append({"dataset":ds,"perturbation":pt,"workflow":wf,"seed":seed,
            "graph_count":vals.shape[1],"graphs_with_any_pair_distance_decline_positive_alpha":int((changes[1:] < -tol).any(0).sum()),
            "decreasing_pair_distance_despite_more_edits":int(((changes < -tol)&more_edits).sum()),
            "comparisons_with_more_edits":int(more_edits.sum()),
            "same_topology_adjacent":int((~different).sum()),
            "same_topology_distance_change":int(((~different)&(abs(changes)>tol)).sum())})
    save("granular_rows.json",rowstats);save("graph_trajectory_diagnostics.json",trajectories)
    return rowstats


def mechanisms(rows,cells):
    out=[]
    selected=[r for r in rows if r["workflow"]=="structural_statistics_mmd"]
    for index,r in enumerate(selected):
        ds,pt,seed,a=(r[k] for k in ("dataset","perturbation","seed","alpha"))
        pairs=cells[(ds,pt,seed,a)]
        x=np.array([p["original"]["descriptors"] for p in pairs]);y=np.array([p["perturbed"]["descriptors"] for p in pairs])
        terms=mmd(x,y)
        assert np.isclose(terms["score"],float(r["distribution_score"]),atol=1e-10)
        sq=((x[:,None,:]-y[None,:,:])**2).mean(axis=(0,1))
        item={"dataset":ds,"perturbation":pt,"seed":seed,"alpha":a,
            "kernel":terms,"paired_l2":float(np.linalg.norm(y-x,axis=1).mean()),
            "cross_squared_distance_feature_shares":dict(zip(FEATURES,(sq/sq.sum()).tolist())) if sq.sum() else {},
            "bandwidth_scores":{str(b):mmd(x,y,b)["score"] for b in (3.,10.,30.,100.)}}
        if ds != "zinc":
            gs=[graph(p["original"]) for p in pairs];hs=[graph(p["perturbed"]) for p in pairs]
            item["wl_levels"]=wl_parts(gs,hs)
            logged=next(q for q in rows if q["dataset"]==ds and q["perturbation"]==pt and q["seed"]==seed and q["alpha"]==a and q["workflow"]=="wl_subtree_kernel_mmd")
            assert np.isclose(sum(z["score"] for z in item["wl_levels"]),float(logged["distribution_score"]),atol=1e-8)
        # Reconstruct corrected NetLSD and identify the scales supplying its energy.
        gs=[graph(p["original"]) for p in pairs];hs=[graph(p["perturbed"]) for p in pairs]
        sx,sy=spectra(gs),spectra(hs)
        delta=sy.mean(0)-sx.mean(0);energy=delta**2;t=np.array(NETLSD_DEFAULT_TIMESCALES)
        logged=next(q for q in rows if q["dataset"]==ds and q["perturbation"]==pt and q["seed"]==seed and q["alpha"]==a and q["workflow"]=="native_netlsd")
        assert np.isclose(np.linalg.norm(delta),float(logged["distribution_score"]),atol=1e-8)
        item["netlsd"]={"score":float(np.linalg.norm(delta)),"energy_by_time_band":
            {label:float(energy[mask].sum()/energy.sum()) if energy.sum()>1e-20 else None for label,mask in
             [("t<1",t<1),("1<=t<10",(t>=1)&(t<10)),("t>=10",t>=10)]},
             "mean_signature_delta":delta.tolist(),
             "mean_component_fraction_delta":float(np.mean([len(h.connected_components())/h.num_nodes-len(g.connected_components())/g.num_nodes for g,h in zip(gs,hs)])),
             "mean_t100_delta":float(delta[-1])}
        out.append(item)
        if index%30==0: print(f"mechanism cells {index+1}/{len(selected)}",flush=True)
    save("mechanism_decompositions.json",out)
    return out


def probes():
    out=[]
    for dc in default_synthetic_dataset_configs():
        pts=["hub_modification"]
        if dc.family=="stochastic_block_model":pts += ["community_weakening"]
        if dc.family=="barabasi_albert":pts += ["edge_insertion","triangle_insertion"]
        for seed in range(3):
            config=replace(dc,seed=seed,master_seed=20260917)
            for pt in pts:
                for a in np.round(np.linspace(0,1,11),1):
                    p=generate_paired_distribution(config,pt,float(a),seed)
                    gs,hs=p.original_graphs,p.perturbed_graphs
                    x=np.array([structural_statistics(g) for g in gs]);y=np.array([structural_statistics(g) for g in hs])
                    stats=defaultdict(list)
                    for g,h,meta in zip(gs,hs,p.metadata["perturbations"]):
                        labels=meta.get("community_labels")
                        if labels:
                            for k,v in partition_stats(g,labels).items():stats[k+"_before"].append(v)
                            for k,v in partition_stats(h,labels).items():stats[k+"_after"].append(v)
                        d,e=np.array(g.degrees()),np.array(h.degrees())
                        stats["degree_l1"].append(float(abs(e-d).sum()))
                        stats["max_degree_before"].append(float(d.max()));stats["max_degree_after"].append(float(e.max()))
                        hubs=meta.get("target_hubs")
                        if hubs:
                            stats["target_hub_degree_before"].append(float(d[list(hubs)].sum()))
                            stats["target_hub_degree_after"].append(float(e[list(hubs)].sum()))
                        stats["realized_edits"].append(len(set(g.edges())^set(h.edges())))
                    item={"dataset":dc.family,"perturbation":pt,"seed":seed,"alpha":float(a),
                          "mean_before":dict(zip(FEATURES,x.mean(0).tolist())),"mean_after":dict(zip(FEATURES,y.mean(0).tolist())),
                          "kernel":mmd(x,y), **{k:float(np.mean(v)) for k,v in stats.items()}}
                    if pt=="community_weakening":
                        item["wl_levels"]=wl_parts(gs,hs)
                        sx,sy=spectra(gs),spectra(hs)
                        item["netlsd_score"]=float(np.linalg.norm(sy.mean(0)-sx.mean(0)))
                        item["netlsd_paired"]=float(np.linalg.norm(sy-sx,axis=1).mean())
                    out.append(item)
                print(f"probe {dc.family} {pt} seed {seed} complete",flush=True)
    save("targeted_probes.json",out)
    return out


def control():
    c=Graph(6);tri=Graph(6)
    for u in range(6):c.add_edge(u,(u+1)%6)
    for b in (0,3):
        for u,v in [(0,1),(1,2),(0,2)]:tri.add_edge(b+u,b+v)
    levels=wl_parts([c],[tri])
    from experimentation.workflows import WLSubtreeMMDWorkflow, StructuralStatisticsMMDWorkflow
    results={w.name:w.run([c],[tri])["distribution_score"] for w in [WLSubtreeMMDWorkflow(label_initialization="degree"),StructuralStatisticsMMDWorkflow(),NetLSDWorkflow(),DiversityCurvesWorkflow()]}
    assert abs(results["wl_subtree_kernel_mmd"])<1e-12
    save("regular_graph_control.json",{"description":"One 6-cycle versus two disjoint triangles: both 6 nodes and degree 2; not a saved experiment", "scores":results,"wl_levels":levels,"descriptors":[structural_statistics(c),structural_statistics(tri)]})


def figures(cells,mechs,probes,gr):
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axs=plt.subplots(2,2,figsize=(12,8),layout="constrained")
    ba=[r for r in mechs if r["dataset"]=="barabasi_albert"]
    for s in range(3):
        rs=sorted([r for r in ba if r["seed"]==s],key=lambda r:r["alpha"]);a=[r["alpha"] for r in rs]
        axs[0,0].plot(a,[r["kernel"]["score"] for r in rs],label=f"replicate {s}")
        axs[0,1].plot(a,[r["paired_l2"] for r in rs])
    rs=sorted([r for r in ba if r["seed"]==0],key=lambda r:r["alpha"])
    for k in ("xx","yy","xy"):axs[1,0].plot(a,[r["kernel"][k] for r in rs],label=k)
    for b in ("3.0","10.0","30.0","100.0"):axs[1,1].plot(a,[r["bandwidth_scores"][b] for r in rs],label=f"bandwidth {b}")
    for ax,title in zip(axs.flat,["RBF MMD²: peak then decline","Mean individual descriptor displacement","Kernel decomposition (replicate 0)","Exploratory bandwidth ablation (replicate 0)"]):ax.set_title(title);ax.set_xlabel("Alpha");ax.grid(alpha=.15)
    axs[0,0].legend();axs[1,0].legend();axs[1,1].legend()
    fig.suptitle("BA triangle insertion: saturation and within-sample dispersion\nCorrected pilot; bandwidth ablations are diagnostic, not selected settings")
    fig.savefig(OUT/"ba_kernel_mechanism.png",dpi=160);plt.close(fig)

    fig,axs=plt.subplots(1,3,figsize=(15,4.5),layout="constrained")
    sbm=[r for r in probes if r["dataset"]=="stochastic_block_model" and r["perturbation"]=="community_weakening"]
    for name in ("intra_density_after","inter_density_after"):
        axs[0].plot(a,[np.mean([r[name] for r in sbm if r["alpha"]==v]) for v in a],label=name.replace("_after","").replace("_"," "))
    for s in range(3):
        rs=sorted([r for r in sbm if r["seed"]==s],key=lambda r:r["alpha"])
        axs[1].plot(a,[r["fixed_partition_modularity_after"] for r in rs],label=f"replicate {s}")
        axs[2].plot(a,[r["degree_l1"] for r in rs])
    axs[1].axhline(0,color="gray",lw=1,ls="--")
    for ax,title in zip(axs,["Original blocks reverse their edge preference","Modularity of the original planted partition","Mean sum of absolute node-degree changes"]):ax.set_title(title);ax.set_xlabel("Alpha");ax.grid(alpha=.15)
    axs[0].legend();axs[1].legend()
    fig.suptitle("Additional corrected SBM diagnostic: community weakening goes beyond erasing communities")
    fig.savefig(OUT/"sbm_operator_mechanism.png",dpi=160);plt.close(fig)

    fig,axs=plt.subplots(1,2,figsize=(12,4.6),layout="constrained")
    for wf in ("wl_subtree_kernel_mmd","native_netlsd","diversity_curves_shortest_path"):
        rs=[r for r in gr if r["dataset"]=="erdos_renyi" and r["workflow"]==wf and r["alpha"]>0]
        aa=sorted(set(r["alpha"] for r in rs))
        axs[0].plot(aa,[np.mean([r["coherence_ratio"] for r in rs if r["alpha"]==v]) for v in aa],label=WF[wf])
    zs=sorted([r for r in mechs if r["dataset"]=="zinc" and r["perturbation"]=="edge_deletion" and r["seed"]==0],key=lambda r:r["alpha"])
    axs[1].plot([r["alpha"] for r in zs],[r["netlsd"]["mean_t100_delta"] for r in zs],label="Heat-trace change at t=100")
    axs[1].plot([r["alpha"] for r in zs],[r["netlsd"]["mean_component_fraction_delta"] for r in zs],ls="--",label="Change in components / nodes")
    axs[0].set_title("ER rewiring: mean displacement / mean pair distance");axs[0].set_ylabel("Coherence ratio (0 to 1)");axs[0].set_ylim(0,1.05)
    axs[1].set_title("ZINC deletion: long-time heat response and fragmentation")
    for ax in axs:ax.set_xlabel("Alpha");ax.legend(fontsize=8);ax.grid(alpha=.15)
    fig.suptitle("Aggregation cancellation and a directly interpretable spectral mechanism")
    fig.savefig(OUT/"aggregation_and_spectrum.png",dpi=160);plt.close(fig)


def main():
    start=time.time();OUT.mkdir(parents=True,exist_ok=True)
    rows,cells,prov=read_runs();print(f"Loaded {len(rows)} rows / {len(cells)} cells",flush=True)
    audit_cells(cells);gr=granular(rows,cells);mechs=mechanisms(rows,cells)
    ps=probes();control();figures(cells,mechs,ps,gr)
    legacy=ROOT/"results/runs/2026-07-03_merged/results/results.csv"
    legacy_rows=[r for r in csv.DictReader(legacy.open()) if r["dataset"]!="imdb_binary"]
    assert len(legacy_rows)==19008
    summary=[];groups=defaultdict(list)
    for r in legacy_rows:groups[(r["dataset"],r["perturbation"],r["workflow"])].append(r)
    for key,rs in sorted(groups.items()):
        aa=sorted(set(float(r["alpha"]) for r in rs));means=[float(np.mean([float(r["distribution_score"]) for r in rs if float(r["alpha"])==a])) for a in aa]
        summary.append({"dataset":key[0],"perturbation":key[1],"workflow":key[2],"alpha":aa,"mean_score":means,"peak_alpha":aa[int(np.argmax(means))],"endpoint":means[-1]})
    save("historical_descriptive_summary.json",summary)
    prov.append({"path":str(legacy.relative_to(ROOT)),"sha256":hashlib.sha256(legacy.read_bytes()).hexdigest(),"used_rows":len(legacy_rows),"interpretation":"Historical exploratory only; shared perturbation streams and old NetLSD solver"})
    save("analysis_manifest.json",{"sources":prov,"corrected_rows":len(rows),"corrected_cells":len(cells),"additional_probe_cells":len(ps),"probe_master_seed":20260917,"probe_graphs_per_cell":100,"probe_replicates":3,"elapsed_seconds":time.time()-start,"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"numpy":np.__version__,"scope":"Descriptive mechanism analysis; no p-values, no changes to experiment source or original results. Targeted probes omit Diversity Curves and are not full four-workflow runs."})
    print(f"Completed {OUT} in {time.time()-start:.1f}s",flush=True)


if __name__=="__main__":main()
