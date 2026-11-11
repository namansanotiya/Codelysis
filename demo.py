"""
Codelysis: Complete End-to-End Local Demonstration.
Demonstrates:
  1. MultiDiGraph Repository Code Graph Construction
  2. Git Diff Parsing & Seed Node Mapping
  3. k-Hop Ego Subgraph Extraction
  4. Weighted Traversal & Personalized PageRank Impact Ranking
  5. Causal Evidence Path Tracing & Error Prediction
  6. Git Historical Co-Change Mining (Jaccard Coupling)
  7. Tri-Part Hybrid Retrieval (Graph + Evolution + Token Lexical)
  8. Test Impact Analysis (TIA: Directly & Indirectly Related Tests)
  9. Structured Graph-RAG Serialization & Markdown Impact Report
Deterministic and runnable locally without requiring paid API access.
"""
import os
import sys
import json
import logging
from typing import Dict, Any

# Ensure Codelysis root is on sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config import K_HOPS, LLM_MODEL, DEFAULT_SAMPLE_DIFF
from sources.local_loader import LocalLoader
from graph.builder import RepoGraphBuilder
from traversal.seed_extractor import extract_seed_nodes
from traversal.ego_graph import extract_ego_graph
from traversal.impact_analyzer import analyze_impact_summary
from traversal.weighted_traversal import calculate_change_conditioned_ranking
from traversal.path_tracer import trace_evidence_paths, predict_potential_errors
from traversal.test_impact_analyzer import identify_relevant_tests
from traversal.hybrid_retriever import retrieve_hybrid_impact
from sources.git_cochange import GitCoChangeMiner
from rag.serializer import serialize_ego_graph
from llm.gemini_client import GeminiClient

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("demo")


