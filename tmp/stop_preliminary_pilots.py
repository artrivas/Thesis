import json
import os
from pathlib import Path
import signal

roots = [112334, 112353, 112443]
for pid in roots:
    command = (Path('/proc')/str(pid)/'cmdline').read_bytes()
    if b'experimentation.cli' not in command or b'2026-09-16_' not in command:
        raise RuntimeError(f'Unexpected process identity: {pid}')
children = {}
for path in Path('/proc').iterdir():
    if path.name.isdigit():
        try:
            for line in (path/'status').read_text().splitlines():
                if line.startswith('PPid:'):
                    children.setdefault(int(line.split()[1]), []).append(int(path.name))
        except (FileNotFoundError, PermissionError):
            pass
targets = list(roots)
for pid in targets:
    targets.extend(children.get(pid, []))
for pid in reversed(targets):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
root = Path(__file__).resolve().parents[1]
for name in ('ba', 'er', 'zinc'):
    path = root/f'results/runs/2026-09-16_{name}_pilot_streams_v1/run_manifest.json'
    manifest = json.loads(path.read_text())
    manifest['status'] = 'stopped_pending_solver_validation'
    manifest['stop_reason'] = 'NetLSD legacy eigensolver lacks convergence check; partial diagnostic run retained, excluded from final analysis.'
    path.write_text(json.dumps(manifest, indent=2)+'\n')
print('Stopped owned preliminary pilot processes:', targets)
