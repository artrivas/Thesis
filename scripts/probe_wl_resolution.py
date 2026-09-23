"""Explain WL feature resolution and empirical self-kernel contributions.

These three descriptive reference draws per family are not a calibrated null
distribution or significance test. Inputs and production settings are unchanged.
"""
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_structural_insights import read_runs, graph, OUT, save, wl_parts, mmd
from experimentation.config import default_synthetic_dataset_configs
from experimentation.datasets import generate_graph_distribution
from experimentation.workflows import wl_feature_matrix, structural_statistics


def diagnostic(gs,hs):
    n=len(gs);fs=wl_feature_matrix(gs+hs,3,label_initialization='degree')
    terms=wl_parts(gs,hs)
    for level,item in enumerate(terms):
        a=[{k:v for k,v in f.items() if k.startswith(f'h{level}:')} for f in fs]
        cx,cy=Counter(),Counter()
        for f in a[:n]:cx.update(f)
        for f in a[n:]:cy.update(f)
        pooled=cx+cy
        item.update({'unique_labels_pooled':len(pooled),
            'fraction_node_labels_occurring_only_once':sum(v for v in pooled.values() if v==1)/sum(pooled.values()),
            'shared_label_types':len(set(cx)&set(cy)),
            'within_sample_diagonal_term':sum(sum(v*v for v in f.values()) for f in a)/(n*n),
            'off_diagonal_plus_cross_term':item['score']-sum(sum(v*v for v in f.values()) for f in a)/(n*n)})
    return terms


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows,cells,prov=read_runs();out=[]
    for (ds,pt,seed,a),pairs in sorted(cells.items()):
        if ds=='zinc' or a not in (.1,1.):continue
        gs=[graph(p['original']) for p in pairs];hs=[graph(p['perturbed']) for p in pairs]
        out.append({'dataset':ds,'perturbation':pt,'seed':seed,'alpha':a,'kind':'recorded_pilot','levels':diagnostic(gs,hs)})
    for dc in default_synthetic_dataset_configs():
        for seed in range(3):
            gs=generate_graph_distribution(replace(dc,seed=seed,master_seed=20260917))
            hs=generate_graph_distribution(replace(dc,seed=100+seed,master_seed=20260917))
            x=np.array([structural_statistics(g) for g in gs]);y=np.array([structural_statistics(g) for g in hs])
            out.append({'dataset':dc.family,'seed':seed,'comparison_replicate':100+seed,'kind':'independent_unperturbed_reference',
                'levels':diagnostic(gs,hs),'graphstats':mmd(x,y),'master_seed':20260917,'graphs_per_sample':100})
    save('wl_resolution_diagnostic.json',{'records':out,'sources':prov,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'interpretation':'Descriptive diagnostics; empirical MMD includes self-kernel terms. Independent reference draws are not significance thresholds.'})
    print('Completed WL resolution and independent reference diagnostics',flush=True)


if __name__=='__main__':main()
