"""
Ego Subgraph Extraction Module (RepoGraph ICLR 2025, Section 3.2).
Retrieves k-hop ego subgraphs centered around seed nodes (or search terms).
"""
import logging
from typing import List, Dict, Set, Any
import networkx as nx

logger = logging.getLogger("ego_graph")


def extract_ego_graph(graph: nx.DiGraph, seed_nodes: List[Dict[str, Any]], k: int = 2) -> nx.DiGraph:
    """
    Extract k-hop Ego Subgraph G_ego = (V_ego, E_ego) from Graph G starting from seed nodes.
    Traverses both forward (successors: callees / internal elements) and backward (predecessors: callers / containers).
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

            # Outgoing neighbors (forward traversal: callees / contained nodes)
            for succ in graph.successors(node_id):
                if succ not in visited_nodes:
                    visited_nodes.add(succ)
                    next_frontier.add(succ)

            # Incoming neighbors (backward traversal: callers / container nodes)
            for pred in graph.predecessors(node_id):
                if pred not in visited_nodes:
                    visited_nodes.add(pred)
                    next_frontier.add(pred)

        current_frontier = next_frontier
        logger.info(f"Hop {hop}: discovered {len(next_frontier)} new nodes (Total ego nodes: {len(visited_nodes)})")

    ego_graph = graph.subgraph(visited_nodes).copy()
    logger.info(f"Extracted Ego Graph with {ego_graph.number_of_nodes()} nodes and {ego_graph.number_of_edges()} edges")
    return ego_graph
