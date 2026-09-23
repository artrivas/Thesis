"""Summarize measured pilot costs without extrapolating unmeasured settings."""
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from experimentation.runner import read_result_rows


def summarize(root):
    manifest = json.loads((root/"run_manifest.json").read_text())
    rows = read_result_rows(root/"results/results.csv")
    if manifest["status"] != "finished" or any(r["status"] != "success" for r in rows):
        raise ValueError(f"Pilot is not complete/successful: {root}")
    groups = defaultdict(list)
    for row in rows:
        groups[row["workflow"]].append(float(row["runtime_seconds"]))
    elapsed = (datetime.fromisoformat(manifest["ended_at"])-datetime.fromisoformat(manifest["started_at"])).total_seconds()
    attempts_path = root/"execution_attempts.json"
    attempts = json.loads(attempts_path.read_text()) if attempts_path.exists() else []
    for attempt in attempts:
        elapsed += (datetime.fromisoformat(attempt["ended_at"])-datetime.fromisoformat(attempt["started_at"])).total_seconds()
    size = sum(p.stat().st_size for p in (root/"results").rglob("*") if p.is_file())
    seeds = len(manifest["seeds"])
    scale = 24/seeds
    return {"run": root.name, "rows": len(rows), "replicates": seeds, "workers": manifest["workers"],
            "previous_execution_segments": attempts,
            "wall_seconds": elapsed, "result_bytes": size,
            "workflow_seconds_sum": {name: sum(values) for name, values in groups.items()},
            "workflow_seconds_mean": {name: sum(values)/len(values) for name, values in groups.items()},
            "max_traced_python_memory_mb": max(float(r["memory_mb"] or 0) for r in rows),
            "projection_same_settings_24_replicates": {"wall_hours_point_estimate": elapsed*scale/3600,
                "result_bytes_point_estimate": int(size*scale)},
            "limitations": "Linear planning projection for the same settings and observed worker schedule, not a guaranteed runtime. Concurrent pilots shared this machine. Earlier segments, if any, are included in wall time. Python traced memory excludes native allocations. Synthetic pilots do not cover all settings; ZINC production samples a different split."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = [summarize(root) for root in args.run]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2)+"\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
