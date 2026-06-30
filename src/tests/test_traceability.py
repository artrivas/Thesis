import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from experimentation.config import (
    PerturbationConfig,
    WorkflowConfig,
    build_run_output_config,
    debug_config,
)
from experimentation.runner import (
    MANIFEST_FILENAME,
    read_result_rows,
    run_experiment,
)


def fast_config(root: Path, seeds=(0, 1)):
    base = debug_config(root)
    return replace(
        base,
        perturbations=PerturbationConfig(methods=("edge_insertion",), alpha_values=(0.0, 0.5)),
        workflows=WorkflowConfig(names=("structural_statistics_mmd",)),
        seeds=seeds,
    )


class RunDirectoryLayoutTests(unittest.TestCase):
    def test_build_run_output_config_layout(self) -> None:
        config = debug_config(Path("unused"))
        run_id, outputs = build_run_output_config("results/runs", config, run_id="fixed")
        self.assertEqual(run_id, "fixed")
        self.assertTrue(str(outputs.root).endswith("fixed"))
        self.assertEqual(outputs.results, outputs.root / "results")
        self.assertEqual(outputs.logs, outputs.root / "logs")
        self.assertEqual(outputs.evaluation, outputs.root / "evaluation")
        self.assertEqual(outputs.figures, outputs.root / "figures")

    def test_auto_run_id_has_timestamp_and_hash(self) -> None:
        config = debug_config(Path("unused"))
        run_id, _ = build_run_output_config("results/runs", config)
        # "<YYYY-MM-DDTHHMM>_<8charhash>"
        self.assertIn("_", run_id)
        self.assertEqual(len(run_id.rsplit("_", 1)[1]), 8)


class ManifestTests(unittest.TestCase):
    def test_manifest_written_with_required_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            _run_id, outputs = build_run_output_config(Path(tmp), fast_config(Path(tmp)), run_id="run-123")
            config = replace(fast_config(Path(tmp), seeds=(0, 1, 2)), outputs=outputs)
            run_experiment(config, workers=1, run_id="run-123")

            manifest_path = outputs.root / MANIFEST_FILENAME
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            for key in (
                "run_id",
                "git_commit",
                "hostname",
                "started_at",
                "ended_at",
                "config",
                "config_hash",
                "seeds",
                "workflows",
                "library_versions",
                "checkpoint_path",
                "output_root",
            ):
                self.assertIn(key, manifest)
            self.assertEqual(manifest["run_id"], "run-123")
            self.assertEqual(manifest["status"], "finished")
            self.assertEqual(manifest["seeds"], [0, 1, 2])
            self.assertEqual(manifest["workflows"], ["structural_statistics_mmd"])
            self.assertIn("python", manifest["library_versions"])
            # Checkpoint lives inside the run directory.
            self.assertTrue(manifest["checkpoint_path"].startswith(str(outputs.root)))

    def test_manifest_records_sharded_seed_subset(self) -> None:
        with TemporaryDirectory() as tmp:
            _run_id, outputs = build_run_output_config(
                Path(tmp), fast_config(Path(tmp)), run_id="shard", seed_range=(1, 3)
            )
            config = replace(fast_config(Path(tmp), seeds=(0, 1, 2, 3)), outputs=outputs)
            run_experiment(config, workers=1, seed_range=(1, 3), run_id="shard")

            manifest = json.loads((outputs.root / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["seeds"], [1, 2])
            self.assertEqual(manifest["seed_range"], [1, 3])


class RunIdResumeTests(unittest.TestCase):
    def test_resume_by_run_id_targets_same_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            _run_id, outputs = build_run_output_config(Path(tmp), fast_config(Path(tmp)), run_id="resumeme")
            config = replace(fast_config(Path(tmp)), outputs=outputs)

            first = run_experiment(config, workers=1, run_id="resumeme")
            first_rows = read_result_rows(first)
            again = run_experiment(config, workers=1, run_id="resumeme")
            again_rows = read_result_rows(again)

            self.assertEqual(first, again)
            self.assertEqual(len(first_rows), len(again_rows))


if __name__ == "__main__":
    unittest.main()
