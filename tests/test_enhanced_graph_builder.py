"""
Comprehensive Unit Tests for Codelysis Graph Construction Extensions:
- Enhanced CodeNode metadata (spans, signatures, docstrings)
- E_import relationships and alias resolution
- E_inherit and E_override relationships
- Scoped, confidence-weighted E_invoke resolution
- MultiDiGraph edge access compatibility
"""
import unittest
import networkx as nx

from core.types import CodeNode, EdgeType, has_edge_type, get_edges_between
from graph.builder import RepoGraphBuilder, build_graph
from traversal.seed_extractor import extract_seed_nodes
from traversal.ego_graph import extract_ego_graph
from traversal.impact_analyzer import analyze_impact_summary


class TestEnhancedGraphBuilder(unittest.TestCase):
    def test_codenode_spans_and_signatures(self):
        code_py = '''"""Module docstring."""
class Calculator:
    """Class docstring."""
    def add(self, a: int, b: int = 0) -> int:
        """Add two numbers."""
        return a + b
'''
        files = {"calc.py": code_py}
        builder = RepoGraphBuilder()
        graph = builder.build_from_files(files)

        calc_node = [d for n, d in graph.nodes(data=True) if d.get("name") == "Calculator"][0]
        self.assertEqual(calc_node["category"], "class")
        self.assertEqual(calc_node["line"], 2)
        self.assertGreaterEqual(calc_node["end_line"], 5)
        self.assertIn("Class docstring", calc_node["docstring"])

        add_node = [d for n, d in graph.nodes(data=True) if d.get("name") == "Calculator.add"][0]
        self.assertEqual(add_node["category"], "method")
        self.assertEqual(add_node["line"], 4)
        self.assertGreaterEqual(add_node["end_line"], 6)
        self.assertIn("(self, a: int, b: int = 0) -> int", add_node["signature"])

    def test_import_edges_and_alias_resolution(self):
        auth_service = """def authenticate(user: str) -> bool:
    return True
"""
        app_code = """from auth.service import authenticate as auth_check

def run_app():
    if auth_check('alice'):
        return 'ok'
"""
        files = {
            "auth/service.py": auth_service,
            "app.py": app_code
        }
        builder = RepoGraphBuilder()
        graph = builder.build_from_files(files)

        # Check E_import edge between app.py file node and auth/service.py or authenticate
        import_edges = [
            (u, v, d) for u, v, d in graph.edges(data=True)
            if d.get("edge_type") == EdgeType.E_IMPORT.value
        ]
        self.assertGreaterEqual(len(import_edges), 1)

        # Check that auth_check invocation resolves to authenticate
        invoke_edges = [
            (u, v, d) for u, v, d in graph.edges(data=True)
            if d.get("edge_type") == EdgeType.E_INVOKE.value
        ]
        self.assertEqual(len(invoke_edges), 1)
        ref_u, target_v, edge_attr = invoke_edges[0]
        self.assertEqual(graph.nodes[target_v]["name"], "authenticate")
        self.assertGreaterEqual(edge_attr.get("confidence", 0), 0.90)

    def test_inheritance_and_override_edges(self):
        base_code = """class BaseService:
    def execute(self) -> str:
        return 'base'
"""
        derived_code = """from base import BaseService

class CustomService(BaseService):
    def execute(self) -> str:
        return 'custom'
"""
        files = {
            "base.py": base_code,
            "derived.py": derived_code
        }
        builder = RepoGraphBuilder()
        graph = builder.build_from_files(files)

        # Check E_inherit edge: CustomService -> BaseService
        inherit_edges = [
            (u, v, d) for u, v, d in graph.edges(data=True)
            if d.get("edge_type") == EdgeType.E_INHERIT.value
        ]
        self.assertEqual(len(inherit_edges), 1)
        self.assertIn("CustomService", graph.nodes[inherit_edges[0][0]]["name"])
        self.assertIn("BaseService", graph.nodes[inherit_edges[0][1]]["name"])

        # Check E_override edge: CustomService.execute -> BaseService.execute
        override_edges = [
            (u, v, d) for u, v, d in graph.edges(data=True)
            if d.get("edge_type") == EdgeType.E_OVERRIDE.value
        ]
        self.assertEqual(len(override_edges), 1)
        self.assertEqual(graph.nodes[override_edges[0][0]]["name"], "CustomService.execute")
        self.assertEqual(graph.nodes[override_edges[0][1]]["name"], "BaseService.execute")

    def test_range_based_seed_node_extraction(self):
        code = """def large_computation(data: list) -> int:
    step_one = len(data) * 2
    step_two = step_one + 42
    result = step_two ** 2
    return result
"""
        files = {"compute.py": code}
        builder = RepoGraphBuilder()
        graph = builder.build_from_files(files)

        # Diff modifying line 3 inside function body (line 1 to 5)
        diff_text = """--- a/compute.py
+++ b/compute.py
@@ -3,1 +3,1 @@
-    step_two = step_one + 42
+    step_two = step_one + 100
"""
        seeds = extract_seed_nodes(graph, diff_text)
        seed_names = [s["name"] for s in seeds]
        self.assertIn("large_computation", seed_names)


if __name__ == "__main__":
    unittest.main()

