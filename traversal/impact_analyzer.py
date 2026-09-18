"""
Impact Analyzer Module.
Categorizes callers (1-hop direct, 2-hop indirect), callees, and impacted files within G_ego.
"""
from typing import List, Dict, Set, Any
import networkx as nx
from core.models import ImpactSummary


def analyze_impact_summary(graph: nx.DiGraph, ego_graph: nx.DiGraph, seed_nodes: List[Dict[str, Any]]) -> ImpactSummary:
    """
    Analyzes ego subgraph topology to categorize direct callers, indirect callers, callees, and affected files.
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

        # Check direct caller relationship via E_invoke pointing to seed
        for succ in ego_graph.successors(nid):
            edge_data = ego_graph.get_edge_data(nid, succ, {})
            if edge_data.get("edge_type") == "E_invoke" and succ in seed_ids:
                if data not in direct_callers:
                    direct_callers.append(data)

        # Check callee relationship (seed calls this node via E_invoke)
        for pred in ego_graph.predecessors(nid):
            edge_data = ego_graph.get_edge_data(pred, nid, {})
            if edge_data.get("edge_type") == "E_invoke" and pred in seed_ids:
                if data not in callees:
                    callees.append(data)

    # Indirect callers: in ego graph, not seed, not direct caller or callee, but functional entity
    for nid, data in ego_graph.nodes(data=True):
        if nid not in seed_ids and data not in direct_callers and data not in callees:
            if data.get("category") in ("function", "method", "class", "struct"):
                indirect_callers.append(data)

    return ImpactSummary(
        seed_nodes=seed_nodes,
        direct_callers=direct_callers,
        indirect_callers=indirect_callers,
        callees=callees,
        affected_files=sorted(list(affected_files)),
        total_ego_nodes=ego_graph.number_of_nodes(),
        total_ego_edges=ego_graph.number_of_edges()
    )
