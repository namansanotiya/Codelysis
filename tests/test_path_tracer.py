"""
Unit tests for Day 2 Causal Evidence Path Tracer & Error Predictor.
"""
import unittest
import networkx as nx

from core.types import EdgeType
from traversal.path_tracer import trace_evidence_paths, predict_potential_errors


class TestPathTracer(unittest.TestCase):
    def setUp(self):
        # Seed func_c <--[E_invoke]-- ref_c <--[E_contain]-- func_b <--[E_invoke]-- ref_b <--[E_contain]-- test_b
        self.graph = nx.DiGraph()

        self.seed_node = {
            "node_id": "service.py:L10:def:validate_token",
            "file": "service.py",
            "line": 10,
            "name": "validate_token",
            "category": "function",
            "type": "def",
            "signature": "(token: str, require_admin: bool = False)"
        }
        self.caller_ref = {
            "node_id": "client.py:L20:ref:validate_token",
            "file": "client.py",
            "line": 20,
            "name": "validate_token",
            "category": "call",
            "type": "ref",
            "snippet": "validate_token(tok)"
        }
        self.caller_func = {
            "node_id": "client.py:L18:def:do_login",
            "file": "client.py",
            "line": 18,
            "name": "do_login",
            "category": "function",
            "type": "def"
        }
        self.test_ref = {
            "node_id": "test_client.py:L5:ref:validate_token",
            "file": "test_client.py",
            "line": 5,
            "name": "validate_token",
            "category": "call",
            "type": "ref",
            "snippet": "assert validate_token('test')"
        }

        for n in [self.seed_node, self.caller_ref, self.caller_func, self.test_ref]:
            self.graph.add_node(n["node_id"], **n)

        # Containment & Invocation
        self.graph.add_edge(self.caller_func["node_id"], self.caller_ref["node_id"], edge_type=EdgeType.E_CONTAIN.value)
        self.graph.add_edge(self.caller_ref["node_id"], self.seed_node["node_id"], edge_type=EdgeType.E_INVOKE.value)
        self.graph.add_edge(self.test_ref["node_id"], self.seed_node["node_id"], edge_type=EdgeType.E_INVOKE.value)

    def test_trace_evidence_paths(self):
        paths = trace_evidence_paths(self.graph, [self.seed_node])
        self.assertIn(self.caller_ref["node_id"], paths)
        caller_paths = paths[self.caller_ref["node_id"]]
        self.assertGreaterEqual(len(caller_paths), 1)

    def test_predict_potential_errors(self):
        diff_text = """--- a/service.py
+++ b/service.py
@@ -10,1 +10,1 @@
-def validate_token(token: str):
+def validate_token(token: str, tenant_id: str):
"""
        errors = predict_potential_errors(self.graph, [self.seed_node], diff_text)
        self.assertGreaterEqual(len(errors), 1)
        err_types = [e["error_type"] for e in errors]
        # Should flag TypeError or AssertionError
        self.assertTrue(any("TypeError" in et or "AssertionError" in et for et in err_types))


if __name__ == "__main__":
    unittest.main()

