"""Workflow implementations for graph distribution comparison."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import hashlib
import math
import random
import time
from typing import Iterable, Sequence

from experimentation.graph import Edge, Graph, normalize_edge


Vector = list[float]
SparseVector = dict[str, float]
Representation = Vector | SparseVector

NATIVE_NETLSD_WORKFLOW = "native_netlsd"
LEGACY_NETLSD_MMD_WORKFLOW = "netlsd_spectral_signatures"
DIVERSITY_CURVES_WORKFLOW = "diversity_curves_shortest_path"

NETLSD_TIME_SCALE_COUNT = 250
NETLSD_TIME_MIN = 1e-2
NETLSD_TIME_MAX = 1e2
NETLSD_DEFAULT_TIMESCALES = tuple(
    NETLSD_TIME_MIN * (NETLSD_TIME_MAX / NETLSD_TIME_MIN) ** (index / (NETLSD_TIME_SCALE_COUNT - 1))
    for index in range(NETLSD_TIME_SCALE_COUNT)
)

NETLSD_NORMALIZATION_MODES = {"none", "empty", "complete"}
WL_LABEL_INITIALIZATION_MODES = {"node_label_or_degree", "degree", "constant"}

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
    if len(left) != len(right):
        raise ValueError(f"Vector length mismatch: {len(left)} != {len(right)}")
    return sum((a - b) ** 2 for a, b in zip(left, right))


def l2(left: Vector, right: Vector) -> float:
    return math.sqrt(squared_l2(left, right))


def dense_mean(vectors: list[Vector]) -> Vector:
    if not vectors:
        return []
    width = len(vectors[0])
    if any(len(vector) != width for vector in vectors):
        raise ValueError("Cannot average dense vectors with different lengths")
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
    """Return biased quadratic RBF-MMD with diagonal kernel terms included."""

    if not vectors_x or not vectors_y:
        return 0.0
    gamma = 1.0 / (2.0 * bandwidth * bandwidth)

    def kernel(a: Vector, b: Vector) -> float:
        return math.exp(-gamma * squared_l2(a, b))

    xx = sum(kernel(a, b) for a in vectors_x for b in vectors_x) / (len(vectors_x) ** 2)
    yy = sum(kernel(a, b) for a in vectors_y for b in vectors_y) / (len(vectors_y) ** 2)
    xy = sum(kernel(a, b) for a in vectors_x for b in vectors_y) / (len(vectors_x) * len(vectors_y))
    return max(0.0, xx + yy - 2.0 * xy)


def rbf_kernel_is_nearly_constant(
    vectors: list[Vector],
    bandwidth: float = 1.0,
    *,
    range_tolerance: float = 1e-3,
    high_similarity_threshold: float = 0.99,
) -> bool:
    """Detect RBF bandwidths that collapse the biased-MMD kernel matrix."""

    if len(vectors) < 2:
        return False
    gamma = 1.0 / (2.0 * bandwidth * bandwidth)
    values = [
        math.exp(-gamma * squared_l2(left, right))
        for left in vectors
        for right in vectors
    ]
    return max(values) - min(values) <= range_tolerance or min(values) >= high_similarity_threshold


def median_heuristic_bandwidth(vectors: list[Vector]) -> float:
    """Median pairwise L2 distance: the standard RBF-MMD bandwidth heuristic.

    Recommended for variable-size real datasets (e.g. IMDB-BINARY) where a fixed
    bandwidth tuned for n=50 can saturate or collapse the kernel. Returns ``1.0``
    when there are fewer than two vectors or all distances are zero, keeping the
    bandwidth positive. The default synthetic workflows do not use this so their
    results stay reproducible; pass it explicitly:
    ``StructuralStatisticsMMDWorkflow(bandwidth=median_heuristic_bandwidth(vecs))``.
    """

    if len(vectors) < 2:
        return 1.0
    distances = [
        l2(vectors[i], vectors[j])
        for i in range(len(vectors))
        for j in range(i + 1, len(vectors))
    ]
    positive = sorted(distance for distance in distances if distance > 0.0)
    if not positive:
        return 1.0
    middle = len(positive) // 2
    if len(positive) % 2:
        return positive[middle]
    return 0.5 * (positive[middle - 1] + positive[middle])


def sparse_linear_mmd(vectors_x: list[SparseVector], vectors_y: list[SparseVector]) -> float:
    """Return linear-kernel MMD as squared distance between mean sparse features."""

    mean_x = sparse_mean(vectors_x)
    mean_y = sparse_mean(vectors_y)
    return sparse_l2(mean_x, mean_y) ** 2


@dataclass
class Workflow:
    name: str

    def parameters(self) -> dict[str, object]:
        return {
            "method": self.name,
            "implementation_mode": "paper_faithful",
        }

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
        parameters = self.parameters()
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
            "implementation_mode": parameters.get("implementation_mode", "paper_faithful"),
            "workflow_params": parameters,
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

    def parameters(self) -> dict[str, object]:
        return {
            **super().parameters(),
            "implementation_mode": "descriptor_baseline",
            "kernel": "rbf_mmd",
            "bandwidth": self.bandwidth,
            "feature_count": 9,
        }

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
    label_initialization: str = "node_label_or_degree"
    node_label_key: str = "node_labels"
    kernel_mode: str = "linear_mmd"

    def __init__(
        self,
        iterations: int = 3,
        label_initialization: str = "node_label_or_degree",
        node_label_key: str = "node_labels",
        kernel_mode: str = "linear_mmd",
    ) -> None:
        super().__init__("wl_subtree_kernel_mmd")
        if iterations < 0:
            raise ValueError("WL iterations must be non-negative")
        if label_initialization not in WL_LABEL_INITIALIZATION_MODES:
            raise ValueError(
                f"label_initialization must be one of {sorted(WL_LABEL_INITIALIZATION_MODES)}"
            )
        if kernel_mode != "linear_mmd":
            raise ValueError("Only linear_mmd distribution comparison is implemented for WL features")
        self.iterations = iterations
        self.label_initialization = label_initialization
        self.node_label_key = node_label_key
        self.kernel_mode = kernel_mode

    def compute_representations(self, graphs: list[Graph]) -> list[SparseVector]:
        return wl_feature_matrix(
            graphs,
            iterations=self.iterations,
            label_initialization=self.label_initialization,
            node_label_key=self.node_label_key,
        )

    def distribution_score(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> float:
        original, perturbed = self._joint_representations(original_graphs, perturbed_graphs)
        return sparse_linear_mmd(original, perturbed)

    def distribution_score_from_representations(
        self,
        original: list[Representation],
        perturbed: list[Representation],
    ) -> float:
        return sparse_linear_mmd(original, perturbed)  # type: ignore[arg-type]

    def mean_shift_score(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> float:
        original, perturbed = self._joint_representations(original_graphs, perturbed_graphs)
        return sparse_l2(sparse_mean(original), sparse_mean(perturbed))

    def paired_score(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> float:
        original, perturbed = self._joint_representations(original_graphs, perturbed_graphs)
        return paired_representation_distance(original, perturbed)

    def run(self, original_graphs: list[Graph], perturbed_graphs: list[Graph]) -> dict[str, object]:
        start = time.perf_counter()
        parameters = self.parameters()
        try:
            original, perturbed = self._joint_representations(original_graphs, perturbed_graphs)
            distribution = sparse_linear_mmd(original, perturbed)
            mean_shift = sparse_l2(sparse_mean(original), sparse_mean(perturbed))
            paired = paired_representation_distance(original, perturbed)
            status = "success"
            error_message = None
        except Exception as exc:  # pragma: no cover - exercised through runner status behavior.
            distribution = None
            mean_shift = None
            paired = None
            status = "failed"
            error_message = str(exc)
        return {
            "workflow": self.name,
            "implementation_mode": parameters.get("implementation_mode", "paper_faithful"),
            "workflow_params": parameters,
            "distribution_score": distribution,
            "mean_shift_score": mean_shift,
            "paired_score": paired,
            "runtime_seconds": time.perf_counter() - start,
            "memory_mb": None,
            "status": status,
            "error_message": error_message,
        }

    def parameters(self) -> dict[str, object]:
        return {
            **super().parameters(),
            "wl_iterations": self.iterations,
            "wl_label_initialization": self.label_initialization,
            "wl_node_label_key": self.node_label_key,
            "wl_feature_construction": "subtree_histograms_across_iterations",
            "wl_compression": "shared_canonical_dictionary_per_comparison",
            "wl_kernel_distance_mode": self.kernel_mode,
        }

    def _joint_representations(
        self,
        original_graphs: list[Graph],
        perturbed_graphs: list[Graph],
    ) -> tuple[list[SparseVector], list[SparseVector]]:
        features = self.compute_representations(original_graphs + perturbed_graphs)
        split = len(original_graphs)
        return features[:split], features[split:]


@dataclass
class NetLSDWorkflow(Workflow):
    timescales: tuple[float, ...] = NETLSD_DEFAULT_TIMESCALES
    normalization: str = "empty"
    laplacian: str = "normalized"

    def __init__(
        self,
        timescales: Iterable[float] | None = None,
        bandwidth: float | None = None,
        normalization: str = "empty",
        laplacian: str = "normalized",
    ) -> None:
        super().__init__(NATIVE_NETLSD_WORKFLOW)
        if normalization not in NETLSD_NORMALIZATION_MODES:
            raise ValueError(f"normalization must be one of {sorted(NETLSD_NORMALIZATION_MODES)}")
        if laplacian != "normalized":
            raise ValueError("NetLSD currently implements the normalized Laplacian from the paper")
        if timescales is not None:
            self.timescales = tuple(timescales)
        else:
            self.timescales = NETLSD_DEFAULT_TIMESCALES
        if not self.timescales:
            raise ValueError("NetLSD requires at least one time scale")
        if any((not math.isfinite(time_value)) or time_value < 0.0 for time_value in self.timescales):
            raise ValueError("NetLSD time scales must be finite non-negative values")
        self.normalization = normalization
        self.laplacian = laplacian

    def compute_representations(self, graphs: list[Graph]) -> list[Vector]:
        return [
            netlsd_signature(graph, self.timescales, normalization=self.normalization)
            for graph in graphs
        ]

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

    def parameters(self) -> dict[str, object]:
        return {
            **super().parameters(),
            "netlsd_time_scale_count": len(self.timescales),
            "netlsd_time_scale_min": min(self.timescales),
            "netlsd_time_scale_max": max(self.timescales),
            "netlsd_time_scale_schedule": "logspace",
            "netlsd_normalization": self.normalization,
            "laplacian_type": self.laplacian,
            "heat_signature": "heat_trace",
            "eigenvalue_mode": "full_spectrum",
            "eigenvalue_count": "all",
            "distribution_distance": "l2_between_mean_signatures",
        }


@dataclass
class DiversityCurvesWorkflow(Workflow):
    max_scales: int | None = None
    repetitions: int = 3
    scales: tuple[int, ...] | None = None
    upsampling: bool = True
    contraction_mode: str = "random_edge"
    random_seed: int = 0

    def __init__(
        self,
        max_scales: int | None = None,
        repetitions: int = 3,
        scales: Iterable[int] | None = None,
        upsampling: bool = True,
        contraction_mode: str = "random_edge",
        random_seed: int = 0,
    ) -> None:
        super().__init__(DIVERSITY_CURVES_WORKFLOW)
        if max_scales is not None and max_scales < 1:
            raise ValueError("max_scales must be at least 1 when provided")
        if repetitions < 1:
            raise ValueError("repetitions must be at least 1")
        if contraction_mode not in {"random_edge", "legacy_deterministic"}:
            raise ValueError("contraction_mode must be 'random_edge' or 'legacy_deterministic'")
        self.max_scales = max_scales
        self.repetitions = repetitions
        self.scales = tuple(sorted(set(scales))) if scales is not None else None
        if self.scales is not None and not self.scales:
            raise ValueError("At least one Diversity Curve scale is required")
        if self.scales is not None and any(scale < 1 for scale in self.scales):
            raise ValueError("Diversity Curve scales must be positive integers")
        self.upsampling = upsampling
        self.contraction_mode = contraction_mode
        self.random_seed = random_seed

    def compute_representations(self, graphs: list[Graph]) -> list[Vector]:
        return diversity_curve_representations(
            graphs,
            scales=self.scales,
            max_scales=self.max_scales,
            repetitions=self.repetitions,
            upsampling=self.upsampling,
            contraction_mode=self.contraction_mode,
            random_seed=self.random_seed,
        )

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

    def parameters(self) -> dict[str, object]:
        return {
            **super().parameters(),
            "diversity_curve_definition": "shortest_path_spread",
            "diversity_scale_schedule": "explicit" if self.scales is not None else "all_integer_cardinalities",
            "diversity_scale_count": len(self.scales) if self.scales is not None else self.max_scales or "dataset_max_nodes",
            "diversity_repetitions": self.repetitions,
            "diversity_upsampling_enabled": self.upsampling,
            "diversity_contraction_mode": self.contraction_mode,
            "distance_metric": "shortest_path",
            "random_seed": self.random_seed,
            "distribution_distance": "l2_between_mean_curves",
        }


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


def wl_features(
    graph: Graph,
    iterations: int,
    *,
    label_initialization: str = "node_label_or_degree",
    node_label_key: str = "node_labels",
) -> SparseVector:
    return wl_feature_matrix(
        [graph],
        iterations=iterations,
        label_initialization=label_initialization,
        node_label_key=node_label_key,
    )[0]


def wl_feature_matrix(
    graphs: Sequence[Graph],
    iterations: int,
    *,
    label_initialization: str = "node_label_or_degree",
    node_label_key: str = "node_labels",
) -> list[SparseVector]:
    """Return WL subtree histograms with shared canonical compression."""

    if iterations < 0:
        raise ValueError("WL iterations must be non-negative")
    if label_initialization not in WL_LABEL_INITIALIZATION_MODES:
        raise ValueError(f"label_initialization must be one of {sorted(WL_LABEL_INITIALIZATION_MODES)}")

    labels_by_graph = [
        _initial_wl_labels(graph, label_initialization=label_initialization, node_label_key=node_label_key)
        for graph in graphs
    ]
    features = [Counter(_iteration_feature_label(0, label) for label in labels.values()) for labels in labels_by_graph]

    for iteration in range(1, iterations + 1):
        signatures_by_graph: list[dict[int, tuple[str, tuple[str, ...]]]] = []
        signature_space: set[tuple[str, tuple[str, ...]]] = set()
        for graph, labels in zip(graphs, labels_by_graph):
            signatures: dict[int, tuple[str, tuple[str, ...]]] = {}
            for node in range(graph.num_nodes):
                neighbor_labels = tuple(sorted(labels[neighbor] for neighbor in graph.adjacency[node]))
                signature = (labels[node], neighbor_labels)
                signatures[node] = signature
                signature_space.add(signature)
            signatures_by_graph.append(signatures)

        compression = {
            signature: f"c{iteration}:{index}"
            for index, signature in enumerate(sorted(signature_space, key=_wl_signature_sort_key))
        }
        labels_by_graph = [
            {node: compression[signature] for node, signature in signatures.items()}
            for signatures in signatures_by_graph
        ]
        for feature_counts, labels in zip(features, labels_by_graph):
            feature_counts.update(_iteration_feature_label(iteration, label) for label in labels.values())

    return [dict(feature_counts) for feature_counts in features]


def wl_subtree_kernel_matrix(features: Sequence[SparseVector]) -> list[list[float]]:
    return [[sparse_dot(left, right) for right in features] for left in features]


def _initial_wl_labels(
    graph: Graph,
    *,
    label_initialization: str,
    node_label_key: str,
) -> dict[int, str]:
    if label_initialization == "constant":
        return {node: "unlabeled" for node in range(graph.num_nodes)}
    if label_initialization == "node_label_or_degree":
        node_labels = _node_labels_from_metadata(graph, node_label_key)
        if node_labels is not None:
            return {node: f"label:{node_labels[node]}" for node in range(graph.num_nodes)}
    return {node: f"degree:{graph.degree(node)}" for node in range(graph.num_nodes)}


def _node_labels_from_metadata(graph: Graph, node_label_key: str) -> list[str] | None:
    labels = graph.metadata.get(node_label_key)
    if labels is None and node_label_key != "labels":
        labels = graph.metadata.get("labels")
    if labels is None:
        return None
    if isinstance(labels, dict):
        try:
            return [str(labels[node]) for node in range(graph.num_nodes)]
        except KeyError as exc:
            raise ValueError(f"Missing WL node label for node {exc.args[0]}") from exc
    if isinstance(labels, (list, tuple)):
        if len(labels) != graph.num_nodes:
            raise ValueError(
                f"WL node label count {len(labels)} does not match graph node count {graph.num_nodes}"
            )
        return [str(value) for value in labels]
    raise ValueError("WL node labels must be a sequence or a node-indexed dictionary")


def _iteration_feature_label(iteration: int, label: str) -> str:
    return f"h{iteration}:{label}"


def _wl_signature_sort_key(signature: tuple[str, tuple[str, ...]]) -> str:
    own_label, neighbor_labels = signature
    return f"{own_label}|{'/'.join(neighbor_labels)}"


def netlsd_signature(
    graph: Graph,
    timescales: Iterable[float],
    *,
    normalization: str = "empty",
) -> Vector:
    if normalization not in NETLSD_NORMALIZATION_MODES:
        raise ValueError(f"normalization must be one of {sorted(NETLSD_NORMALIZATION_MODES)}")
    eigenvalues = normalized_laplacian_eigenvalues(graph)
    signature = []
    for time_value in timescales:
        if not math.isfinite(time_value) or time_value < 0.0:
            raise ValueError("NetLSD time scales must be finite non-negative values")
        heat_trace = sum(math.exp(-time_value * eigenvalue) for eigenvalue in eigenvalues)
        normalizer = netlsd_neutral_heat_trace(graph.num_nodes, time_value, normalization)
        signature.append(heat_trace / normalizer)
    return signature


def netlsd_neutral_heat_trace(num_nodes: int, time_value: float, normalization: str) -> float:
    if normalization == "none":
        return 1.0
    if normalization == "empty":
        return float(num_nodes) if num_nodes > 0 else 1.0
    if normalization == "complete":
        if num_nodes <= 1:
            return 1.0
        return 1.0 + (num_nodes - 1) * math.exp(-time_value)
    raise ValueError(f"normalization must be one of {sorted(NETLSD_NORMALIZATION_MODES)}")


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
    """Compute legacy graph-local spread over deterministic edge-contraction levels.

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


