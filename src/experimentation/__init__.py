"""Experimentation module for synthetic graph distribution comparisons."""

from experimentation.config import ExperimentConfig, debug_config, default_config, full_synthetic_config
from experimentation.datasets import SyntheticDatasetConfig, generate_graph_distribution, generate_paired_distribution
from experimentation.evaluation import evaluate_results
from experimentation.figures import generate_figures
from experimentation.graph import Graph
from experimentation.perturbations import perturb_graph
from experimentation.runner import run_debug_experiment, run_experiment, run_full_synthetic_experiment
from experimentation.workflows import default_workflows

__all__ = [
    "ExperimentConfig",
    "Graph",
    "SyntheticDatasetConfig",
    "debug_config",
    "default_config",
    "default_workflows",
    "evaluate_results",
    "full_synthetic_config",
    "generate_figures",
    "generate_graph_distribution",
    "generate_paired_distribution",
    "perturb_graph",
    "run_debug_experiment",
    "run_experiment",
    "run_full_synthetic_experiment",
]
