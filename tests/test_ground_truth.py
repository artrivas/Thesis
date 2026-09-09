import unittest

from experimentation.datasets import SyntheticDatasetConfig, generate_paired_distribution
from experimentation.graph import Graph
from experimentation.ground_truth import (
    betweenness_product_weight,
    cell_edit_distances,
    edge_betweenness,
    edited_edge_ops,
    pair_edit_distances,
)
from experimentation.perturbations import perturb_graph


def path_graph(n: int) -> Graph:
    graph = Graph(n)
    for u in range(n - 1):
        graph.add_edge(u, u + 1)
    return graph


def barbell_graph() -> Graph:
    """Two 4-cliques joined by a single bridge edge (3, 4)."""

    graph = Graph(8)
    for block_start in (0, 4):
        members = range(block_start, block_start + 4)
        for u in members:
            for v in members:
                if u < v:
                    graph.add_edge(u, v)
    graph.add_edge(3, 4)
    return graph


class EditedEdgeOpsTests(unittest.TestCase):
    def test_symmetric_difference_counts_added_and_removed(self) -> None:
        original = path_graph(4)  # edges (0,1),(1,2),(2,3)
        perturbed = original.copy()
        perturbed.remove_edge(1, 2)
        perturbed.add_edge(0, 3)

        ops = edited_edge_ops(original, perturbed)

        self.assertIn(("remove", 1, 2), ops)
        self.assertIn(("add", 0, 3), ops)
        self.assertEqual(len(ops), 2)

    def test_add_then_remove_cancels(self) -> None:
        original = path_graph(4)
        perturbed = original.copy()  # identical
        self.assertEqual(edited_edge_ops(original, perturbed), [])


class RawEditDistanceTests(unittest.TestCase):
    def test_raw_distance_equals_known_edge_deletion_count(self) -> None:
        graph = path_graph(5)  # 4 edges
        result = perturb_graph(graph, 1.0, "edge_deletion", seed=0)

        edited = result.metadata["edited_edges"]
        raw, _weighted = pair_edit_distances(graph, edited)

        self.assertEqual(result.metadata["edges_removed"], 4)
        self.assertEqual(raw, 4)
        self.assertEqual(raw, len(edited))

    def test_raw_distance_matches_metadata_for_edge_insertion(self) -> None:
        graph = path_graph(6)
        result = perturb_graph(graph, 0.5, "edge_insertion", seed=1)
        raw, _weighted = pair_edit_distances(graph, result.metadata["edited_edges"])
        self.assertEqual(raw, result.metadata["edges_added"])


class ImportanceWeightingTests(unittest.TestCase):
    def test_hub_edge_outweighs_leaf_edge_when_removed(self) -> None:
        graph = barbell_graph()

        raw_hub, weighted_hub = pair_edit_distances(graph, [("remove", 3, 4)])
        raw_leaf, weighted_leaf = pair_edit_distances(graph, [("remove", 0, 1)])

        # Raw distance cannot tell the two edits apart.
        self.assertEqual(raw_hub, raw_leaf)
        # Importance weighting ranks the central bridge edit above the peripheral one.
        self.assertGreater(weighted_hub, weighted_leaf)

    def test_edge_betweenness_peaks_on_the_bridge(self) -> None:
        graph = barbell_graph()
        betweenness = edge_betweenness(graph)
        bridge = max(betweenness, key=betweenness.get)
        self.assertEqual(bridge, (3, 4))

    def test_weight_factory_runs_once_and_is_pluggable(self) -> None:
        graph = barbell_graph()
        weight = betweenness_product_weight(graph)
        self.assertGreater(weight((3, 4)), weight((0, 1)))


class CellEditDistanceTests(unittest.TestCase):
    def test_cell_edit_distance_zero_at_alpha_zero(self) -> None:
        config = SyntheticDatasetConfig("erdos_renyi", num_graphs=4, num_nodes=10, edge_probability=0.4, seed=0)
        paired = generate_paired_distribution(config, "edge_deletion", 0.0, seed=0)
        raw, weighted = cell_edit_distances(paired)
        self.assertEqual(raw, 0.0)
        self.assertEqual(weighted, 0.0)

    def test_cell_edit_distance_positive_and_increases_with_alpha(self) -> None:
        config = SyntheticDatasetConfig("erdos_renyi", num_graphs=5, num_nodes=12, edge_probability=0.4, seed=0)
        low_raw, low_weighted = cell_edit_distances(
            generate_paired_distribution(config, "edge_deletion", 0.2, seed=0)
        )
        high_raw, high_weighted = cell_edit_distances(
            generate_paired_distribution(config, "edge_deletion", 0.8, seed=0)
        )
        self.assertGreater(high_raw, low_raw)
        self.assertGreater(high_weighted, low_weighted)


if __name__ == "__main__":
    unittest.main()
