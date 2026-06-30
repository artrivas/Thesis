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
    if perturbation_type == "edge_insertion":
        return _edge_insertion(graph, alpha, seed)
    if perturbation_type == "edge_deletion":
        return _edge_deletion(graph, alpha, seed)
    if perturbation_type == "edge_addition_deletion":
        return _edge_addition_deletion(graph, alpha, seed)
    if perturbation_type == "triangle_insertion":
        return _triangle_insertion(graph, alpha, seed)
    if perturbation_type == "triangle_deletion":
        return _triangle_deletion(graph, alpha, seed)
    if perturbation_type == "triangle_injection_removal":
        return _triangle_injection_removal(graph, alpha, seed)
    if perturbation_type == "community_weakening":
        return _community_weakening(graph, alpha, seed, context)
    if perturbation_type == "hub_modification":
        return _hub_modification(graph, alpha, seed)
    raise ValueError(f"Unknown perturbation type: {perturbation_type}")


def _base_metadata(
    alpha: float,
    perturbation_type: str,
    *,
    family: str | None = None,
    direction: str | None = None,
) -> dict[str, object]:
    return {
        "perturbation_type": perturbation_type,
        "perturbation_family": family or perturbation_type,
        "perturbation_direction": direction or "mixed",
        "alpha": alpha,
        "edges_added": 0,
        "edges_removed": 0,
        "rewires": 0,
        "triangles_affected": 0,
        "status": "success",
        "error_message": None,
    }


def _edge_insertion(graph: Graph, alpha: float, seed: int) -> PerturbationResult:
    rng = random.Random(seed)
    perturbed = graph.copy()
    info = _base_metadata(alpha, "edge_insertion", family="edge", direction="insertion")
    additions = math.floor(alpha * graph.number_of_edges())
    if additions == 0:
        return PerturbationResult(perturbed, info)

    non_edges = graph.non_edges()
    rng.shuffle(non_edges)
    for u, v in non_edges[: min(additions, len(non_edges))]:
        if perturbed.add_edge(u, v):
            info["edges_added"] = int(info["edges_added"]) + 1
    return PerturbationResult(perturbed, info)


def _edge_deletion(graph: Graph, alpha: float, seed: int) -> PerturbationResult:
    rng = random.Random(seed)
    perturbed = graph.copy()
    info = _base_metadata(alpha, "edge_deletion", family="edge", direction="deletion")
    removals = math.floor(alpha * graph.number_of_edges())
    if removals == 0:
        return PerturbationResult(perturbed, info)

    edges = graph.edges()
    rng.shuffle(edges)
    for u, v in edges[: min(removals, len(edges))]:
        if perturbed.remove_edge(u, v):
            info["edges_removed"] = int(info["edges_removed"]) + 1
    return PerturbationResult(perturbed, info)


def _edge_addition_deletion(graph: Graph, alpha: float, seed: int) -> PerturbationResult:
    rng = random.Random(seed)
    perturbed = graph.copy()
    info = _base_metadata(alpha, "edge_addition_deletion", family="edge", direction="mixed")
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


def _triangle_insertion(graph: Graph, alpha: float, seed: int) -> PerturbationResult:
    rng = random.Random(seed)
    perturbed = graph.copy()
    info = _base_metadata(alpha, "triangle_insertion", family="triangle", direction="insertion")
    budget = math.floor(alpha * max(1, graph.number_of_edges()))
    if budget == 0:
        return PerturbationResult(perturbed, info)

    open_wedges = graph.open_wedges()
    rng.shuffle(open_wedges)
    for u, v in open_wedges[: min(budget, len(open_wedges))]:
        if perturbed.add_edge(u, v):
            info["edges_added"] = int(info["edges_added"]) + 1
            info["triangles_affected"] = int(info["triangles_affected"]) + 1
    return PerturbationResult(perturbed, info)


