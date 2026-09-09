import unittest

from experimentation.datasets import SyntheticDatasetConfig, generate_graph_distribution
from experimentation.graph import Graph
from experimentation.perturbations import detect_communities, perturb_graph


class PerturbationTests(unittest.TestCase):
    def test_alpha_zero_returns_structurally_equivalent_separate_graph(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("erdos_renyi", num_graphs=1, num_nodes=12, edge_probability=0.4, seed=5)
        )[0]

        result = perturb_graph(graph, 0.0, "edge_addition_deletion", seed=1)

        self.assertIsNot(result.graph, graph)
        self.assertTrue(result.graph.structurally_equal(graph))

    def test_edge_perturbation_changes_edge_set_with_expected_budget(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("erdos_renyi", num_graphs=1, num_nodes=14, edge_probability=0.5, seed=2)
        )[0]
        expected_budget = int(0.4 * graph.number_of_edges())

        result = perturb_graph(graph, 0.4, "edge_addition_deletion", seed=9)
        changed = len(set(graph.edges()).symmetric_difference(set(result.graph.edges())))

        self.assertGreaterEqual(changed, expected_budget)
        self.assertEqual(result.metadata["edges_added"] + result.metadata["edges_removed"], expected_budget)
        self.assertFalse(result.graph.structurally_equal(graph))

    def test_edge_insertion_and_deletion_are_separate_operations(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("erdos_renyi", num_graphs=1, num_nodes=14, edge_probability=0.5, seed=2)
        )[0]

        insertion = perturb_graph(graph, 0.4, "edge_insertion", seed=9)
        deletion = perturb_graph(graph, 0.4, "edge_deletion", seed=9)

        self.assertEqual(insertion.metadata["perturbation_family"], "edge")
        self.assertEqual(insertion.metadata["perturbation_direction"], "insertion")
        self.assertGreater(insertion.metadata["edges_added"], 0)
        self.assertEqual(insertion.metadata["edges_removed"], 0)
        self.assertEqual(deletion.metadata["perturbation_family"], "edge")
        self.assertEqual(deletion.metadata["perturbation_direction"], "deletion")
        self.assertGreater(deletion.metadata["edges_removed"], 0)
        self.assertEqual(deletion.metadata["edges_added"], 0)

    def test_triangle_insertion_and_deletion_are_separate_operations(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("stochastic_block_model", num_graphs=1, num_nodes=12, num_blocks=2, p_in=0.9, p_out=0.0, seed=3)
        )[0]

        insertion = perturb_graph(graph, 0.5, "triangle_insertion", seed=4)
        deletion = perturb_graph(graph, 0.5, "triangle_deletion", seed=4)

        self.assertEqual(insertion.metadata["perturbation_family"], "triangle")
        self.assertEqual(insertion.metadata["perturbation_direction"], "insertion")
        self.assertEqual(insertion.metadata["edges_removed"], 0)
        self.assertEqual(deletion.metadata["perturbation_family"], "triangle")
        self.assertEqual(deletion.metadata["perturbation_direction"], "deletion")
        self.assertEqual(deletion.metadata["edges_added"], 0)

    def test_community_weakening_uses_sbm_metadata(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("stochastic_block_model", num_graphs=1, num_nodes=18, num_blocks=3, p_in=0.9, p_out=0.0, seed=4)
        )[0]

        result = perturb_graph(graph, 0.5, "community_weakening", seed=8, metadata=graph.metadata)

        self.assertEqual(result.metadata["status"], "success")
        self.assertEqual(result.metadata["label_source"], "ground_truth")
        self.assertGreater(result.metadata["rewires"], 0)
        self.assertEqual(graph.number_of_edges(), result.graph.number_of_edges())

    def test_community_weakening_detects_communities_without_metadata(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("erdos_renyi", num_graphs=1, num_nodes=20, edge_probability=0.3, seed=6)
        )[0]

        result = perturb_graph(graph, 0.5, "community_weakening", seed=8)

        # No longer skipped: communities are detected and the row is tagged.
        self.assertNotEqual(result.metadata["status"], "skipped")
        self.assertEqual(result.metadata["label_source"], "detected")
        self.assertIn("num_communities", result.metadata)

    def test_community_weakening_detected_on_barabasi_albert(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("barabasi_albert", num_graphs=1, num_nodes=30, m=2, seed=7)
        )[0]

        result = perturb_graph(graph, 0.6, "community_weakening", seed=3)

        self.assertNotEqual(result.metadata["status"], "skipped")
        self.assertEqual(result.metadata["label_source"], "detected")

    def test_detect_communities_recovers_planted_partition(self) -> None:
        # Two 6-cliques joined by a single bridge edge.
        graph = Graph(12)
        for block_start in (0, 6):
            members = range(block_start, block_start + 6)
            for u in members:
                for v in members:
                    if u < v:
                        graph.add_edge(u, v)
        graph.add_edge(5, 6)  # bridge

        labels = detect_communities(graph)

        self.assertEqual(len(labels), 12)
        self.assertEqual(len(set(labels)), 2)
        self.assertEqual(len(set(labels[0:6])), 1)
        self.assertEqual(len(set(labels[6:12])), 1)
        self.assertNotEqual(labels[0], labels[6])

    def test_detect_communities_handles_edgeless_graph(self) -> None:
        graph = Graph(5)
        labels = detect_communities(graph)
        self.assertEqual(len(labels), 5)

    def test_hub_modification_targets_high_degree_nodes(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("barabasi_albert", num_graphs=1, num_nodes=25, m=2, seed=10)
        )[0]
        degrees = graph.degrees()
        highest_degree_node = max(range(graph.num_nodes), key=lambda node: degrees[node])

        result = perturb_graph(graph, 0.4, "hub_modification", seed=12)

        self.assertIn(highest_degree_node, result.metadata["target_hubs"])
        self.assertGreater(result.metadata["edges_removed"], 0)

    def test_hub_modification_metadata_matches_actual_edge_changes(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("barabasi_albert", num_graphs=1, num_nodes=25, m=2, seed=10)
        )[0]

        result = perturb_graph(graph, 0.8, "hub_modification", seed=12)
        changed = len(set(graph.edges()).symmetric_difference(set(result.graph.edges())))

        self.assertEqual(changed, result.metadata["edges_added"] + result.metadata["edges_removed"])


if __name__ == "__main__":
    unittest.main()
