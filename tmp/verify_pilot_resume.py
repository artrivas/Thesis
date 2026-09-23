import json
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'src'))
from experimentation.runner import read_result_rows, _row_key

run = root/'results/runs/2026-09-16_zinc_pilot_validated'
before = read_result_rows(run/'execution_history/before_worker_reallocation.csv')
after = read_result_rows(run/'results/results.csv')
indexed = {_row_key(row): row for row in after}
if len(indexed) != len(after):
    raise ValueError('Duplicate rows after resume')
for row in before:
    if indexed.get(_row_key(row)) != row:
        raise ValueError('A checkpointed row changed during resume')
report = {'passed': True, 'checkpointed_rows_preserved_exactly': len(before),
          'final_rows': len(after), 'duplicate_rows': len(after)-len(indexed)}
output = root/'results/analysis/2026-09-16_implementation_validation/checkpoint_resume_check.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