def diversity_curve_representations(
    graphs: Sequence[Graph],
    *,
    scales: Iterable[int] | None = None,
    max_scales: int | None = None,
    repetitions: int = 3,
    upsampling: bool = True,
    contraction_mode: str = "random_edge",
    random_seed: int = 0,
) -> list[Vector]:
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    if contraction_mode not in {"random_edge", "legacy_deterministic"}:
        raise ValueError("contraction_mode must be 'random_edge' or 'legacy_deterministic'")
    if not graphs:
        return []
    target_scales = _resolve_diversity_workflow_scales(graphs, scales=scales, max_scales=max_scales)
    return [
        diversity_curve_for_scales(
            graph,
            target_scales,
            repetitions=repetitions,
            upsampling=upsampling,
            contraction_mode=contraction_mode,
            random_seed=_diversity_seed_for_graph(graph, random_seed),
        )
        for graph in graphs
    ]


def _diversity_seed_for_graph(graph: Graph, random_seed: int) -> int:
    payload = f"{random_seed}|{_graph_structural_signature(graph)}|{graph.num_nodes}|{graph.number_of_edges()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def diversity_curve_for_scales(
    graph: Graph,
    scales: Sequence[int],
    *,
    repetitions: int = 3,
    upsampling: bool = True,
    contraction_mode: str = "random_edge",
    random_seed: int = 0,
) -> Vector:
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    if any(scale < 1 for scale in scales):
        raise ValueError("Diversity Curve scales must be positive integers")
    if graph.num_nodes == 0:
        return [0.0] * len(scales)

    totals = [0.0 for _ in scales]
    for repeat in range(repetitions):
        rng = random.Random(random_seed + repeat * 1_009)
        values = _paper_diversity_curve_once(
            graph,
            scales,
            upsampling=upsampling,
            contraction_mode=contraction_mode,
            rng=rng,
            repeat=repeat,
        )
        for index, value in enumerate(values):
            totals[index] += value
    return [value / repetitions for value in totals]


