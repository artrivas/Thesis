from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experimentation.evaluation import (
    correlation_label,
    evaluate_results,
    generate_evaluation_summary,
    monotonicity_label,
    monotonicity_violation_fraction,
    robustness_label,
    spearman_correlation,
)
from experimentation.runner import write_result_rows


class EvaluationTests(unittest.TestCase):
    def test_sensitivity_returns_one_for_monotonic_data(self) -> None:
        self.assertAlmostEqual(spearman_correlation([0.0, 0.5, 1.0], [0.0, 2.0, 4.0]), 1.0)

    def test_monotonicity_detects_violations(self) -> None:
        pairs = [(0.0, 0.0), (0.3, 1.0), (0.6, 0.5), (1.0, 2.0)]
        self.assertAlmostEqual(monotonicity_violation_fraction(pairs), 1 / 3)

    def test_labels_are_assigned_correctly(self) -> None:
        self.assertEqual(correlation_label(0.90), "Very high")
        self.assertEqual(correlation_label(0.75), "High")
        self.assertEqual(correlation_label(0.50), "Medium")
        self.assertEqual(correlation_label(0.49), "Low")
        self.assertEqual(monotonicity_label(0.05), "Very high")
        self.assertEqual(monotonicity_label(0.15), "High")
        self.assertEqual(monotonicity_label(0.30), "Medium")
        self.assertEqual(monotonicity_label(0.31), "Low")
        self.assertEqual(robustness_label(0.10), "Very high")
        self.assertEqual(robustness_label(0.20), "High")
        self.assertEqual(robustness_label(0.35), "Medium")
        self.assertEqual(robustness_label(0.36), "Low")

    def test_evaluation_summary_can_be_generated_from_fake_result_table(self) -> None:
        rows = fake_result_rows()

        summary = generate_evaluation_summary(rows)

        self.assertEqual(len(summary), 2)
        self.assertTrue(all(row["sensitivity"] == 1.0 for row in summary))
        self.assertTrue(all(row["monotonicity"] == 0.0 for row in summary))

    def test_evaluate_results_writes_outputs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            results_path = Path(tmpdir) / "results.csv"
            write_result_rows(fake_result_rows(), results_path)

            outputs = evaluate_results(results_path, Path(tmpdir) / "evaluation")

            self.assertTrue(outputs["evaluation_summary"].is_file())
            self.assertTrue(outputs["final_matrix"].is_file())


def fake_result_rows():
    rows = []
    for workflow, runtime in (("structural_statistics_mmd", 1.0), ("wl_subtree_kernel_mmd", 2.0)):
        for seed in (0, 1):
            for alpha, score in ((0.0, 0.0), (0.5, 0.5), (1.0, 1.0)):
                rows.append(
                    {
                        "dataset": "erdos_renyi",
                        "dataset_params": "{}",
                        "perturbation": "edge_addition_deletion",
                        "perturbation_params": "{}",
                        "alpha": alpha,
                        "seed": seed,
                        "workflow": workflow,
                        "distribution_score": score,
                        "mean_shift_score": score,
                        "paired_score": score,
                        "runtime_seconds": runtime,
                        "memory_mb": 0.1,
                        "status": "success",
                        "error_message": "",
                    }
                )
    return rows


if __name__ == "__main__":
    unittest.main()
