"""Edit-distance ground truth for validating the nominal ``alpha`` control.

``alpha`` is only a *nominal* dial: it sets the expected number of edge edits, but
the edits themselves are random. To check that ``alpha`` really tracks structural
distance we compare workflow scores against a cheap, exact, per-pair edit
distance computed from the logged perturbation operations — never the NP-hard
graph edit distance.

Two quantities are computed per perturbed pair and then averaged over the cell:

- **raw edit distance** — the number of edited edges, i.e. the size of the
  symmetric difference between the original and perturbed edge sets (each edge
  add or removal counts once). With the known node correspondence from the paired
  protocol this is the exact edit distance under the identity node map.
- **importance-weighted edit distance** — each edited edge is weighted by a
  topology importance score computed on the ORIGINAL graph, so that touching a
  hub/bridge edge counts for more than touching a peripheral edge. The weight
  function is pluggable; the default uses Brandes betweenness.
"""

from __future__ import annotations

from collections import deque
from typing import Callable

from experimentation.graph import Edge, Graph, normalize_edge


EditOp = tuple[str, int, int]
WeightFunction = Callable[[Edge], float]
WeightFactory = Callable[[Graph], WeightFunction]


def edited_edge_ops(original: Graph, perturbed: Graph) -> list[EditOp]:
    """Return the exact net edited edges as ``(op, u, v)`` tuples.

    Computed as the symmetric difference of the two edge sets, so an edge that
    was added and then removed within one perturbation correctly cancels out.
    """

    original_edges = set(original.edges())
    perturbed_edges = set(perturbed.edges())
    removed = sorted(original_edges - perturbed_edges)
    added = sorted(perturbed_edges - original_edges)
    return [("remove", u, v) for u, v in removed] + [("add", u, v) for u, v in added]


def brandes_betweenness(graph: Graph) -> tuple[list[float], dict[Edge, float]]:
    """Return (node betweenness list, edge betweenness dict) via Brandes' algorithm.

    Dependency-free, unweighted, undirected. Both centralities are halved to use
    the standard undirected convention (each shortest path counted once).
    """

    n = graph.num_nodes
    node_bc = [0.0] * n
    edge_bc: dict[Edge, float] = {}
    for source in range(n):
        stack: list[int] = []
        predecessors: list[list[int]] = [[] for _ in range(n)]
        sigma = [0.0] * n
        sigma[source] = 1.0
        distance = [-1] * n
        distance[source] = 0
        queue: deque[int] = deque([source])
        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in graph.adjacency[v]:
                if distance[w] < 0:
                    distance[w] = distance[v] + 1
                    queue.append(w)
                if distance[w] == distance[v] + 1:
                    sigma[w] += sigma[v]
                    predecessors[w].append(v)
        delta = [0.0] * n
        while stack:
            w = stack.pop()
            for v in predecessors[w]:
                contribution = (sigma[v] / sigma[w]) * (1.0 + delta[w])
                edge = normalize_edge(v, w)
                edge_bc[edge] = edge_bc.get(edge, 0.0) + contribution
                delta[v] += contribution
            if w != source:
                node_bc[w] += delta[w]
    node_bc = [value / 2.0 for value in node_bc]
    edge_bc = {edge: value / 2.0 for edge, value in edge_bc.items()}
    return node_bc, edge_bc


def edge_betweenness(graph: Graph) -> dict[Edge, float]:
    """Brandes edge betweenness for the edges present in the graph."""

    return brandes_betweenness(graph)[1]


def node_betweenness(graph: Graph) -> list[float]:
    """Brandes node betweenness centrality."""

    return brandes_betweenness(graph)[0]


def betweenness_product_weight(graph: Graph) -> WeightFunction:
    """Default weight: ``1 + cb[u]·cb[v]`` from normalized node betweenness.

    Defined for every node pair, so it weights edge *additions* (absent in the
    original) and *removals* on the same scale. Hub/bridge edges (both endpoints
    central) outweigh peripheral edges; the ``1 +`` baseline keeps the weighted
    distance monotone in the raw count. Runs Brandes once per graph.
    """

    node_bc, _ = brandes_betweenness(graph)
    max_bc = max(node_bc, default=0.0)
    if max_bc > 0.0:
        normalized = [value / max_bc for value in node_bc]
    else:
        normalized = [0.0] * len(node_bc)

    def weight(edge: Edge) -> float:
        u, v = edge
        return 1.0 + normalized[u] * normalized[v]

    return weight


def edge_betweenness_weight(graph: Graph) -> WeightFunction:
    """Literal Brandes edge betweenness as the weight (absent edges weigh 0).

    Exact for edge *removals*; edge *additions* get weight 0 because edge
    betweenness is undefined for absent edges. Use ``betweenness_product_weight``
    (the default) when a perturbation adds edges.
    """

    _, edge_bc = brandes_betweenness(graph)

    def weight(edge: Edge) -> float:
        return edge_bc.get(edge, 0.0)

    return weight


WEIGHT_FACTORIES: dict[str, WeightFactory] = {
    "betweenness_product": betweenness_product_weight,
    "edge_betweenness": edge_betweenness_weight,
}
DEFAULT_WEIGHT_FACTORY = betweenness_product_weight


def pair_edit_distances(
    original: Graph,
    edited_edges: list[EditOp],
    weight_factory: WeightFactory = DEFAULT_WEIGHT_FACTORY,
) -> tuple[int, float]:
    """Return ``(raw, weighted)`` edit distance for one perturbed pair."""

    raw = len(edited_edges)
    if raw == 0:
        return 0, 0.0
    weight = weight_factory(original)
    weighted = sum(weight(normalize_edge(u, v)) for _op, u, v in edited_edges)
    return raw, weighted


def cell_edit_distances(
    paired,
    weight_factory: WeightFactory = DEFAULT_WEIGHT_FACTORY,
) -> tuple[float | None, float | None]:
    """Return the cell-mean ``(raw, weighted)`` edit distance over all pairs.

    Reads each pair's ``edited_edges`` from the perturbation metadata (recorded by
    ``perturb_graph``) and weights them on the corresponding original graph. The
    Brandes pass is skipped for pairs with no edits (e.g. ``alpha == 0``).
    """

    metadata = paired.metadata.get("perturbations", [])
    pairs = paired.pairs
    if not pairs:
        return None, None
    raw_values: list[float] = []
    weighted_values: list[float] = []
    for (original, _perturbed), meta in zip(pairs, metadata):
        edited = list(meta.get("edited_edges", []))
        raw, weighted = pair_edit_distances(original, edited, weight_factory)
        raw_values.append(float(raw))
        weighted_values.append(float(weighted))
    if not raw_values:
        return None, None
    return (
        sum(raw_values) / len(raw_values),
        sum(weighted_values) / len(weighted_values),
    )
