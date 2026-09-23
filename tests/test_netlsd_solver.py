import math
import unittest
from experimentation.graph import Graph
from experimentation.workflows import normalized_laplacian_eigenvalues, jacobi_eigenvalues, NetLSDWorkflow
from experimentation.datasets import SyntheticDatasetConfig, generate_graph_distribution


class NetLSDSolverTests(unittest.TestCase):
    def test_known_normalized_spectra(self):
        path = Graph(3)
        path.add_edge(0, 1)
        path.add_edge(1, 2)
        for actual, expected in zip(normalized_laplacian_eigenvalues(path), (0., 1., 2.)):
            self.assertAlmostEqual(actual, expected, places=9)
        self.assertEqual(normalized_laplacian_eigenvalues(Graph(4)), [0.] * 4)
        disconnected = Graph(5)
        disconnected.add_edge(0, 1)
        disconnected.add_edge(2, 3)
        for actual, expected in zip(normalized_laplacian_eigenvalues(disconnected), (0., 0., 0., 2., 2.)):
            self.assertAlmostEqual(actual, expected, places=9)

    def test_fifty_node_complete_graph_spectrum(self):
        graph = Graph(50)
        for u in range(50):
            for v in range(u+1, 50):
                graph.add_edge(u, v)
        values = normalized_laplacian_eigenvalues(graph)
        self.assertAlmostEqual(values[0], 0, places=9)
        for value in values[1:]:
            self.assertAlmostEqual(value, 50/49, places=9)

    def test_unconverged_solver_raises_instead_of_silent_diagonal(self):
        with self.assertRaisesRegex(RuntimeError, "did not converge"):
            jacobi_eigenvalues([[1., -.5, -.5], [-.5, 1., -.5], [-.5, -.5, 1.]], max_iterations=0)

    def test_backend_is_recorded_in_parameters(self):
        self.assertIn("eigenvalue_solver", NetLSDWorkflow().parameters())
        self.assertEqual(NetLSDWorkflow(eigensolver="legacy_jacobi").parameters()["eigenvalue_solver"],
                         "legacy_jacobi_1000_unchecked")

    def test_library_matches_converged_reference_on_fifty_node_graph(self):
        graph = generate_graph_distribution(SyntheticDatasetConfig("barabasi_albert", num_graphs=1))[0]
        degrees = graph.degrees()
        matrix = [[float(i == j) for j in range(50)] for i in range(50)]
        for u, v in graph.edges():
            matrix[u][v] = matrix[v][u] = -1/math.sqrt(degrees[u]*degrees[v])
        reference = jacobi_eigenvalues(matrix, max_iterations=125000)
        actual = normalized_laplacian_eigenvalues(graph)
        for a, b in zip(actual, reference):
            self.assertAlmostEqual(a, b, places=8)
