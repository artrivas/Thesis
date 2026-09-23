"""Atomic graph-level sidecars and score decompositions (outside timing)."""
import gzip
import hashlib
import json
import math
import os
from pathlib import Path

from experimentation.randomness import canonical_json
from experimentation.workflows import (
    representation_distance, structural_statistics, sparse_mean, sparse_dot,
    squared_l2,
)

SCHEMA_VERSION = "graph_records_v1"


def fingerprint(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def graph_record(graph):
    value = {"num_nodes": graph.num_nodes, "edges": sorted(graph.edges()),
             "metadata": graph.metadata}
    return {**value, "topology_hash": fingerprint([graph.num_nodes, sorted(graph.edges())]),
            "record_hash": fingerprint(value), "descriptors": structural_statistics(graph)}


def pair_records(paired):
    result = []
    for i, (a, b, metadata) in enumerate(zip(paired.original_graphs, paired.perturbed_graphs,
                                           paired.metadata["perturbations"])):
        edits = len(set(a.edges()) ^ set(b.edges()))
        result.append({"graph_index": i, "graph_id": metadata["graph_id"],
                       "original": graph_record(a), "perturbed": graph_record(b),
                       "raw_edits": edits, "no_op": edits == 0, "perturbation": metadata})
    return result


def representation_details(workflow, representations):
    if representations is None:
        return {"available": False, "reason": "Workflow did not expose cached representations"}
    x, y = representations
    if len(x) != len(y) or not x:
        raise ValueError("Granular diagnostics require nonempty paired representations")
    n = len(x)
    details = {"available": True, "paired_distances": [representation_distance(a, b) for a, b in zip(x, y)]}
    if workflow.name == "structural_statistics_mmd":
        kernel = lambda a, b: math.exp(-squared_l2(a, b) / (2 * workflow.bandwidth**2))
        xx = [[kernel(a, b) for b in x] for a in x]
        yy = [[kernel(a, b) for b in y] for a in y]
        xy = [[kernel(a, b) for b in y] for a in x]
        details["kernel_means"] = {name: sum(map(sum, matrix)) / n**2
                                    for name, matrix in (("xx", xx), ("yy", yy), ("xy", xy))}
        details["mmd_contributions"] = [(sum(xx[i]) + sum(yy[i]) - sum(xy[i])
                                          - sum(row[i] for row in xy)) / n for i in range(n)]
    elif workflow.name == "wl_subtree_kernel_mmd":
        mx, my = sparse_mean(x), sparse_mean(y)
        delta = {k: my.get(k, 0.) - mx.get(k, 0.) for k in set(mx) | set(my)}
        details["squared_mean_displacement"] = sum(v*v for v in delta.values())
        details["mmd_contributions"] = [sparse_dot(b, delta)-sparse_dot(a, delta) for a, b in zip(x, y)]
    if "mmd_contributions" in details:
        details["contribution_interpretation"] = "Signed sample-dependent MMD² decomposition, not independent graph distances"
    return details


def write_artifact(directory, name, value):
    """Content checksum is independent of gzip timestamps and worker order."""
    path = Path(directory) / "graph_records" / (name + ".json.gz")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = canonical_json(value).encode()
    checksum = hashlib.sha256(content).hexdigest()
    if path.exists():
        try:
            if hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() == checksum:
                return path.relative_to(directory).as_posix(), checksum
        except (OSError, EOFError):
            pass
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(gzip.compress(content, mtime=0))
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    return path.relative_to(directory).as_posix(), checksum


def read_artifact(directory, relative_path, checksum):
    root = Path(directory).resolve()
    path = (root / relative_path).resolve()
    if not relative_path or not path.is_relative_to(root):
        raise ValueError("Invalid artifact path")
    content = gzip.decompress(path.read_bytes())
    if hashlib.sha256(content).hexdigest() != checksum:
        raise ValueError("Graph artifact checksum mismatch")
    return json.loads(content)


def row_artifacts_valid(row, directory):
    try:
        graphs = read_artifact(directory, row.get("graph_artifact", ""), row.get("graph_sha256", ""))
        details = read_artifact(directory, row.get("workflow_artifact", ""), row.get("workflow_sha256", ""))
        if graphs["schema"] != SCHEMA_VERSION or details["schema"] != SCHEMA_VERSION:
            return False
        return len(graphs["pairs"]) == int(row["graph_count"]) and details["workflow"] == row["workflow"]
    except (OSError, ValueError, KeyError, EOFError, TypeError):
        return False


def persist_row_artifacts(row, directory):
    graphs = row.pop("_graph_records", None)
    details = row.pop("_workflow_details", None)
    if graphs is None:
        return
    cell = {key: row[key] for key in ("dataset", "dataset_params", "perturbation", "alpha", "seed")}
    graph_payload = {"schema": SCHEMA_VERSION, "cell": cell, "pairs": graphs}
    graph_id = fingerprint(cell)
    row["graph_artifact"], row["graph_sha256"] = write_artifact(directory, graph_id, graph_payload)
    payload = {"schema": SCHEMA_VERSION, "cell": cell, "workflow": row["workflow"],
               "workflow_params": row["workflow_params"], "status": row["status"], "details": details}
    row["workflow_artifact"], row["workflow_sha256"] = write_artifact(
        directory, fingerprint([cell, row["workflow"], row["workflow_params"]]), payload)
