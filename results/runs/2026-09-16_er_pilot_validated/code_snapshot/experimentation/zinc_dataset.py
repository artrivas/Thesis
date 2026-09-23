"""Versioned ZINC JSON cache: standard-library runtime, topology-only study."""
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import random

from experimentation.graph import Graph
from experimentation.randomness import canonical_json, graph_stream

CACHE_SCHEMA = "zinc_topology_cache_v1"


def validate_record(record):
    n = record["num_nodes"]
    if not isinstance(n, int) or n < 1 or len(record["atom_types"]) != n:
        raise ValueError("Invalid ZINC atom/node counts")
    edges = record["edges"]
    if len(edges) != len(record["bond_types"]):
        raise ValueError("Invalid ZINC bond counts")
    seen = set()
    for u, v in edges:
        if not (0 <= u < v < n) or (u, v) in seen:
            raise ValueError("Unsupported loop, duplicate, or invalid edge in ZINC cache")
        seen.add((u, v))
    if not record["source_id"]:
        raise ValueError("Missing source ID")


def load_manifest(data_root):
    path = Path(data_root) / "ZINC" / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"ZINC cache missing: {path}; run scripts/fetch_zinc.py")
    manifest = json.loads(path.read_text())
    if manifest["schema"] != CACHE_SCHEMA or manifest["variant"] != "subset12k":
        raise ValueError("Unsupported ZINC cache schema/variant")
    expected = hashlib.sha256(canonical_json(manifest["splits"]).encode()).hexdigest()
    if expected != manifest["fingerprint"]:
        raise ValueError("ZINC manifest fingerprint mismatch")
    return manifest


def resolve_zinc_config(config):
    from dataclasses import replace
    manifest = load_manifest(config.data_root)
    if config.dataset_variant != manifest["variant"] or config.projection != "simple_undirected_topology_v1":
        raise ValueError("ZINC variant/projection mismatch")
    if config.dataset_fingerprint and config.dataset_fingerprint != manifest["fingerprint"]:
        raise ValueError("ZINC dataset fingerprint changed")
    return replace(config, dataset_fingerprint=manifest["fingerprint"])


@lru_cache(maxsize=8)
def _load_records(path_string, checksum, mtime_ns, size):
    path = Path(path_string)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != checksum:
        raise ValueError("ZINC cache checksum mismatch")
    records = [json.loads(line) for line in gzip.decompress(raw).decode().splitlines()]
    for record in records:
        validate_record(record)
    if len({r["source_id"] for r in records}) != len(records):
        raise ValueError("Duplicate ZINC source ID")
    return records


def records_for_split(config):
    manifest = load_manifest(config.data_root)
    if manifest["fingerprint"] != config.dataset_fingerprint:
        raise ValueError("ZINC fingerprint must be resolved before loading")
    info = manifest["splits"][config.dataset_split]
    root = (Path(config.data_root) / "ZINC").resolve()
    path = (root / info["file"]).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Invalid ZINC cache path")
    stat = path.stat()
    records = _load_records(str(path), info["sha256"], stat.st_mtime_ns, stat.st_size)
    if len(records) != info["count"]:
        raise ValueError("ZINC split count mismatch")
    return records


def sample_zinc(config):
    if config.num_graphs < 1:
        raise ValueError("ZINC sample size must be positive")
    records = records_for_split(config)
    if config.num_graphs > len(records):
        raise ValueError("ZINC sample size exceeds split size")
    indices = sorted(random.Random(graph_stream(config, "dataset_sampling", None)).sample(
        range(len(records)), config.num_graphs))
    graphs = []
    for index in indices:
        record = records[index]
        graph = Graph(record["num_nodes"], metadata={
            "family": "zinc", "source_id": record["source_id"], "graph_index": index,
            "dataset_split": config.dataset_split, "dataset_fingerprint": config.dataset_fingerprint,
            "projection": config.projection,
            # Immutable source attributes; not labels of the perturbed topology.
            "source_atom_types": tuple(record["atom_types"]),
            "source_bonds": tuple((u, v, b) for (u, v), b in zip(record["edges"], record["bond_types"])),
            "source_record_hash": hashlib.sha256(canonical_json(record).encode()).hexdigest(),
        })
        for u, v in record["edges"]:
            graph.add_edge(u, v)
        graphs.append(graph)
    return graphs
