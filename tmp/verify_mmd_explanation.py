from pathlib import Path
import hashlib,json,re
import numpy as np
root=Path.cwd();out=root/'results/analysis/2026-09-17_mmd_explanation'
m=json.loads((out/'manifest.json').read_text())
for r in m['corrected_sources']:assert hashlib.sha256((root/r['path']).read_bytes()).hexdigest()==r['sha256']
for p,h in m['additional_inputs'].items():assert hashlib.sha256((root/p).read_bytes()).hexdigest()==h
assert hashlib.sha256((root/'scripts/explain_mmd_comparison.py').read_bytes()).hexdigest()==m['script_sha256']
ab=json.loads((out/'community_descriptor_ablation.json').read_text())
assert hashlib.sha256((root/'scripts/probe_community_descriptors.py').read_bytes()).hexdigest()==ab['script_sha256']
old=json.loads((root/'results/analysis/2026-09-16_structural_insights/targeted_probes.json').read_text())
for r in ab['records']:
 if r['dataset']=='stochastic_block_model':
  ref=next(x for x in old if x['dataset']==r['dataset'] and x['seed']==r['seed'] and x['alpha']==1 and x['perturbation']=='community_weakening')
  assert np.isclose(r['full_rbf10'],ref['kernel']['score'],atol=1e-10)
for link in re.findall(r'\]\(([^)]+)\)',(out/'README.md').read_text()):
 if link.startswith('//wsl.localhost/Ubuntu/home/artrivas/Thesis/'):
  link=link.removeprefix('//wsl.localhost/Ubuntu/home/artrivas/Thesis/')
  assert (root/link).exists(),link
 elif not link.startswith('https://'):assert (out/link).exists(),link
addition=json.loads((out/'addition_sensitivity.json').read_text())
for p,h in addition['input_sha256'].items():assert hashlib.sha256((root/p).read_bytes()).hexdigest()==h
assert hashlib.sha256((root/'scripts/analyze_addition_sensitivity.py').read_bytes()).hexdigest()==addition['script_sha256']
mechanisms=json.loads((root/'results/analysis/2026-09-16_structural_insights/mechanism_decompositions.json').read_text())
for setting in addition['settings']:
 assert len(setting['records'])==33
 if setting['dataset']=='barabasi_albert' and setting['perturbation']=='triangle_insertion':
  for row in setting['records']:
   ref=next(r for r in mechanisms if r['dataset']=='barabasi_albert' and r['perturbation']=='triangle_insertion' and r['seed']==row['seed'] and r['alpha']==row['alpha'])
   assert np.isclose(row['score'],ref['kernel']['score'],atol=1e-10)
print('Verified input hashes, analysis code hashes, SBM reproduction, and all report links.')
print('Verified addition inputs, 132 records, and BA triangle probe/pilot agreement.')
