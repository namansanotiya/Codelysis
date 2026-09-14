"""
Unit tests for impact_analyzer.py
"""
import unittest
import networkx as nx

from code_impact_graph_rag.impact_analyzer import extract_ego_graph, analyze_impact_summary


class TestImpactAnalyzer(unittest.TestCase):
    def setUp(self):
        # Construct graph:
        # func_c (def) <--[E_invoke]-- ref:func_c <--[E_contain]-- func_b (def) <--[E_invoke]-- ref:func_b <--[E_contain]-- func_a (def)
        self.graph = nx.DiGraph()

        self.node_c_def = {"node_id": "c.py:L1:def:func_c", "file": "c.py", "line": 1, "name": "func_c", "type": "def", "category": "function"}
        self.node_b_def = {"node_id": "b.py:L1:def:func_b", "file": "b.py", "line": 1, "name": "func_b", "type": "def", "category": "function"}
        self.node_b_ref = {"node_id": "b.py:L2:ref:func_c", "file": "b.py", "line": 2, "name": "func_c", "type": "ref", "category": "call"}
        self.node_a_def = {"node_id": "a.py:L1:def:func_a", "file": "a.py", "line": 1, "name": "func_a", "type": "def", "category": "function"}
        self.node_a_ref = {"node_id": "a.py:L2:ref:func_b", "file": "a.py", "line": 2, "name": "func_b", "type": "ref", "category": "call"}

        for n in [self.node_c_def, self.node_b_def, self.node_b_ref, self.node_a_def, self.node_a_ref]:
            self.graph.add_node(n["node_id"], **n)

        # Containment & Invocation edges
        self.graph.add_edge("b.py:L1:def:func_b", "b.py:L2:ref:func_c", edge_type="E_contain")
        self.graph.add_edge("b.py:L2:ref:func_c", "c.py:L1:def:func_c", edge_type="E_invoke")

        self.graph.add_edge("a.py:L1:def:func_a", "a.py:L2:ref:func_b", edge_type="E_contain")
        self.graph.add_edge("a.py:L2:ref:func_b", "b.py:L1:def:func_b", edge_type="E_invoke")

    def test_ego_graph_traversal(self):
        seed_nodes = [self.node_c_def]
        
        # 1-hop traversal should reach node_b_ref
        ego_1 = extract_ego_graph(self.graph, seed_nodes, k=1)
        self.assertIn("b.py:L2:ref:func_c", ego_1)

        # 2-hop traversal reaches node_b_def
        ego_2 = extract_ego_graph(self.graph, seed_nodes, k=2)
        self.assertIn("b.py:L1:def:func_b", ego_2)

        # 4-hop traversal reaches indirect caller node_a_def
        ego_4 = extract_ego_graph(self.graph, seed_nodes, k=4)
        self.assertIn("a.py:L1:def:func_a", ego_4)

        summary_2 = analyze_impact_summary(self.graph, ego_2, seed_nodes)
        self.assertIn("b.py", summary_2["affected_files"])

        summary_4 = analyze_impact_summary(self.graph, ego_4, seed_nodes)
        self.assertIn("a.py", summary_4["affected_files"])


if __name__ == "__main__":
    unittest.main()
