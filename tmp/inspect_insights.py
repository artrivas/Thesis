import json
from pathlib import Path
import numpy as np
p=Path('results/analysis/2026-09-16_structural_insights')
m=json.loads((p/'mechanism_decompositions.json').read_text())
g=json.loads((p/'granular_rows.json').read_text())
c=json.loads((p/'cell_structure.json').read_text())
t=json.loads((p/'graph_trajectory_diagnostics.json').read_text())
for ds in ('barabasi_albert','erdos_renyi'):
 print('\nDATASET',ds)
 for a in (0.,.1,.3,.5,.7,1.):
  rs=[r for r in m if r['dataset']==ds and r['alpha']==a]
  print(a,'MMD terms', {k:round(np.mean([r['kernel'][k] for r in rs]),6) for k in ('xx','yy','xy','score')},'paired',round(np.mean([r['paired_l2'] for r in rs]),3))
  print('WL levels',np.round(np.mean([[v['score'] for v in r['wl_levels']] for r in rs],axis=0),3).tolist())
  print('coherence',{w:round(np.mean([r['coherence_ratio'] for r in g if r['dataset']==ds and r['alpha']==a and r['workflow']==w]),3) for w in ('wl_subtree_kernel_mmd','native_netlsd','diversity_curves_shortest_path')} if a else {})
 rs=[r for r in m if r['dataset']==ds and r['alpha']==1]
 print('geometry', {k:round(np.mean([r['cross_squared_distance_feature_shares'][k] for r in rs]),4) for k in ('edges','triangles','degree_variance')})
 for wf in ('structural_statistics_mmd','wl_subtree_kernel_mmd','native_netlsd','diversity_curves_shortest_path'):
  rs=[r for r in t if r['dataset']==ds and r['workflow']==wf]
  print('pair declines',wf,[r['graphs_with_any_pair_distance_decline_positive_alpha'] for r in rs], 'despite more edits',sum(r['decreasing_pair_distance_despite_more_edits'] for r in rs), '/',sum(r['comparisons_with_more_edits'] for r in rs))
for pt in ('triangle_deletion','edge_deletion','community_weakening','hub_modification'):
 print('\nZINC',pt)
 for a in (0.,.1,.3,.5,.7,1.):
  rs=[r for r in c if r['dataset']=='zinc' and r['perturbation']==pt and r['alpha']==a]
  print(a,'edits',np.mean([r['mean_raw_edits'] for r in rs]),'noops',sum(r['no_ops'] for r in rs),'components',np.mean([r['mean_after']['components'] for r in rs]),'triangles',np.mean([r['mean_after']['triangles'] for r in rs]))
 print('spectrum endpoint',[r['netlsd']['energy_by_time_band'] for r in m if r['dataset']=='zinc' and r['perturbation']==pt and r['alpha']==1])
print('same topology changed representation',sum(r['same_topology_distance_change'] for r in t))
if (p/'targeted_probes.json').exists():
 ps=json.loads((p/'targeted_probes.json').read_text())
 for ds in ('erdos_renyi','stochastic_block_model','barabasi_albert'):
  rs=[r for r in ps if r['dataset']==ds and r['alpha']==1 and r['perturbation']=='hub_modification']
  print('HUB',ds,{k:round(np.mean([r[k] for r in rs]),3) for k in ('target_hub_degree_before','target_hub_degree_after','max_degree_before','max_degree_after','degree_l1','realized_edits')})
 for a in (0,.1,.3,.5,.6,.7,1):
  rs=[r for r in ps if r['dataset']=='stochastic_block_model' and r['perturbation']=='community_weakening' and r['alpha']==a]
  print('SBM',a,{k:round(np.mean([r[k] for r in rs]),6) for k in ('intra_density_after','inter_density_after','fixed_partition_modularity_after','degree_l1','netlsd_score','netlsd_paired')})
 for pt in ('edge_insertion','triangle_insertion'):
  rs=[r for r in ps if r['dataset']=='barabasi_albert' and r['perturbation']==pt and r['alpha']==1]
  print('BA endpoint',pt,'before',{k:round(np.mean([r['mean_before'][k] for r in rs]),3) for k in ('edges','triangles','clustering')},'after',{k:round(np.mean([r['mean_after'][k] for r in rs]),3) for k in ('edges','triangles','clustering')})
if (p/'wl_resolution_diagnostic.json').exists():
 wr=json.loads((p/'wl_resolution_diagnostic.json').read_text())['records']
 for ds in ('barabasi_albert','erdos_renyi','stochastic_block_model'):
  for kind in ('recorded_pilot','independent_unperturbed_reference'):
   rs=[r for r in wr if r['dataset']==ds and r['kind']==kind and r.get('alpha',1)==1]
   if not rs:continue
   print('WL RESOLUTION',ds,kind,'scores',np.mean([[z['score'] for z in r['levels']] for r in rs],axis=0).tolist(),
    'singletons',np.mean([[z['fraction_node_labels_occurring_only_once'] for z in r['levels']] for r in rs],axis=0).tolist(),
    'diagonal',np.mean([[z['within_sample_diagonal_term'] for z in r['levels']] for r in rs],axis=0).tolist())
   if kind=='independent_unperturbed_reference':print('RBF independent reference',[r['graphstats']['score'] for r in rs])