def _resolve_diversity_workflow_scales(
    graphs: Sequence[Graph],
    *,
    scales: Iterable[int] | None,
    max_scales: int | None,
) -> tuple[int, ...]:
    if scales is not None:
        resolved = tuple(sorted(set(scales)))
        if not resolved:
            raise ValueError("At least one Diversity Curve scale is required")
        if any(scale < 1 for scale in resolved):
            raise ValueError("Diversity Curve scales must be positive integers")
        return resolved
    max_nodes = max((graph.num_nodes for graph in graphs), default=0)
    if max_nodes == 0:
        return (1,)
    if max_scales is None:
        return tuple(range(1, max_nodes + 1))
    return tuple(_diversity_scales(max_nodes, max_scales))


def _paper_diversity_curve_once(
    graph: Graph,
    scales: Sequence[int],
    *,
    upsampling: bool,
    contraction_mode: str,
    rng: random.Random,
    repeat: int,
) -> Vector:
    values_by_scale: dict[int, float] = {}
    down_scales = sorted({scale for scale in scales if scale <= graph.num_nodes}, reverse=True)
    current_down = graph.copy()
    for scale in down_scales:
        current_down = _coarsen_to_scale_paper(
            current_down,
            scale,
            contraction_mode=contraction_mode,
            rng=rng,
            repeat=repeat,
        )
        values_by_scale[scale] = shortest_path_spread(current_down)

    up_scales = sorted({scale for scale in scales if scale > graph.num_nodes})
    if up_scales:
        if not upsampling:
            raise ValueError(
                "Diversity Curve scale exceeds graph size and upsampling is disabled"
            )
        current_up = graph.copy()
        for scale in up_scales:
            current_up = upsample_graph_to_scale(current_up, scale, rng)
            values_by_scale[scale] = shortest_path_spread(current_up)

    _interpolate_unreachable_diversity_scales(graph, values_by_scale)
    return [values_by_scale[scale] for scale in scales]


