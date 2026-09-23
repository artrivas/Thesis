"""Mathematical checks for descriptive analysis, without rerunning experiments."""
import importlib.util
from pathlib import Path
import unittest

def load_script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    import numpy as np
    import pandas
    import scipy
    import matplotlib
except ImportError:
    HAS_ANALYSIS = False
else:
    HAS_ANALYSIS = True
    seed = load_script("analyze_seed_granularity")
    pilot = load_script("analyze_graph_pair_pilot")


@unittest.skipUnless(HAS_ANALYSIS, "optional analysis dependencies are not installed")
class GranularAnalysisTests(unittest.TestCase):
    def test_large_minority_can_reverse_mean(self):
        result = seed.step_summary([5, -1, -1], 1e-12)
        self.assertEqual(result["mean_change"], 1)
        self.assertEqual(result["median_change"], -1)
        self.assertTrue(result["mean_opposes_absolute_majority"])

    def test_nonzero_majority_is_not_absolute_majority(self):
        result = seed.step_summary([10, -1, -1, 0, 0, 0], 1e-12)
        self.assertTrue(result["mean_opposes_more_nonzero_seeds"])
        self.assertFalse(result["mean_opposes_absolute_majority"])
        self.assertEqual(result["zero"], 3)

    def test_rbf_decomposition_matches_kernel_definition(self):
        x = np.array([[0., 1.], [1., 0.], [2., 3.]])
        y = np.array([[3., 1.], [1., 1.], [2., 2.]])
        kernel = lambda a, b: np.exp(-np.sum((a - b)**2) / 8.)
        expected = sum(kernel(a, b) for a in x for b in x) / 9
        expected += sum(kernel(a, b) for a in y for b in y) / 9
        expected -= 2 * sum(kernel(a, b) for a in x for b in y) / 9
        self.assertAlmostEqual(pilot.rbf_contributions(x, y, 2.).mean(), expected)
        np.testing.assert_allclose(pilot.rbf_contributions(x, x, 2.), 0, atol=1e-15)

    def test_linear_decomposition_matches_squared_mean_distance(self):
        x = [{"a": 1.}, {"b": 2.}, {"a": 4., "b": 3.}]
        y = [{"a": 2., "b": 1.}, {"b": 5.}, {"a": 1.}]
        expected = (3/3 - 5/3)**2 + (6/3 - 5/3)**2
        self.assertAlmostEqual(pilot.linear_contributions(x, y).mean(), expected)
        np.testing.assert_allclose(pilot.linear_contributions(x, x), 0)


if __name__ == "__main__":
    unittest.main()
