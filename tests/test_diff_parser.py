"""
Unit tests for diff_parser.py
"""
import unittest
import networkx as nx

from code_impact_graph_rag.diff_parser import parse_unified_diff, extract_seed_nodes


class TestDiffParser(unittest.TestCase):
    def test_parse_unified_diff(self):
        sample_diff = """--- a/service.py
+++ b/service.py
@@ -10,3 +10,4 @@
 def process():
-    return 1
+    return 2
+    print("done")
"""
        file_changes = parse_unified_diff(sample_diff)
        self.assertIn("service.py", file_changes)
        self.assertIn(11, file_changes["service.py"])
        self.assertIn(12, file_changes["service.py"])

    def test_extract_seed_nodes(self):
        graph = nx.DiGraph()
        graph.add_node("service.py:L10:def:process", file="service.py", line=10, name="process", type="def", category="function")

        sample_diff = """--- a/service.py
+++ b/service.py
@@ -10,2 +10,2 @@
-def process():
+def process(arg=True):
"""
        seeds = extract_seed_nodes(graph, sample_diff)
        self.assertEqual(len(seeds), 1)
        self.assertEqual(seeds[0]["name"], "process")


if __name__ == "__main__":
    unittest.main()
