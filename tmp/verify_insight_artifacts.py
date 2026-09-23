"""Verify analysis provenance, report links, and key evidence after generation."""
from pathlib import Path
import hashlib,json,re
root=Path.cwd();out=root/'results/analysis/2026-09-16_structural_insights'
m=json.loads((out/'analysis_manifest.json').read_text())
for source in m['sources']:
    assert hashlib.sha256((root/source['path']).read_bytes()).hexdigest()==source['sha256']
assert hashlib.sha256((root/'scripts/analyze_structural_insights.py').read_bytes()).hexdigest()==m['script_sha256']
w=json.loads((out/'wl_resolution_diagnostic.json').read_text())
assert hashlib.sha256((root/'scripts/probe_wl_resolution.py').read_bytes()).hexdigest()==w['script_sha256']
for link in re.findall(r'\]\(([^)]+)\)',(out/'README.md').read_text()):
    if not link.startswith('https://'):assert (out/link).exists(),link
g=json.loads((out/'graph_trajectory_diagnostics.json').read_text())
ba=[r for r in g if r['dataset']=='barabasi_albert' and r['workflow']=='wl_subtree_kernel_mmd']
assert sum(r['graphs_with_any_pair_distance_decline_positive_alpha'] for r in ba)==186
assert sum(r['decreasing_pair_distance_despite_more_edits'] for r in ba)==257
assert all(r['same_topology_distance_change']==0 for r in g)
assert m['corrected_rows']==1056 and m['additional_probe_cells']==198
source_paths=['src/experimentation/'+f for f in ['datasets.py','randomness.py','perturbations.py','workflows.py','artifacts.py','graph.py','config.py']]
report={'passed':True,'source_files_unchanged_since_analysis':len(m['sources']),
        'report_local_links_exist':True,'key_count_checks_passed':True,
        'implementation_source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in source_paths}}
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
