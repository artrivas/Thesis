import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
snapshot = root/'archive/results_snapshots/2026-09-16_before_randomness_fix'
manifest = json.loads((snapshot/'snapshot_manifest.json').read_text())
for item in manifest['files']:
    for base in (root/'results', snapshot/'results'):
        content = (base/item['path']).read_bytes()
        if len(content) != item['bytes'] or hashlib.sha256(content).hexdigest() != item['sha256']:
            raise ValueError(f'Historical result changed: {base/item["path"]}')
output = root/'results/analysis/2026-09-16_implementation_validation'
output.mkdir(parents=True, exist_ok=True)
(output/'historical_results_check.json').write_text(json.dumps({
    'passed': True, 'files': len(manifest['files']), 'bytes': manifest['total_bytes'],
    'verification': 'Both historical originals and snapshot match the pre-implementation SHA-256 inventory'
}, indent=2)+'\n')
(output/'unit_tests.txt').write_text(Path('/tmp/thesis-tests.log').read_text())
print('All 181 historical files and their snapshot copies remain byte-identical.')
