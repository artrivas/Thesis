import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from experimentation.config import (
    DatasetConfig,
    PerturbationConfig,
    WorkflowConfig,
    build_run_output_config,
    config_hash,
    debug_config,
    output_config_for_root,
)
from experimentation.datasets import SyntheticDatasetConfig
from experimentation.evaluation import generate_evaluation_summary
from experimentation.runner import (
    _resolve_seeds,
    _row_key,
    merge_runs,
    read_result_rows,
    run_experiment,
    write_result_rows,
)

SCORE_COLUMNS = ("distribution_score", "mean_shift_score", "paired_score")


def multi_seed_config(root: Path, seeds=(0, 1, 2, 3)):
    """A tiny multi-seed, multi-cell config that still varies across seeds."""

    base = debug_config(root)
    return replace(
        base,
        datasets=DatasetConfig(families=("erdos_renyi", "stochastic_block_model"), graphs_per_distribution=4),
        dataset_configs=(
            SyntheticDatasetConfig("erdos_renyi", num_graphs=4, num_nodes=8, edge_probability=0.45, seed=0),
            SyntheticDatasetConfig(
                "stochastic_block_model", num_graphs=4, num_nodes=8, num_blocks=2, p_in=0.8, p_out=0.05, seed=0
            ),
        ),
        perturbations=PerturbationConfig(methods=("edge_insertion", "edge_deletion"), alpha_values=(0.0, 0.5, 1.0)),
        workflows=WorkflowConfig(names=("structural_statistics_mmd", "wl_subtree_kernel_mmd")),
        seeds=seeds,
        outputs=output_config_for_root(root),
    )


def score_map(path: Path) -> dict:
    result = {}
    for row in read_result_rows(path):
        result[_row_key(row)] = tuple(row.get(column) for column in SCORE_COLUMNS)
    return result


class SeedResolutionTests(unittest.TestCase):
    def test_seed_range_is_half_open_index_slice(self) -> None:
        seeds = (10, 11, 12, 13, 14)
        self.assertEqual(_resolve_seeds(seeds, None), seeds)
        self.assertEqual(_resolve_seeds(seeds, (0, 2)), (10, 11))
        self.assertEqual(_resolve_seeds(seeds, (2, 5)), (12, 13, 14))

    def test_invalid_seed_range_raises(self) -> None:
        with self.assertRaises(ValueError):
            _resolve_seeds((0, 1, 2), (2, 1))


class ParallelDeterminismTests(unittest.TestCase):
    def test_parallel_matches_serial_scores(self) -> None:
        with TemporaryDirectory() as tmp:
            serial_root = Path(tmp) / "serial"
            parallel_root = Path(tmp) / "parallel"
            serial = run_experiment(multi_seed_config(serial_root), workers=1)
            parallel = run_experiment(multi_seed_config(parallel_root), workers=3)

            serial_scores = score_map(serial)
            parallel_scores = score_map(parallel)
            self.assertEqual(set(serial_scores), set(parallel_scores))
            self.assertEqual(serial_scores, parallel_scores)
            # No duplicated row keys.
            self.assertEqual(len(read_result_rows(parallel)), len(parallel_scores))


