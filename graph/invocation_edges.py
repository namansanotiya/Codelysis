"""
Invocation Dependency Edges (E_invoke) Module.
Connects reference/call sites (ref) to target definition sites (def).
RepoGraph ICLR 2025: (V1_ref, E_invoke, V2_def).
"""
import logging
from typing import Dict, List, Tuple, Optional, Set
import networkx as nx
from core.types import CodeNode, EdgeType

logger = logging.getLogger("invocation_edges")


def resolve_invocation_edges(
    graph: nx.DiGraph,
    references: List[Tuple[str, CodeNode, Optional[str]]],
    symbol_defs: Dict[str, List[CodeNode]],
    ignored_symbols: Set[str] = None
) -> int:
    """
    Resolve and wire E_invoke edges from call references to matching definitions.
    Returns the count of successfully resolved invocations.
    """
    resolved_count = 0
    ignored = ignored_symbols or set()

    for rel_path, ref_node, enclosing_def_id in references:
        called_symbol = ref_node.name
        if called_symbol in ignored and called_symbol not in symbol_defs:
            continue

        matching_defs = symbol_defs.get(called_symbol, [])
        if matching_defs:
            for target_def in matching_defs:
                # Avoid self-referencing containment loop
                if target_def.node_id != enclosing_def_id:
                    graph.add_edge(
                        ref_node.node_id,
                        target_def.node_id,
                        edge_type=EdgeType.E_INVOKE.value
                    )
                    resolved_count += 1

    return resolved_count
