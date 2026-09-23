from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experimentation.config import zinc_config, PerturbationConfig
from experimentation.datasets import SyntheticDatasetConfig, generate_paired_distribution
from experimentation.graph import Graph
from experimentation.randomness import canonical_json
from experimentation.runner import run_experiment, read_result_rows, workflows_from_config
from experimentation.zinc_dataset import CACHE_SCHEMA, resolve_zinc_config, sample_zinc, validate_record


def fixture_cache(directory):
    root = Path(directory) / "ZINC"
    root.mkdir()
    splits = {}
    for split in ("train", "val", "test"):
        records = [{"source_id": f"{split}:{i}", "num_nodes": 5, "atom_types": [1, 2, 1, 3, 1],
                    "edges": [[0, 1], [1, 2], [2, 3]], "bond_types": [1, 2, 1]} for i in range(12)]
        raw = gzip.compress(("\n".join(canonical_json(r) for r in records)+"\n").encode(), mtime=0)
        name = f"{split}.jsonl.gz"
        (root / name).write_bytes(raw)
        splits[split] = {"file": name, "count": len(records), "sha256": hashlib.sha256(raw).hexdigest()}
    (root / "manifest.json").write_text(json.dumps({"schema": CACHE_SCHEMA, "variant": "subset12k",
        "splits": splits, "fingerprint": hashlib.sha256(canonical_json(splits).encode()).hexdigest()}))


class ZincTests(unittest.TestCase):
    def test_sampling_preserves_isolated_nodes_labels_and_pairing(self):
        with TemporaryDirectory() as tmp:
            fixture_cache(tmp)
            cfg = resolve_zinc_config(SyntheticDatasetConfig("zinc", data_root=tmp, num_graphs=5,
                dataset_variant="subset12k", dataset_split="train"))
            graphs = sample_zinc(cfg)
            self.assertEqual(len({g.metadata["source_id"] for g in graphs}), 5)
            self.assertEqual([g.metadata["source_id"] for g in graphs],
                             [g.metadata["source_id"] for g in sample_zinc(cfg)])
            self.assertTrue(all(g.num_nodes == 5 and g.degree(4) == 0 for g in graphs))
            self.assertEqual(graphs[0].metadata["source_atom_types"], (1, 2, 1, 3, 1))
            original_hashes = [g.metadata["source_record_hash"] for g in graphs]
            paired = generate_paired_distribution(cfg, "edge_insertion", .5, cfg.seed)
            self.assertEqual(original_hashes, [g.metadata["source_record_hash"] for g in paired.original_graphs])
            with self.assertRaisesRegex(ValueError, "exceeds"):
                sample_zinc(replace(cfg, num_graphs=13))
            self.assertNotEqual([g.metadata["source_id"] for g in graphs],
                               [g.metadata["source_id"] for g in sample_zinc(replace(cfg, seed=1))])

    def test_cache_corruption_and_duplicate_edges_are_rejected(self):
        with TemporaryDirectory() as tmp:
            fixture_cache(tmp)
            cfg = resolve_zinc_config(SyntheticDatasetConfig("zinc", data_root=tmp,
                dataset_variant="subset12k", dataset_split="train"))
            path = Path(tmp)/"ZINC/train.jsonl.gz"
            path.write_bytes(path.read_bytes()+b"corruption")
            with self.assertRaisesRegex(ValueError, "checksum"):
                sample_zinc(cfg)
        with self.assertRaises(ValueError):
            validate_record({"source_id": "x", "num_nodes": 2, "atom_types": [1, 1],
                             "edges": [[0, 1], [0, 1]], "bond_types": [1, 1]})

    def test_topology_config_and_offline_end_to_end(self):
        with TemporaryDirectory() as tmp:
            fixture_cache(tmp)
            cfg = zinc_config(Path(tmp)/"run", data_root=tmp, mode="debug")
            cfg = replace(cfg, seed_count=1, perturbations=PerturbationConfig(
                methods=("edge_insertion", "triangle_deletion"), alpha_values=(0., .5)))
            wl = next(w for w in workflows_from_config(cfg) if w.name == "wl_subtree_kernel_mmd")
            self.assertEqual(wl.label_initialization, "degree")
            rows = read_result_rows(run_experiment(cfg))
            self.assertEqual(len(rows), 16)
            self.assertTrue(all(r["status"] == "success" for r in rows))
            self.assertTrue(all(float(r["distribution_score"]) == 0 for r in rows if float(r["alpha"]) == 0))

    def test_graph_copy_isolates_nested_metadata(self):
        graph = Graph(2, metadata={"nested": {"labels": [1, 2]}})
        copied = graph.copy()
        copied.metadata["nested"]["labels"][0] = 99
        self.assertEqual(graph.metadata["nested"]["labels"], [1, 2])
