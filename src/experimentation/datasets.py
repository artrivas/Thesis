"""Synthetic graph distribution generators."""

from __future__ import annotations

from dataclasses import dataclass
import random

from experimentation.graph import Graph
from experimentation.perturbations import PerturbationResult, perturb_graph


@dataclass(frozen=True)
class SyntheticDatasetConfig:
    family: str
    num_graphs: int = 100
    num_nodes: int = 50
    edge_probability: float = 0.1
    num_blocks: int = 3
    p_in: float = 0.25
    p_out: float = 0.03
    m: int = 2
    seed: int = 0


@dataclass(frozen=True)
class PairedDistribution:
    original_graphs: list[Graph]
    perturbed_graphs: list[Graph]
    pairs: list[tuple[Graph, Graph]]
    metadata: dict[str, object]


def generate_graph_distribution(dataset_config: SyntheticDatasetConfig) -> list[Graph]:
    """Generate a synthetic graph distribution using a common interface."""

    family = dataset_config.family
    if family == "erdos_renyi":
        return _generate_erdos_renyi(dataset_config)
    if family == "stochastic_block_model":
        return _generate_stochastic_block_model(dataset_config)
    if family == "barabasi_albert":
        return _generate_barabasi_albert(dataset_config)
    raise ValueError(f"Unknown synthetic dataset family: {family}")


def generate_paired_distribution(
    dataset_config: SyntheticDatasetConfig,
    perturbation_type: str,
    alpha: float,
    seed: int,
) -> PairedDistribution:
    """Generate original and perturbed graph distributions while preserving pairs."""

    original_graphs = generate_graph_distribution(dataset_config)
    perturbed_graphs: list[Graph] = []
    perturbation_metadata: list[dict[str, object]] = []
    for index, graph in enumerate(original_graphs):
        result = perturb_graph(graph, alpha, perturbation_type, seed + index, graph.metadata)
        perturbed_graphs.append(result.graph)
        perturbation_metadata.append(result.metadata)
    return PairedDistribution(
        original_graphs=original_graphs,
        perturbed_graphs=perturbed_graphs,
        pairs=list(zip(original_graphs, perturbed_graphs)),
        metadata={
            "dataset": dataset_config.family,
            "perturbation": perturbation_type,
            "alpha": alpha,
            "seed": seed,
            "num_pairs": len(original_graphs),
            "perturbations": perturbation_metadata,
        },
    )


def _generate_erdos_renyi(config: SyntheticDatasetConfig) -> list[Graph]:
    rng = random.Random(config.seed)
    graphs = []
    for graph_index in range(config.num_graphs):
        graph = Graph(config.num_nodes, metadata={"family": config.family, "graph_index": graph_index})
        for u in range(config.num_nodes):
            for v in range(u + 1, config.num_nodes):
                if rng.random() < config.edge_probability:
                    graph.add_edge(u, v)
        graphs.append(graph)
    return graphs


def _generate_stochastic_block_model(config: SyntheticDatasetConfig) -> list[Graph]:
    rng = random.Random(config.seed)
    block_sizes = _balanced_block_sizes(config.num_nodes, config.num_blocks)
    community_labels = []
    for block, size in enumerate(block_sizes):
        community_labels.extend([block] * size)

    graphs = []
    for graph_index in range(config.num_graphs):
        graph = Graph(
            config.num_nodes,
            metadata={
                "family": config.family,
                "graph_index": graph_index,
                "community_labels": tuple(community_labels),
            },
        )
        for u in range(config.num_nodes):
            for v in range(u + 1, config.num_nodes):
                probability = config.p_in if community_labels[u] == community_labels[v] else config.p_out
                if rng.random() < probability:
                    graph.add_edge(u, v)
        graphs.append(graph)
    return graphs


def _generate_barabasi_albert(config: SyntheticDatasetConfig) -> list[Graph]:
    if config.m < 1:
        raise ValueError("Barabasi-Albert parameter m must be at least 1")
    if config.m >= config.num_nodes:
        raise ValueError("Barabasi-Albert parameter m must be smaller than num_nodes")

    rng = random.Random(config.seed)
    graphs = []
    for graph_index in range(config.num_graphs):
        graph = Graph(config.num_nodes, metadata={"family": config.family, "graph_index": graph_index})
        for u in range(config.m + 1):
            for v in range(u + 1, config.m + 1):
                graph.add_edge(u, v)

        repeated_nodes = []
        for node in range(config.m + 1):
            repeated_nodes.extend([node] * max(1, graph.degree(node)))

        for new_node in range(config.m + 1, config.num_nodes):
            targets: set[int] = set()
            while len(targets) < config.m:
                targets.add(rng.choice(repeated_nodes))
            for target in targets:
                graph.add_edge(new_node, target)
            repeated_nodes.extend(targets)
            repeated_nodes.extend([new_node] * graph.degree(new_node))
        graphs.append(graph)
    return graphs


def _balanced_block_sizes(num_nodes: int, num_blocks: int) -> list[int]:
    if num_blocks < 1:
        raise ValueError("num_blocks must be at least 1")
    base = num_nodes // num_blocks
    remainder = num_nodes % num_blocks
    return [base + (1 if block < remainder else 0) for block in range(num_blocks)]
