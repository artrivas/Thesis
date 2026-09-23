"""Check corrected-run artifacts, pairing, streams, and score reconstruction."""
import argparse
from collections import Counter
from itertools import combinations
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from experimentation.artifacts import read_artifact, row_artifacts_valid, fingerprint
from experimentation.runner import read_result_rows, _row_key


def audit(path):
    path = Path(path)
    rows = read_result_rows(path)
    issues, seen_keys, graph_files, original, streams = [], set(), set(), {}, {}
    counts, no_ops, reasons, kernel_ranges = Counter(), Counter(), Counter(), {}
    source_ids, topologies, replicate_sources = set(), set(), {}
    graph_pairs = 0
    for row in rows:
        key = _row_key(row)
        if key in seen_keys:
            issues.append(f"Duplicate row: {key}")
        seen_keys.add(key)
        counts[row["status"]] += 1
        if row["status"] != "success":
            issues.append(f"Non-success row: {key}: {row['error_message']}")
            continue
        if not row_artifacts_valid(row, path.parent):
            issues.append(f"Missing/corrupt artifact: {key}")
            continue
        data = read_artifact(path.parent, row["workflow_artifact"], row["workflow_sha256"])["details"]
        n = int(row["graph_count"])
        alpha = float(row["alpha"])
        for name in ("distribution_score", "paired_score", "mean_shift_score"):
            score = float(row[name])
            if not math.isfinite(score) or score < -1e-10 or (alpha == 0 and abs(score) > 1e-10):
                issues.append(f"Invalid {name}: {key}")
        if not data.get("available") or len(data["paired_distances"]) != n:
            issues.append(f"Missing individual distances: {key}")
        else:
            if any(not math.isfinite(d) or d < 0 for d in data["paired_distances"]):
                issues.append(f"Invalid individual distance: {key}")
            if not math.isclose(sum(data["paired_distances"])/n, float(row["paired_score"]), rel_tol=1e-9, abs_tol=1e-10):
                issues.append(f"Paired score mismatch: {key}")
            if "mmd_contributions" in data and not math.isclose(sum(data["mmd_contributions"])/n,
                    float(row["distribution_score"]), rel_tol=1e-9, abs_tol=1e-10):
                issues.append(f"MMD reconstruction mismatch: {key}")
            if "kernel_means" in data:
                if float(row["distribution_score"]) > 2 + 1e-10:
                    issues.append(f"MMD bound violation: {key}")
                for name, value in data["kernel_means"].items():
                    bounds = kernel_ranges.setdefault(name, [value, value])
                    bounds[0], bounds[1] = min(bounds[0], value), max(bounds[1], value)
        if row["graph_artifact"] in graph_files:
            continue
        graph_files.add(row["graph_artifact"])
        records = read_artifact(path.parent, row["graph_artifact"], row["graph_sha256"])["pairs"]
        for record in records:
            graph_pairs += 1
            a, b = record["original"], record["perturbed"]
            identity = (row["dataset"], row["seed"], record["graph_index"])
            metadata = a["metadata"]
            source_key = (row["dataset"], "fixed:"+metadata["dataset_fingerprint"], metadata["source_id"]) if "source_id" in metadata else (row["dataset"], row["seed"], str(record["graph_id"]))
            source_ids.add(source_key)
            topologies.add(a["topology_hash"])
            replicate_sources.setdefault((row["dataset"], row["seed"]), set()).add(source_key)
            if identity in original and original[identity] != a["record_hash"]:
                issues.append(f"Source graphs changed across cells: {identity}")
            original[identity] = a["record_hash"]
            for graph in (a, b):
                edges = graph["edges"]
                if len({tuple(e) for e in edges}) != len(edges) or any(not (0 <= u < v < graph["num_nodes"]) for u, v in edges):
                    issues.append(f"Invalid graph edges: {identity}")
                if fingerprint([graph["num_nodes"], edges]) != graph["topology_hash"]:
                    issues.append(f"Topology hash mismatch: {identity}")
            edits = len({tuple(e) for e in a["edges"]} ^ {tuple(e) for e in b["edges"]})
            if edits != record["raw_edits"] or (alpha == 0 and edits):
                issues.append(f"Edit-count/identity mismatch: {identity}")
            stream = record["perturbation"]["perturbation_seed"]
            intended = (row["dataset"], row["seed"], record["graph_id"], row["perturbation"])
            if stream in streams and streams[stream] != intended:
                issues.append(f"Unexpected random-stream reuse: {intended}")
            streams[stream] = intended
            if alpha > 0 and edits == 0:
                no_ops[f"{row['dataset']}/{row['perturbation']}"] += 1
                reasons[str(record["perturbation"]["no_op_reason"])] += 1
    manifest_path = path.parent.parent / "run_manifest.json"
    expected = None
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        cfg = manifest["config"]
        expected = len(cfg["dataset_configs"]) * len(cfg["perturbations"]["methods"]) * len(cfg["perturbations"]["alpha_values"]) * len(manifest["seeds"]) * len(manifest["workflows"])
        if len(rows) != expected:
            issues.append(f"Incomplete grid: expected {expected}, got {len(rows)}")
    overlap = [{"dataset": a[0], "replicate_a": a[1], "replicate_b": b[1],
                "shared_source_ids": len(replicate_sources[a] & replicate_sources[b])}
               for a, b in combinations(sorted(replicate_sources), 2) if a[0] == b[0]]
    return {"passed": not issues, "source": str(path), "rows": len(rows), "expected_rows": expected,
            "statuses": dict(counts), "cells": len(graph_files), "graph_pairs": graph_pairs,
            "source_graph_instances_by_replicate": len(original), "unique_source_record_ids": len(source_ids),
            "unique_labeled_topology_hashes": len(topologies), "source_id_overlap_between_replicates": overlap,
            "unique_perturbation_streams": len(streams),
            "positive_alpha_no_ops": dict(no_ops), "no_op_reasons": dict(reasons),
            "graphstats_kernel_ranges": kernel_ranges, "issues": issues,
            "interpretation": "Implementation and recorded-data checks; not proof of population independence or metric monotonicity"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.results)
    output = args.output or args.results.parent.parent / "sanity_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
