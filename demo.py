"""
Main entry point for demonstrating the Graph-RAG Code Change Impact Analysis pipeline.
Runs AST graph construction, Git diff seed extraction, k-hop ego subgraph traversal,
Graph-RAG context synthesis, and LLM recommendation generation.
"""
import argparse
import os
import sys
import logging

# Ensure project root is in sys.path when running as script
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from code_impact_graph_rag.config import K_HOPS
from code_impact_graph_rag.graph_builder import build_graph
from code_impact_graph_rag.diff_parser import get_git_diff, extract_seed_nodes
from code_impact_graph_rag.impact_analyzer import extract_ego_graph, analyze_impact_summary
from code_impact_graph_rag.graph_rag_engine import serialize_ego_graph
from code_impact_graph_rag.recommender import generate_recommendations

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("demo")

DEFAULT_SAMPLE_DIFF = """--- a/auth/service.py
+++ b/auth/service.py
@@ -3,4 +3,4 @@
-def validate_token(token: str) -> bool:
+def validate_token(token: str, require_admin: bool = False, tenant_id: str = "default") -> bool:
     \"\"\"Validates security token and checks authorization level.\"\"\"
     claims = decode_token(token)
"""


def run_pipeline(repo_path: str, k: int = K_HOPS, diff_text: str = None, output_file: str = None) -> str:
    """Execute end-to-end Graph-RAG Impact Analysis pipeline."""
    repo_path = os.path.abspath(repo_path)
    logger.info(f"Step 1: Building repository dependency graph for '{repo_path}'...")
    graph = build_graph(repo_path)

    if graph.number_of_nodes() == 0:
        logger.error("Empty repository graph built. Please verify repository path.")
        return ""

    logger.info("Step 2: Identifying changed code & Seed Nodes from Git Diff...")
    if not diff_text:
        diff_text = get_git_diff(repo_path)
    if not diff_text:
        logger.info("No active Git diff detected. Using default sample modification diff for auth/service.py...")
        diff_text = DEFAULT_SAMPLE_DIFF

    seed_nodes = extract_seed_nodes(graph, diff_text)
    if not seed_nodes:
        logger.warning("No seed nodes matched the diff line ranges. Fallback: using default function nodes.")
        # Fallback: pick first definition node in graph
        for nid, d in graph.nodes(data=True):
            if d.get("category") in ("function", "method"):
                seed_nodes = [d]
                break

    logger.info(f"Step 3: Extracting {k}-hop Ego Subgraph around seed nodes...")
    ego_graph = extract_ego_graph(graph, seed_nodes, k=k)
    impact_summary = analyze_impact_summary(graph, ego_graph, seed_nodes)

    logger.info(f"Found {len(impact_summary['affected_files'])} potentially affected files")
    logger.info("Step 4: Synthesizing Graph-RAG structured context...")
    graph_context = serialize_ego_graph(ego_graph, seed_nodes, diff_text)

    logger.info("Step 5: Generating impact recommendations via LLM / Graph-RAG Engine...")
    report = generate_recommendations(graph_context, diff_text, impact_summary)

    if output_file:
        out_path = os.path.abspath(output_file)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"Report saved to {out_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Graph-RAG Code Change Impact Analysis & Co-Change Recommender")
    default_sample_dir = os.path.join(current_dir, "sample_repo")
    parser.add_argument("--repo", type=str, default=default_sample_dir, help="Path to target repository")
    parser.add_argument("--k", type=int, default=K_HOPS, help="Number of hops for ego subgraph traversal")
    parser.add_argument("--diff", type=str, default=None, help="Unified diff text string")
    parser.add_argument("--output", type=str, default=None, help="Output markdown report filepath")

    args = parser.parse_args()
    report = run_pipeline(repo_path=args.repo, k=args.k, diff_text=args.diff, output_file=args.output)
    
    print("\n" + "=" * 60)
    print("GENERATED GRAPH-RAG IMPACT ANALYSIS REPORT:")
    print("=" * 60 + "\n")
    print(report)


if __name__ == "__main__":
    main()
