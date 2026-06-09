import math
import unittest

from experimentation.datasets import SyntheticDatasetConfig, generate_paired_distribution
from experimentation.graph import Graph
from experimentation.workflows import (
    default_workflows,
    diversity_curve,
    shortest_path_spread,
    wl_features,
)


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

    def test_wl_iteration_labels_are_canonical_across_graphs(self) -> None:
        edge_with_isolate = Graph(3)
        edge_with_isolate.add_edge(0, 1)
        path = Graph(3)
        path.add_edge(0, 1)
        path.add_edge(1, 2)

        edge_features = wl_features(edge_with_isolate, iterations=1)
        path_features = wl_features(path, iterations=1)
        iteration_overlap = {
            key
            for key in edge_features
            if key in path_features and key.startswith("i0:")
        }

        self.assertEqual(iteration_overlap, set())

    def test_diversity_curve_uses_shortest_path_spread(self) -> None:
        path = Graph(3)
        path.add_edge(0, 1)
        path.add_edge(1, 2)

        curve = diversity_curve(path, max_scales=3, repetitions=1)

        self.assertAlmostEqual(curve[0], 1.0)
        self.assertAlmostEqual(curve[-1], shortest_path_spread(path))

    def test_disconnected_diversity_curve_interpolates_unreachable_scales(self) -> None:
        graph = Graph(3)

        curve = diversity_curve(graph, max_scales=3, repetitions=1)

        self.assertEqual(curve, [1.0, 2.0, 3.0])

    def test_default_diversity_workflow_uses_shortest_path_name(self) -> None:
        self.assertIn("diversity_curves_shortest_path", {workflow.name for workflow in default_workflows()})


if __name__ == "__main__":
    unittest.main()
