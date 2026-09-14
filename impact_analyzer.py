"""
Impact Analyzer module.
Performs k-hop traversal on repository graph G from Seed Nodes S to extract Ego Subgraph G_ego.
Categorizes direct callers, indirect callers, callees, and impacted files.
"""
import logging
from typing import List, Dict, Set, Any, Tuple
import networkx as nx

logger = logging.getLogger("impact_analyzer")


def extract_ego_graph(graph: nx.DiGraph, seed_nodes: List[Dict[str, Any]], k: int = 2) -> nx.DiGraph:
    """
    Extract k-hop Ego Subgraph G_ego = (V_ego, E_ego) from Graph G starting from seed nodes.
    Traverses both forward (calls/containment) and backward (callers/containers) up to k hops.
    """
    if not seed_nodes:
        logger.warning("No seed nodes provided for ego graph extraction.")
        return nx.DiGraph()

    seed_ids: Set[str] = {node["node_id"] for node in seed_nodes if "node_id" in node}
    visited_nodes: Set[str] = set(seed_ids)
    current_frontier: Set[str] = set(seed_ids)

    logger.info(f"Extracting {k}-hop Ego Graph starting from {len(seed_ids)} Seed Nodes...")

    for hop in range(1, k + 1):
        next_frontier: Set[str] = set()

        for node_id in current_frontier:
            if node_id not in graph:
                continue

            # Outgoing neighbors (forward: callees / internal elements)
            for successor in graph.successors(node_id):
                if successor not in visited_nodes:
                    visited_nodes.add(successor)
                    next_frontier.add(successor)

            # Incoming neighbors (backward: callers / parent containers)
            for predecessor in graph.predecessors(node_id):
                if predecessor not in visited_nodes:
                    visited_nodes.add(predecessor)
                    next_frontier.add(predecessor)

        current_frontier = next_frontier
        logger.info(f"Hop {hop}: discovered {len(next_frontier)} new nodes (Total ego nodes: {len(visited_nodes)})")

    # Construct induced subgraph copy
    ego_graph = graph.subgraph(visited_nodes).copy()
    logger.info(f"Extracted Ego Graph with {ego_graph.number_of_nodes()} nodes and {ego_graph.number_of_edges()} edges")
    return ego_graph


def analyze_impact_summary(graph: nx.DiGraph, ego_graph: nx.DiGraph, seed_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze the ego graph to produce a structured summary of impact:
    - seed_nodes
    - direct_callers
    - indirect_callers
    - callees
    - affected_files
    """
    seed_ids = {node["node_id"] for node in seed_nodes if "node_id" in node}
    direct_callers: List[Dict[str, Any]] = []
    indirect_callers: List[Dict[str, Any]] = []
    callees: List[Dict[str, Any]] = []
    affected_files: Set[str] = set()

    for nid, data in ego_graph.nodes(data=True):
        file_path = data.get("file")
        if file_path:
            affected_files.add(file_path)

        if nid in seed_ids:
            continue

        # Check call relationship to seed nodes
        # If node points to a seed node or call site of seed node via E_invoke
        for succ in ego_graph.successors(nid):
            edge_data = ego_graph.get_edge_data(nid, succ, {})
            if edge_data.get("edge_type") == "E_invoke" and succ in seed_ids:
                if data not in direct_callers:
                    direct_callers.append(data)

        # Check if seed node calls this node via E_invoke
        for pred in ego_graph.predecessors(nid):
            edge_data = ego_graph.get_edge_data(pred, nid, {})
            if edge_data.get("edge_type") == "E_invoke" and pred in seed_ids:
                if data not in callees:
                    callees.append(data)

    # Indirect callers: in ego graph, not seed, not direct caller, but has path to direct caller or seed
    for nid, data in ego_graph.nodes(data=True):
        if nid not in seed_ids and data not in direct_callers and data not in callees:
            if data.get("category") in ("function", "method", "class"):
                indirect_callers.append(data)

    return {
        "seed_nodes": seed_nodes,
        "direct_callers": direct_callers,
        "indirect_callers": indirect_callers,
        "callees": callees,
        "affected_files": sorted(list(affected_files)),
        "total_ego_nodes": ego_graph.number_of_nodes(),
        "total_ego_edges": ego_graph.number_of_edges()
    }
