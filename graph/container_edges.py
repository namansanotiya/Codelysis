"""
Structural Containment Edges (E_contain) Module.
Connects parent containers to enclosed definitions and reference sites.
RepoGraph ICLR 2025: (V1, E_contain, V2).
"""
import networkx as nx
from core.types import EdgeType


def add_containment_edge(graph: nx.DiGraph, parent_id: str, child_id: str) -> None:
    """Add directed containment edge parent -> child."""
    if parent_id and child_id and parent_id != child_id:
        graph.add_edge(parent_id, child_id, edge_type=EdgeType.E_CONTAIN.value)
