"""Configuration objects for synthetic graph distribution experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from experimentation.datasets import SyntheticDatasetConfig


DEFAULT_ALPHA_VALUES = tuple(round(i / 10, 1) for i in range(11))
DEFAULT_SEEDS = tuple(range(5))
DEFAULT_PERTURBATION_METHODS = (
    "edge_insertion",
    "edge_deletion",
    "triangle_insertion",
    "triangle_deletion",
    "community_weakening",
    "hub_modification",
)
DEFAULT_WORKFLOW_NAMES = (
    "structural_statistics_mmd",
    "wl_subtree_kernel_mmd",
    "native_netlsd",
    "diversity_curves_shortest_path",
)


def default_synthetic_dataset_configs(
    num_graphs: int = 100,
    num_nodes: int = 50,
) -> tuple[SyntheticDatasetConfig, ...]:
    """Return the default ER, SBM, and BA synthetic dataset settings."""

    return (
        SyntheticDatasetConfig(
            family="erdos_renyi",
            num_graphs=num_graphs,
            num_nodes=num_nodes,
            edge_probability=0.12,
        ),
        SyntheticDatasetConfig(
            family="stochastic_block_model",
            num_graphs=num_graphs,
            num_nodes=num_nodes,
            num_blocks=4,
            p_in=0.28,
            p_out=0.04,
        ),
        SyntheticDatasetConfig(
            family="barabasi_albert",
            num_graphs=num_graphs,
            num_nodes=num_nodes,
            m=2,
        ),
    )


@dataclass(frozen=True)
class DatasetConfig:
    """Synthetic dataset family configuration."""

    families: tuple[str, ...] = (
        "erdos_renyi",
        "stochastic_block_model",
        "barabasi_albert",
    )
    graphs_per_distribution: int = 100


@dataclass(frozen=True)
class PerturbationConfig:
    """Supported perturbation families and alpha schedule."""

    methods: tuple[str, ...] = DEFAULT_PERTURBATION_METHODS
    alpha_values: tuple[float, ...] = DEFAULT_ALPHA_VALUES


@dataclass(frozen=True)
class WorkflowConfig:
    """Representative graph-distribution comparison workflows."""

    names: tuple[str, ...] = DEFAULT_WORKFLOW_NAMES


@dataclass(frozen=True)
class OutputConfig:
    """Filesystem locations for generated experiment artifacts."""

    root: Path = Path("outputs/experimentation_native_netlsd")
    results: Path = Path("outputs/experimentation_native_netlsd/results")
    figures: Path = Path("outputs/experimentation_native_netlsd/figures")
    logs: Path = Path("outputs/experimentation_native_netlsd/logs")
    evaluation: Path = Path("outputs/experimentation_native_netlsd/evaluation")

    def create_directories(self) -> None:
        """Create configured output directories if they do not exist."""

        for path in (self.root, self.results, self.figures, self.logs, self.evaluation):
            path.mkdir(parents=True, exist_ok=True)


def output_config_for_root(root: Path | str) -> OutputConfig:
    """Return a standard ``OutputConfig`` rooted at a single run directory."""

    root = Path(root)
    return OutputConfig(
        root=root,
        results=root / "results",
        figures=root / "figures",
        logs=root / "logs",
        evaluation=root / "evaluation",
    )


@dataclass(frozen=True)
class ExperimentConfig:
    """Top-level configuration for synthetic paired graph experiments."""

    datasets: DatasetConfig = field(default_factory=DatasetConfig)
    dataset_configs: tuple[SyntheticDatasetConfig, ...] = field(
        default_factory=default_synthetic_dataset_configs
    )
    perturbations: PerturbationConfig = field(default_factory=PerturbationConfig)
    workflows: WorkflowConfig = field(default_factory=WorkflowConfig)
    seeds: tuple[int, ...] = DEFAULT_SEEDS
    outputs: OutputConfig = field(default_factory=OutputConfig)

    def resolved_dataset_configs(self) -> tuple[SyntheticDatasetConfig, ...]:
        """Return concrete synthetic dataset configs for the runner."""

        if self.dataset_configs:
            return self.dataset_configs
        return default_synthetic_dataset_configs(
            num_graphs=self.datasets.graphs_per_distribution,
            num_nodes=50,
        )


def default_config() -> ExperimentConfig:
    """Return the default synthetic experiment configuration."""

    return full_synthetic_config()


def debug_config(output_root: Path | str = Path("outputs/debug_experimentation")) -> ExperimentConfig:
    """Return a very small configuration for tests and local debugging."""

    root = Path(output_root)
    return ExperimentConfig(
        datasets=DatasetConfig(graphs_per_distribution=5),
        dataset_configs=default_synthetic_dataset_configs(num_graphs=5, num_nodes=8),
        perturbations=PerturbationConfig(alpha_values=(0.0, 0.5, 1.0)),
        seeds=(0,),
        outputs=output_config_for_root(root),
    )


def full_synthetic_config(output_root: Path | str = Path("outputs/experimentation_native_netlsd")) -> ExperimentConfig:
    """Return the full synthetic-only grid configuration."""

    root = Path(output_root)
    return ExperimentConfig(
        datasets=DatasetConfig(graphs_per_distribution=100),
        dataset_configs=default_synthetic_dataset_configs(num_graphs=100, num_nodes=50),
        perturbations=PerturbationConfig(alpha_values=DEFAULT_ALPHA_VALUES),
        seeds=DEFAULT_SEEDS,
        outputs=output_config_for_root(root),
    )


def resolved_config_payload(config: ExperimentConfig) -> dict[str, object]:
    """Return a JSON-serializable, seed-normalized view of a config.

    Per-graph ``seed`` fields are normalized to ``0`` because the runner
    overrides the dataset seed for every grid cell; the swept seed list is
    recorded separately. This keeps the config hash stable across machines and
    independent of which seed shard happens to run first.
    """

    return {
        "dataset_configs": [asdict(replace(dc, seed=0)) for dc in config.resolved_dataset_configs()],
        "perturbations": {
            "methods": list(config.perturbations.methods),
            "alpha_values": [float(value) for value in config.perturbations.alpha_values],
        },
        "workflows": list(config.workflows.names),
        "seeds": [int(seed) for seed in config.seeds],
    }


def config_hash(config: ExperimentConfig) -> str:
    """Return a short, deterministic, machine-independent config fingerprint."""

    payload = json.dumps(resolved_config_payload(config), sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def run_id_for_config(config: ExperimentConfig, when: datetime | None = None) -> str:
    """Return a timestamped, hash-tagged run identifier for traceability."""

    moment = when or datetime.now(timezone.utc)
    return f"{moment.strftime('%Y-%m-%dT%H%M')}_{config_hash(config)}"


def shard_suffix(seed_range: tuple[int, int] | None) -> str:
    """Return the directory suffix used to isolate a seed-range shard."""

    if seed_range is None:
        return ""
    return f"_shard-{seed_range[0]}-{seed_range[1]}"


def build_run_output_config(
    results_root: Path | str,
    config: ExperimentConfig,
    *,
    run_id: str | None = None,
    seed_range: tuple[int, int] | None = None,
    when: datetime | None = None,
) -> tuple[str, OutputConfig]:
    """Build the traceable ``results/runs/<run_id>[_shard-A-B]/`` output layout.

    Returns the resolved ``run_id`` (without the shard suffix) and an
    ``OutputConfig`` rooted inside the per-run directory. The shard suffix keeps
    each seed-range shard in its own directory so there is no cross-process or
    cross-machine write contention.
    """

    resolved_run_id = run_id or run_id_for_config(config, when)
    directory_name = f"{resolved_run_id}{shard_suffix(seed_range)}"
    root = Path(results_root) / directory_name
    return resolved_run_id, output_config_for_root(root)