def _coarsen_to_scale_paper(
    graph: Graph,
    target_nodes: int,
    *,
    contraction_mode: str,
    rng: random.Random,
    repeat: int,
) -> Graph:
    if target_nodes < 1:
        raise ValueError("target_nodes must be at least 1")
    if contraction_mode == "legacy_deterministic":
        return _coarsen_to_scale(graph, target_nodes, repeat)
    current = graph.copy()
    while current.num_nodes > target_nodes and current.number_of_edges() > 0:
        edge = _selected_random_contraction_edge(current, rng)
        current = contract_edge(current, edge)
    return current


def _selected_random_contraction_edge(graph: Graph, rng: random.Random) -> Edge:
    edges = sorted(
        graph.edges(),
        key=lambda edge: (
            _edge_structural_signature(graph, edge),
            _edge_priority(str(_graph_structural_signature(graph)), edge),
        ),
    )
    if not edges:
        raise ValueError("Cannot select a contraction edge from an edgeless graph")
    return edges[rng.randrange(len(edges))]


def upsample_graph_to_scale(graph: Graph, target_nodes: int, rng: random.Random | None = None) -> Graph:
    if target_nodes < graph.num_nodes:
        raise ValueError("target_nodes must be at least the graph node count")
    if graph.num_nodes == 0:
        return Graph(target_nodes, metadata=dict(graph.metadata))
    rng = rng or random.Random(0)
    current = graph.copy()
    sources: list[int] = []
    while len(sources) < target_nodes - graph.num_nodes:
        block = list(range(graph.num_nodes))
        rng.shuffle(block)
        sources.extend(block)
    for source in sources[: target_nodes - graph.num_nodes]:
        current = _duplicate_node_with_closed_neighborhood(current, source)
    return current