def run_demo(repo_path: str = None, diff_text: str = None, k: int = 2) -> Dict[str, Any]:
    """Execute complete Codelysis pipeline demonstration."""
    target_repo = repo_path or os.path.join(root_dir, "sample_repo")
    logger.info("=================================================================")
    logger.info(f"CODELYSIS: REPOSITORY GRAPH-RAG & IMPACT INTELLIGENCE DEMONSTRATION")
    logger.info(f"Target Repository: {target_repo}")
    logger.info("=================================================================")

    # 1. Ingestion
    loader = LocalLoader(target_repo)
    file_contents = loader.load_all_files()
    logger.info(f"[1/8] Ingested {len(file_contents)} repository files.")

    # 2. Graph Construction
    builder = RepoGraphBuilder(multigraph=True)
    graph = builder.build_from_files(file_contents)
    logger.info(
        f"[2/8] Constructed MultiDiGraph: {graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges across {len(file_contents)} files."
    )

    # 3. Diff & Seed Extraction
    active_diff = diff_text or DEFAULT_SAMPLE_DIFF
    seed_nodes = extract_seed_nodes(graph, active_diff)
    if not seed_nodes:
        # Fallback to first function definition
        seed_nodes = [d for n, d in graph.nodes(data=True) if d.get("category") in ("function", "method")][:1]
    logger.info(f"[3/8] Extracted {len(seed_nodes)} Seed Node(s) from Git Diff:")
    for s in seed_nodes:
        logger.info(f"      - [{s.get('category').upper()}] {s.get('name')} ({s.get('file')}:L{s.get('line')})")

    # 4. Ego Subgraph & Impact Summary
    ego_graph = extract_ego_graph(graph, seed_nodes, k=k)
    impact_summary = analyze_impact_summary(graph, ego_graph, seed_nodes)
    logger.info(
        f"[4/8] Extracted {k}-hop Ego Subgraph: {ego_graph.number_of_nodes()} nodes, "
        f"{ego_graph.number_of_edges()} edges. Direct Callers: {len(impact_summary.direct_callers)}, "
        f"Indirect Callers: {len(impact_summary.indirect_callers)}."
    )

    # 5. Weighted Traversal & Causal Path Tracing
    ranked_nodes = calculate_change_conditioned_ranking(graph, seed_nodes, k_hops=k)
    evidence_paths = trace_evidence_paths(ego_graph, seed_nodes)
    predicted_errors = predict_potential_errors(ego_graph, seed_nodes, active_diff)
    logger.info(f"[5/8] Computed Weighted PPR Impact Ranking: {len(ranked_nodes)} ranked nodes.")
    logger.info(f"      Predicted Potential Errors: {len(predicted_errors)} diagnostic warnings.")

    # 6. Git Co-Change Mining & Evolution
    miner = GitCoChangeMiner(target_repo)
    seed_files = list({s.get("file", "") for s in seed_nodes if s.get("file")})
    co_changes = [c.to_dict() for c in miner.get_co_changed_files(seed_files)]
    logger.info(f"[6/8] Mined Git Evolution History: {len(co_changes)} historical co-change relations.")

    # 7. Hybrid Retrieval & Test Impact Analysis
    hybrid_rankings = [
        r.to_dict() for r in retrieve_hybrid_impact(
            graph, seed_nodes, diff_text=active_diff, repo_path=target_repo, git_miner=miner
        )
    ]
    test_recs = identify_relevant_tests(
        graph=graph,
        ego_graph=ego_graph,
        seed_nodes=seed_nodes,
        ranked_nodes=ranked_nodes,
        co_changes=co_changes,
        evidence_paths=evidence_paths
    )
    test_recommendations = [t.to_dict() for t in test_recs]
    impact_summary.test_recommendations = test_recommendations
    logger.info(f"[7/8] Hybrid Retrieval: {len(hybrid_rankings)} fused candidates.")
    logger.info(f"      Test Impact Analysis: {len(test_recommendations)} relevant test suites identified.")

    # 8. Context Serialization & LLM Report
    graph_context = serialize_ego_graph(
        ego_graph,
        seed_nodes,
        active_diff,
        test_recommendations=test_recommendations
    )
    llm_client = GeminiClient(model_name=LLM_MODEL)
    report = llm_client.generate_report(graph_context, active_diff, impact_summary)
    logger.info(f"[8/8] Synthesized Graph-RAG Report ({len(report)} chars).")

    # Console Summary Printout
    print("\n" + "=" * 75)
    print("DEMO SUMMARY: TOP IMPACTED COMPONENTS & SUGGESTED TESTS")
    print("=" * 75)
    print("\n--- TOP RANKED IMPACTED COMPONENTS (WEIGHTED PPR) ---")
    for r in ranked_nodes[:5]:
        print(f"[{r.rank}] [{r.severity}] {r.name} ({r.file}:L{r.line}) - Score: {r.impact_score:.3f} | {r.impact_category}")
        print(f"    Reason: {r.causal_explanation}")

    print("\n--- TEST IMPACT ANALYSIS (SUGGESTED RELEVANT TESTS) ---")
    for tr in test_recommendations:
        print(f"- [{tr['classification'].upper()}] {tr['test_name']} in {tr['test_file']} (Score: {tr['impact_score']:.2f})")
        print(f"  Evidence: {tr['reason']}")

    if predicted_errors:
        print("\n--- PREDICTED POTENTIAL RUNTIME / COMPILE ERRORS ---")
        for err in predicted_errors:
            print(f"- [{err['severity']}] {err['error_type']} at {err['file']}:L{err['line']}")
            print(f"  Cause: {err['cause']}")
            print(f"  Fix:   {err['recommended_fix']}")

    print("\n" + "=" * 75)
    print("DEMONSTRATION COMPLETE - ALL MODULES FUNCTIONAL")
    print("=" * 75 + "\n")

    return {
        "graph_nodes": graph.number_of_nodes(),
        "graph_edges": graph.number_of_edges(),
        "seed_nodes": len(seed_nodes),
        "ego_nodes": ego_graph.number_of_nodes(),
        "ranked_nodes": len(ranked_nodes),
        "predicted_errors": len(predicted_errors),
        "test_recommendations": len(test_recommendations),
        "report_length": len(report)
    }


if __name__ == "__main__":
    run_demo()
