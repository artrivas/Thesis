import math
import unittest

from experimentation.datasets import SyntheticDatasetConfig, generate_paired_distribution
from experimentation.workflows import default_workflows


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        paired = generate_paired_distribution(
            SyntheticDatasetConfig("erdos_renyi", num_graphs=3, num_nodes=8, edge_probability=0.45, seed=21),
            perturbation_type="edge_addition_deletion",
            alpha=0.5,
            seed=31,
        )
        self.original = paired.original_graphs
        self.perturbed = paired.perturbed_graphs

    def test_each_workflow_runs_and_returns_numeric_scores(self) -> None:
        for workflow in default_workflows():
            with self.subTest(workflow.name):
                result = workflow.run(self.original, self.perturbed)

                self.assertEqual(result["status"], "success")
                self.assertTrue(math.isfinite(result["distribution_score"]))
                self.assertTrue(math.isfinite(result["mean_shift_score"]))
                self.assertTrue(math.isfinite(result["paired_score"]))
                self.assertGreaterEqual(result["runtime_seconds"], 0.0)

    def test_paired_score_uses_pairs(self) -> None:
        for workflow in default_workflows():
            with self.subTest(workflow.name):
                same_score = workflow.paired_score(self.original, self.original)
                perturbed_score = workflow.paired_score(self.original, self.perturbed)

                self.assertEqual(same_score, 0.0)
                self.assertGreaterEqual(perturbed_score, 0.0)

    def test_distribution_and_mean_shift_scores_run_without_errors(self) -> None:
        for workflow in default_workflows():
            with self.subTest(workflow.name):
                self.assertTrue(math.isfinite(workflow.distribution_score(self.original, self.perturbed)))
                self.assertTrue(math.isfinite(workflow.mean_shift_score(self.original, self.perturbed)))


if __name__ == "__main__":
    unittest.main()