def _duplicate_node_with_closed_neighborhood(graph: Graph, source: int) -> Graph:
    expanded = Graph(graph.num_nodes + 1, metadata=dict(graph.metadata))
    for u, v in graph.edges():
        expanded.add_edge(u, v)
    new_node = graph.num_nodes
    expanded.add_edge(source, new_node)
    for neighbor in graph.adjacency[source]:
        expanded.add_edge(new_node, neighbor)
    return expanded


def _interpolate_unreachable_diversity_scales(graph: Graph, values_by_scale: dict[int, float]) -> None:
    components = len(graph.connected_components())
    known_scales = sorted(values_by_scale)
    first_reachable = next((scale for scale in known_scales if scale >= components), None)
    if first_reachable is None and components > 1:
        for scale in known_scales:
            if scale < components:
                values_by_scale[scale] = 1.0
        return
    if first_reachable is not None and first_reachable > 1:
        first_value = values_by_scale[first_reachable]
        for scale in known_scales:
            if scale < first_reachable:
                values_by_scale[scale] = _linear_interpolate(scale, 1, 1.0, first_reachable, first_value)


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
    graph_signature = f"{repeat}|{graph.num_nodes}|{_graph_structural_signature(graph)}"
    return min(
        edges,
        key=lambda edge: (
            _edge_structural_signature(graph, edge),
            _edge_priority(graph_signature, edge),
        ),
    )


