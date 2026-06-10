import math
import unittest

from experimentation.datasets import SyntheticDatasetConfig, generate_paired_distribution
from experimentation.graph import Graph
from experimentation.workflows import (
    DIVERSITY_CURVES_WORKFLOW,
    NATIVE_NETLSD_WORKFLOW,
    DiversityCurvesWorkflow,
    NetLSDWorkflow,
    WLSubtreeMMDWorkflow,
    dense_mean,
    default_workflows,
    diversity_curve,
    l2,
    rbf_kernel_is_nearly_constant,
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

    def test_identical_graph_sets_have_zero_or_near_zero_distance(self) -> None:
        for workflow in default_workflows():
            with self.subTest(workflow.name):
                result = workflow.run(self.original, self.original)

                self.assertEqual(result["status"], "success")
                self.assertAlmostEqual(result["distribution_score"], 0.0, places=9)
                self.assertAlmostEqual(result["mean_shift_score"], 0.0, places=9)
                self.assertAlmostEqual(result["paired_score"], 0.0, places=9)

    def test_distribution_score_is_symmetric_and_order_invariant(self) -> None:
        for workflow in default_workflows():
            with self.subTest(workflow.name):
                forward = workflow.distribution_score(self.original, self.perturbed)
                reverse = workflow.distribution_score(self.perturbed, self.original)
                shuffled = workflow.distribution_score(list(reversed(self.original)), list(reversed(self.perturbed)))

                self.assertAlmostEqual(forward, reverse, places=9)
                self.assertAlmostEqual(forward, shuffled, places=9)

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

    def test_wl_netlsd_and_diversity_are_isomorphism_invariant(self) -> None:
        graph = Graph(5)
        for edge in ((0, 1), (1, 2), (2, 3), (2, 4)):
            graph.add_edge(*edge)
        relabeled = relabel_graph(graph, {0: 3, 1: 0, 2: 4, 3: 1, 4: 2})

        workflows = (
            WLSubtreeMMDWorkflow(iterations=2),
            NetLSDWorkflow(timescales=(0.1, 1.0, 10.0)),
            DiversityCurvesWorkflow(max_scales=4, repetitions=3),
        )
        for workflow in workflows:
            with self.subTest(workflow.name):
                self.assertAlmostEqual(workflow.paired_score([graph], [relabeled]), 0.0, places=9)

    def test_native_netlsd_distribution_score_is_mean_signature_l2(self) -> None:
        workflow = NetLSDWorkflow(timescales=(0.1, 1.0, 10.0))
        original = workflow.compute_representations(self.original)
        perturbed = workflow.compute_representations(self.perturbed)

        expected = l2(dense_mean(original), dense_mean(perturbed))

        self.assertEqual(workflow.name, NATIVE_NETLSD_WORKFLOW)
        self.assertAlmostEqual(workflow.distribution_score_from_representations(original, perturbed), expected)

    def test_native_netlsd_paired_score_is_mean_pairwise_signature_l2(self) -> None:
        workflow = NetLSDWorkflow(timescales=(0.1, 1.0, 10.0))
        original = workflow.compute_representations(self.original)
        perturbed = workflow.compute_representations(self.perturbed)
        expected = sum(l2(left, right) for left, right in zip(original, perturbed)) / len(original)

        self.assertAlmostEqual(workflow.paired_score(self.original, self.perturbed), expected)

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

    def test_rbf_kernel_nearly_constant_diagnostic_detects_bandwidth_collapse(self) -> None:
        vectors = [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]]

        self.assertTrue(rbf_kernel_is_nearly_constant(vectors, bandwidth=1000.0))
        self.assertFalse(rbf_kernel_is_nearly_constant(vectors, bandwidth=0.1))

    def test_default_diversity_workflow_uses_shortest_path_name(self) -> None:
        self.assertIn(DIVERSITY_CURVES_WORKFLOW, {workflow.name for workflow in default_workflows()})
        self.assertIn(NATIVE_NETLSD_WORKFLOW, {workflow.name for workflow in default_workflows()})


def relabel_graph(graph: Graph, mapping: dict[int, int]) -> Graph:
    relabeled = Graph(graph.num_nodes)
    for u, v in graph.edges():
        relabeled.add_edge(mapping[u], mapping[v])
    return relabeled


if __name__ == "__main__":
    unittest.main()
