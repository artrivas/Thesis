"""Audit all imported ZINC records and cross-split exact-record overlap."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from experimentation.datasets import SyntheticDatasetConfig
from experimentation.zinc_dataset import resolve_zinc_config, records_for_split, load_manifest
from experimentation.graph import Graph
from experimentation.artifacts import fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="data")
    args = parser.parse_args()
    report = {"dataset_fingerprint": load_manifest(args.data_root)["fingerprint"], "splits": {}, "exact_record_overlap": {}}
    signatures = {}
    for split in ("train", "val", "test"):
        cfg = resolve_zinc_config(SyntheticDatasetConfig("zinc", data_root=args.data_root,
            dataset_variant="subset12k", dataset_split=split))
        records = records_for_split(cfg)
        stats = {name: [] for name in ("nodes", "edges", "components", "triangles")}
        digests = []
        for record in records:
            graph = Graph(record["num_nodes"])
            for u, v in record["edges"]:
                graph.add_edge(u, v)
            stats["nodes"].append(graph.num_nodes)
            stats["edges"].append(graph.number_of_edges())
            stats["components"].append(len(graph.connected_components()))
            stats["triangles"].append(graph.triangle_count())
            digests.append(fingerprint({k: record[k] for k in ("num_nodes", "edges", "atom_types", "bond_types")}))
        signatures[split] = set(digests)
        report["splits"][split] = {"count": len(records), "exact_record_duplicates": len(digests)-len(set(digests)),
            "triangle_free_graphs": stats["triangles"].count(0),
            "disconnected_graphs": sum(n>1 for n in stats["components"]),
            "summary": {k: {"min": min(v), "median": statistics.median(v), "max": max(v)} for k, v in stats.items()}}
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        report["exact_record_overlap"][f"{a}/{b}"] = len(signatures[a] & signatures[b])
    report["overlap_scope"] = "Exact attributed records in source node ordering, not a graph-isomorphism deduplication guarantee"
    path = Path(args.data_root)/"ZINC/sanity_report.json"
    path.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