def _graph_structural_signature(graph: Graph) -> tuple[tuple[int, ...], tuple[int, ...]]:
    degrees = graph.degrees()
    component_sizes = sorted(len(component) for component in graph.connected_components())
    return tuple(sorted(degrees)), tuple(component_sizes)


def _edge_structural_signature(graph: Graph, edge: Edge) -> tuple[tuple[object, object], int, tuple[int, ...]]:
    u, v = edge
    endpoint_signatures = tuple(sorted((_node_local_signature(graph, u), _node_local_signature(graph, v))))
    common_neighbors = len(graph.adjacency[u] & graph.adjacency[v])
    neighbor_degrees = tuple(
        sorted(
            graph.degree(node)
            for node in (graph.adjacency[u] | graph.adjacency[v])
            if node not in edge
        )
    )
    return endpoint_signatures, common_neighbors, neighbor_degrees


def _node_local_signature(graph: Graph, node: int) -> tuple[int, tuple[int, ...], tuple[int, ...]]:
    neighbors = graph.adjacency[node]
    neighbor_degrees = tuple(sorted(graph.degree(neighbor) for neighbor in neighbors))
    two_hop_degrees = tuple(
        sorted(
            graph.degree(two_hop)
            for neighbor in neighbors
            for two_hop in graph.adjacency[neighbor]
            if two_hop != node
        )
    )
    return graph.degree(node), neighbor_degrees, two_hop_degrees


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
