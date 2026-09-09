import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experimentation.dashboard import (
    _add_display_labels,
    _add_normalized_metric,
    _clean_facet_label_text,
    EVALUATION_HEATMAP_METRICS,
    build_evaluation_tables,
    community_label_source_rows,
    default_chart_rows,
    default_results_path,
    discover_runs,
    edit_distance_validation_rows,
    exclude_aggregate_perturbations,
    has_legacy_diversity_rows,
    has_legacy_workflow_rows,
    is_excluded_perturbation,
    load_failure_map_rows,
    prepare_result_rows,
    run_results_path,
    seed_band_table,
)
from experimentation.evaluation import FAILURE_MAP_COLUMNS, write_table
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
                {
                    **fake_result_rows()[0],
                    "status": "success",
                    "distribution_score": "1.0",
                    "perturbation": "edge_insertion",
                },
                {
                    **fake_result_rows()[0],
                    "status": "failed",
                    "distribution_score": "2.0",
                    "perturbation": "edge_insertion",
                },
                {
                    **fake_result_rows()[0],
                    "status": "success",
                    "distribution_score": "",
                    "perturbation": "edge_insertion",
                },
                {
                    **fake_result_rows()[0],
                    "status": "success",
                    "distribution_score": "3.0",
                    "perturbation": "edge_addition_deletion",
                },
            ]
        )

        chart_rows = default_chart_rows(rows)

        self.assertEqual(len(chart_rows), 1)
        self.assertEqual(chart_rows[0]["distribution_score"], 1.0)

    def test_aggregate_edge_triangle_perturbations_are_excluded(self) -> None:
        rows = prepare_result_rows(
            [
                {**fake_result_rows()[0], "perturbation": "edge_addition_deletion"},
                {**fake_result_rows()[0], "perturbation": "triangle_injection_removal"},
                {**fake_result_rows()[0], "perturbation": "edge_insertion"},
            ]
        )

        filtered = exclude_aggregate_perturbations(rows)

        self.assertTrue(is_excluded_perturbation(rows[0]))
        self.assertTrue(is_excluded_perturbation(rows[1]))
        self.assertFalse(is_excluded_perturbation(rows[2]))
        self.assertEqual([row["perturbation"] for row in filtered], ["edge_insertion"])

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
                    "perturbation": "edge_insertion",
                    "workflow": "native_netlsd",
                }
            ]
        )

        labeled = _add_display_labels(rows)

        self.assertEqual(labeled.loc[0, "dataset_label"], "SBM")
        self.assertEqual(labeled.loc[0, "perturbation_label"], "edge insertion")
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

    def test_evaluation_heatmap_metrics_include_non_sensitivity_options(self) -> None:
        self.assertEqual(EVALUATION_HEATMAP_METRICS["Sensitivity"], "sensitivity")
        self.assertEqual(EVALUATION_HEATMAP_METRICS["Relative runtime"], "relative_runtime")
        self.assertEqual(EVALUATION_HEATMAP_METRICS["Robustness CV"], "robustness_cv")

    def test_facet_label_text_drops_plotly_column_prefix(self) -> None:
        self.assertEqual(_clean_facet_label_text("perturbation_label=edge"), "edge")


class RunSelectorTests(unittest.TestCase):
    def test_discover_runs_finds_run_dirs_newest_first(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("2026-01-01T0900_aaaa", "2026-06-01T0900_bbbb"):
                results = root / name / "results"
                results.mkdir(parents=True)
                (results / "results.csv").write_text("header\n", encoding="utf-8")
            # A directory without results/results.csv is ignored.
            (root / "not_a_run").mkdir()

            runs = discover_runs(root)

            self.assertEqual([run.name for run in runs], ["2026-06-01T0900_bbbb", "2026-01-01T0900_aaaa"])
            self.assertTrue(run_results_path(runs[0]).is_file())

    def test_discover_runs_handles_missing_root(self) -> None:
        self.assertEqual(discover_runs(Path("does/not/exist")), [])


class SeedBandTests(unittest.TestCase):
    def test_seed_band_table_computes_mean_and_std_over_seeds(self) -> None:
        rows = prepare_result_rows(
            [
                {**fake_result_rows()[0], "perturbation": "edge_insertion", "seed": 0, "alpha": 0.5, "distribution_score": "1.0"},
                {**fake_result_rows()[0], "perturbation": "edge_insertion", "seed": 1, "alpha": 0.5, "distribution_score": "3.0"},
            ]
        )

        table = seed_band_table(rows, "erdos_renyi", "edge_insertion")

        self.assertEqual(len(table), 1)
        self.assertAlmostEqual(table[0]["mean"], 2.0)
        self.assertAlmostEqual(table[0]["std"], 1.0)
        self.assertEqual(table[0]["n_seeds"], 2)


class ValidationRowsTests(unittest.TestCase):
    def test_edit_distance_validation_rows_require_finite_scores(self) -> None:
        rows = prepare_result_rows(
            [
                {**fake_result_rows()[0], "perturbation": "edge_insertion", "edit_distance_weighted": "5.0"},
                {**fake_result_rows()[0], "perturbation": "edge_insertion", "edit_distance_weighted": ""},
            ]
        )
        validated = edit_distance_validation_rows(rows)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]["edit_distance_weighted"], 5.0)

    def test_community_label_source_rows_filter(self) -> None:
        rows = prepare_result_rows(
            [
                {**fake_result_rows()[0], "perturbation": "community_weakening", "label_source": "detected"},
                {**fake_result_rows()[0], "perturbation": "community_weakening", "label_source": "ground_truth"},
                {**fake_result_rows()[0], "perturbation": "community_weakening", "label_source": ""},
                {**fake_result_rows()[0], "perturbation": "edge_insertion", "label_source": "detected"},
            ]
        )
        community = community_label_source_rows(rows)
        self.assertEqual(len(community), 2)
        self.assertEqual({row["label_source"] for row in community}, {"detected", "ground_truth"})


class FailureMapLoadingTests(unittest.TestCase):
    def test_prefers_precomputed_failure_map_csv(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "evaluation").mkdir()
            write_table(
                [
                    {
                        "dataset": "erdos_renyi",
                        "perturbation": "triangle_deletion",
                        "cause": "perturbation_starved",
                        "note": "precomputed",
                    }
                ],
                FAILURE_MAP_COLUMNS,
                run_dir / "evaluation" / "failure_map.csv",
            )

            loaded = load_failure_map_rows(run_dir, [])

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["cause"], "perturbation_starved")

    def test_falls_back_to_deriving_from_rows(self) -> None:
        rows = prepare_result_rows(
            [
                {**fake_result_rows()[0], "perturbation": "edge_insertion", "edit_distance_raw": "10.0", "alpha": "0.5"}
            ]
        )
        loaded = load_failure_map_rows(None, rows)
        self.assertTrue(loaded)
        self.assertIn("cause", loaded[0])


def _import_pandas():
    try:
        import pandas as pd  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise unittest.SkipTest("pandas is not installed") from exc
    return pd


if __name__ == "__main__":
    unittest.main()
