from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experimentation.artifacts import read_artifact, row_artifacts_valid
from experimentation.config import debug_config, PerturbationConfig, WorkflowConfig, DEFAULT_PERTURBATION_METHODS
from experimentation.datasets import SyntheticDatasetConfig, generate_paired_distribution, generate_graph_distribution
from experimentation.randomness import graph_stream, LEGACY_PROTOCOL
from experimentation.runner import run_experiment, read_result_rows, write_result_rows, merge_runs


def tiny(root):
    return replace(debug_config(root), dataset_configs=(SyntheticDatasetConfig("erdos_renyi",
        num_graphs=3, num_nodes=6, edge_probability=.4),), seed_count=2,
        perturbations=PerturbationConfig(methods=("edge_insertion",), alpha_values=(0., .5)),
        workflows=WorkflowConfig(names=("structural_statistics_mmd", "wl_subtree_kernel_mmd")))


class RandomStreamTests(unittest.TestCase):
    def test_full_synthetic_inventory_has_no_unintended_collisions(self):
        seeds = set()
        for family in ("erdos_renyi", "barabasi_albert", "stochastic_block_model"):
            for replicate in range(24):
                cfg = SyntheticDatasetConfig(family, seed=replicate)
                for graph_id in range(100):
                    for purpose, method in [("graph_generation", None)] + [("perturbation", m) for m in DEFAULT_PERTURBATION_METHODS]:
                        derived = graph_stream(cfg, purpose, graph_id, method)
                        self.assertNotIn(derived, seeds)
                        seeds.add(derived)
        self.assertEqual(len(seeds), 50400)

    def test_old_collision_is_fixed_and_pairing_is_preserved(self):
        a = SyntheticDatasetConfig("erdos_renyi", num_graphs=3, num_nodes=8, seed=0)
        b = replace(a, seed=1)
        self.assertNotEqual(graph_stream(a, "perturbation", 1, "edge_insertion"),
                            graph_stream(b, "perturbation", 0, "edge_insertion"))
        lo = generate_paired_distribution(a, "edge_insertion", .3, 0)
        hi = generate_paired_distribution(a, "edge_insertion", .7, 0)
        self.assertEqual([g.edges() for g in lo.original_graphs], [g.edges() for g in hi.original_graphs])
        self.assertEqual([m["perturbation_seed"] for m in lo.metadata["perturbations"]],
                         [m["perturbation_seed"] for m in hi.metadata["perturbations"]])
        self.assertEqual([g.edges() for g in hi.perturbed_graphs],
            [g.edges() for g in generate_paired_distribution(a, "edge_insertion", .7, 0).perturbed_graphs])

    def test_generation_graph_prefix_is_stable(self):
        for family in ("erdos_renyi", "barabasi_albert", "stochastic_block_model"):
            cfg = SyntheticDatasetConfig(family, num_graphs=3, num_nodes=8)
            self.assertEqual([g.edges() for g in generate_graph_distribution(cfg)],
                [g.edges() for g in generate_graph_distribution(replace(cfg, num_graphs=5))[:3]])


class ArtifactTests(unittest.TestCase):
    def test_all_workflows_match_serial_parallel_and_shared_inputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = replace(tiny(root/"serial"), workflows=WorkflowConfig())
            serial = read_result_rows(run_experiment(config, workers=1))
            parallel_config = replace(config, outputs=debug_config(root/"parallel").outputs)
            parallel = read_result_rows(run_experiment(parallel_config, workers=2))
            key = lambda r: (r["seed"], r["alpha"], r["workflow"])
            left = {key(r): r for r in serial}
            right = {key(r): r for r in parallel}
            self.assertEqual(set(left), set(right))
            for identity, row in left.items():
                self.assertEqual(row["graph_sha256"], right[identity]["graph_sha256"])
                for score in ("distribution_score", "paired_score", "mean_shift_score"):
                    self.assertAlmostEqual(float(row[score]), float(right[identity][score]), places=9)

    def test_repair_missing_sidecar_and_reconstruct_scores(self):
        with TemporaryDirectory() as tmp:
            cfg = tiny(Path(tmp))
            path = run_experiment(cfg)
            before = read_result_rows(path)
            for row in before:
                self.assertTrue(row_artifacts_valid(row, path.parent))
                details = read_artifact(path.parent, row["workflow_artifact"], row["workflow_sha256"])["details"]
                self.assertAlmostEqual(sum(details["paired_distances"])/3, float(row["paired_score"]))
                self.assertAlmostEqual(sum(details["mmd_contributions"])/3, float(row["distribution_score"]))
            (path.parent / before[0]["graph_artifact"]).unlink()
            run_experiment(cfg)
            after = read_result_rows(path)
            self.assertEqual(len(before), len(after))
            self.assertTrue(all(row_artifacts_valid(row, path.parent) for row in after))
            self.assertEqual({r["workflow_sha256"] for r in before}, {r["workflow_sha256"] for r in after})

    def test_reject_legacy_resume_and_changed_master_seed(self):
        with TemporaryDirectory() as tmp:
            cfg = tiny(Path(tmp))
            path = run_experiment(cfg)
            changed = replace(cfg, dataset_configs=tuple(replace(dc, master_seed=99) for dc in cfg.dataset_configs))
            with self.assertRaisesRegex(ValueError, "configuration changed"):
                run_experiment(changed)
            rows = read_result_rows(path)
            for row in rows:
                row["schema_version"] = ""
            write_result_rows(rows, path)
            with self.assertRaisesRegex(ValueError, "historical/schema"):
                run_experiment(cfg)

    def test_corrupt_workflow_sidecar_is_recomputed_without_duplicate_rows(self):
        with TemporaryDirectory() as tmp:
            cfg = tiny(Path(tmp))
            path = run_experiment(cfg)
            rows = read_result_rows(path)
            sidecar = path.parent / rows[0]["workflow_artifact"]
            sidecar.write_bytes(b"invalid gzip")
            run_experiment(cfg)
            repaired = read_result_rows(path)
            self.assertEqual(len(rows), len(repaired))
            self.assertTrue(all(row_artifacts_valid(r, path.parent) for r in repaired))

    def test_merge_keeps_portable_sidecars_and_rejects_mixed_protocol(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = run_experiment(tiny(root / "a"), seed_range=(0, 1))
            b = run_experiment(tiny(root / "b"), seed_range=(1, 2))
            merged = merge_runs([a, b], root / "merged/results.csv")
            rows = read_result_rows(merged)
            self.assertEqual(len(rows), 8)
            self.assertTrue(all(row_artifacts_valid(r, merged.parent) for r in rows))
            legacy = read_result_rows(a)
            legacy[0]["randomness_protocol"] = LEGACY_PROTOCOL
            write_result_rows(legacy, root / "legacy.csv")
            with self.assertRaisesRegex(ValueError, "incompatible"):
                merge_runs([b, root / "legacy.csv"], root / "bad/results.csv")
