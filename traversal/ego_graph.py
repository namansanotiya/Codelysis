"""
Ego Subgraph Extraction Module (RepoGraph ICLR 2025, Section 3.2).
Retrieves k-hop ego subgraphs centered around seed nodes (or search terms).

Compatible with both nx.DiGraph and nx.MultiDiGraph.
"""
import logging
from typing import List, Dict, Set, Any, Optional, Union
import networkx as nx

logger = logging.getLogger("ego_graph")


def extract_ego_graph(
    graph: Union[nx.DiGraph, nx.MultiDiGraph],
    seed_nodes: List[Dict[str, Any]],
    k: int = 2,
    edge_types: Optional[Set[str]] = None,
    include_candidates: bool = False,
) -> Union[nx.DiGraph, nx.MultiDiGraph]:
    """
    Extract k-hop Ego Subgraph G_ego = (V_ego, E_ego) from Graph G starting from seed nodes.
    Traverses both forward (successors) and backward (predecessors).
    By default, excludes unconfirmed E_invoke_candidate edges to avoid pulling in false dependencies.
    """
    if not seed_nodes:
        logger.warning("No seed nodes provided for ego graph extraction.")
        return graph.__class__()

    seed_ids: Set[str] = {node["node_id"] for node in seed_nodes if "node_id" in node}
    visited_nodes: Set[str] = set(seed_ids)
    current_frontier: Set[str] = set(seed_ids)

    logger.info(f"Extracting {k}-hop Ego Graph starting from {len(seed_ids)} Seed Nodes (candidates={include_candidates})...")

    for hop in range(1, k + 1):
        next_frontier: Set[str] = set()

        for node_id in current_frontier:
            if node_id not in graph:
                continue

            # Outgoing neighbors (forward traversal: callees / contained nodes)
            for succ in graph.successors(node_id):
                if succ not in visited_nodes and _edge_matches(graph, node_id, succ, edge_types, include_candidates):
                    visited_nodes.add(succ)
                    next_frontier.add(succ)

            # Incoming neighbors (backward traversal: callers / container nodes)
            for pred in graph.predecessors(node_id):
                if pred not in visited_nodes and _edge_matches(graph, pred, node_id, edge_types, include_candidates):
                    visited_nodes.add(pred)
                    next_frontier.add(pred)

        current_frontier = next_frontier
        logger.info(f"Hop {hop}: discovered {len(next_frontier)} new nodes (Total ego nodes: {len(visited_nodes)})")

    ego_graph = graph.subgraph(visited_nodes).copy()
    logger.info(f"Extracted Ego Graph with {ego_graph.number_of_nodes()} nodes and {ego_graph.number_of_edges()} edges")
    return ego_graph


def _edge_matches(
    graph: Union[nx.DiGraph, nx.MultiDiGraph],
    u: str,
    v: str,
    edge_types: Optional[Set[str]],
    include_candidates: bool = False,
) -> bool:
    """Return True if the edge (u, v) matches requested types and confirmed status."""
    if not graph.has_edge(u, v):
        return False
        
    from core.types import EdgeType
    cand_type = EdgeType.E_INVOKE_CANDIDATE.value

    if edge_types is not None:
        if graph.is_multigraph():
            edge_data = graph.get_edge_data(u, v)
            return any(attrs.get("edge_type") in edge_types for attrs in edge_data.values())
        else:
            return graph.get_edge_data(u, v, {}).get("edge_type") in edge_types

    # Default: Do not follow ambiguous E_invoke_candidate edges unless explicitly requested
    if not include_candidates:
        if graph.is_multigraph():
            edge_data = graph.get_edge_data(u, v)
            return any(attrs.get("edge_type") != cand_type for attrs in edge_data.values())
        else:
            return graph.get_edge_data(u, v, {}).get("edge_type") != cand_type

    return True
