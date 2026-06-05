"""Small undirected graph utilities used by the experimentation module."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from itertools import combinations


Edge = tuple[int, int]


def normalize_edge(u: int, v: int) -> Edge:
    if u == v:
        raise ValueError("Self-loops are not supported")
    return (u, v) if u < v else (v, u)


@dataclass
class Graph:
    """Minimal undirected simple graph with integer node ids."""

    num_nodes: int
    adjacency: dict[int, set[int]] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for node in range(self.num_nodes):
            self.adjacency.setdefault(node, set())

    def copy(self) -> "Graph":
        return Graph(
            self.num_nodes,
            {node: set(neighbors) for node, neighbors in self.adjacency.items()},
            dict(self.metadata),
        )

    def add_edge(self, u: int, v: int) -> bool:
        u, v = normalize_edge(u, v)
        self._validate_node(u)
        self._validate_node(v)
        if v in self.adjacency[u]:
            return False
        self.adjacency[u].add(v)
        self.adjacency[v].add(u)
        return True

    def remove_edge(self, u: int, v: int) -> bool:
        u, v = normalize_edge(u, v)
        if v not in self.adjacency.get(u, set()):
            return False
        self.adjacency[u].remove(v)
        self.adjacency[v].remove(u)
        return True

    def has_edge(self, u: int, v: int) -> bool:
        u, v = normalize_edge(u, v)
        return v in self.adjacency.get(u, set())

    def edges(self) -> list[Edge]:
        return [(u, v) for u in range(self.num_nodes) for v in self.adjacency[u] if u < v]

    def non_edges(self) -> list[Edge]:
        return [
            (u, v)
            for u, v in combinations(range(self.num_nodes), 2)
            if v not in self.adjacency[u]
        ]

    def degree(self, node: int) -> int:
        self._validate_node(node)
        return len(self.adjacency[node])

    def degrees(self) -> list[int]:
        return [self.degree(node) for node in range(self.num_nodes)]

    def number_of_edges(self) -> int:
        return sum(len(neighbors) for neighbors in self.adjacency.values()) // 2

    def density(self) -> float:
        possible_edges = self.num_nodes * (self.num_nodes - 1) / 2
        if possible_edges == 0:
            return 0.0
        return self.number_of_edges() / possible_edges

    def connected_components(self) -> list[set[int]]:
        unseen = set(range(self.num_nodes))
        components: list[set[int]] = []
        while unseen:
            start = unseen.pop()
            component = {start}
            queue: deque[int] = deque([start])
            while queue:
                node = queue.popleft()
                for neighbor in self.adjacency[node]:
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        component.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
        return components

    def triangle_count(self) -> int:
        count = 0
        for u, v, w in combinations(range(self.num_nodes), 3):
            if self.has_edge(u, v) and self.has_edge(u, w) and self.has_edge(v, w):
                count += 1
        return count

    def triangle_edges(self) -> set[Edge]:
        edges: set[Edge] = set()
        for u, v, w in combinations(range(self.num_nodes), 3):
            if self.has_edge(u, v) and self.has_edge(u, w) and self.has_edge(v, w):
                edges.update({normalize_edge(u, v), normalize_edge(u, w), normalize_edge(v, w)})
        return edges

    def open_wedges(self) -> list[Edge]:
        wedges: set[Edge] = set()
        for center in range(self.num_nodes):
            for u, v in combinations(sorted(self.adjacency[center]), 2):
                if not self.has_edge(u, v):
                    wedges.add(normalize_edge(u, v))
        return sorted(wedges)

    def structurally_equal(self, other: "Graph") -> bool:
        return self.num_nodes == other.num_nodes and set(self.edges()) == set(other.edges())

    def _validate_node(self, node: int) -> None:
        if node < 0 or node >= self.num_nodes:
            raise ValueError(f"Node {node} is outside graph with {self.num_nodes} nodes")