class ResumeAfterKillTests(unittest.TestCase):
    def test_resume_completes_partial_csv_without_duplication(self) -> None:
        with TemporaryDirectory() as tmp:
            reference_root = Path(tmp) / "reference"
            reference = run_experiment(multi_seed_config(reference_root), workers=1)
            reference_rows = read_result_rows(reference)

            crashed_root = Path(tmp) / "crashed"
            config = multi_seed_config(crashed_root)
            config.outputs.create_directories()
            # Simulate a crash: only the first third of the rows made it to disk.
            partial = reference_rows[: len(reference_rows) // 3]
            write_result_rows(partial, config.outputs.results / "results.csv")

            resumed = run_experiment(config, workers=2)
            resumed_rows = read_result_rows(resumed)

            self.assertEqual(len(resumed_rows), len(reference_rows))
            self.assertEqual(score_map(resumed), score_map(reference))
            # Keys are unique -> no recomputation duplicated a completed cell.
            keys = [_row_key(row) for row in resumed_rows]
            self.assertEqual(len(keys), len(set(keys)))


class FailedCellTests(unittest.TestCase):
    def test_worker_failure_records_failed_rows_without_killing_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "failed"
            config = replace(
                multi_seed_config(root, seeds=(0,)),
                perturbations=PerturbationConfig(
                    methods=("edge_insertion", "definitely_not_a_perturbation"),
                    alpha_values=(0.5,),
                ),
            )

            result_path = run_experiment(config, workers=2)
            rows = read_result_rows(result_path)

            by_perturbation = {}
            for row in rows:
                by_perturbation.setdefault(row["perturbation"], []).append(row)

            self.assertIn("edge_insertion", by_perturbation)
            self.assertIn("definitely_not_a_perturbation", by_perturbation)
            self.assertTrue(all(r["status"] == "success" for r in by_perturbation["edge_insertion"]))
            failed = by_perturbation["definitely_not_a_perturbation"]
            self.assertTrue(all(r["status"] == "failed" for r in failed))
            self.assertTrue(all("cell_execution_failed" in r["error_message"] for r in failed))

    def test_rerun_failed_repicks_failed_cells_on_resume(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "rerun"
            config = replace(
                multi_seed_config(root, seeds=(0,)),
                perturbations=PerturbationConfig(
                    methods=("edge_insertion", "definitely_not_a_perturbation"),
                    alpha_values=(0.5,),
                ),
            )
            run_experiment(config, workers=2)
            # Resume with rerun-failed: failed rows are dropped and recomputed,
            # never duplicated.
            result_path = run_experiment(config, workers=2, rerun_failed=True)
            rows = read_result_rows(result_path)
            keys = [_row_key(row) for row in rows]
            self.assertEqual(len(keys), len(set(keys)))


class SeedShardingTests(unittest.TestCase):
    def test_disjoint_shards_merge_equals_unsharded(self) -> None:
        with TemporaryDirectory() as tmp:
            seeds = (0, 1, 2, 3)
            unsharded = run_experiment(multi_seed_config(Path(tmp) / "whole", seeds), workers=2)

            shard_a = run_experiment(
                multi_seed_config(Path(tmp) / "shard_a", seeds), workers=2, seed_range=(0, 2)
            )
            shard_b = run_experiment(
                multi_seed_config(Path(tmp) / "shard_b", seeds), workers=2, seed_range=(2, 4)
            )

            merged_dir = Path(tmp) / "merged"
            merged_dir.mkdir()
            merged = merge_runs([shard_a, shard_b], merged_dir / "results.csv")

            self.assertEqual(score_map(merged), score_map(unsharded))
            merged_keys = [_row_key(row) for row in read_result_rows(merged)]
            self.assertEqual(len(merged_keys), len(set(merged_keys)))
            self.assertEqual(len(merged_keys), len(read_result_rows(unsharded)))

    def test_shard_run_directories_are_isolated(self) -> None:
        config = multi_seed_config(Path("unused"), seeds=(0, 1, 2, 3))
        run_id_a, outputs_a = build_run_output_config("results/runs", config, run_id="fixed", seed_range=(0, 2))
        run_id_b, outputs_b = build_run_output_config("results/runs", config, run_id="fixed", seed_range=(2, 4))
        self.assertEqual(run_id_a, "fixed")
        self.assertEqual(run_id_b, "fixed")
        self.assertNotEqual(outputs_a.root, outputs_b.root)
        self.assertTrue(str(outputs_a.root).endswith("fixed_shard-0-2"))
        self.assertTrue(str(outputs_b.root).endswith("fixed_shard-2-4"))


class NonDegenerateReplicationTests(unittest.TestCase):
    def test_multi_seed_run_yields_nonzero_cv(self) -> None:
        # The CV=0 / tau=1 degeneracy was a single-seed artifact. With several
        # distinct seeds the per-seed means genuinely vary, so robustness CV
        # must be strictly positive for at least one cell.
        with TemporaryDirectory() as tmp:
            result_path = run_experiment(
                multi_seed_config(Path(tmp) / "rep", seeds=(0, 1, 2, 3, 4)), workers=2
            )
            summary = generate_evaluation_summary(read_result_rows(result_path))
            cvs = [float(row["robustness_cv"]) for row in summary]
            self.assertTrue(any(cv > 0.0 for cv in cvs), "multi-seed run produced degenerate CV=0 everywhere")


class ConfigHashTests(unittest.TestCase):
    def test_config_hash_is_seed_normalized_and_stable(self) -> None:
        a = multi_seed_config(Path("a"), seeds=(0, 1, 2, 3))
        b = multi_seed_config(Path("b"), seeds=(0, 1, 2, 3))
        self.assertEqual(config_hash(a), config_hash(b))

    def test_config_hash_changes_with_seed_list(self) -> None:
        a = multi_seed_config(Path("a"), seeds=(0, 1, 2, 3))
        b = multi_seed_config(Path("a"), seeds=(0, 1))
        self.assertNotEqual(config_hash(a), config_hash(b))


if __name__ == "__main__":
    unittest.main()
