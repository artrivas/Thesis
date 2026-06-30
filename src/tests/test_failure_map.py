import unittest

from experimentation.evaluation import generate_failure_map
from experimentation.figures import failure_map_svg


def make_row(dataset, perturbation, workflow, alpha, seed, *, score, edits, status="success"):
    return {
        "dataset": dataset,
        "dataset_params": "{}",
        "perturbation": perturbation,
        "perturbation_params": "{}",
        "alpha": alpha,
        "seed": seed,
        "workflow": workflow,
        "distribution_score": score,
        "mean_shift_score": score,
        "paired_score": score,
        "edit_distance_raw": edits,
        "edit_distance_weighted": edits,
        "runtime_seconds": 1.0,
        "memory_mb": 0.1,
        "status": status,
        "error_message": "",
    }


def cell_rows(dataset, perturbation, *, score_fn, edits_fn, seeds=(0, 1, 2), alphas=(0.0, 0.5, 1.0)):
    rows = []
    for seed in seeds:
        for alpha in alphas:
            rows.append(
                make_row(
                    dataset,
                    perturbation,
                    "structural_statistics_mmd",
                    alpha,
                    seed,
                    score=score_fn(alpha, seed),
                    edits=edits_fn(alpha, seed),
                )
            )
    return rows


def cause_for(rows):
    return generate_failure_map(rows)[0]["cause"]


class FailureMapDiagnosisTests(unittest.TestCase):
    def test_ok_cell(self) -> None:
        rows = cell_rows(
            "stochastic_block_model",
            "edge_deletion",
            score_fn=lambda a, s: a,  # clean monotone rise, no seed noise
            edits_fn=lambda a, s: 10 * a,
        )
        self.assertEqual(cause_for(rows), "ok")

    def test_perturbation_starved_cell(self) -> None:
        # alpha>0 but essentially nothing edited (triangle_deletion-on-ER analogue).
        rows = cell_rows(
            "erdos_renyi",
            "triangle_deletion",
            score_fn=lambda a, s: 0.0,
            edits_fn=lambda a, s: 0.0,
        )
        self.assertEqual(cause_for(rows), "perturbation_starved")

    def test_method_blind_cell(self) -> None:
        # Lots of edits, but the score never moves -> the method is blind.
        rows = cell_rows(
            "barabasi_albert",
            "hub_modification",
            score_fn=lambda a, s: 0.5,
            edits_fn=lambda a, s: 12 * a,
        )
        self.assertEqual(cause_for(rows), "method_blind")

    def test_unstable_cell(self) -> None:
        # Edits happen and there is an overall rise, but a strong non-monotone
        # zig-zag in the alpha-mean makes the response unstable.
        pattern = {0.0: 0.0, 0.25: 1.0, 0.5: 0.2, 0.75: 1.2, 1.0: 0.3}
        rows = cell_rows(
            "stochastic_block_model",
            "community_weakening",
            score_fn=lambda a, s: pattern[a],
            edits_fn=lambda a, s: 8 * a,
            alphas=tuple(pattern),
        )
        self.assertEqual(cause_for(rows), "unstable")

    def test_inapplicable_cell(self) -> None:
        rows = [
            make_row("erdos_renyi", "community_weakening", "structural_statistics_mmd", a, s, score="", edits="", status="skipped")
            for s in (0, 1)
            for a in (0.0, 0.5, 1.0)
        ]
        self.assertEqual(cause_for(rows), "inapplicable")

    def test_triangle_deletion_on_er_is_perturbation_starved(self) -> None:
        # The documented worked example: ER has too few triangles to spend budget.
        rows = cell_rows(
            "erdos_renyi",
            "triangle_deletion",
            score_fn=lambda a, s: 0.01 * a,
            edits_fn=lambda a, s: 0.0,
        )
        self.assertEqual(cause_for(rows), "perturbation_starved")


class FailureMapRenderTests(unittest.TestCase):
    def test_failure_map_svg_renders(self) -> None:
        rows = cell_rows(
            "erdos_renyi",
            "edge_deletion",
            score_fn=lambda a, s: a,
            edits_fn=lambda a, s: 10 * a,
        )
        svg = failure_map_svg(generate_failure_map(rows))
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("Failure map", svg)

    def test_empty_failure_map_is_placeholder(self) -> None:
        self.assertIn("No result rows", failure_map_svg([]))


if __name__ == "__main__":
    unittest.main()
