"""Checks for the optional analysis script's statistical edge cases."""
import importlib.util
from itertools import product
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    import pandas as pd
    import scipy
    import matplotlib
except ImportError:
    HAS_ANALYSIS = False
else:
    HAS_ANALYSIS = True
    path = Path(__file__).resolve().parents[1]/"scripts/analyze_statistical_assumptions.py"
    spec = importlib.util.spec_from_file_location("audit", path)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    shape_path = path.parent / "check_distributional_conditions.py"
    shape_spec = importlib.util.spec_from_file_location("shape_audit", shape_path)
    shape_audit = importlib.util.module_from_spec(shape_spec)
    shape_spec.loader.exec_module(shape_audit)
    inference_path = path.parent / "run_paired_statistical_tests.py"
    inference_spec = importlib.util.spec_from_file_location("paired_tests", inference_path)
    paired_tests = importlib.util.module_from_spec(inference_spec)
    inference_spec.loader.exec_module(paired_tests)


@unittest.skipUnless(HAS_ANALYSIS, "optional analysis dependencies are not installed")
class StatisticalAuditTests(unittest.TestCase):
    def test_small_sample_resolution_and_ties(self):
        self.assertEqual(audit.sign_summary([1]*5)["p_independent_seeds"], .0625)
        tied = audit.sign_summary([1, 1, 0, -1, float("nan")])
        self.assertEqual((tied["positive"], tied["negative"], tied["zero"]), (2, 1, 1))
        self.assertEqual(tied["p_independent_seeds"], 1.)
        self.assertEqual(audit.sign_summary([0]*5)["p_independent_seeds"], 1.)

    def test_holm_adjusts_in_original_order(self):
        np.testing.assert_allclose(audit.holm([.04, .001, .03]), [.06, .003, .06])

    def test_missing_alpha_is_rejected(self):
        frame = pd.DataFrame([dict(dataset="toy", perturbation="toy", workflow="toy", seed=0,
                                   alpha=a, distribution_score=a, mean_shift_score=a,
                                   paired_score=a, edit_distance_raw=a, status="success")
                              for a in np.linspace(0, 1, 11)])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                audit.audit(frame.iloc[:-1], Path(directory))

    def test_symmetry_is_about_location_not_zero(self):
        low = np.full(24, 100.)
        high = low + np.arange(24.) + 10.
        result = shape_audit.inspect_difference(low, high)
        self.assertGreater(result["mean"], 0.)
        self.assertAlmostEqual(result["sample_skewness"], 0., places=12)
        self.assertAlmostEqual(result["bowley_asymmetry"], 0., places=12)
        self.assertAlmostEqual(result["tail_asymmetry"], 0., places=12)

    def test_constant_and_sparse_differences_remain_distinct(self):
        low = np.ones(24)
        zero = shape_audit.inspect_difference(low, low)
        self.assertTrue(zero["all_zero"])
        self.assertIsNone(zero["shapiro_p"])
        high = low.copy()
        high[0] += 1.
        sparse = shape_audit.inspect_difference(low, high)
        self.assertFalse(sparse["constant"])
        self.assertEqual(sparse["nonzero_count"], 1)
        self.assertIsNone(sparse["bowley_asymmetry"])

    def test_shape_metrics_do_not_depend_on_score_units(self):
        low = np.full(24, 100.)
        high = low + np.linspace(.1, 2., 24)**2
        first = shape_audit.inspect_difference(low, high)
        second = shape_audit.inspect_difference(low*10, high*10)
        for key in ["sample_skewness", "bowley_asymmetry", "shapiro_p", "normal_qq_r"]:
            self.assertAlmostEqual(first[key], second[key], places=10)

    def test_exact_signed_rank_matches_scipy_without_ties(self):
        from scipy import stats
        d = np.array([1., -2., 3., -4., 5., 6., -7., 8.])
        actual = paired_tests.signed_rank_exact(d, 1e-12)
        reference = stats.wilcoxon(d, method="exact")
        self.assertEqual(actual["statistic"], reference.statistic)
        self.assertEqual(actual["p_raw"], reference.pvalue)

    def test_exact_signed_rank_ties_match_enumeration(self):
        # Nonzero magnitudes [1,1,2,3] have ranks [1.5,1.5,3,4].
        d = np.array([0., 1., -1., 2., 3.])
        ranks = np.array([1.5,1.5,3.,4.])
        observed = 1.5+3.+4.
        sums = np.array([sum(r for r, s in zip(ranks, signs) if s) for signs in product([0,1], repeat=4)])
        p = min(1., 2*min(np.mean(sums<=observed), np.mean(sums>=observed)))
        actual = paired_tests.signed_rank_exact(d, 1e-12)
        self.assertEqual(actual["n_nonzero"], 4)
        self.assertEqual(actual["p_raw"], p)
        self.assertIsNone(paired_tests.signed_rank_exact(np.zeros(24), 1e-12))

    def test_unavailable_tests_remain_in_multiplicity_family(self):
        np.testing.assert_allclose(paired_tests.holm([.01, 1., 1.]), [.03, 1., 1.])


if __name__ == "__main__":
    unittest.main()
