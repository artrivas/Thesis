"""Workflow implementations for graph distribution comparison."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import time
from typing import Iterable

from experimentation.graph import Graph


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
    max_radius: int = 4

    def __init__(self, max_radius: int = 4) -> None:
        super().__init__("diversity_curves_l2")
        self.max_radius = max_radius

    def compute_representations(self, graphs: list[Graph]) -> list[Vector]:
        return [diversity_curve(graph, self.max_radius) for graph in graphs]

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
        mapping = {signature: f"i{iteration}_{index}" for index, signature in enumerate(sorted(set(signatures.values())))}
        labels = {node: mapping[signature] for node, signature in signatures.items()}
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


def diversity_curve(graph: Graph, max_radius: int) -> Vector:
    curve = []
    for radius in range(1, max_radius + 1):
        neighborhoods = [_reachable_within_radius(graph, node, radius) for node in range(graph.num_nodes)]
        sizes = [len(nodes) for nodes in neighborhoods]
        unique_signatures = {
            tuple(sorted(graph.degree(node) for node in nodes))
            for nodes in neighborhoods
        }
        average_size = sum(sizes) / len(sizes) if sizes else 0.0
        curve.extend([average_size / max(1, graph.num_nodes), len(unique_signatures) / max(1, graph.num_nodes)])
    return curve


def _reachable_within_radius(graph: Graph, source: int, radius: int) -> set[int]:
    reached = {source}
    frontier = {source}
    for _ in range(radius):
        next_frontier: set[int] = set()
        for node in frontier:
            next_frontier.update(graph.adjacency[node])
        next_frontier -= reached
        reached |= next_frontier
        frontier = next_frontier
        if not frontier:
            break
    return reached


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
    matrix[diagonal, diagonal] = torch.where(degree_tensor == 0, 0.0, 1.0)
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
