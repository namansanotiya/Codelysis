"""
Main CLI entry point for Codelysis (RepoGraph ICLR 2025).
Supports both direct GitHub API analysis (zero clone) and local repositories.
"""
import argparse
import os
import sys
import logging

# Ensure Codelysis root is on sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config import K_HOPS, LLM_MODEL, DEFAULT_SAMPLE_DIFF
from graph.builder import RepoGraphBuilder
from traversal.seed_extractor import extract_seed_nodes
from traversal.ego_graph import extract_ego_graph
from traversal.impact_analyzer import analyze_impact_summary
from rag.serializer import serialize_ego_graph
from sources.local_loader import LocalLoader
from sources.github_client import GitHubClient
from llm.gemini_client import GeminiClient

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("main")


def run_pipeline(
    repo_path: str = None,
    github_slug: str = None,
    pr_number: int = None,
    commit_sha: str = None,
    k: int = K_HOPS,
    diff_text: str = None,
    model_name: str = LLM_MODEL,
    output_file: str = None
) -> str:
    """
    Execute end-to-end RepoGraph Impact Analysis pipeline.
    """
    # 1. Initialize data source (GitHub API or Local)
    if github_slug:
        logger.info(f"Using GitHub REST API for repository: {github_slug}")
        loader = GitHubClient(repo_slug=github_slug, pr_number=pr_number, commit_sha=commit_sha)
    else:
        target_path = repo_path or os.path.join(root_dir, "sample_repo")
        logger.info(f"Using local filesystem repository: {target_path}")
        loader = LocalLoader(target_path)

    # 2. Ingest files & Build RepoGraph
    file_contents = loader.load_all_files()
    if not file_contents:
        logger.error("No source files loaded. Please check repository path or GitHub slug.")
        return ""

    builder = RepoGraphBuilder()
    graph = builder.build_from_files(file_contents)

    # 3. Obtain Diff Text
    if not diff_text:
        diff_text = loader.get_diff()

    if not diff_text:
        logger.info("No active Git diff detected. Using default sample modification diff...")
        diff_text = DEFAULT_SAMPLE_DIFF

    # 4. Extract Seed Nodes
    seed_nodes = extract_seed_nodes(graph, diff_text)
    if not seed_nodes:
        logger.warning("No seed nodes matched diff lines directly. Fallback: using top definitions.")
        for nid, d in graph.nodes(data=True):
            if d.get("category") in ("function", "method", "class"):
                seed_nodes = [d]
                break

    # 5. Extract k-hop Ego Subgraph
    ego_graph = extract_ego_graph(graph, seed_nodes, k=k)
    impact_summary = analyze_impact_summary(graph, ego_graph, seed_nodes)

    logger.info(f"Impacted files identified: {impact_summary.affected_files}")

    # 6. Synthesize Graph-RAG Context
    graph_context = serialize_ego_graph(ego_graph, seed_nodes, diff_text)

    # 7. Query Gemini API / Mock Recommender
    llm_client = GeminiClient(model_name=model_name)
    report = llm_client.generate_report(graph_context, diff_text, impact_summary)

    if output_file:
        out_path = os.path.abspath(output_file)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"Report saved to {out_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Codelysis: Multi-Language RepoGraph Code Impact Analysis")
    parser.add_argument("--repo", type=str, default=None, help="Path to local repository directory")
    parser.add_argument("--github", type=str, default=None, help="GitHub repository in 'owner/repo' format")
    parser.add_argument("--pr", type=int, default=None, help="Pull request number (when using --github)")
    parser.add_argument("--commit", type=str, default=None, help="Commit SHA (when using --github)")
    parser.add_argument("--k", type=int, default=K_HOPS, help="Number of hops for ego-graph traversal")
    parser.add_argument("--diff", type=str, default=None, help="Unified diff text string or diff file path")
    parser.add_argument("--model", type=str, default=LLM_MODEL, help="Gemini model name")
    parser.add_argument("--output", type=str, default=None, help="Path to save markdown output report")

    args = parser.parse_args()

    # If diff is a file path, read it
    diff_input = args.diff
    if diff_input and os.path.isfile(diff_input):
        with open(diff_input, "r", encoding="utf-8") as f:
            diff_input = f.read()

    report = run_pipeline(
        repo_path=args.repo,
        github_slug=args.github,
        pr_number=args.pr,
        commit_sha=args.commit,
        k=args.k,
        diff_text=diff_input,
        model_name=args.model,
        output_file=args.output
    )

    print("\n" + "=" * 60)
    print("CODELYSIS IMPACT ANALYSIS REPORT:")
    print("=" * 60 + "\n")
    print(report)


if __name__ == "__main__":
    main()
