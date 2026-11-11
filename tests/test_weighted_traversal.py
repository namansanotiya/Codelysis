"""
Unit and Integration Tests for Weighted Traversal, Git Co-Change Mining, and Hybrid Retrieval.
"""
import unittest
import os
import textwrap
import tempfile
import shutil

from graph.builder import build_graph
from traversal.weighted_traversal import calculate_change_conditioned_ranking, pure_python_ppr
from sources.git_cochange import GitCoChangeMiner
from traversal.hybrid_retriever import retrieve_hybrid_impact, extract_tokens


class TestWeightedTraversal(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "auth/service.py": textwrap.dedent("""\
                def validate_token(token):
                    return True

                def login(token):
                    return validate_token(token)
            """),
            "core/worker.py": textwrap.dedent("""\
                from auth.service import validate_token

                def handle_job(token):
                    if validate_token(token):
                        return "ok"
            """),
        }
        self.graph = build_graph(self.sources)
        self.seed_nodes = [
            d for n, d in self.graph.nodes(data=True)
            if d.get("name") == "validate_token" and d.get("type") == "def"
        ]

    def test_weighted_ranking_prioritizes_direct_callers(self):
        ranked = calculate_change_conditioned_ranking(self.graph, self.seed_nodes, k_hops=2)
        self.assertGreater(len(ranked), 0, "Expected ranked impact nodes")

        top_names = [n.name for n in ranked[:3]]
        # Direct callers (login or validate_token call site) should be in top ranks
        self.assertTrue(
            any("validate_token" in name or "login" in name for name in top_names),
            f"Direct caller should be top ranked, got: {top_names}"
        )
        self.assertEqual(ranked[0].severity, "CRITICAL")
        self.assertGreater(ranked[0].impact_score, 0.0)

    def test_pure_python_ppr(self):
        import networkx as nx
        G = nx.DiGraph()
        G.add_edge("A", "B", weight=1.0)
        G.add_edge("B", "C", weight=0.8)
        scores = pure_python_ppr(G, seeds=["A"], alpha=0.85)
        self.assertIn("A", scores)
        self.assertIn("B", scores)
        self.assertIn("C", scores)
        self.assertGreater(scores["B"], scores["C"])

    def test_weighted_dijkstra_selects_strongest_evidence_path(self):
        """
        Verify that Dijkstra on additive cost = -log(weight) selects the path with
        the highest multiplicative evidence strength rather than an unweighted shortcut.
        Path A: Seed -> Target via E_invoke_candidate (w=0.25, cost ~ 1.386)
        Path B: Seed -> Mid -> Target via confirmed E_invoke (w=1.0, cost = 0.0)
        Cost of Path B (0.0) is much lower than Path A (1.386), so Path B must be chosen.
        """
        import networkx as nx
        from traversal.weighted_traversal import calculate_change_conditioned_ranking
        from core.types import EdgeType

        g = nx.MultiDiGraph()
        seed = {"node_id": "seed:def:core", "name": "core", "file": "core.py", "line": 1, "type": "def", "category": "function"}
        mid = {"node_id": "mid:def:handler", "name": "handler", "file": "handler.py", "line": 5, "type": "def", "category": "function"}
        tgt = {"node_id": "tgt:def:client", "name": "client", "file": "client.py", "line": 10, "type": "def", "category": "function"}

        g.add_node(seed["node_id"], **seed)
        g.add_node(mid["node_id"], **mid)
        g.add_node(tgt["node_id"], **tgt)

        # Weak shortcut: tgt calls seed via E_invoke_candidate (w=0.25)
        g.add_edge(tgt["node_id"], seed["node_id"], edge_type=EdgeType.E_INVOKE_CANDIDATE.value, confidence=0.25)
        # Strong 2-hop path: tgt -> mid -> seed via confirmed E_invoke (w=1.0)
        g.add_edge(tgt["node_id"], mid["node_id"], edge_type=EdgeType.E_INVOKE.value, confidence=1.0)
        g.add_edge(mid["node_id"], seed["node_id"], edge_type=EdgeType.E_INVOKE.value, confidence=1.0)

        ranked = calculate_change_conditioned_ranking(g, [seed], k_hops=3)
        tgt_ranked = next((n for n in ranked if n.node_id == tgt["node_id"]), None)

        self.assertIsNotNone(tgt_ranked)
        # Strongest path should pass through mid
        self.assertEqual(tgt_ranked.hop_distance, 2, "Expected 2-hop strong path over weak candidate shortcut")
        path_nodes = [step["from"] for step in tgt_ranked.evidence_path] + [tgt_ranked.evidence_path[-1]["to"]]
        self.assertIn(mid["node_id"], path_nodes, "Evidence path must traverse confirmed high-weight intermediate node")


