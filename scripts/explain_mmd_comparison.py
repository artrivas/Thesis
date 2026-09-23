"""Annotated, corrected-results-only comparison of GraphStats and WL.

Kernel substitutions are exploratory mechanisms, not new benchmark settings.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.sparse import csr_matrix
from scipy.stats import spearmanr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_structural_insights import read_runs,graph
from experimentation.workflows import wl_feature_matrix

SOURCE=ROOT/'results/analysis/2026-09-16_structural_insights'
OUT=ROOT/'results/analysis/2026-09-17_mmd_explanation'
BLUE='#1769aa';ORANGE='#d86222';GREEN='#26846a'


def dump(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def sparse_gram(features):
    keys=sorted(set().union(*(f.keys() for f in features)));idx={k:i for i,k in enumerate(keys)}
    rr=[];cc=[];vv=[]
    for i,f in enumerate(features):
        for k,v in f.items():rr.append(i);cc.append(idx[k]);vv.append(float(v))
    mat=csr_matrix((vv,(rr,cc)),shape=(len(features),len(keys)))
    return (mat@mat.T).toarray()


def from_gram(k,n):
    return float(k[:n,:n].mean()+k[n:,n:].mean()-2*k[:n,n:].mean())


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows,cells,provenance=read_runs()
    mechs=json.loads((SOURCE/'mechanism_decompositions.json').read_text())
    probes=json.loads((SOURCE/'targeted_probes.json').read_text())
    records=[]
    for (ds,pt,seed,a),pairs in sorted(cells.items()):
        if ds!='barabasi_albert':continue
        x=np.array([p['original']['descriptors'] for p in pairs]);y=np.array([p['perturbed']['descriptors'] for p in pairs])
        gs=[graph(p['original']) for p in pairs];hs=[graph(p['perturbed']) for p in pairs];n=len(gs)
        gram=sparse_gram(wl_feature_matrix(gs+hs,3,label_initialization='degree'))
        dd=np.maximum(0,np.diag(gram)[:,None]+np.diag(gram)[None,:]-2*gram)
        distances=np.sqrt(dd[:n,:n][np.triu_indices(n,1)])
        sigma=float(np.median(distances[distances>0]))
        gauss=np.exp(-dd/(2*sigma*sigma))
        base=next(r for r in mechs if r['dataset']==ds and r['seed']==seed and r['alpha']==a)
        linear=from_gram(gram,n)
        assert np.isclose(linear,sum(r['score'] for r in base['wl_levels']),atol=1e-8)
        records.append({'seed':seed,'alpha':a,'graphstats_rbf10':base['kernel']['score'],
            'graphstats_linear':float(((x.mean(0)-y.mean(0))**2).sum()),
            'wl_linear':linear,'wl_rbf_reference_median':from_gram(gauss,n),'wl_rbf_bandwidth':sigma,
            'graphstats_bandwidth_scores':base['bandwidth_scores']})
    for seed in range(3):
        sigmas=[r['wl_rbf_bandwidth'] for r in records if r['seed']==seed]
        assert np.ptp(sigmas)<1e-10,'Reference bandwidth changed along trajectory'
    dump('kernel_substitutions.json',records)

    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    a=np.round(np.linspace(0,1,11),1)
    def mean_record(key):return np.array([np.mean([r[key] for r in records if r['alpha']==v]) for v in a])
    fig,axs=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for key,label,color in [('graphstats_rbf10','GraphStats + RBF',ORANGE),('wl_linear','WL + linear',BLUE)]:
        vals=mean_record(key)
        axs[0].plot(a,vals/vals.max(),marker='o',color=color,label=label)
    axs[0].set(ylabel='Score / maximum of its own mean curve',title='GraphStats responds earlier on this alpha grid')
    axs[0].annotate('Early jump, then decline',xy=(.3,1),xytext=(.42,1.1),arrowprops={'arrowstyle':'->','color':ORANGE},fontsize=10)
    axs[0].set_ylim(0,1.23);axs[0].legend(loc='lower right')
    for b,col in [('3.0','#707b87'),('10.0',ORANGE),('30.0',GREEN),('100.0','#784bb2')]:
        vals=[np.mean([r['graphstats_bandwidth_scores'][b] for r in records if r['alpha']==v]) for v in a]
        axs[1].plot(a,vals,label=f'bandwidth {float(b):g}',color=col,lw=2)
    axs[1].set(ylabel='GraphStats RBF MMD²',title='Same graphs and descriptors; only bandwidth changes')
    axs[1].legend(fontsize=9)
    for ax in axs:ax.set_xlabel('Alpha');ax.grid(alpha=.17)
    fig.suptitle('BA triangle insertion | means of 3 corrected replicates\nLeft: relative response shape only; scaling does not compare accuracy or raw magnitude',fontsize=12)
    fig.savefig(OUT/'bandwidth_response.png',dpi=165);plt.close(fig)

    fig,axs=plt.subplots(1,2,figsize=(12,4.2),layout='constrained')
    for ax,representation,settings in [(axs[0],'GraphStats',[('graphstats_rbf10','RBF, bandwidth 10',ORANGE),('graphstats_linear','Linear kernel',BLUE)]),
            (axs[1],'WL',[('wl_linear','Original linear kernel',BLUE),('wl_rbf_reference_median','RBF, reference-median bandwidth',ORANGE)])]:
        for key,label,col in settings:
            v=mean_record(key);ax.plot(a,v/v.max(),label=label,color=col,lw=2,marker='o')
        ax.set(title=f'{representation}: representation held fixed',xlabel='Alpha',ylabel='Score / maximum of its own mean curve')
        ax.legend(fontsize=9);ax.grid(alpha=.17)
    fig.suptitle('Changing the kernel changes the response shape\nExploratory substitutions on identical saved graphs; each bandwidth is fixed across alpha',fontsize=12)
    fig.savefig(OUT/'kernel_substitution.png',dpi=165);plt.close(fig)

    summary=[]
    fig,axs=plt.subplots(2,3,figsize=(13,7),layout='constrained',sharex=True)
    for col,(ds,title) in enumerate([('erdos_renyi','ER: detected partition'),('stochastic_block_model','SBM: planted partition'),('zinc','ZINC: detected partition')]):
        for row,(wf,key,label,color) in enumerate([('structural_statistics_mmd','graphstats','GraphStats + RBF MMD²',ORANGE),('wl_subtree_kernel_mmd','wl','WL + linear MMD²',BLUE)]):
            ax=axs[row,col];trajectories=[]
            for seed in range(3):
                if ds=='stochastic_block_model':
                    rs=sorted([r for r in probes if r['dataset']==ds and r['perturbation']=='community_weakening' and r['seed']==seed],key=lambda r:r['alpha'])
                    vals=[r['kernel']['score'] if key=='graphstats' else sum(v['score'] for v in r['wl_levels']) for r in rs]
                else:
                    rs=sorted([r for r in rows if r['dataset']==ds and r['perturbation']=='community_weakening' and r['workflow']==wf and r['seed']==seed],key=lambda r:r['alpha'])
                    vals=[float(r['distribution_score']) for r in rs]
                trajectories.append(vals);ax.plot(a,vals,color=color,alpha=.28,lw=1.4)
            v=np.array(trajectories);rho=[float(spearmanr(a[1:],z[1:]).statistic) for z in v]
            ax.plot(a,v.mean(0),color=color,lw=2.8,label='Mean; thin lines = replicates')
            ax.set_title(title if row==0 else f'Median positive-alpha rho = {np.median(rho):.2f}',fontsize=11)
            ax.set_ylabel(label,fontsize=10);ax.grid(alpha=.17)
            if row==0:ax.text(.04,.95,f'Median positive-alpha rho = {np.median(rho):.2f}',transform=ax.transAxes,va='top',fontsize=9)
            else:ax.set_xlabel('Alpha')
            summary.append({'dataset':ds,'workflow':wf,'alpha':a.tolist(),'trajectories':v.tolist(),'mean':v.mean(0).tolist(),
                'positive_alpha_spearman_by_replicate':rho,'median_rho':float(np.median(rho)),
                'positive_alpha_declines_by_replicate':(np.diff(v[:,1:],axis=1)<-1e-10).sum(1).tolist()})
    fig.suptitle('Community weakening: WL does not dominate across the corrected settings\nSeparate vertical scales: compare ordering and shape, not heights. SBM is an additional targeted probe.',fontsize=12)
    fig.savefig(OUT/'community_comparison.png',dpi=165);plt.close(fig)
    dump('community_comparison.json',summary)
    dump('manifest.json',{'corrected_sources':provenance,'additional_inputs':
        {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE/'mechanism_decompositions.json',SOURCE/'targeted_probes.json']},
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope':'Corrected pilots and corrected targeted probes only. Three replicates, descriptive correlations, no p-values. Kernel substitutions isolate aggregation changes without selecting new defaults.'})
    print(json.dumps({'community':[{k:r[k] for k in ['dataset','workflow','median_rho']} for r in summary],
        'BA_first_positive_fraction_of_peak':{k:float(mean_record(k)[1]/mean_record(k).max()) for k in ['graphstats_rbf10','wl_linear','graphstats_linear','wl_rbf_reference_median']},
        'WL_RBF_bandwidths':sorted(set(r['wl_rbf_bandwidth'] for r in records))},indent=2))


if __name__=='__main__':main()
