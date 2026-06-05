import unittest

from experimentation.datasets import SyntheticDatasetConfig, generate_graph_distribution


class SyntheticDatasetTests(unittest.TestCase):
    def test_generators_return_expected_number_of_non_empty_graphs(self) -> None:
        configs = [
            SyntheticDatasetConfig("erdos_renyi", num_graphs=4, num_nodes=12, edge_probability=0.3, seed=7),
            SyntheticDatasetConfig("stochastic_block_model", num_graphs=4, num_nodes=12, num_blocks=3, p_in=0.7, p_out=0.05, seed=7),
            SyntheticDatasetConfig("barabasi_albert", num_graphs=4, num_nodes=12, m=2, seed=7),
        ]

        for config in configs:
            with self.subTest(config.family):
                graphs = generate_graph_distribution(config)
                self.assertEqual(len(graphs), config.num_graphs)
                self.assertTrue(all(graph.num_nodes == config.num_nodes for graph in graphs))
                self.assertTrue(all(graph.number_of_edges() > 0 for graph in graphs))

    def test_generation_is_reproducible_with_fixed_seed(self) -> None:
        config = SyntheticDatasetConfig("erdos_renyi", num_graphs=3, num_nodes=10, edge_probability=0.4, seed=11)

        first = generate_graph_distribution(config)
        second = generate_graph_distribution(config)

        self.assertEqual([set(graph.edges()) for graph in first], [set(graph.edges()) for graph in second])

    def test_sbm_stores_community_labels(self) -> None:
        config = SyntheticDatasetConfig("stochastic_block_model", num_graphs=2, num_nodes=9, num_blocks=3, seed=3)
        graphs = generate_graph_distribution(config)

        self.assertEqual(len(graphs[0].metadata["community_labels"]), 9)


if __name__ == "__main__":
    unittest.main()