class TestGitCoChangeMining(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Initialize a temporary git repo to test history mining
        import subprocess
        subprocess.run(["git", "init"], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=self.test_dir, capture_output=True)

        # Commit 1: file A and B together
        with open(os.path.join(self.test_dir, "auth.py"), "w") as f:
            f.write("def auth(): pass\n")
        with open(os.path.join(self.test_dir, "test_auth.py"), "w") as f:
            f.write("def test(): pass\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "commit 1"], cwd=self.test_dir, capture_output=True)

        # Commit 2: file A and B together again
        with open(os.path.join(self.test_dir, "auth.py"), "a") as f:
            f.write("# comment\n")
        subprocess.run(["git", "commit", "-am", "commit 2"], cwd=self.test_dir, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_miner_detects_co_change(self):
        miner = GitCoChangeMiner(self.test_dir)
        self.assertTrue(miner.is_git_available)
        self.assertGreaterEqual(miner.total_analyzed_commits, 2)

        co_changes = miner.get_co_changed_files(["auth.py"], min_support=1, min_jaccard=0.1)
        self.assertGreaterEqual(len(co_changes), 1)
        self.assertEqual(co_changes[0].target_file, "test_auth.py")

        score = miner.get_evolution_score(["auth.py"], "test_auth.py")
        self.assertGreater(score, 0.0)

    def test_temporal_leakage_exclusion(self):
        """
        Verify that future commits are strictly excluded and cannot leak into historical co-change scores.
        """
        import subprocess
        # Commit 3 (future commit): modifies auth.py and future_feature.py
        with open(os.path.join(self.test_dir, "future_feature.py"), "w") as f:
            f.write("# future\n")
        with open(os.path.join(self.test_dir, "auth.py"), "a") as f:
            f.write("# future edit\n")
        subprocess.run(["git", "add", "."], cwd=self.test_dir, capture_output=True)
        res = subprocess.run(["git", "commit", "-m", "future commit"], cwd=self.test_dir, capture_output=True, text=True)

        # Get latest commit hash
        c_hash = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.test_dir, capture_output=True, text=True).stdout.strip()

        # Miner with exclude_commits containing the future commit
        miner = GitCoChangeMiner(self.test_dir, exclude_commits={c_hash})
        future_score = miner.get_evolution_score(["auth.py"], "future_feature.py")
        self.assertEqual(future_score, 0.0, "Future commit must be excluded from historical co-change scores")


class TestHybridRetriever(unittest.TestCase):
    def setUp(self):
        self.sources = {
            "token.py": "def decode_token(): pass\n",
            "service.py": "from token import decode_token\ndef run(): decode_token()\n",
        }
        self.graph = build_graph(self.sources)
        self.seeds = [
            d for n, d in self.graph.nodes(data=True)
            if d.get("name") == "decode_token" and d.get("type") == "def"
        ]

    def test_extract_tokens(self):
        tokens = extract_tokens("def validateToken(user_id): return True")
        self.assertIn("validate", tokens)
        self.assertIn("token", tokens)
        self.assertIn("user", tokens)

    def test_hybrid_retrieval_returns_fused_scores(self):
        results = retrieve_hybrid_impact(
            self.graph,
            self.seeds,
            diff_text="diff --git a/token.py\n+def decode_token(secret):\n"
        )
        self.assertGreater(len(results), 0)
        self.assertIn("hybrid_score", results[0].to_dict())
        self.assertIn("graph_score", results[0].to_dict())

    def test_hybrid_retrieval_handles_missing_signals_safely(self):
        """
        Verify that missing lexical diff tokens and missing Git history are handled gracefully
        without crashes or division-by-zero errors.
        """
        # Call with no diff_text (missing lexical) and no repo_path / git_miner (missing evolution)
        results = retrieve_hybrid_impact(
            self.graph,
            self.seeds,
            diff_text="",
            repo_path=None,
            git_miner=None,
            alpha=1.0,
            beta=0.0,
            gamma=0.0
        )
        self.assertIsInstance(results, list)
        if results:
            self.assertEqual(results[0].evolution_score, 0.0)
            self.assertEqual(results[0].semantic_score, 0.0)
            self.assertGreater(results[0].graph_score, 0.0)


class TestTestImpactAnalysis(unittest.TestCase):
    def setUp(self):
        from sources.local_loader import LocalLoader
        from graph.builder import RepoGraphBuilder
        from traversal.ego_graph import extract_ego_graph
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sample_path = os.path.join(root, "sample_repo")
        loader = LocalLoader(sample_path)
        files = loader.load_all_files()
        builder = RepoGraphBuilder(multigraph=True)
        self.graph = builder.build_from_files(files)
        self.seed_nodes = [
            d for n, d in self.graph.nodes(data=True)
            if d.get("name") == "validate_token" and d.get("type") == "def"
        ]
        self.ego = extract_ego_graph(self.graph, self.seed_nodes, k=2)

    def test_identify_relevant_tests_finds_direct_test(self):
        from traversal.test_impact_analyzer import identify_relevant_tests
        recs = identify_relevant_tests(self.graph, self.ego, self.seed_nodes)
        self.assertGreater(len(recs), 0, "Expected test recommendations")

        rec_names = [t.test_name for t in recs]
        self.assertIn("test_validate_token_success", rec_names)

        direct_rec = next(t for t in recs if t.test_name == "test_validate_token_success")
        self.assertEqual(direct_rec.classification, "directly_related")
        self.assertTrue(direct_rec.requires_execution)
        self.assertIn("directly calls", direct_rec.reason.lower())


if __name__ == "__main__":
    unittest.main()