def _triangle_deletion(graph: Graph, alpha: float, seed: int) -> PerturbationResult:
    rng = random.Random(seed)
    perturbed = graph.copy()
    info = _base_metadata(alpha, "triangle_deletion", family="triangle", direction="deletion")
    budget = math.floor(alpha * max(1, graph.number_of_edges()))
    if budget == 0:
        return PerturbationResult(perturbed, info)

    triangle_edges = list(graph.triangle_edges())
    rng.shuffle(triangle_edges)
    removed = 0
    for u, v in triangle_edges:
        if removed >= budget:
            break
        if perturbed.remove_edge(u, v):
            removed += 1
            info["edges_removed"] = int(info["edges_removed"]) + 1
            info["triangles_affected"] = int(info["triangles_affected"]) + 1
    return PerturbationResult(perturbed, info)


def _triangle_injection_removal(graph: Graph, alpha: float, seed: int) -> PerturbationResult:
    rng = random.Random(seed)
    perturbed = graph.copy()
    info = _base_metadata(alpha, "triangle_injection_removal", family="triangle", direction="mixed")
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
    info = _base_metadata(alpha, "community_weakening", family="community", direction="weakening")
    labels = metadata.get("community_labels") or graph.metadata.get("community_labels")
    if labels is not None:
        # Ground-truth blocks (e.g. the SBM planted partition).
        labels = tuple(labels)
        info["label_source"] = "ground_truth"
    else:
        # No planted partition (ER/BA): detect communities so the perturbation
        # is always applicable. On a structureless graph the detected partition
        # is essentially noise, which is the intended negative control.
        labels = detect_communities(graph)
        info["label_source"] = "detected"
    info["num_communities"] = len(set(labels))

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
    info = _base_metadata(alpha, "hub_modification", family="hub", direction="modification")
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


def detect_communities(graph: Graph) -> tuple[int, ...]:
    """Detect communities by greedy modularity maximization (Clauset-Newman-Moore).

    Dependency-free agglomerative maximization of Newman's modularity. Every node
    starts in its own community; on each step the pair of adjacent communities
    whose merge yields the largest positive modularity gain is merged, stopping
    when no merge improves modularity. Returns a community label per node with
    contiguous ids starting at ``0``.

    The merge gain for communities ``c`` and ``d`` is

        dQ(c, d) = B_cd / m  -  (D_c * D_d) / (2 * m^2)

    where ``B_cd`` is the number of edges between the communities, ``D_c`` the
    total degree of community ``c`` and ``m`` the edge count. The procedure is
    deterministic: ties are broken toward the lowest community ids.
    """

    n = graph.num_nodes
    if n == 0:
        return ()
    community_of = list(range(n))
    m = graph.number_of_edges()
    if m == 0:
        return _contiguous_labels(community_of)

    degree = {node: graph.degree(node) for node in range(n)}
    between: dict[int, dict[int, int]] = {node: {} for node in range(n)}
    for u, v in graph.edges():
        between[u][v] = between[u].get(v, 0) + 1
        between[v][u] = between[v].get(u, 0) + 1

    members: dict[int, set[int]] = {node: {node} for node in range(n)}
    active = set(range(n))
    two_m_squared = 2.0 * m * m
    while len(active) > 1:
        best_gain = 1e-12
        best_pair: tuple[int, int] | None = None
        for c in sorted(active):
            degree_c = degree[c]
            for d, edges_between in sorted(between[c].items()):
                if d <= c:
                    continue
                gain = edges_between / m - (degree_c * degree[d]) / two_m_squared
                if gain > best_gain:
                    best_gain = gain
                    best_pair = (c, d)
        if best_pair is None:
            break
        c, d = best_pair
        members[c] |= members[d]
        degree[c] += degree[d]
        for neighbor, edges_between in between[d].items():
            if neighbor == c:
                continue
            between[c][neighbor] = between[c].get(neighbor, 0) + edges_between
            between[neighbor][c] = between[neighbor].get(c, 0) + edges_between
            between[neighbor].pop(d, None)
        between[c].pop(d, None)
        between.pop(d, None)
        for node in members[d]:
            community_of[node] = c
        active.discard(d)
    return _contiguous_labels(community_of)


def _contiguous_labels(community_of: list[int]) -> tuple[int, ...]:
    remap: dict[int, int] = {}
    labels = []
    for community in community_of:
        if community not in remap:
            remap[community] = len(remap)
        labels.append(remap[community])
    return tuple(labels)
