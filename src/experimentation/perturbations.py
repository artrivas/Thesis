"""Controlled perturbations for paired synthetic graph experiments."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from experimentation.graph import Edge, Graph, normalize_edge


@dataclass(frozen=True)
class PerturbationResult:
    graph: Graph
    metadata: dict[str, object]


def perturb_graph(
    graph: Graph,
    alpha: float,
    perturbation_type: str,
    seed: int,
    metadata: dict[str, object] | None = None,
) -> PerturbationResult:
    """Return a perturbed copy of a graph and metadata about the changes."""

    if alpha < 0.0 or alpha > 1.0:
        raise ValueError("alpha must be between 0.0 and 1.0")
    context = metadata or {}
    if perturbation_type == "edge_addition_deletion":
        return _edge_addition_deletion(graph, alpha, seed)
    if perturbation_type == "triangle_injection_removal":
        return _triangle_injection_removal(graph, alpha, seed)
    if perturbation_type == "community_weakening":
        return _community_weakening(graph, alpha, seed, context)
    if perturbation_type == "hub_modification":
        return _hub_modification(graph, alpha, seed)
    raise ValueError(f"Unknown perturbation type: {perturbation_type}")


def _base_metadata(alpha: float, perturbation_type: str) -> dict[str, object]:
    return {
        "perturbation_type": perturbation_type,
        "alpha": alpha,
        "edges_added": 0,
        "edges_removed": 0,
        "rewires": 0,
        "triangles_affected": 0,
        "status": "success",
        "error_message": None,
    }


def _edge_addition_deletion(graph: Graph, alpha: float, seed: int) -> PerturbationResult:
    rng = random.Random(seed)
    perturbed = graph.copy()
    info = _base_metadata(alpha, "edge_addition_deletion")
    edge_count = graph.number_of_edges()
    changes = math.floor(alpha * edge_count)
    if changes == 0:
        return PerturbationResult(perturbed, info)

    edges = graph.edges()
    rng.shuffle(edges)
    remove_count = min(len(edges), changes // 2)
    for u, v in edges[:remove_count]:
        if perturbed.remove_edge(u, v):
            info["edges_removed"] = int(info["edges_removed"]) + 1

    non_edges = graph.non_edges()
    rng.shuffle(non_edges)
    add_count = min(len(non_edges), changes - remove_count)
    for u, v in non_edges[:add_count]:
        if perturbed.add_edge(u, v):
            info["edges_added"] = int(info["edges_added"]) + 1
    return PerturbationResult(perturbed, info)


def _triangle_injection_removal(graph: Graph, alpha: float, seed: int) -> PerturbationResult:
    rng = random.Random(seed)
    perturbed = graph.copy()
    info = _base_metadata(alpha, "triangle_injection_removal")
    budget = math.floor(alpha * max(1, graph.number_of_edges()))
    if budget == 0:
        return PerturbationResult(perturbed, info)

    open_wedges = graph.open_wedges()
    rng.shuffle(open_wedges)
    injection_budget = budget // 2 + budget % 2
    for u, v in open_wedges[:injection_budget]:
        if perturbed.add_edge(u, v):
            info["edges_added"] = int(info["edges_added"]) + 1
            info["triangles_affected"] = int(info["triangles_affected"]) + 1

    triangle_edges = list(perturbed.triangle_edges())
    rng.shuffle(triangle_edges)
    removal_budget = budget // 2
    removed = 0
    for u, v in triangle_edges:
        if removed >= removal_budget:
            break
        if perturbed.remove_edge(u, v):
            removed += 1
            info["edges_removed"] = int(info["edges_removed"]) + 1
            info["triangles_affected"] = int(info["triangles_affected"]) + 1
    return PerturbationResult(perturbed, info)


def _community_weakening(
    graph: Graph,
    alpha: float,
    seed: int,
    metadata: dict[str, object],
) -> PerturbationResult:
    rng = random.Random(seed)
    perturbed = graph.copy()
    info = _base_metadata(alpha, "community_weakening")
    labels = metadata.get("community_labels") or graph.metadata.get("community_labels")
    if labels is None:
        info["status"] = "skipped"
        info["error_message"] = "community_weakening requires community_labels metadata"
        return PerturbationResult(perturbed, info)

    labels = tuple(labels)
    intra_edges = [(u, v) for u, v in graph.edges() if labels[u] == labels[v]]
    rewires = math.floor(alpha * len(intra_edges))
    rng.shuffle(intra_edges)
    inter_non_edges = [
        (u, v)
        for u, v in perturbed.non_edges()
        if labels[u] != labels[v]
    ]
    rng.shuffle(inter_non_edges)
    rewires = min(rewires, len(inter_non_edges))

    for (old_u, old_v), (new_u, new_v) in zip(intra_edges[:rewires], inter_non_edges[:rewires]):
        if perturbed.remove_edge(old_u, old_v):
            info["edges_removed"] = int(info["edges_removed"]) + 1
            if perturbed.add_edge(new_u, new_v):
                info["edges_added"] = int(info["edges_added"]) + 1
                info["rewires"] = int(info["rewires"]) + 1
    return PerturbationResult(perturbed, info)


def _hub_modification(graph: Graph, alpha: float, seed: int) -> PerturbationResult:
    rng = random.Random(seed)
    perturbed = graph.copy()
    info = _base_metadata(alpha, "hub_modification")
    edge_count = graph.number_of_edges()
    budget = math.floor(alpha * edge_count)
    if budget == 0 or edge_count == 0:
        info["target_hubs"] = ()
        return PerturbationResult(perturbed, info)

    degrees = graph.degrees()
    hub_count = max(1, math.ceil(0.1 * graph.num_nodes))
    hubs = tuple(node for node, _ in sorted(enumerate(degrees), key=lambda item: item[1], reverse=True)[:hub_count])
    info["target_hubs"] = hubs

    hub_edges = [edge for edge in graph.edges() if edge[0] in hubs or edge[1] in hubs]
    rng.shuffle(hub_edges)
    removals = min(budget, len(hub_edges))
    removed_edges: set[Edge] = set()
    for u, v in hub_edges[:removals]:
        if perturbed.remove_edge(u, v):
            removed_edges.add(normalize_edge(u, v))
            info["edges_removed"] = int(info["edges_removed"]) + 1

    candidates: list[Edge] = []
    for hub in hubs:
        for node in range(graph.num_nodes):
            if node == hub:
                continue
            edge = normalize_edge(hub, node)
            if edge not in removed_edges and not perturbed.has_edge(hub, node):
                candidates.append(edge)
    rng.shuffle(candidates)
    additions = min(removals, len(candidates))
    seen: set[Edge] = set()
    for edge in candidates:
        if int(info["edges_added"]) >= additions:
            break
        if edge in seen:
            continue
        seen.add(edge)
        if perturbed.add_edge(*edge):
            info["edges_added"] = int(info["edges_added"]) + 1
            info["rewires"] = int(info["rewires"]) + 1
    return PerturbationResult(perturbed, info)
