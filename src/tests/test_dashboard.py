import math
import unittest

from experimentation.dashboard import (
    build_evaluation_tables,
    default_chart_rows,
    has_legacy_diversity_rows,
    prepare_result_rows,
)
from tests.test_evaluation import fake_result_rows


class DashboardTests(unittest.TestCase):
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

    def test_build_evaluation_tables_from_prepared_rows(self) -> None:
        rows = prepare_result_rows(fake_result_rows())

        summary, matrix = build_evaluation_tables(rows)

        self.assertEqual(len(summary), 2)
        self.assertEqual(len(matrix), 2)
        self.assertTrue(all(math.isfinite(float(row["sensitivity"])) for row in summary))


if __name__ == "__main__":
    unittest.main()
