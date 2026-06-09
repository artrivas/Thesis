"""Workflow implementations for graph distribution comparison."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import hashlib
import math
import time
from typing import Iterable

from experimentation.graph import Edge, Graph, normalize_edge


Vector = list[float]
SparseVector = dict[str, float]
Representation = Vector | SparseVector

_DEVICE_PREFERENCE = "auto"


def configure_acceleration(device: str = "auto") -> None:
    """Configure optional tensor acceleration for supported workflow internals."""

    normalized = device.strip().lower()
    if normalized not in {"auto", "cpu"} and not normalized.startswith("cuda"):
        raise ValueError("device must be 'auto', 'cpu', 'cuda', or a CUDA device such as 'cuda:0'")
    global _DEVICE_PREFERENCE
    _DEVICE_PREFERENCE = normalized


def acceleration_summary() -> str:
    """Return a short description of the active acceleration preference."""

    if _DEVICE_PREFERENCE == "cpu":
        return "cpu"
    torch = _import_torch()
    if torch is None:
        return f"{_DEVICE_PREFERENCE} requested; torch not installed"
    if _DEVICE_PREFERENCE.startswith("cuda"):
        return f"{_DEVICE_PREFERENCE} requested; cuda_available={torch.cuda.is_available()}"
    if torch.cuda.is_available():
        return f"auto using cuda:{torch.cuda.current_device()}"
    return "auto using cpu fallback"


def squared_l2(left: Vector, right: Vector) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right))


def l2(left: Vector, right: Vector) -> float:
    return math.sqrt(squared_l2(left, right))


def dense_mean(vectors: list[Vector]) -> Vector:
    if not vectors:
        return []
    width = len(vectors[0])
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(width)]


def sparse_dot(left: SparseVector, right: SparseVector) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(key, 0.0) for key, value in left.items())


def sparse_norm_squared(vector: SparseVector) -> float:
    return sum(value * value for value in vector.values())


def sparse_l2(left: SparseVector, right: SparseVector) -> float:
    keys = set(left) | set(right)
    return math.sqrt(sum((left.get(key, 0.0) - right.get(key, 0.0)) ** 2 for key in keys))


def sparse_mean(vectors: list[SparseVector]) -> SparseVector:
    if not vectors:
        return {}
    total: Counter[str] = Counter()
    for vector in vectors:
        total.update(vector)
    return {key: value / len(vectors) for key, value in total.items()}


def rbf_mmd(vectors_x: list[Vector], vectors_y: list[Vector], bandwidth: float = 1.0) -> float:
    if not vectors_x or not vectors_y:
        return 0.0
    gamma = 1.0 / (2.0 * bandwidth * bandwidth)

    def kernel(a: Vector, b: Vector) -> float:
        return math.exp(-gamma * squared_l2(a, b))

    xx = sum(kernel(a, b) for a in vectors_x for b in vectors_x) / (len(vectors_x) ** 2)
    yy = sum(kernel(a, b) for a in vectors_y for b in vectors_y) / (len(vectors_y) ** 2)
    xy = sum(kernel(a, b) for a in vectors_x for b in vectors_y) / (len(vectors_x) * len(vectors_y))
    return max(0.0, xx + yy - 2.0 * xy)


def sparse_linear_mmd(vectors_x: list[SparseVector], vectors_y: list[SparseVector]) -> float:
    mean_x = sparse_mean(vectors_x)
    mean_y = sparse_mean(vectors_y)
    return sparse_l2(mean_x, mean_y) ** 2


@dataclass
class Workflow:
    name: str

    def compute_representations(self, graphs: list[Graph]):
        raise NotImplementedError

    def distribution_score(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> float:
        raise NotImplementedError

    def distribution_score_from_representations(
        self,
        original: list[Representation],
        perturbed: list[Representation],
    ) -> float:
        raise NotImplementedError

    def mean_shift_score(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> float:
        original = self.compute_representations(original_graphs)
        perturbed = self.compute_representations(perturbed_graphs)
        return representation_mean_distance(original, perturbed)

    def paired_score(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> float:
        original = self.compute_representations(original_graphs)
        perturbed = self.compute_representations(perturbed_graphs)
        if len(original) != len(perturbed):
            raise ValueError("paired_score requires equal-size graph distributions")
        if not original:
            return 0.0
        return sum(representation_distance(a, b) for a, b in zip(original, perturbed)) / len(original)

    def run(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> dict[str, object]:
        start = time.perf_counter()
        try:
            if self._uses_cached_representations():
                original = self.compute_representations(original_graphs)
                perturbed = self.compute_representations(perturbed_graphs)
                distribution = self.distribution_score_from_representations(original, perturbed)
                mean_shift = representation_mean_distance(original, perturbed)
                paired = paired_representation_distance(original, perturbed)
            else:
                distribution = self.distribution_score(original_graphs, perturbed_graphs)
                mean_shift = self.mean_shift_score(original_graphs, perturbed_graphs)
                paired = self.paired_score(original_graphs, perturbed_graphs)
            status = "success"
            error_message = None
        except Exception as exc:  # pragma: no cover - tested through status behavior in orchestration later.
            distribution = None
            mean_shift = None
            paired = None
            status = "failed"
            error_message = str(exc)
        return {
            "workflow": self.name,
            "distribution_score": distribution,
            "mean_shift_score": mean_shift,
            "paired_score": paired,
            "runtime_seconds": time.perf_counter() - start,
            "memory_mb": None,
            "status": status,
            "error_message": error_message,
        }

    def _uses_cached_representations(self) -> bool:
        return type(self).distribution_score_from_representations is not Workflow.distribution_score_from_representations


@dataclass
class StructuralStatisticsMMDWorkflow(Workflow):
    bandwidth: float = 10.0

    def __init__(self, bandwidth: float = 10.0) -> None:
        super().__init__("structural_statistics_mmd")
        self.bandwidth = bandwidth

    def compute_representations(self, graphs: list[Graph]) -> list[Vector]:
        return [structural_statistics(graph) for graph in graphs]

    def distribution_score(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> float:
        return self.distribution_score_from_representations(
            self.compute_representations(original_graphs),
            self.compute_representations(perturbed_graphs),
        )

    def distribution_score_from_representations(
        self,
        original: list[Representation],
        perturbed: list[Representation],
    ) -> float:
        return rbf_mmd(original, perturbed, self.bandwidth)  # type: ignore[arg-type]


@dataclass
class WLSubtreeMMDWorkflow(Workflow):
    iterations: int = 3

    def __init__(self, iterations: int = 3) -> None:
        super().__init__("wl_subtree_kernel_mmd")
        self.iterations = iterations

    def compute_representations(self, graphs: list[Graph]) -> list[SparseVector]:
        return [wl_features(graph, self.iterations) for graph in graphs]

    def distribution_score(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> float:
        return self.distribution_score_from_representations(
            self.compute_representations(original_graphs),
            self.compute_representations(perturbed_graphs),
        )

    def distribution_score_from_representations(
        self,
        original: list[Representation],
        perturbed: list[Representation],
    ) -> float:
        return sparse_linear_mmd(original, perturbed)  # type: ignore[arg-type]


@dataclass
class NetLSDWorkflow(Workflow):
    timescales: tuple[float, ...] = tuple(10 ** (-2 + i * 4 / 15) for i in range(16))
    bandwidth: float = 10.0

    def __init__(self, timescales: Iterable[float] | None = None, bandwidth: float = 10.0) -> None:
        super().__init__("netlsd_spectral_signatures")
        if timescales is not None:
            self.timescales = tuple(timescales)
        self.bandwidth = bandwidth

    def compute_representations(self, graphs: list[Graph]) -> list[Vector]:
        return [netlsd_signature(graph, self.timescales) for graph in graphs]

    def distribution_score(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> float:
        return self.distribution_score_from_representations(
            self.compute_representations(original_graphs),
            self.compute_representations(perturbed_graphs),
        )

    def distribution_score_from_representations(
        self,
        original: list[Representation],
        perturbed: list[Representation],
    ) -> float:
        return rbf_mmd(original, perturbed, self.bandwidth)  # type: ignore[arg-type]


@dataclass
class DiversityCurvesWorkflow(Workflow):
    max_scales: int = 4
    repetitions: int = 3

    def __init__(self, max_scales: int = 4, repetitions: int = 3) -> None:
        super().__init__("diversity_curves_shortest_path")
        self.max_scales = max_scales
        self.repetitions = repetitions

    def compute_representations(self, graphs: list[Graph]) -> list[Vector]:
        return [diversity_curve(graph, self.max_scales, self.repetitions) for graph in graphs]

    def distribution_score(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> float:
        return self.distribution_score_from_representations(
            self.compute_representations(original_graphs),
            self.compute_representations(perturbed_graphs),
        )

    def distribution_score_from_representations(
        self,
        original: list[Representation],
        perturbed: list[Representation],
    ) -> float:
        return l2(dense_mean(original), dense_mean(perturbed))  # type: ignore[arg-type]


def default_workflows() -> list[Workflow]:
    return [
        StructuralStatisticsMMDWorkflow(),
        WLSubtreeMMDWorkflow(),
        NetLSDWorkflow(),
        DiversityCurvesWorkflow(),
    ]


def structural_statistics(graph: Graph) -> Vector:
    degrees = graph.degrees()
    node_count = graph.num_nodes
    edge_count = graph.number_of_edges()
    average_degree = sum(degrees) / node_count if node_count else 0.0
    degree_variance = (
        sum((degree - average_degree) ** 2 for degree in degrees) / node_count
        if node_count
        else 0.0
    )
    triangles = graph.triangle_count()
    connected_triples = sum(degree * (degree - 1) / 2 for degree in degrees)
    transitivity = (3 * triangles / connected_triples) if connected_triples else 0.0
    return [
        float(node_count),
        float(edge_count),
        graph.density(),
        average_degree,
        degree_variance,
        average_clustering(graph),
        float(triangles),
        transitivity,
        float(len(graph.connected_components())),
    ]


def average_clustering(graph: Graph) -> float:
    values = []
    for node in range(graph.num_nodes):
        neighbors = sorted(graph.adjacency[node])
        possible = len(neighbors) * (len(neighbors) - 1) / 2
        if possible == 0:
            values.append(0.0)
            continue
        actual = 0
        for index, u in enumerate(neighbors):
            for v in neighbors[index + 1 :]:
                if graph.has_edge(u, v):
                    actual += 1
        values.append(actual / possible)
    return sum(values) / len(values) if values else 0.0


def wl_features(graph: Graph, iterations: int) -> SparseVector:
    labels = {node: f"d{graph.degree(node)}" for node in range(graph.num_nodes)}
    features: Counter[str] = Counter(labels.values())
    for iteration in range(iterations):
        signatures = {}
        for node in range(graph.num_nodes):
            neighbor_labels = sorted(labels[neighbor] for neighbor in graph.adjacency[node])
            signatures[node] = f"{labels[node]}|{'/'.join(neighbor_labels)}"
        labels = {node: f"i{iteration}:{signature}" for node, signature in signatures.items()}
        features.update(labels.values())
    return dict(features)


def netlsd_signature(graph: Graph, timescales: Iterable[float]) -> Vector:
    eigenvalues = normalized_laplacian_eigenvalues(graph)
    return [sum(math.exp(-time_value * eigenvalue) for eigenvalue in eigenvalues) for time_value in timescales]


def normalized_laplacian_eigenvalues(graph: Graph) -> list[float]:
    accelerated = _accelerated_laplacian_eigenvalues(graph)
    if accelerated is not None:
        return accelerated

    n = graph.num_nodes
    if n == 0:
        return []
    degrees = graph.degrees()
    matrix = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 0.0 if degrees[i] == 0 else 1.0
    for u, v in graph.edges():
        if degrees[u] and degrees[v]:
            value = -1.0 / math.sqrt(degrees[u] * degrees[v])
            matrix[u][v] = value
            matrix[v][u] = value
    return jacobi_eigenvalues(matrix)


def jacobi_eigenvalues(matrix: list[list[float]], tolerance: float = 1e-10, max_iterations: int = 1000) -> list[float]:
    n = len(matrix)
    if n <= 1:
        return [matrix[0][0]] if n else []
    a = [row[:] for row in matrix]
    for _ in range(max_iterations):
        p, q = 0, 1
        max_value = abs(a[p][q])
        for i in range(n):
            for j in range(i + 1, n):
                if abs(a[i][j]) > max_value:
                    p, q = i, j
                    max_value = abs(a[i][j])
        if max_value < tolerance:
            break
        if abs(a[p][p] - a[q][q]) < tolerance:
            angle = math.pi / 4
        else:
            angle = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c = math.cos(angle)
        s = math.sin(angle)
        app = c * c * a[p][p] - 2 * s * c * a[p][q] + s * s * a[q][q]
        aqq = s * s * a[p][p] + 2 * s * c * a[p][q] + c * c * a[q][q]
        a[p][q] = 0.0
        a[q][p] = 0.0
        for r in range(n):
            if r not in (p, q):
                arp = c * a[r][p] - s * a[r][q]
                arq = s * a[r][p] + c * a[r][q]
                a[r][p] = a[p][r] = arp
                a[r][q] = a[q][r] = arq
        a[p][p] = app
        a[q][q] = aqq
    return sorted(max(0.0, a[i][i]) for i in range(n))


def diversity_curve(graph: Graph, max_scales: int, repetitions: int = 3) -> Vector:
    """Compute spread over deterministic edge-contraction levels.

    The spread at each level uses graph shortest-path distances. Multiple
    deterministic pseudo-random contraction orders approximate the repeated
    random coarsening used by the reference diversity-curves method while
    keeping experiment rows reproducible.
    """

    if max_scales < 1:
        raise ValueError("max_scales must be at least 1")
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    if graph.num_nodes == 0:
        return [0.0] * max_scales

    scales = _diversity_scales(graph.num_nodes, max_scales)
    totals = [0.0 for _ in scales]
    for repeat in range(repetitions):
        values = _diversity_curve_once(graph, scales, repeat)
        for index, value in enumerate(values):
            totals[index] += value
    return [value / repetitions for value in totals]


def shortest_path_spread(graph: Graph) -> float:
    distances = all_pairs_shortest_path_distances(graph)
    spread = 0.0
    for row in distances:
        denominator = sum(math.exp(-distance) for distance in row if math.isfinite(distance))
        if denominator > 0.0:
            spread += 1.0 / denominator
    return spread


def all_pairs_shortest_path_distances(graph: Graph) -> list[list[float]]:
    distances = []
    for source in range(graph.num_nodes):
        row = [math.inf] * graph.num_nodes
        row[source] = 0.0
        queue: deque[int] = deque([source])
        while queue:
            node = queue.popleft()
            for neighbor in graph.adjacency[node]:
                if math.isinf(row[neighbor]):
                    row[neighbor] = row[node] + 1.0
                    queue.append(neighbor)
        distances.append(row)
    return distances


def _diversity_scales(num_nodes: int, max_scales: int) -> list[int]:
    count = min(max_scales, num_nodes)
    if count == 1:
        return [num_nodes]
    raw_scales = [
        1 + round(index * (num_nodes - 1) / (count - 1))
        for index in range(count)
    ]
    return sorted(set(raw_scales))


def _diversity_curve_once(graph: Graph, scales: list[int], repeat: int) -> Vector:
    values_by_scale: dict[int, float] = {}
    current = graph.copy()
    for scale in sorted(scales, reverse=True):
        current = _coarsen_to_scale(current, scale, repeat)
        values_by_scale[scale] = shortest_path_spread(current)

    components = len(graph.connected_components())
    known_scales = sorted(values_by_scale)
    first_reachable = next((scale for scale in known_scales if scale >= components), None)
    if first_reachable is not None and first_reachable > 1:
        first_value = values_by_scale[first_reachable]
        for scale in known_scales:
            if scale < first_reachable:
                values_by_scale[scale] = _linear_interpolate(scale, 1, 1.0, first_reachable, first_value)
    return [values_by_scale[scale] for scale in scales]


def _coarsen_to_scale(graph: Graph, target_nodes: int, repeat: int) -> Graph:
    current = graph.copy()
    while current.num_nodes > target_nodes and current.number_of_edges() > 0:
        edge = _selected_contraction_edge(current, repeat)
        current = contract_edge(current, edge)
    return current


def _selected_contraction_edge(graph: Graph, repeat: int) -> Edge:
    edges = graph.edges()
    if not edges:
        raise ValueError("Cannot select a contraction edge from an edgeless graph")
    graph_signature = f"{repeat}|{graph.num_nodes}|{sorted(edges)}"
    return min(edges, key=lambda edge: _edge_priority(graph_signature, edge))


def _edge_priority(graph_signature: str, edge: Edge) -> str:
    payload = f"{graph_signature}|{edge}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def contract_edge(graph: Graph, edge: Edge) -> Graph:
    u, v = normalize_edge(*edge)
    if not graph.has_edge(u, v):
        raise ValueError(f"Cannot contract missing edge {(u, v)}")
    if graph.num_nodes <= 1:
        return graph.copy()

    mapping = {}
    next_node = 0
    for node in range(graph.num_nodes):
        if node == v:
            continue
        mapping[node] = next_node
        next_node += 1
    merged = mapping[u]
    contracted = Graph(graph.num_nodes - 1, metadata=dict(graph.metadata))
    for left, right in graph.edges():
        mapped_left = merged if left == v else mapping[left]
        mapped_right = merged if right == v else mapping[right]
        if mapped_left != mapped_right:
            contracted.add_edge(mapped_left, mapped_right)
    return contracted


def _linear_interpolate(x: int, x0: int, y0: float, x1: int, y1: float) -> float:
    if x1 == x0:
        return y1
    return y0 + (y1 - y0) * ((x - x0) / (x1 - x0))


def representation_distance(left, right) -> float:
    if isinstance(left, dict) and isinstance(right, dict):
        return sparse_l2(left, right)
    return l2(left, right)


def representation_mean_distance(original, perturbed) -> float:
    if not original or not perturbed:
        return 0.0
    if isinstance(original[0], dict):
        return sparse_l2(sparse_mean(original), sparse_mean(perturbed))
    return l2(dense_mean(original), dense_mean(perturbed))


def paired_representation_distance(original, perturbed) -> float:
    if len(original) != len(perturbed):
        raise ValueError("paired_score requires equal-size graph distributions")
    if not original:
        return 0.0
    return sum(representation_distance(a, b) for a, b in zip(original, perturbed)) / len(original)


def _accelerated_laplacian_eigenvalues(graph: Graph) -> list[float] | None:
    device_name = _torch_device_name()
    if device_name is None:
        return None

    torch = _import_torch()
    if torch is None:
        if _DEVICE_PREFERENCE.startswith("cuda"):
            raise RuntimeError("CUDA device was requested, but torch is not installed")
        return None

    n = graph.num_nodes
    if n == 0:
        return []
    device = torch.device(device_name)
    degrees = graph.degrees()
    matrix = torch.zeros((n, n), dtype=torch.float64, device=device)
    degree_tensor = torch.tensor(degrees, dtype=torch.float64, device=device)
    diagonal = torch.arange(n, device=device)
    matrix[diagonal, diagonal] = torch.where(
        degree_tensor == 0,
        torch.zeros_like(degree_tensor),
        torch.ones_like(degree_tensor),
    )
    for u, v in graph.edges():
        if degrees[u] and degrees[v]:
            value = -1.0 / math.sqrt(degrees[u] * degrees[v])
            matrix[u, v] = value
            matrix[v, u] = value
    eigenvalues = torch.linalg.eigvalsh(matrix)
    return sorted(max(0.0, float(value)) for value in eigenvalues.detach().cpu().tolist())


def _torch_device_name() -> str | None:
    if _DEVICE_PREFERENCE == "cpu":
        return None
    torch = _import_torch()
    if torch is None:
        if _DEVICE_PREFERENCE.startswith("cuda"):
            return _DEVICE_PREFERENCE
        return None
    if _DEVICE_PREFERENCE.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError(f"{_DEVICE_PREFERENCE} was requested, but CUDA is not available to torch")
        return _DEVICE_PREFERENCE
    if torch.cuda.is_available():
        return "cuda"
    return None


def _import_torch():
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError:
        return None
    return torch
