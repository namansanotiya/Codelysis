"""
Structural Containment Edges (E_contain) Module.
Connects parent containers to enclosed definitions and reference sites.
RepoGraph ICLR 2025: (V1, E_contain, V2).
"""
from typing import Union
import networkx as nx
from core.types import EdgeType


def add_containment_edge(graph: Union[nx.DiGraph, nx.MultiDiGraph], parent_id: str, child_id: str) -> None:
    """Add directed containment edge parent -> child."""
    if parent_id and child_id and parent_id != child_id:
        if graph.is_multigraph():
            graph.add_edge(parent_id, child_id, key=EdgeType.E_CONTAIN.value, edge_type=EdgeType.E_CONTAIN.value)
        else:
            graph.add_edge(parent_id, child_id, edge_type=EdgeType.E_CONTAIN.value)
