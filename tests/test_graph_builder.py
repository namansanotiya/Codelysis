"""
Unit tests for graph_builder.py (Python and Multi-Language support)
"""
import unittest
import os
import tempfile
import shutil

from code_impact_graph_rag.graph_builder import build_graph, CodeNode


class TestGraphBuilder(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

        # Create Python files
        self.file_a = os.path.join(self.test_dir, "a.py")
        with open(self.file_a, "w", encoding="utf-8") as f:
            f.write("def helper():\n    return 42\n")

        self.file_b = os.path.join(self.test_dir, "b.py")
        with open(self.file_b, "w", encoding="utf-8") as f:
            f.write("from a import helper\n\ndef main():\n    return helper()\n")

        # Create TypeScript files
        self.file_ts_service = os.path.join(self.test_dir, "authService.ts")
        with open(self.file_ts_service, "w", encoding="utf-8") as f:
            f.write("export function validateUser(token: string): boolean {\n    return true;\n}\n")

        self.file_ts_controller = os.path.join(self.test_dir, "authController.ts")
        with open(self.file_ts_controller, "w", encoding="utf-8") as f:
            f.write("import { validateUser } from './authService';\n\nexport function handleLogin(token: string) {\n    if (validateUser(token)) {\n        return 'ok';\n    }\n}\n")

        # Create Java file
        self.file_java = os.path.join(self.test_dir, "UserService.java")
        with open(self.file_java, "w", encoding="utf-8") as f:
            f.write("public class UserService {\n    public void processUser() {\n        validateUser(\"token\");\n    }\n}\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_build_graph_nodes_and_edges(self):
        graph = build_graph(self.test_dir)
        
        # Verify node count across multi-language files
        self.assertGreaterEqual(graph.number_of_nodes(), 8)
        
        # Find validateUser definition and references across TS and Java
        val_defs = [d for n, d in graph.nodes(data=True) if d.get("name") == "validateUser" and d.get("type") == "def"]
        val_refs = [d for n, d in graph.nodes(data=True) if d.get("name") == "validateUser" and d.get("type") == "ref"]

        self.assertEqual(len(val_defs), 1)
        self.assertGreaterEqual(len(val_refs), 2)  # called in authController.ts and UserService.java

        # Verify E_invoke edge from TS call site to TS definition site
        def_id = val_defs[0]["node_id"]
        for ref in val_refs:
            ref_id = ref["node_id"]
            if graph.has_edge(ref_id, def_id):
                edge_type = graph.get_edge_data(ref_id, def_id).get("edge_type")
                self.assertEqual(edge_type, "E_invoke")


if __name__ == "__main__":
    unittest.main()
