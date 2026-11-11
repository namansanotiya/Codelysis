"""
Main CLI entry point for Codelysis (RepoGraph ICLR 2025 & Codelysis Extension).
Supports both direct GitHub API analysis (zero clone) and local repositories,
and produces full structured JSON or Markdown reports.
"""
import argparse
import json
import os
import sys
import logging
from typing import Dict, Any, Optional

# Ensure Codelysis root is on sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config import K_HOPS, LLM_MODEL, DEFAULT_SAMPLE_DIFF
from graph.builder import RepoGraphBuilder
from traversal.seed_extractor import extract_seed_nodes
from traversal.ego_graph import extract_ego_graph
from traversal.impact_analyzer import analyze_impact_summary
from traversal.path_tracer import trace_evidence_paths, predict_potential_errors
from traversal.weighted_traversal import calculate_change_conditioned_ranking
from traversal.hybrid_retriever import retrieve_hybrid_impact
from traversal.test_impact_analyzer import identify_relevant_tests
from sources.git_cochange import GitCoChangeMiner
from rag.serializer import serialize_ego_graph
from sources.local_loader import LocalLoader
from sources.github_client import GitHubClient
from llm.gemini_client import GeminiClient

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("main")


def run_pipeline_data(
    repo_path: str = None,
    github_slug: str = None,
    pr_number: int = None,
    commit_sha: str = None,
    k: int = K_HOPS,
    diff_text: str = None,
    model_name: str = LLM_MODEL
) -> Dict[str, Any]:
    """
    Execute end-to-end Codelysis pipeline and return rich structured dictionary
    containing graph elements, evidence paths, predicted errors, and recommendations.
    """
    # 1. Ingestion source
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
        return {"error": "No source files loaded. Please check repository path or GitHub slug."}

    builder = RepoGraphBuilder()
    graph = builder.build_from_files(file_contents)

    # 3. Diff Text
    if not diff_text:
        diff_text = loader.get_diff()

    if not diff_text:
        diff_text = DEFAULT_SAMPLE_DIFF

    # 4. Extract Seed Nodes
    seed_nodes = extract_seed_nodes(graph, diff_text)
    if not seed_nodes:
        for nid, d in graph.nodes(data=True):
            if d.get("category") in ("function", "method", "class"):
                seed_nodes = [d]
                break

    # 5. Extract k-hop Ego Subgraph
    ego_graph = extract_ego_graph(graph, seed_nodes, k=k)
    impact_summary = analyze_impact_summary(graph, ego_graph, seed_nodes)

    # 6. Causal Evidence Paths & Error Prediction
    evidence_paths = trace_evidence_paths(ego_graph, seed_nodes)
    predicted_errors = predict_potential_errors(ego_graph, seed_nodes, diff_text)

    # 6b. Weighted Relationship Traversal & Change-Conditioned Impact Ranking
    ranked_impact_nodes = calculate_change_conditioned_ranking(graph, seed_nodes, k_hops=k)

    # 6c. Software Evolution Intelligence (Git Historical Co-Changes)
    git_repo_path = repo_path or (target_repo if 'target_repo' in locals() else None)
    miner = None
    co_changes = []
    if git_repo_path and os.path.isdir(git_repo_path):
        miner = GitCoChangeMiner(git_repo_path)
        seed_files = list({s.get("file", "") for s in seed_nodes if s.get("file")})
        co_changes = [c.to_dict() for c in miner.get_co_changed_files(seed_files)]

    # 6d. Hybrid Structural + Semantic Retrieval
    hybrid_rankings = [
        r.to_dict() for r in retrieve_hybrid_impact(
            graph, seed_nodes, diff_text=diff_text, repo_path=git_repo_path, git_miner=miner
        )
    ]

    # 6e. Test Impact Analysis (TIA)
    test_recs = identify_relevant_tests(
        graph=graph,
        ego_graph=ego_graph,
        seed_nodes=seed_nodes,
        ranked_nodes=ranked_impact_nodes,
        co_changes=co_changes,
        evidence_paths=evidence_paths
    )
    test_recommendations = [t.to_dict() for t in test_recs]
    impact_summary.test_recommendations = test_recommendations

    # 7. Synthesize Graph-RAG Context & Query LLM
    graph_context = serialize_ego_graph(
        ego_graph,
        seed_nodes,
        diff_text,
        test_recommendations=test_recommendations
    )
    llm_client = GeminiClient(model_name=model_name)
    report = llm_client.generate_report(graph_context, diff_text, impact_summary)

    # 8. Format Nodes and Edges for UI Visualization
    seed_ids = {s.get("node_id") for s in seed_nodes}
    direct_caller_ids = {c.get("node_id") for c in impact_summary.direct_callers}
    indirect_caller_ids = {c.get("node_id") for c in impact_summary.indirect_callers}
    callee_ids = {c.get("node_id") for c in impact_summary.callees}

    formatted_nodes = []
    for nid, data in ego_graph.nodes(data=True):
        status = "normal"
        file_path = data.get("file", "")
        is_test = "test" in file_path.lower()

        if nid in seed_ids:
            status = "seed"
        elif nid in direct_caller_ids:
            status = "test" if is_test else "direct_caller"
        elif nid in indirect_caller_ids:
            status = "test" if is_test else "indirect_caller"
        elif nid in callee_ids:
            status = "callee"
        elif is_test:
            status = "test"

        formatted_nodes.append({
            "id": nid,
            "name": data.get("name", ""),
            "file": file_path,
            "line": data.get("line", 0),
            "end_line": data.get("end_line", 0),
            "category": data.get("category", "symbol"),
            "type": data.get("type", "def"),
            "status": status,
            "signature": data.get("signature", ""),
            "snippet": data.get("snippet", ""),
            "docstring": data.get("docstring", ""),
            "parent_scope": data.get("parent_scope", "")
        })

    formatted_edges = []
    for u, v, data in ego_graph.edges(data=True):
        formatted_edges.append({
            "source": u,
            "target": v,
            "edge_type": data.get("edge_type", "E_invoke"),
            "confidence": data.get("confidence", 1.0),
            "symbol": data.get("symbol", "")
        })

    return {
        "success": True,
        "repo": github_slug or (repo_path or "sample_repo"),
        "diff_text": diff_text,
        "k_hops": k,
        "nodes": formatted_nodes,
        "edges": formatted_edges,
        "seed_nodes": seed_nodes,
        "affected_files": impact_summary.affected_files,
        "direct_callers_count": len(impact_summary.direct_callers),
        "indirect_callers_count": len(impact_summary.indirect_callers),
        "total_nodes_in_repo": graph.number_of_nodes(),
        "total_edges_in_repo": graph.number_of_edges(),
        "ego_nodes_count": ego_graph.number_of_nodes(),
        "ego_edges_count": ego_graph.number_of_edges(),
        "evidence_paths": evidence_paths,
        "predicted_errors": predicted_errors,
        "ranked_impact_nodes": [n.to_dict() for n in ranked_impact_nodes],
        "git_co_changes": co_changes,
        "hybrid_rankings": hybrid_rankings,
        "test_recommendations": test_recommendations,
        "markdown_report": report
    }


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
    """Execute end-to-end pipeline returning markdown string."""
    data = run_pipeline_data(
        repo_path=repo_path,
        github_slug=github_slug,
        pr_number=pr_number,
        commit_sha=commit_sha,
        k=k,
        diff_text=diff_text,
        model_name=model_name
    )
    if "error" in data:
        return data["error"]

    report = data["markdown_report"]
    if output_file:
        out_path = os.path.abspath(output_file)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"Report saved to {out_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Codelysis: Multi-Language RepoGraph Code Impact Analysis")
    parser.add_argument("--repo", type=str, default=None, help="Path to local repository directory")
    parser.add_argument("--github", type=str, default=None, help="GitHub repository slug (e.g. 'owner/repo')")
    parser.add_argument("--pr", type=int, default=None, help="GitHub Pull Request number")
    parser.add_argument("--commit", type=str, default=None, help="GitHub Commit SHA")
    parser.add_argument("--hops", type=int, default=K_HOPS, help=f"Ego-subgraph traversal depth (default: {K_HOPS})")
    parser.add_argument("--diff", type=str, default=None, help="Custom unified git diff string or path to .diff file")
    parser.add_argument("--model", type=str, default=LLM_MODEL, help="LLM model name")
    parser.add_argument("--output", type=str, default=None, help="Output markdown report file path")
    parser.add_argument("--json", action="store_true", help="Output full structured JSON payload")

    args = parser.parse_args()

    diff_content = None
    if args.diff:
        if os.path.isfile(args.diff):
            with open(args.diff, "r", encoding="utf-8") as f:
                diff_content = f.read()
        else:
            diff_content = args.diff

    if args.json:
        data = run_pipeline_data(
            repo_path=args.repo,
            github_slug=args.github,
            pr_number=args.pr,
            commit_sha=args.commit,
            k=args.hops,
            diff_text=diff_content,
            model_name=args.model
        )
        print(json.dumps(data, indent=2))
    else:
        report = run_pipeline(
            repo_path=args.repo,
            github_slug=args.github,
            pr_number=args.pr,
            commit_sha=args.commit,
            k=args.hops,
            diff_text=diff_content,
            model_name=args.model,
            output_file=args.output
        )
        print("\n" + "=" * 60)
        print("CODELYSIS IMPACT ANALYSIS REPORT:")
        print("=" * 60 + "\n")
        print(report)


if __name__ == "__main__":
    main()
