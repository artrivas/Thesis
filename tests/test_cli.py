from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from experimentation.cli import main
from experimentation.runner import read_result_rows


class CliTests(unittest.TestCase):
    def test_workflow_argument_filters_debug_run(self) -> None:
        with TemporaryDirectory() as tmpdir:
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "run_debug_experiment",
                        "--output-root",
                        tmpdir,
                        "--workflow",
                        "structural_statistics_mmd",
                        "--no-resume",
                    ]
                )

            result_path = Path(stdout.getvalue().strip())
            rows = read_result_rows(result_path)

            self.assertEqual(exit_code, 0)
            self.assertTrue(rows)
            self.assertEqual({row["workflow"] for row in rows}, {"structural_statistics_mmd"})

    def test_workflow_argument_can_be_repeated(self) -> None:
        with TemporaryDirectory() as tmpdir:
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "run_debug_experiment",
                        "--output-root",
                        tmpdir,
                        "--workflow",
                        "structural_statistics_mmd",
                        "--workflow",
                        "wl_subtree_kernel_mmd",
                        "--no-resume",
                    ]
                )

            result_path = Path(stdout.getvalue().strip())
            rows = read_result_rows(result_path)

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                {row["workflow"] for row in rows},
                {"structural_statistics_mmd", "wl_subtree_kernel_mmd"},
            )


if __name__ == "__main__":
    unittest.main()
