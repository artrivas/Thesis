import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experimentation.dashboard import (
    _add_display_labels,
    _add_normalized_metric,
    _clean_facet_label_text,
    build_evaluation_tables,
    default_chart_rows,
    default_results_path,
    has_legacy_diversity_rows,
    has_legacy_workflow_rows,
    prepare_result_rows,
)
from tests.test_evaluation import fake_result_rows


class DashboardTests(unittest.TestCase):
    def test_default_results_path_prefers_fixed_candidate_when_present(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixed = root / "fixed.csv"
            legacy = root / "legacy.csv"
            fixed.write_text("header\n", encoding="utf-8")
            legacy.write_text("header\n", encoding="utf-8")

            self.assertEqual(default_results_path((fixed, legacy)), fixed)

    def test_default_results_path_falls_back_to_legacy_candidate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixed = root / "fixed.csv"
            legacy = root / "legacy.csv"
            legacy.write_text("header\n", encoding="utf-8")

            self.assertEqual(default_results_path((fixed, legacy)), legacy)

    def test_prepare_result_rows_coerces_numeric_values(self) -> None:
        rows = prepare_result_rows(fake_result_rows()[:1])

        self.assertIsInstance(rows[0]["alpha"], float)
        self.assertIsInstance(rows[0]["seed"], int)
        self.assertIsInstance(rows[0]["distribution_score"], float)

    def test_default_chart_rows_include_only_successful_finite_scores(self) -> None:
        rows = prepare_result_rows(
            [
                {**fake_result_rows()[0], "status": "success", "distribution_score": "1.0"},
                {**fake_result_rows()[0], "status": "failed", "distribution_score": "2.0"},
                {**fake_result_rows()[0], "status": "success", "distribution_score": ""},
            ]
        )

        chart_rows = default_chart_rows(rows)

        self.assertEqual(len(chart_rows), 1)
        self.assertEqual(chart_rows[0]["distribution_score"], 1.0)

    def test_legacy_diversity_rows_are_detected(self) -> None:
        rows = prepare_result_rows([{**fake_result_rows()[0], "workflow": "diversity_curves_l2"}])

        self.assertTrue(has_legacy_diversity_rows(rows))
        self.assertTrue(has_legacy_workflow_rows(rows))

    def test_legacy_netlsd_mmd_rows_are_detected(self) -> None:
        rows = prepare_result_rows([{**fake_result_rows()[0], "workflow": "netlsd_spectral_signatures"}])

        self.assertTrue(has_legacy_workflow_rows(rows))

    def test_build_evaluation_tables_from_prepared_rows(self) -> None:
        rows = prepare_result_rows(fake_result_rows())

        summary, matrix = build_evaluation_tables(rows)

        self.assertEqual(len(summary), 2)
        self.assertEqual(len(matrix), 2)
        self.assertTrue(all(math.isfinite(float(row["sensitivity"])) for row in summary))

    def test_display_labels_shorten_chart_categories(self) -> None:
        pd = _import_pandas()
        rows = pd.DataFrame(
            [
                {
                    "dataset": "stochastic_block_model",
                    "perturbation": "edge_addition_deletion",
                    "workflow": "native_netlsd",
                }
            ]
        )

        labeled = _add_display_labels(rows)

        self.assertEqual(labeled.loc[0, "dataset_label"], "SBM")
        self.assertEqual(labeled.loc[0, "perturbation_label"], "edge")
        self.assertEqual(labeled.loc[0, "workflow_label"], "NativeNetLSD")

    def test_normalized_metric_scales_each_panel_workflow(self) -> None:
        pd = _import_pandas()
        rows = pd.DataFrame(
            [
                {
                    "dataset": "erdos_renyi",
                    "perturbation": "edge_addition_deletion",
                    "workflow": "wl_subtree_kernel_mmd",
                    "distribution_score": 50.0,
                },
                {
                    "dataset": "erdos_renyi",
                    "perturbation": "edge_addition_deletion",
                    "workflow": "wl_subtree_kernel_mmd",
                    "distribution_score": 100.0,
                },
                {
                    "dataset": "erdos_renyi",
                    "perturbation": "edge_addition_deletion",
                    "workflow": "native_netlsd",
                    "distribution_score": 0.2,
                },
            ]
        )

        normalized = _add_normalized_metric(rows, "distribution_score", "normalized")

        self.assertEqual(list(normalized["normalized"]), [0.5, 1.0, 1.0])

    def test_facet_label_text_drops_plotly_column_prefix(self) -> None:
        self.assertEqual(_clean_facet_label_text("perturbation_label=edge"), "edge")


def _import_pandas():
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise unittest.SkipTest("pandas is not installed") from exc
    return pd


if __name__ == "__main__":
    unittest.main()
