import json
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
p=Path('results/analysis/2026-09-16_structural_insights')
g=json.loads((p/'granular_rows.json').read_text());s=json.loads((p/'targeted_probes.json').read_text())
for ds in ('erdos_renyi','stochastic_block_model','zinc'):
 print('\n',ds)
 for wf in ('structural_statistics_mmd','wl_subtree_kernel_mmd'):
  trajectories=[]
  for seed in range(3):
   if ds=='stochastic_block_model':
    rows=sorted([r for r in s if r['dataset']==ds and r['perturbation']=='community_weakening' and r['seed']==seed],key=lambda r:r['alpha'])
    scores=[r['kernel']['score'] if wf=='structural_statistics_mmd' else sum(v['score'] for v in r['wl_levels']) for r in rows]
   else:
    rows=sorted([r for r in g if r['dataset']==ds and r['perturbation']=='community_weakening' and r['seed']==seed and r['workflow']==wf],key=lambda r:r['alpha'])
    scores=[r['distribution_score'] for r in rows]
   trajectories.append(scores)
  v=np.array(trajectories)
  print(wf,'means',np.round(v.mean(0),5).tolist(),'rhos positive',[round(spearmanr(np.arange(10),z[1:]).statistic,4) for z in v], 'declines', (np.diff(v,axis=1)<-1e-10).sum(1).tolist())
 if ds=='stochastic_block_model':
  for a in (.1,.5,1):
   rows=[r for r in s if r['dataset']==ds and r['perturbation']=='community_weakening' and r['alpha']==a]
   print('levels',a,np.mean([[x['score'] for x in r['wl_levels']] for r in rows],axis=0).tolist())
for ds in ('erdos_renyi','stochastic_block_model'):
 rows=([r for r in s if r['dataset']==ds and r['perturbation']=='community_weakening' and r['alpha']==1] if ds=='stochastic_block_model' else [r for r in json.loads((p/'cell_structure.json').read_text()) if r['dataset']==ds and r['perturbation']=='community_weakening' and r['alpha']==1])
 print('STRUCTURE',ds)
 for side in ('mean_before','mean_after'):
  print(side,{k:round(np.mean([r[side][k] for r in rows]),4) for k in ('edges','degree_variance','clustering','triangles','components')})
