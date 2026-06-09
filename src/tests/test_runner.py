import csv
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experimentation.config import DatasetConfig, OutputConfig, PerturbationConfig, WorkflowConfig, debug_config
from experimentation.datasets import SyntheticDatasetConfig
from experimentation.runner import RESULT_COLUMNS, read_result_rows, run_experiment, write_result_rows
from experimentation.workflows import Workflow


class FailingWorkflow(Workflow):
    def __init__(self) -> None:
        super().__init__("failing_workflow")

    def compute_representations(self, graphs):
        return []

    def distribution_score(self, original_graphs, perturbed_graphs):
        raise RuntimeError("intentional failure")


class RecoveredWorkflow(Workflow):
    def __init__(self) -> None:
        super().__init__("failing_workflow")

    def compute_representations(self, graphs):
        return [[float(len(graph.edges()))] for graph in graphs]

    def distribution_score(self, original_graphs, perturbed_graphs):
        return 0.0


class RunnerTests(unittest.TestCase):
    def test_debug_experiment_runs_end_to_end_and_writes_expected_columns(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = tiny_debug_config(Path(tmpdir))

            result_path = run_experiment(config)

            self.assertTrue(result_path.is_file())
            with result_path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, list(RESULT_COLUMNS))
                rows = list(reader)
            self.assertGreater(len(rows), 0)

    def test_failed_workflow_does_not_crash_full_experiment(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = tiny_debug_config(Path(tmpdir))

            result_path = run_experiment(config, workflows=[FailingWorkflow()])
            rows = read_result_rows(result_path)

            self.assertGreater(len(rows), 0)
            self.assertTrue(all(row["status"] == "failed" for row in rows))
            self.assertTrue(all("intentional failure" in row["error_message"] for row in rows))

    def test_resume_skips_existing_result_rows(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = tiny_debug_config(Path(tmpdir))

            result_path = run_experiment(config)
            initial_rows = read_result_rows(result_path)
            resumed_path = run_experiment(config)
            resumed_rows = read_result_rows(resumed_path)

            self.assertEqual(result_path, resumed_path)
            self.assertEqual(len(initial_rows), len(resumed_rows))

    def test_checkpoint_file_records_progress(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = tiny_debug_config(Path(tmpdir))

            run_experiment(config)

            checkpoint_path = Path(tmpdir) / "logs" / "checkpoint.json"
            self.assertTrue(checkpoint_path.is_file())
            self.assertIn('"remaining_rows": 0', checkpoint_path.read_text(encoding="utf-8"))

    def test_rerun_failed_drops_failed_rows_before_resuming(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = tiny_debug_config(Path(tmpdir))

            result_path = run_experiment(config, workflows=[FailingWorkflow()])
            self.assertTrue(all(row["status"] == "failed" for row in read_result_rows(result_path)))

            run_experiment(config, workflows=[RecoveredWorkflow()], rerun_failed=True)
            rows = read_result_rows(result_path)

            self.assertGreater(len(rows), 0)
            self.assertTrue(all(row["status"] == "success" for row in rows))

    def test_resume_rejects_legacy_diversity_results(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = replace(
                tiny_debug_config(Path(tmpdir)),
                workflows=WorkflowConfig(names=("diversity_curves_shortest_path",)),
            )
            result_path = config.outputs.results / "results.csv"
            write_result_rows(
                [
                    {
                        "dataset": "erdos_renyi",
                        "dataset_params": "{}",
                        "perturbation": "edge_addition_deletion",
                        "perturbation_params": "{}",
                        "alpha": 0.0,
                        "seed": 0,
                        "workflow": "diversity_curves_l2",
                        "distribution_score": 0.0,
                        "mean_shift_score": 0.0,
                        "paired_score": 0.0,
                        "runtime_seconds": 0.0,
                        "memory_mb": 0.0,
                        "status": "success",
                        "error_message": "",
                    }
                ],
                result_path,
            )

            with self.assertRaisesRegex(ValueError, "legacy workflow"):
                run_experiment(config)


def tiny_debug_config(root: Path):
    base = debug_config(root)
    output = OutputConfig(root=root, results=root / "results", figures=root / "figures", logs=root / "logs")
    return replace(
        base,
        datasets=DatasetConfig(families=("erdos_renyi",), graphs_per_distribution=2),
        dataset_configs=(
            SyntheticDatasetConfig("erdos_renyi", num_graphs=2, num_nodes=6, edge_probability=0.5, seed=0),
        ),
        perturbations=PerturbationConfig(methods=("edge_addition_deletion",), alpha_values=(0.0, 0.5)),
        workflows=WorkflowConfig(names=("structural_statistics_mmd", "wl_subtree_kernel_mmd")),
        seeds=(0,),
        outputs=output,
    )


if __name__ == "__main__":
    unittest.main()
