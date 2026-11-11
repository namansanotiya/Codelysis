"""
Impact Analyzer Module.
Categorizes callers (1-hop direct, 2-hop indirect), callees, inheritance overrides, and impacted files within G_ego.
Supports both nx.DiGraph and nx.MultiDiGraph transparently.
"""
from typing import List, Dict, Set, Any, Union
import networkx as nx
from core.models import ImpactSummary
from core.types import EdgeType, has_edge_type, get_edges_between


def analyze_impact_summary(
    graph: Union[nx.DiGraph, nx.MultiDiGraph],
    ego_graph: Union[nx.DiGraph, nx.MultiDiGraph],
    seed_nodes: List[Dict[str, Any]]
) -> ImpactSummary:
    """
    Analyzes ego subgraph topology to categorize direct callers, indirect callers, callees,
    inherited overrides, and affected files.
    """
    seed_ids = {node["node_id"] for node in seed_nodes if "node_id" in node}
    direct_callers: List[Dict[str, Any]] = []
    indirect_callers: List[Dict[str, Any]] = []
    callees: List[Dict[str, Any]] = []
    candidate_callers: List[Dict[str, Any]] = []
    affected_files: Set[str] = set()

    for nid, data in ego_graph.nodes(data=True):
        file_path = data.get("file")
        if file_path:
            affected_files.add(file_path)

        if nid in seed_ids:
            continue

        # 1. Direct Caller: confirmed invocation or inheritance/override edge pointing from nid to a seed node
        for succ in ego_graph.successors(nid):
            if succ in seed_ids:
                if has_edge_type(ego_graph, nid, succ, EdgeType.E_INVOKE.value):
                    if data not in direct_callers:
                        direct_callers.append(data)
                elif has_edge_type(ego_graph, nid, succ, EdgeType.E_OVERRIDE.value):
                    if data not in direct_callers:
                        direct_callers.append(data)
                elif has_edge_type(ego_graph, nid, succ, EdgeType.E_INHERIT.value):
                    if data not in direct_callers:
                        direct_callers.append(data)
                elif has_edge_type(ego_graph, nid, succ, EdgeType.E_INVOKE_CANDIDATE.value):
                    if data not in candidate_callers and data not in direct_callers:
                        candidate_callers.append(data)

        # 2. Callee: seed node calls nid
        for pred in ego_graph.predecessors(nid):
            if pred in seed_ids:
                if has_edge_type(ego_graph, pred, nid, EdgeType.E_INVOKE.value):
                    if data not in callees:
                        callees.append(data)

    # 3. Indirect Callers: functional entities in ego graph not yet classified as direct caller/callee/candidate
    for nid, data in ego_graph.nodes(data=True):
        if (
            nid not in seed_ids
            and data not in direct_callers
            and data not in callees
            and data not in candidate_callers
        ):
            if data.get("category") in ("function", "method", "class", "struct"):
                indirect_callers.append(data)

    return ImpactSummary(
        seed_nodes=seed_nodes,
        direct_callers=direct_callers,
        indirect_callers=indirect_callers,
        callees=callees,
        candidate_callers=candidate_callers,
        affected_files=sorted(list(affected_files)),
        total_ego_nodes=ego_graph.number_of_nodes(),
        total_ego_edges=ego_graph.number_of_edges()
    )
