"""Configuration objects for synthetic graph distribution experiments."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from experimentation.datasets import SyntheticDatasetConfig


DEFAULT_ALPHA_VALUES = tuple(round(i / 10, 1) for i in range(11))
DEFAULT_SEEDS = tuple(range(5))
DEFAULT_PERTURBATION_METHODS = (
    "edge_addition_deletion",
    "triangle_injection_removal",
    "community_weakening",
    "hub_modification",
)
DEFAULT_WORKFLOW_NAMES = (
    "structural_statistics_mmd",
    "wl_subtree_kernel_mmd",
    "netlsd_spectral_signatures",
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

    root: Path = Path("outputs/experimentation")
    results: Path = Path("outputs/experimentation/results")
    figures: Path = Path("outputs/experimentation/figures")
    logs: Path = Path("outputs/experimentation/logs")

    def create_directories(self) -> None:
        """Create configured output directories if they do not exist."""

        for path in (self.root, self.results, self.figures, self.logs):
            path.mkdir(parents=True, exist_ok=True)


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
        outputs=OutputConfig(
            root=root,
            results=root / "results",
            figures=root / "figures",
            logs=root / "logs",
        ),
    )


def full_synthetic_config(output_root: Path | str = Path("outputs/experimentation")) -> ExperimentConfig:
    """Return the full synthetic-only grid configuration."""

    root = Path(output_root)
    return ExperimentConfig(
        datasets=DatasetConfig(graphs_per_distribution=100),
        dataset_configs=default_synthetic_dataset_configs(num_graphs=100, num_nodes=50),
        perturbations=PerturbationConfig(alpha_values=DEFAULT_ALPHA_VALUES),
        seeds=DEFAULT_SEEDS,
        outputs=OutputConfig(
            root=root,
            results=root / "results",
            figures=root / "figures",
            logs=root / "logs",
        ),
    )
