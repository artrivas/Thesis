from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experimentation.config import debug_config, default_config


class ExperimentationBaselineTests(unittest.TestCase):
    def test_default_configuration_loads(self) -> None:
        config = default_config()

        self.assertEqual(config.datasets.graphs_per_distribution, 100)
        self.assertEqual(config.perturbations.alpha_values, tuple(round(i / 10, 1) for i in range(11)))
        self.assertEqual(config.seeds, tuple(range(5)))
        self.assertIn("edge_insertion", config.perturbations.methods)
        self.assertIn("edge_deletion", config.perturbations.methods)
        self.assertIn("triangle_insertion", config.perturbations.methods)
        self.assertIn("triangle_deletion", config.perturbations.methods)
        self.assertIn("erdos_renyi", config.datasets.families)
        self.assertIn("wl_subtree_kernel_mmd", config.workflows.names)
        self.assertIn("diversity_curves_shortest_path", config.workflows.names)

    def test_output_directories_can_be_created(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = debug_config(Path(tmpdir) / "outputs")
            config.outputs.create_directories()

            self.assertTrue(config.outputs.root.is_dir())
            self.assertTrue(config.outputs.results.is_dir())
            self.assertTrue(config.outputs.figures.is_dir())
            self.assertTrue(config.outputs.logs.is_dir())

    def test_documentation_files_exist(self) -> None:
        docs = Path("docs/experimentation")

        self.assertTrue((docs / "theory.md").is_file())
        self.assertTrue((docs / "implementation_log.md").is_file())
        self.assertTrue((docs / "experimental_protocol.md").is_file())
        self.assertTrue((docs / "results_schema.md").is_file())


if __name__ == "__main__":
    unittest.main()
