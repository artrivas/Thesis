import unittest

from experimentation.datasets import SyntheticDatasetConfig, generate_graph_distribution
from experimentation.perturbations import perturb_graph


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

    def test_community_weakening_uses_sbm_metadata(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("stochastic_block_model", num_graphs=1, num_nodes=18, num_blocks=3, p_in=0.9, p_out=0.0, seed=4)
        )[0]

        result = perturb_graph(graph, 0.5, "community_weakening", seed=8, metadata=graph.metadata)

        self.assertEqual(result.metadata["status"], "success")
        self.assertGreater(result.metadata["rewires"], 0)
        self.assertEqual(graph.number_of_edges(), result.graph.number_of_edges())

    def test_community_weakening_skips_without_metadata(self) -> None:
        graph = generate_graph_distribution(
            SyntheticDatasetConfig("erdos_renyi", num_graphs=1, num_nodes=10, edge_probability=0.4, seed=6)
        )[0]

        result = perturb_graph(graph, 0.5, "community_weakening", seed=8)

        self.assertEqual(result.metadata["status"], "skipped")
        self.assertTrue(result.graph.structurally_equal(graph))

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
