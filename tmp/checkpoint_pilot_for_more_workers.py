"""Stop an owned pilot, preserve its checkpoint, and record its timing segment."""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import time

parser = argparse.ArgumentParser()
parser.add_argument('--pid', type=int, required=True)
parser.add_argument('--run', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
run = args.run.resolve()
if not run.is_relative_to(root/'results/runs'):
    raise ValueError('Run must be inside this workspace results/runs')
command = (Path('/proc')/str(args.pid)/'cmdline').read_bytes().split(b'\0')
if b'experimentation.cli' not in command or run.name.encode() not in command:
    raise ValueError('Unexpected process command; refusing to stop it')
if (Path('/proc')/str(args.pid)/'cwd').resolve() != root:
    raise ValueError('Unexpected process working directory')
children = {}
for path in Path('/proc').iterdir():
    if path.name.isdigit():
        try:
            for line in (path/'status').read_text().splitlines():
                if line.startswith('PPid:'):
                    children.setdefault(int(line.split()[1]), []).append(int(path.name))
        except (FileNotFoundError, PermissionError):
            pass
targets = [args.pid]
for pid in targets:
    targets.extend(children.get(pid, []))
# Stop the sole CSV writer before workers, avoiding synthetic failure rows.
for pid in targets:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
time.sleep(1)
if (Path('/proc')/str(args.pid)/'cmdline').exists():
    if (Path('/proc')/str(args.pid)/'cmdline').read_bytes():
        raise RuntimeError('Writer still alive; do not resume yet')
manifest = json.loads((run/'run_manifest.json').read_text())
history = run/'execution_history'
history.mkdir(exist_ok=True)
csv_path = run/'results/results.csv'
shutil.copy2(csv_path, history/'before_worker_reallocation.csv')
(history/'initial_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
content = csv_path.read_bytes()
if not content.endswith(b'\n'):
    temporary = csv_path.with_suffix('.repair.tmp')
    temporary.write_bytes(content[:content.rfind(b'\n')+1])
    temporary.replace(csv_path)
with csv_path.open() as handle:
    rows = list(csv.DictReader(handle))
if any(None in row or any(value is None for value in row.values()) for row in rows):
    raise ValueError('Malformed CSV; preserved copy requires inspection before resume')
segment = {'started_at': manifest['started_at'], 'ended_at': datetime.now(timezone.utc).isoformat(),
           'workers': manifest['workers'], 'rows_completed': len(rows),
           'reason': 'Reallocate cores from completed synthetic pilots; resume same inputs and code'}
(run/'execution_attempts.json').write_text(json.dumps([segment], indent=2)+'\n')
print(json.dumps(segment, indent=2))
