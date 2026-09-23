"""Sample Linux process RSS for a finite set of active experiment runs.

This reports an observed peak of summed RSS, not a physical-memory accounting:
shared pages can be counted in multiple processes, and sampling can miss peaks.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-minutes", type=float, default=180)
    args = parser.parse_args()
    if not Path("/proc/self/status").exists():
        parser.error("This optional monitor requires Linux /proc")
    start = time.monotonic()
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "samples": 0,
              "peak_observed_sum_rss_kib": 0, "per_run_peak_observed_sum_rss_kib": {},
              "limitations": "Sampled every 30 seconds; shared pages may be double-counted; unobserved peaks may be missed."}
    while time.monotonic()-start < args.timeout_minutes*60:
        totals = {run.name: 0 for run in args.run}
        processes = []
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                cmd = (proc/"cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
                if "python" not in cmd.split(" ")[0]:
                    continue
                if "experimentation.cli" not in cmd and "/experimentation/cli.py" not in cmd:
                    continue
                matching = [name for name in totals if name in cmd]
                if not matching:
                    continue
                fields = dict(line.split(":", 1) for line in (proc/"status").read_text().splitlines() if ":" in line)
                rss = int(fields.get("VmRSS", "0 kB").split()[0])
                peak = int(fields.get("VmHWM", "0 kB").split()[0])
                for name in matching:
                    totals[name] += rss
                processes.append({"pid": int(proc.name), "runs": matching, "rss_kib": rss, "process_peak_rss_kib": peak})
            except (OSError, ValueError, IndexError):
                continue
        report["samples"] += 1
        report["peak_observed_sum_rss_kib"] = max(report["peak_observed_sum_rss_kib"], sum(totals.values()))
        for name, rss in totals.items():
            report["per_run_peak_observed_sum_rss_kib"][name] = max(report["per_run_peak_observed_sum_rss_kib"].get(name, 0), rss)
        report["last_sample_at"] = datetime.now(timezone.utc).isoformat()
        report["last_processes"] = processes
        statuses = {run.name: json.loads((run/"run_manifest.json").read_text())["status"] for run in args.run}
        report["run_statuses"] = statuses
        report["finished"] = all(status != "running" for status in statuses.values())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2)+"\n")
        temporary.replace(args.output)
        if report["finished"]:
            break
        time.sleep(30)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
