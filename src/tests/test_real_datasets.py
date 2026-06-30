import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from experimentation.config import OutputConfig, PerturbationConfig, WorkflowConfig, debug_config
from experimentation.datasets import SyntheticDatasetConfig, generate_graph_distribution
from experimentation.real_datasets import load_tu_dataset, tu_dataset_dir
from experimentation.runner import read_result_rows, run_experiment
from experimentation.workflows import median_heuristic_bandwidth

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class TuLoaderTests(unittest.TestCase):
    def test_loads_three_graphs_with_correct_structure(self) -> None:
        graphs = load_tu_dataset(FIXTURES, "TINYTU", family="imdb_binary")

        self.assertEqual(len(graphs), 3)
        triangle, path, single_edge = graphs

        self.assertEqual(triangle.num_nodes, 3)
        self.assertEqual(triangle.number_of_edges(), 3)
        self.assertEqual(triangle.triangle_count(), 1)

        self.assertEqual(path.num_nodes, 3)
        self.assertEqual(path.number_of_edges(), 2)
        self.assertEqual(path.triangle_count(), 0)

        self.assertEqual(single_edge.num_nodes, 2)
        self.assertEqual(single_edge.number_of_edges(), 1)

    def test_graph_labels_and_family_metadata(self) -> None:
        graphs = load_tu_dataset(FIXTURES, "TINYTU", family="imdb_binary")
        self.assertEqual([g.metadata["graph_label"] for g in graphs], [0, 1, 0])
        self.assertTrue(all(g.metadata["family"] == "imdb_binary" for g in graphs))
        # IMDB-BINARY is unlabeled; the fixture has no node labels either.
        self.assertNotIn("node_labels", graphs[0].metadata)

    def test_missing_dataset_raises_with_actionable_message(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(FileNotFoundError, "fetch_imdb_binary"):
                load_tu_dataset(tmp, "IMDB-BINARY")

    def test_tu_dataset_dir_resolves_nested_layout(self) -> None:
        self.assertEqual(tu_dataset_dir(FIXTURES, "TINYTU"), FIXTURES / "TINYTU")


class RealDatasetGridIntegrationTests(unittest.TestCase):
    def test_real_family_flows_through_generate_distribution(self) -> None:
        config = SyntheticDatasetConfig(
            family="imdb_binary", num_graphs=3, data_root=str(FIXTURES), dataset_name="TINYTU", seed=0
        )
        graphs = generate_graph_distribution(config)
        self.assertEqual(len(graphs), 3)

    def test_full_pipeline_runs_on_real_family_with_detected_communities(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = debug_config(root)
            config = replace(
                base,
                dataset_configs=(
                    SyntheticDatasetConfig(
                        family="imdb_binary",
                        num_graphs=3,
                        data_root=str(FIXTURES),
                        dataset_name="TINYTU",
                        seed=0,
                    ),
                ),
                perturbations=PerturbationConfig(
                    methods=("edge_insertion", "community_weakening"), alpha_values=(0.0, 1.0)
                ),
                workflows=WorkflowConfig(names=("structural_statistics_mmd", "native_netlsd")),
                seeds=(0, 1),
                outputs=OutputConfig(
                    root=root,
                    results=root / "results",
                    figures=root / "figures",
                    logs=root / "logs",
                    evaluation=root / "evaluation",
                ),
            )

            result_path = run_experiment(config, workers=1, write_manifest=False)
            rows = read_result_rows(result_path)

            self.assertTrue(rows)
            self.assertTrue(all(r["dataset"] == "imdb_binary" for r in rows))
            # The real family is unlabeled -> community_weakening uses detected labels.
            community_rows = [r for r in rows if r["perturbation"] == "community_weakening"]
            self.assertTrue(community_rows)
            self.assertTrue(all(r["label_source"] == "detected" for r in community_rows))
            # Edit-distance ground truth applies unchanged to the real family.
            edited = [r for r in rows if r["edit_distance_raw"] not in ("", "0.0") and float(r["alpha"]) > 0]
            self.assertTrue(edited)


class AutoBandwidthTests(unittest.TestCase):
    def test_median_heuristic_bandwidth_is_the_pairwise_median(self) -> None:
        # Three collinear points: pairwise distances {1, 2, 3} -> median 2.
        vectors = [[0.0], [1.0], [3.0]]
        self.assertEqual(median_heuristic_bandwidth(vectors), 2.0)

    def test_median_heuristic_bandwidth_degenerate_inputs(self) -> None:
        self.assertEqual(median_heuristic_bandwidth([[1.0]]), 1.0)
        self.assertEqual(median_heuristic_bandwidth([[1.0], [1.0]]), 1.0)


if __name__ == "__main__":
    unittest.main()
