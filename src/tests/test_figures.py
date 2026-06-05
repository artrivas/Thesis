from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experimentation.config import DatasetConfig, OutputConfig, PerturbationConfig, WorkflowConfig, debug_config
from experimentation.datasets import SyntheticDatasetConfig
from experimentation.figures import FIGURE_FILES, generate_figures
from experimentation.runner import run_experiment, write_result_rows
from tests.test_evaluation import fake_result_rows


class FigureTests(unittest.TestCase):
    def test_plot_functions_run_on_small_fake_result_table(self) -> None:
        with TemporaryDirectory() as tmpdir:
            results_path = Path(tmpdir) / "results.csv"
            figure_dir = Path(tmpdir) / "figures"
            write_result_rows(fake_result_rows(), results_path)

            outputs = generate_figures(results_path, figure_dir)

            self.assertEqual(set(outputs), set(FIGURE_FILES))
            self.assertTrue(all(path.is_file() for path in outputs.values()))
            self.assertTrue(all(path.read_text(encoding="utf-8").startswith("<svg") for path in outputs.values()))

    def test_final_documentation_file_exists(self) -> None:
        self.assertTrue(Path("docs/experimentation/final_experimentation_plan.md").is_file())

    def test_debug_pipeline_produces_at_least_one_figure(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result_path = run_experiment(tiny_figure_config(root))

            outputs = generate_figures(result_path, root / "figures")

            self.assertTrue(outputs["score_vs_alpha"].is_file())

    def test_cli_commands_are_documented(self) -> None:
        text = Path("docs/experimentation/final_experimentation_plan.md").read_text(encoding="utf-8")
        self.assertIn("run_debug_experiment", text)
        self.assertIn("run_full_synthetic_experiment", text)
        self.assertIn("evaluate_results", text)
        self.assertIn("generate_figures", text)


def tiny_figure_config(root: Path):
    base = debug_config(root)
    return replace(
        base,
        datasets=DatasetConfig(families=("erdos_renyi",), graphs_per_distribution=2),
        dataset_configs=(
            SyntheticDatasetConfig("erdos_renyi", num_graphs=2, num_nodes=6, edge_probability=0.5, seed=0),
        ),
        perturbations=PerturbationConfig(methods=("edge_addition_deletion",), alpha_values=(0.0, 0.5)),
        workflows=WorkflowConfig(names=("structural_statistics_mmd",)),
        seeds=(0,),
        outputs=OutputConfig(root=root, results=root / "results", figures=root / "figures", logs=root / "logs"),
    )


if __name__ == "__main__":
    unittest.main()
