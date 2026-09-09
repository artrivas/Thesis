import math
import unittest

from experimentation.datasets import SyntheticDatasetConfig, generate_paired_distribution
from experimentation.graph import Graph
from experimentation.workflows import (
    DIVERSITY_CURVES_WORKFLOW,
    NETLSD_TIME_SCALE_COUNT,
    NATIVE_NETLSD_WORKFLOW,
    DiversityCurvesWorkflow,
    NetLSDWorkflow,
    WLSubtreeMMDWorkflow,
    all_pairs_shortest_path_distances,
    dense_mean,
    default_workflows,
    diversity_curve,
    diversity_curve_representations,
    l2,
    netlsd_signature,
    normalized_laplacian_eigenvalues,
    rbf_kernel_is_nearly_constant,
    shortest_path_spread,
    squared_l2,
    wl_feature_matrix,
    wl_features,
    wl_subtree_kernel_matrix,
)


class WorkflowTests(unittest.TestCase):
    def assertSequenceAlmostEqual(self, left: list[float], right: list[float], places: int = 9) -> None:
        self.assertEqual(len(left), len(right))
        for actual, expected in zip(left, right):
            self.assertAlmostEqual(actual, expected, places=places)

    def setUp(self) -> None:
        paired = generate_paired_distribution(
            SyntheticDatasetConfig("erdos_renyi", num_graphs=3, num_nodes=8, edge_probability=0.45, seed=21),
            perturbation_type="edge_insertion",
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

        edge_features, path_features = wl_feature_matrix([edge_with_isolate, path], iterations=1)
        iteration_overlap = {
            key
            for key in edge_features
            if key in path_features and key.startswith("h1:")
        }

        self.assertEqual(iteration_overlap, set())

    def test_wl_features_match_manual_path_counts(self) -> None:
        path = Graph(3)
        path.add_edge(0, 1)
        path.add_edge(1, 2)

        features = wl_features(path, iterations=1)

        self.assertEqual(features["h0:degree:1"], 2)
        self.assertEqual(features["h0:degree:2"], 1)
        self.assertEqual(features["h1:c1:0"], 2)
        self.assertEqual(features["h1:c1:1"], 1)

    def test_wl_uses_node_labels_when_present(self) -> None:
        left = Graph(2, metadata={"node_labels": ("a", "b")})
        left.add_edge(0, 1)
        right = Graph(2, metadata={"node_labels": ("a", "a")})
        right.add_edge(0, 1)

        left_features, right_features = wl_feature_matrix([left, right], iterations=1)

        self.assertNotEqual(left_features, right_features)
        self.assertIn("h0:label:a", left_features)
        self.assertIn("h0:label:b", left_features)

    def test_wl_kernel_matrix_is_symmetric(self) -> None:
        edge = Graph(2)
        edge.add_edge(0, 1)
        path = Graph(3)
        path.add_edge(0, 1)
        path.add_edge(1, 2)

        features = wl_feature_matrix([edge, path], iterations=2)
        kernel = wl_subtree_kernel_matrix(features)

        self.assertEqual(len(kernel), 2)
        self.assertAlmostEqual(kernel[0][1], kernel[1][0])
        self.assertGreater(kernel[0][0], 0.0)

    def test_wl_netlsd_and_diversity_are_isomorphism_invariant(self) -> None:
        graph = Graph(5)
        for edge in ((0, 1), (1, 2), (2, 3), (2, 4)):
            graph.add_edge(*edge)
        relabeled = relabel_graph(graph, {0: 3, 1: 0, 2: 4, 3: 1, 4: 2})

        workflows = (
            WLSubtreeMMDWorkflow(iterations=2),
            NetLSDWorkflow(timescales=(0.1, 1.0, 10.0), normalization="none"),
            DiversityCurvesWorkflow(max_scales=4, repetitions=3),
        )
        for workflow in workflows:
            with self.subTest(workflow.name):
                self.assertAlmostEqual(workflow.paired_score([graph], [relabeled]), 0.0, places=9)

    def test_native_netlsd_distribution_score_is_mean_signature_l2(self) -> None:
        workflow = NetLSDWorkflow(timescales=(0.1, 1.0, 10.0), normalization="none")
        original = workflow.compute_representations(self.original)
        perturbed = workflow.compute_representations(self.perturbed)

        expected = l2(dense_mean(original), dense_mean(perturbed))

        self.assertEqual(workflow.name, NATIVE_NETLSD_WORKFLOW)
        self.assertAlmostEqual(workflow.distribution_score_from_representations(original, perturbed), expected)

    def test_native_netlsd_paired_score_is_mean_pairwise_signature_l2(self) -> None:
        workflow = NetLSDWorkflow(timescales=(0.1, 1.0, 10.0), normalization="none")
        original = workflow.compute_representations(self.original)
        perturbed = workflow.compute_representations(self.perturbed)
        expected = sum(l2(left, right) for left, right in zip(original, perturbed)) / len(original)

        self.assertAlmostEqual(workflow.paired_score(self.original, self.perturbed), expected)

    def test_netlsd_normalized_laplacian_known_eigenvalues(self) -> None:
        edge = Graph(2)
        edge.add_edge(0, 1)
        path = Graph(3)
        path.add_edge(0, 1)
        path.add_edge(1, 2)
        isolates = Graph(2)

        self.assertSequenceAlmostEqual(normalized_laplacian_eigenvalues(edge), [0.0, 2.0])
        self.assertSequenceAlmostEqual(normalized_laplacian_eigenvalues(path), [0.0, 1.0, 2.0])
        self.assertSequenceAlmostEqual(normalized_laplacian_eigenvalues(isolates), [0.0, 0.0])

    def test_netlsd_heat_trace_matches_manual_eigen_sum(self) -> None:
        edge = Graph(2)
        edge.add_edge(0, 1)
        signature = netlsd_signature(edge, timescales=(0.0, 1.0), normalization="none")

        self.assertSequenceAlmostEqual(signature, [2.0, 1.0 + math.exp(-2.0)])
        self.assertGreater(signature[0], signature[1])

    def test_netlsd_default_uses_paper_time_scale_count(self) -> None:
        workflow = NetLSDWorkflow()

        self.assertEqual(len(workflow.timescales), NETLSD_TIME_SCALE_COUNT)
        self.assertAlmostEqual(min(workflow.timescales), 1e-2)
        self.assertAlmostEqual(max(workflow.timescales), 1e2)
        self.assertEqual(workflow.normalization, "empty")

    def test_netlsd_empty_normalization_is_size_neutral_for_empty_graphs(self) -> None:
        small = Graph(2)
        large = Graph(5)

        small_signature = netlsd_signature(small, timescales=(0.1, 1.0, 10.0), normalization="empty")
        large_signature = netlsd_signature(large, timescales=(0.1, 1.0, 10.0), normalization="empty")

        self.assertSequenceAlmostEqual(small_signature, [1.0, 1.0, 1.0])
        self.assertSequenceAlmostEqual(large_signature, [1.0, 1.0, 1.0])

    def test_netlsd_is_finite_and_deterministic_with_isolated_nodes(self) -> None:
        graph = Graph(4)
        graph.add_edge(0, 1)

        first = netlsd_signature(graph, timescales=(0.01, 0.1, 1.0, 10.0))
        second = netlsd_signature(graph, timescales=(0.01, 0.1, 1.0, 10.0))

        self.assertEqual(first, second)
        self.assertTrue(all(math.isfinite(value) for value in first))

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

    def test_shortest_path_spread_matches_manual_values(self) -> None:
        edge = Graph(2)
        edge.add_edge(0, 1)
        path = Graph(3)
        path.add_edge(0, 1)
        path.add_edge(1, 2)

        expected_edge = 2.0 / (1.0 + math.exp(-1.0))
        expected_path = (
            2.0 / (1.0 + math.exp(-1.0) + math.exp(-2.0))
            + 1.0 / (1.0 + 2.0 * math.exp(-1.0))
        )

        self.assertAlmostEqual(shortest_path_spread(edge), expected_edge)
        self.assertAlmostEqual(shortest_path_spread(path), expected_path)

    def test_shortest_path_distances_mark_disconnected_nodes_as_infinite(self) -> None:
        graph = Graph(3)
        graph.add_edge(0, 1)

        distances = all_pairs_shortest_path_distances(graph)

        self.assertEqual(distances[0][1], 1.0)
        self.assertTrue(math.isinf(distances[0][2]))
        self.assertEqual(distances[2][2], 0.0)

    def test_diversity_curve_is_deterministic_across_repeated_calls(self) -> None:
        graph = Graph(5)
        for edge in ((0, 1), (1, 2), (2, 3), (3, 4), (0, 4)):
            graph.add_edge(*edge)

        first = diversity_curve(graph, max_scales=5, repetitions=3)
        second = diversity_curve(graph, max_scales=5, repetitions=3)

        self.assertEqual(first, second)

    def test_diversity_workflow_uses_dataset_level_all_integer_scales(self) -> None:
        edge = Graph(2)
        edge.add_edge(0, 1)
        path = Graph(4)
        for edge_tuple in ((0, 1), (1, 2), (2, 3)):
            path.add_edge(*edge_tuple)

        workflow = DiversityCurvesWorkflow(repetitions=1, random_seed=7)
        representations = workflow.compute_representations([edge, path])

        self.assertEqual(len(representations), 2)
        self.assertEqual(len(representations[0]), 4)
        self.assertEqual(len(representations[1]), 4)
        self.assertTrue(all(math.isfinite(value) for vector in representations for value in vector))

    def test_diversity_representations_upsample_smaller_graphs(self) -> None:
        edge = Graph(2)
        edge.add_edge(0, 1)
        path = Graph(3)
        path.add_edge(0, 1)
        path.add_edge(1, 2)

        representations = diversity_curve_representations([edge, path], repetitions=1, random_seed=5)

        self.assertEqual(len(representations[0]), 3)
        self.assertGreater(representations[0][-1], 0.0)

    def test_dense_vector_length_mismatches_raise(self) -> None:
        with self.assertRaises(ValueError):
            squared_l2([1.0, 2.0], [1.0])
        with self.assertRaises(ValueError):
            l2([1.0], [1.0, 2.0])
        with self.assertRaises(ValueError):
            dense_mean([[1.0, 2.0], [3.0]])

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
