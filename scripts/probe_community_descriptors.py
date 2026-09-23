"""Endpoint descriptor ablations on corrected community experiments."""
from dataclasses import replace
import hashlib,json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_structural_insights import read_runs,mmd
from experimentation.config import default_synthetic_dataset_configs
from experimentation.datasets import generate_paired_distribution
from experimentation.workflows import structural_statistics

out=ROOT/'results/analysis/2026-09-17_mmd_explanation'
out.mkdir(parents=True,exist_ok=True)
rows,cells,provenance=read_runs();records=[]
for ds in ('erdos_renyi','stochastic_block_model'):
 for seed in range(3):
  if ds=='erdos_renyi':
   pairs=cells[(ds,'community_weakening',seed,1.)]
   x=np.array([p['original']['descriptors'] for p in pairs]);y=np.array([p['perturbed']['descriptors'] for p in pairs])
  else:
   dc=next(d for d in default_synthetic_dataset_configs() if d.family==ds)
   p=generate_paired_distribution(replace(dc,seed=seed,master_seed=20260917),'community_weakening',1.,seed)
   x=np.array([structural_statistics(g) for g in p.original_graphs]);y=np.array([structural_statistics(g) for g in p.perturbed_graphs])
  no_tri=[i for i in range(9) if i!=6]
  records.append({'dataset':ds,'seed':seed,'alpha':1.,'full_rbf10':mmd(x,y)['score'],
    'without_triangle_count_rbf10':mmd(x[:,no_tri],y[:,no_tri])['score'],
    'triangle_count_only_rbf10':mmd(x[:,[6]],y[:,[6]])['score'],
    'mean_before':x.mean(0).tolist(),'mean_after':y.mean(0).tolist()})
payload={'records':records,'corrected_sources':provenance,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'interpretation':'Exploratory descriptor omission using unchanged bandwidth 10; differences are not additive causal feature importance. SBM is reproduced from pilot master 20260917.'}
(out/'community_descriptor_ablation.json').write_text(json.dumps(payload,indent=2)+'\n')
for ds in ('erdos_renyi','stochastic_block_model'):
 print(ds,{k:float(np.mean([r[k] for r in records if r['dataset']==ds])) for k in ('full_rbf10','without_triangle_count_rbf10','triangle_count_only_rbf10')})

plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,2,figsize=(11.8,4.7),layout='constrained')
for i,(ds,label) in enumerate([('erdos_renyi','ER'),('stochastic_block_model','SBM')]):
 rs=[r for r in records if r['dataset']==ds]
 vals=[np.mean([r[k][6] for r in rs]) for k in ('mean_before','mean_after')]
 for j,(v,col) in enumerate(zip(vals,['#8099ac','#d86222'])):
  b=axes[0].bar(i+(j-.5)*.3,v,width=.28,color=col,label=('Original' if j==0 else 'Rewired') if i==0 else None)
  axes[0].bar_label(b,fmt='%.2f',padding=3,fontsize=10)
axes[0].set_xticks([0,1],['ER','SBM']);axes[0].set(ylabel='Mean triangles per graph',title='Community rewiring changes triangles in SBM')
axes[0].legend(loc='upper right',fontsize=9);axes[0].set_ylim(0,41)
rs=[r for r in records if r['dataset']=='stochastic_block_model']
vals=[np.mean([r[k] for r in rs]) for k in ('full_rbf10','without_triangle_count_rbf10','triangle_count_only_rbf10')]
b=axes[1].bar(range(3),vals,color=['#d86222','#1769aa','#26846a'],width=.65)
axes[1].bar_label(b,labels=[f'{v:.6f}' if v<.01 else f'{v:.3f}' for v in vals],padding=4)
axes[1].set_xticks(range(3),['All 9\ndescriptors','Omit triangle\ncount','Triangle\ncount only'])
axes[1].set(ylabel='GraphStats RBF MMD²',title='Same SBM graphs; bandwidth fixed at 10',ylim=(0,.51))
for ax in axes:ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
fig.suptitle('Why GraphStats responds to community weakening\nAlpha 1; means of 3 corrected replicates. Descriptor ablations are not additive feature importance.',fontsize=12)
fig.savefig(out/'community_triangle_mechanism.png',dpi=165);plt.close(fig)
