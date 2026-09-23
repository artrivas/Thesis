"""Loader for TU-Dortmund (TUDataset) text-format graph collections.

Targets IMDB-BINARY but works for any TU dataset stored in the standard text
format. Real graphs are loaded into the repo's own ``Graph`` objects so that the
exact same perturbations, workflows, metrics, edit-distance ground truth, and
failure map apply unchanged — the only difference from the synthetic families is
where the original graphs come from.

TU text format (files live in ``<data_root>/<NAME>/`` or ``<data_root>/``):

- ``<NAME>_A.txt``                — one edge per line ``i, j`` (1-indexed GLOBAL
                                    node ids; undirected edges appear in both
                                    directions);
- ``<NAME>_graph_indicator.txt``  — line ``i`` = graph id of global node ``i``;
- ``<NAME>_graph_labels.txt``     — line ``g`` = label of graph ``g``;
- ``<NAME>_node_labels.txt``      — (optional) line ``i`` = label of global node
                                    ``i`` (IMDB-BINARY has none — it is unlabeled).
"""

from __future__ import annotations

from pathlib import Path

from experimentation.graph import Graph


REAL_DATASET_FAMILIES = {"imdb_binary": "IMDB-BINARY"}


def tu_dataset_dir(data_root: Path | str, name: str) -> Path:
    """Return the directory holding ``<name>_A.txt`` (``<root>/<name>`` or ``<root>``)."""

    root = Path(data_root)
    nested = root / name
    if (nested / f"{name}_A.txt").is_file():
        return nested
    if (root / f"{name}_A.txt").is_file():
        return root
    # Default to the conventional nested layout for a clear error message.
    return nested


def load_tu_dataset(
    data_root: Path | str,
    name: str = "IMDB-BINARY",
    *,
    family: str | None = None,
) -> list[Graph]:
    """Load a TU-format dataset into a list of ``Graph`` objects (ordered by graph id)."""

    directory = tu_dataset_dir(data_root, name)
    adjacency_file = directory / f"{name}_A.txt"
    indicator_file = directory / f"{name}_graph_indicator.txt"
    if not adjacency_file.is_file() or not indicator_file.is_file():
        raise FileNotFoundError(
            f"TU dataset '{name}' not found under {directory}. "
            f"Expected {name}_A.txt and {name}_graph_indicator.txt. "
            "Run scripts/fetch_imdb_binary.py on a machine with internet access."
        )

    node_graph = _read_int_lines(indicator_file)  # global node index (0-based) -> graph id
    graph_labels = _read_optional_labels(directory / f"{name}_graph_labels.txt")
    node_labels = _read_optional_labels(directory / f"{name}_node_labels.txt")

    # Group global nodes per graph and assign 0-based local indices.
    graph_nodes: dict[int, list[int]] = {}
    for global_index, graph_id in enumerate(node_graph):
        graph_nodes.setdefault(graph_id, []).append(global_index)
    local_index: dict[int, int] = {}
    for nodes in graph_nodes.values():
        for position, global_index in enumerate(nodes):
            local_index[global_index] = position

    resolved_family = family or _family_for_name(name)
    graphs: dict[int, Graph] = {}
    for graph_id, nodes in graph_nodes.items():
        metadata: dict[str, object] = {
            "family": resolved_family,
            "graph_index": graph_id,
            "source": "tu_dataset",
            "dataset_name": name,
        }
        if graph_labels is not None:
            metadata["graph_label"] = graph_labels[graph_id - 1] if graph_id - 1 < len(graph_labels) else None
        if node_labels is not None:
            metadata["node_labels"] = tuple(node_labels[global_index] for global_index in nodes)
        graphs[graph_id] = Graph(len(nodes), metadata=metadata)

    for source, target in _read_edges(adjacency_file):
        graph_id = node_graph[source]
        if node_graph[target] != graph_id:
            continue  # malformed cross-graph edge; skip defensively
        u = local_index[source]
        v = local_index[target]
        if u != v:
            graphs[graph_id].add_edge(u, v)  # Graph.add_edge dedupes undirected pairs

    return [graphs[graph_id] for graph_id in sorted(graphs)]


def _family_for_name(name: str) -> str:
    for family, dataset_name in REAL_DATASET_FAMILIES.items():
        if dataset_name == name:
            return family
    return name.lower().replace("-", "_")


def _read_edges(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            left, right = line.split(",")
            # TU node ids are 1-indexed globally; convert to 0-based.
            yield int(left) - 1, int(right) - 1


def _read_int_lines(path: Path) -> list[int]:
    values = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                values.append(int(line))
    return values


def _read_optional_labels(path: Path) -> list[int] | None:
    if not path.is_file():
        return None
    labels = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            # Labels may be ints; keep them as ints when possible, else strings.
            try:
                labels.append(int(line))
            except ValueError:
                labels.append(line)  # type: ignore[arg-type]
    return labels
